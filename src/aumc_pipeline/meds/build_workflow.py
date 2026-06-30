"""MEDS build workflow: pre-MEDS parquet → MEDS event parquet.

Consumes:
  <pre_meds_dir>/admissions.parquet
  <pre_meds_dir>/numericitems_binned/ (preferred when present)
  <pre_meds_dir>/numericitems/        (fallback, partitioned)
  <pre_meds_dir>/listitems/          (partitioned)
  <pre_meds_dir>/drugitems/          (partitioned)
  <pre_meds_dir>/processitems.parquet
  outputs/aumc_supplied_vocab.csv

Writes:
  <output_dir>/data/0.parquet        (CORE_COLUMNS predictor table)
  <output_dir>/debug/0.parquet       (DEBUG_COLUMNS with full provenance)
  <audit_dir>/meds_summary.json
  <audit_dir>/meds_exclusion_counts.csv
  <audit_dir>/meds_interval_audit.csv
  <audit_dir>/meds_static_context_dedup_audit.csv
  <audit_dir>/meds_top_token_counts.csv
  <audit_dir>/meds_sequence_length_summary.csv
  <audit_dir>/meds_timeline_sample.csv
  <audit_dir>/meds_numeric_quantile_boundaries.csv
  <audit_dir>/meds_numeric_quantile_assignments.csv
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import polars as pl

from aumc_pipeline.meds.anchors import anchor_and_context_events, sample_admissions
from aumc_pipeline.meds.categorical import list_events
from aumc_pipeline.meds.common import (
    CORE_COLUMNS,
    counts_dict,
    empty_debug_frame,
    sort_meds_events,
    validate_meds_event_invariants,
)
from aumc_pipeline.meds.intervals import interval_events
from aumc_pipeline.meds.numeric import numeric_events
from aumc_pipeline.meds.vocab import load_vocab
from aumc_pipeline.utils.parquet_datasets import parquet_exists, resolve_table_parquet, scan_parquet


@dataclass(frozen=True)
class MEDSConfig:
    """Inputs, outputs, and policy settings for one MEDS conversion run."""

    pre_meds_dir: Path
    vocab_path: Path
    output_dir: Path
    audit_dir: Path
    mode: str = "full"
    # Secondary subject sample drawn within the pre-MEDS cohort; None = use all.
    # Only active when mode="bounded".
    num_patients: int | None = None
    seed: int = 20260618
    # Temporal phases included in predictor output. 'postadmission' excluded
    # by default to prevent leakage. Outcome tokens (ICU_DISCHARGE, MEDS_DEATH)
    # are written to debug but must be excluded by training code when used as labels.
    include_temporal_phases: Sequence[str] = field(
        default_factory=lambda: ("preadmission", "admission")
    )
    quantile_bins: int = 10
    # Per-table raw-row cap for smoke tests; None = full table. When set, the
    # first max_rows rows of numericitems/listitems are scanned before join.
    max_rows: int | None = None
    write_debug: bool = True
    overwrite: bool = False


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def _log(msg: str) -> None:
    print(f"[build_meds] {msg}", flush=True)


def _elapsed(start: float) -> str:
    return f"{time.perf_counter() - start:.1f}s"


def _preflight(config: MEDSConfig) -> None:
    if not config.pre_meds_dir.is_dir():
        raise FileNotFoundError(f"pre_meds_dir not found: {config.pre_meds_dir}")
    if not config.vocab_path.is_file():
        raise FileNotFoundError(f"vocab not found: {config.vocab_path}")
    if config.mode not in ("bounded", "full"):
        raise ValueError(f"mode must be 'bounded' or 'full', got: {config.mode!r}")
    if config.quantile_bins != 10:
        raise ValueError("Only quantile_bins=10 is supported in this port.")


def _prepare_output_dir(config: MEDSConfig) -> None:
    if config.output_dir.exists():
        if not config.overwrite:
            raise FileExistsError(
                f"MEDS output already exists: {config.output_dir}. "
                "Set run.overwrite=true to replace."
            )
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.audit_dir.mkdir(parents=True, exist_ok=True)


def _count_skipped_table(pre_meds_dir: Path, table: str, admission_ids: list[int]) -> int:
    path = resolve_table_parquet(pre_meds_dir, table)
    if not parquet_exists(path):
        return 0
    return int(
        scan_parquet(path)
        .filter(pl.col("admissionid").is_in(admission_ids))
        .select(pl.len().alias("n"))
        .collect(engine="streaming")["n"][0]
    )


def _write_audit_files(
    debug: pl.DataFrame,
    exclusions: list[dict],
    interval_audit: list[dict],
    static_context_audit: dict,
    config: MEDSConfig,
) -> None:
    adir = config.audit_dir

    excl_df = (
        pl.DataFrame(exclusions)
        if exclusions
        else pl.DataFrame(schema={"source_table": pl.String, "exclusion_reason": pl.String, "row_count": pl.Int64})
    )
    excl_df.write_csv(adir / "meds_exclusion_counts.csv")

    intv_df = pl.DataFrame(interval_audit) if interval_audit else pl.DataFrame()
    intv_df.write_csv(adir / "meds_interval_audit.csv")

    sc_df = (
        pl.DataFrame([static_context_audit])
        if static_context_audit
        else pl.DataFrame()
    )
    sc_df.write_csv(adir / "meds_static_context_dedup_audit.csv")

    if debug.height:
        debug.group_by("code").len(name="event_count").sort("event_count", descending=True).head(100).write_csv(
            adir / "meds_top_token_counts.csv"
        )
        debug.group_by(["subject_id", "hadm_id"]).len(name="event_count").sort(
            "event_count", descending=True
        ).write_csv(adir / "meds_sequence_length_summary.csv")
        sort_meds_events(debug).head(250).write_csv(adir / "meds_timeline_sample.csv")
    else:
        pl.DataFrame(schema={"code": pl.String, "event_count": pl.Int64}).write_csv(
            adir / "meds_top_token_counts.csv"
        )
        pl.DataFrame(schema={"subject_id": pl.Int64, "hadm_id": pl.Int64, "event_count": pl.Int64}).write_csv(
            adir / "meds_sequence_length_summary.csv"
        )
        empty_debug_frame().write_csv(adir / "meds_timeline_sample.csv")


def write_meds_outputs(config: MEDSConfig) -> dict[str, Path]:
    """Run the full MEDS conversion and return a dict of output paths."""
    total_start = time.perf_counter()
    _preflight(config)
    _prepare_output_dir(config)

    _log(f"loading vocab from {config.vocab_path.name}")
    vocab = load_vocab(config.vocab_path)

    _log(
        f"sampling admissions (mode={config.mode}"
        + (f", num_patients={config.num_patients}" if config.num_patients else "")
        + ")"
    )
    admissions = sample_admissions(
        config.pre_meds_dir, config.mode, config.num_patients, config.seed
    )
    admission_ids = admissions["admissionid"].to_list()
    _log(
        f"  {admissions['subject_id'].n_unique()} subjects, "
        f"{len(admission_ids)} admissions"
    )

    frames: list[pl.DataFrame] = []
    all_exclusions: list[dict] = []
    all_interval_audit: list[dict] = []
    static_context_audit: dict = {}

    # -- anchor and context events (from admissions table)
    step = time.perf_counter()
    _log("1/5 anchor and context events")
    anchor_df = anchor_and_context_events(admissions)
    frames.append(anchor_df)
    _log(f"  {anchor_df.height:,} rows [{_elapsed(step)}]")

    # -- numericitems
    step = time.perf_counter()
    _log("2/5 numericitems → quantile-coded events")
    num_df, num_excl = numeric_events(
        admission_ids,
        config.pre_meds_dir,
        vocab,
        config.include_temporal_phases,
        config.quantile_bins,
        config.audit_dir,
        max_rows=config.max_rows,
    )
    frames.append(num_df)
    all_exclusions.extend(num_excl)
    _log(f"  {num_df.height:,} events [{_elapsed(step)}]")

    # -- listitems
    step = time.perf_counter()
    _log("3/5 listitems → static context + dynamic events")
    list_df, list_excl, sc_audit = list_events(
        admission_ids,
        config.pre_meds_dir,
        vocab,
        config.include_temporal_phases,
        max_rows=config.max_rows,
    )
    frames.append(list_df)
    all_exclusions.extend(list_excl)
    static_context_audit = sc_audit
    _log(f"  {list_df.height:,} events [{_elapsed(step)}]")

    # -- drugitems and processitems
    step = time.perf_counter()
    _log("4/5 interval events (drugitems, processitems)")
    for table in ["drugitems", "processitems"]:
        intv_df, intv_excl, intv_audit = interval_events(
            admission_ids, config.pre_meds_dir, vocab, table, config.include_temporal_phases
        )
        frames.append(intv_df)
        all_exclusions.extend(intv_excl)
        if intv_audit:
            all_interval_audit.append(intv_audit)
        _log(f"  {table}: {intv_df.height:,} events")
    _log(f"  interval tables done [{_elapsed(step)}]")

    # -- skipped tables (policy: not emitted in first-pass model)
    step = time.perf_counter()
    _log("5/5 recording skipped tables (freetextitems, procedureorderitems)")
    for table in ["freetextitems", "procedureorderitems"]:
        count = _count_skipped_table(config.pre_meds_dir, table, admission_ids)
        if count:
            all_exclusions.append({
                "source_table": table,
                "exclusion_reason": "excluded_table_policy",
                "row_count": count,
            })
        _log(f"  {table}: {count:,} rows skipped")

    # -- concat, sort, validate
    non_empty = [f for f in frames if f is not None and not f.is_empty()]
    debug = pl.concat(non_empty, how="vertical_relaxed") if non_empty else empty_debug_frame()
    if not debug.is_empty():
        debug = sort_meds_events(debug)
    validate_meds_event_invariants(debug)

    # -- write outputs
    events_path = config.output_dir / "data" / "0.parquet"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    debug.select(CORE_COLUMNS).write_parquet(events_path)

    debug_path: Path | None = None
    if config.write_debug:
        debug_path = config.output_dir / "debug" / "0.parquet"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug.write_parquet(debug_path)

    _write_audit_files(debug, all_exclusions, all_interval_audit, static_context_audit, config)

    summary = {
        "mode": config.mode,
        "pre_meds_dir": str(config.pre_meds_dir),
        "vocab_path": str(config.vocab_path),
        "output_dir": str(config.output_dir),
        "subjects": int(admissions["subject_id"].n_unique()),
        "admissions": int(len(admission_ids)),
        "events": int(debug.height),
        "unique_codes": int(debug["code"].n_unique()) if debug.height else 0,
        "include_temporal_phases": list(config.include_temporal_phases),
        "quantile_bins": config.quantile_bins,
        "by_source_table": counts_dict(debug, "source_table"),
        "by_token_role": counts_dict(debug, "token_role"),
        "by_temporal_phase": counts_dict(debug, "temporal_phase"),
        "exclusion_counts": all_exclusions,
        "interval_audit": all_interval_audit,
        "static_context_dedup_audit": static_context_audit,
        "elapsed_seconds": round(time.perf_counter() - total_start, 1),
    }
    summary_path = config.audit_dir / "meds_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, cls=_JsonEncoder) + "\n")
    _log(f"done in {_elapsed(total_start)} -> {summary_path}")

    outputs: dict[str, Path] = {
        "events": events_path,
        "summary": summary_path,
    }
    if debug_path:
        outputs["debug"] = debug_path
    return outputs
