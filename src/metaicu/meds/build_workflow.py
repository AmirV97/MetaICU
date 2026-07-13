"""MEDS build workflow: pre-MEDS parquet -> MEDS event parquet.

Single-cohort mode converts one pre-MEDS directory. Split-aware mode fits
numeric quantile boundaries on ``pre_meds/train`` and reuses them for train,
val, and test.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import polars as pl

from metaicu.meds.anchors import anchor_and_context_events, sample_admissions
from metaicu.meds.categorical import list_events
from metaicu.meds.common import (
    CORE_COLUMNS,
    counts_dict,
    empty_debug_frame,
    sort_meds_events,
    validate_meds_event_invariants,
)
from metaicu.meds.intervals import interval_events
from metaicu.meds.numeric import (
    fit_numeric_quantile_boundaries,
    numeric_events,
    numeric_input_table_name,
)
from metaicu.meds.vocab import load_vocab
from metaicu.utils.parquet_datasets import parquet_exists, resolve_table_parquet, scan_parquet


@dataclass(frozen=True)
class MEDSConfig:
    """Inputs, outputs, and policy settings for one MEDS conversion run."""

    pre_meds_dir: Path
    vocab_path: Path
    output_dir: Path
    audit_dir: Path
    mode: str = "full"
    num_patients: int | None = None
    seed: int = 20260618
    include_temporal_phases: Sequence[str] = field(default_factory=lambda: ("preadmission", "admission"))
    quantile_bins: int = 10
    max_rows: int | None = None
    write_debug: bool = True
    overwrite: bool = False
    quantile_boundaries: pl.DataFrame | None = None


@dataclass(frozen=True)
class SplitMEDSConfig:
    """Inputs and policy settings for train/val/test MEDS conversion."""

    pre_meds_dir: Path
    vocab_path: Path
    output_dir: Path
    audit_dir: Path
    metadata_dir: Path
    splits: Sequence[str] = field(default_factory=lambda: ("train", "val", "test"))
    mode: str = "full"
    num_patients: int | None = None
    seed: int = 20260618
    include_temporal_phases: Sequence[str] = field(default_factory=lambda: ("preadmission", "admission"))
    quantile_bins: int = 10
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


def _preflight_split(config: SplitMEDSConfig) -> None:
    if not config.pre_meds_dir.is_dir():
        raise FileNotFoundError(f"pre_meds_dir not found: {config.pre_meds_dir}")
    if not config.vocab_path.is_file():
        raise FileNotFoundError(f"vocab not found: {config.vocab_path}")
    if "train" not in set(config.splits):
        raise ValueError("split-aware MEDS requires a train split for quantile fitting")
    for split in config.splits:
        split_dir = config.pre_meds_dir / split
        if not split_dir.is_dir():
            raise FileNotFoundError(f"pre-MEDS split directory not found: {split_dir}")
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

    sc_df = pl.DataFrame([static_context_audit]) if static_context_audit else pl.DataFrame()
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
        pl.DataFrame(schema={"code": pl.String, "event_count": pl.Int64}).write_csv(adir / "meds_top_token_counts.csv")
        pl.DataFrame(schema={"subject_id": pl.Int64, "hadm_id": pl.Int64, "event_count": pl.Int64}).write_csv(
            adir / "meds_sequence_length_summary.csv"
        )
        empty_debug_frame().write_csv(adir / "meds_timeline_sample.csv")


def write_meds_outputs(config: MEDSConfig) -> dict[str, Path]:
    """Run one MEDS conversion and return a dict of output paths."""
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
    admissions = sample_admissions(config.pre_meds_dir, config.mode, config.num_patients, config.seed)
    admission_ids = admissions["admissionid"].to_list()
    _log(f"  {admissions['subject_id'].n_unique()} subjects, {len(admission_ids)} admissions")

    frames: list[pl.DataFrame] = []
    all_exclusions: list[dict] = []
    all_interval_audit: list[dict] = []
    static_context_audit: dict = {}
    numeric_input_table = numeric_input_table_name(config.pre_meds_dir)

    step = time.perf_counter()
    _log("1/5 anchor and context events")
    anchor_df = anchor_and_context_events(admissions)
    frames.append(anchor_df)
    _log(f"  {anchor_df.height:,} rows [{_elapsed(step)}]")

    step = time.perf_counter()
    _log("2/5 numericitems -> quantile-coded events")
    num_df, num_excl = numeric_events(
        admission_ids,
        config.pre_meds_dir,
        vocab,
        config.include_temporal_phases,
        config.quantile_bins,
        config.audit_dir,
        max_rows=config.max_rows,
        quantile_boundaries=config.quantile_boundaries,
    )
    frames.append(num_df)
    all_exclusions.extend(num_excl)
    _log(f"  {num_df.height:,} events from {numeric_input_table} [{_elapsed(step)}]")

    step = time.perf_counter()
    _log("3/5 listitems -> static context + dynamic events")
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

    non_empty = [f for f in frames if f is not None and not f.is_empty()]
    debug = pl.concat(non_empty, how="vertical_relaxed") if non_empty else empty_debug_frame()
    if not debug.is_empty():
        debug = sort_meds_events(debug)
    validate_meds_event_invariants(debug)

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
        "numeric_input_table": numeric_input_table,
        "quantile_boundaries_source": "provided" if config.quantile_boundaries is not None else "cohort_fit",
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

    outputs: dict[str, Path] = {"events": events_path, "summary": summary_path}
    if debug_path:
        outputs["debug"] = debug_path
    return outputs


def _add_split_column(df: pl.DataFrame, split: str) -> pl.DataFrame:
    if df.is_empty():
        return df.with_columns(pl.lit(split).alias("split")) if "split" not in df.columns else df
    return df.with_columns(pl.lit(split).alias("split")).select(["split"] + df.columns)


def _read_csv_with_split(path: Path, split: str) -> pl.DataFrame:
    if not path.is_file() or path.stat().st_size == 0:
        return pl.DataFrame()
    df = pl.read_csv(path)
    return _add_split_column(df, split)


def _write_split_global_audits(
    config: SplitMEDSConfig,
    split_outputs: dict[str, dict[str, Path]],
    boundaries_path: Path,
    fit_exclusions: list[dict],
) -> Path:
    audit_root = config.audit_dir / "meds"
    audit_root.mkdir(parents=True, exist_ok=True)

    split_summaries = []
    event_counts = []
    sequence_lengths = []
    top_tokens = []
    quantile_counts = []
    exclusion_counts = []

    for split, outputs in split_outputs.items():
        summary = json.loads(outputs["summary"].read_text())
        summary["split"] = split
        split_summaries.append(summary)

        debug_path = outputs.get("debug")
        if debug_path and debug_path.is_file():
            event_counts.append(
                pl.scan_parquet(debug_path)
                .group_by("source_table")
                .len(name="event_count")
                .with_columns(pl.lit(split).alias("split"))
                .select(["split", "source_table", "event_count"])
                .collect(engine="streaming")
            )
        sequence_lengths.append(_read_csv_with_split(config.audit_dir / "meds" / split / "meds_sequence_length_summary.csv", split))
        top_tokens.append(_read_csv_with_split(config.audit_dir / "meds" / split / "meds_top_token_counts.csv", split))
        quantile_counts.append(_read_csv_with_split(config.audit_dir / "meds" / split / "meds_numeric_quantile_assignments.csv", split))
        exclusion_counts.append(_read_csv_with_split(config.audit_dir / "meds" / split / "meds_exclusion_counts.csv", split))

    def write_concat(frames: list[pl.DataFrame], path: Path) -> None:
        non_empty = [f for f in frames if not f.is_empty()]
        if non_empty:
            pl.concat(non_empty, how="vertical_relaxed").write_csv(path)
        else:
            pl.DataFrame().write_csv(path)

    write_concat(event_counts, audit_root / "meds_split_event_counts.csv")
    write_concat(sequence_lengths, audit_root / "meds_split_sequence_length_summary.csv")
    write_concat(top_tokens, audit_root / "meds_split_top_tokens.csv")
    write_concat(quantile_counts, audit_root / "meds_split_quantile_assignment_counts.csv")
    write_concat(exclusion_counts, audit_root / "meds_split_exclusion_counts.csv")

    summary = {
        "splits": list(config.splits),
        "quantile_boundaries": str(boundaries_path),
        "fit_split": "train",
        "fit_exclusion_counts": fit_exclusions,
        "split_summaries": split_summaries,
    }
    summary_path = audit_root / "meds_split_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, cls=_JsonEncoder) + "\n")
    return summary_path


def write_split_meds_outputs(config: SplitMEDSConfig) -> dict[str, Path]:
    """Run train/val/test MEDS conversion with train-frozen numeric quantiles."""
    total_start = time.perf_counter()
    _preflight_split(config)
    config.metadata_dir.mkdir(parents=True, exist_ok=True)
    (config.audit_dir / "meds").mkdir(parents=True, exist_ok=True)

    _log("split-aware MEDS: loading vocab")
    vocab = load_vocab(config.vocab_path)

    _log("split-aware MEDS: fitting numeric quantile boundaries on train")
    boundaries, fit_exclusions = fit_numeric_quantile_boundaries(
        config.pre_meds_dir / "train",
        vocab,
        config.include_temporal_phases,
        bins=config.quantile_bins,
        max_rows=config.max_rows,
    )
    boundaries_path = config.metadata_dir / "numeric_quantile_boundaries.parquet"
    if boundaries_path.exists() and not config.overwrite:
        raise FileExistsError(
            f"Quantile boundary file already exists: {boundaries_path}. Set run.overwrite=true to replace."
        )
    boundaries.write_parquet(boundaries_path)
    _log(f"  boundaries: {boundaries.height:,} rows -> {boundaries_path}")

    split_outputs: dict[str, dict[str, Path]] = {}
    for split in config.splits:
        _log(f"split-aware MEDS: converting {split}")
        split_outputs[split] = write_meds_outputs(
            MEDSConfig(
                pre_meds_dir=config.pre_meds_dir / split,
                vocab_path=config.vocab_path,
                output_dir=config.output_dir / split,
                audit_dir=config.audit_dir / "meds" / split,
                mode=config.mode,
                num_patients=config.num_patients,
                seed=config.seed,
                include_temporal_phases=config.include_temporal_phases,
                quantile_bins=config.quantile_bins,
                max_rows=config.max_rows,
                write_debug=config.write_debug,
                overwrite=config.overwrite,
                quantile_boundaries=boundaries,
            )
        )

    summary_path = _write_split_global_audits(config, split_outputs, boundaries_path, fit_exclusions)
    _log(f"split-aware MEDS done in {_elapsed(total_start)} -> {summary_path}")

    outputs: dict[str, Path] = {
        "quantile_boundaries": boundaries_path,
        "split_summary": summary_path,
    }
    for split, split_result in split_outputs.items():
        outputs[f"{split}_events"] = split_result["events"]
        outputs[f"{split}_summary"] = split_result["summary"]
        if "debug" in split_result:
            outputs[f"{split}_debug"] = split_result["debug"]
    return outputs
