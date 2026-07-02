"""Pre-MEDS build workflow: converts raw Amsterdam CSVs to pre-MEDS parquet.

Three phases run in order:
  1. admissions + patient (prerequisite for all anchor joins)
  2. small tables: freetextitems, processitems, procedureorderitems
  3. large tables (chunked): numericitems, listitems, drugitems
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl

from aumc_pipeline.pre_meds.admissions import (
    load_epoch_map,
    write_admissions_outputs,
)
from aumc_pipeline.pre_meds.common import (
    admission_anchor_columns,
    interval_time_anomalies,
    measurement_time_anomalies,
    temporal_phase_counts,
)
from aumc_pipeline.pre_meds.interval_tables import (
    transform_drugitems,
    transform_procedureorderitems,
    transform_processitems,
)
from aumc_pipeline.pre_meds.large_tables import (
    TableAccumulator,
    build_raw_shards_for_tables,
    transform_table,
)
from aumc_pipeline.pre_meds.measured import (
    transform_freetextitems,
    transform_listitems,
    transform_numericitems,
)
from aumc_pipeline.splits.build_splits import SplitConfig, write_subject_splits
from aumc_pipeline.transforms.binning import CausalMeanBinningConfig, CausalMeanBinningTransform
from aumc_pipeline.transforms.hf_inventory import HFInventoryBuilder, HFInventoryConfig
from aumc_pipeline.utils.parquet_datasets import parquet_exists

REQUIRED_RAW_TABLES = [
    "admissions.csv",
    "numericitems.csv",
    "listitems.csv",
    "drugitems.csv",
    "freetextitems.csv",
    "processitems.csv",
    "procedureorderitems.csv",
]

# Small tables read entirely into memory; large tables use chunked reads.
_SMALL_TABLES = ["freetextitems", "processitems", "procedureorderitems"]
_LARGE_TABLES = ["numericitems", "listitems", "drugitems"]

# Dispatch map: table name → transform function for small tables.
# Each transform takes (raw: pl.DataFrame, anchors: pl.DataFrame).
_SMALL_TABLE_TRANSFORMS = {
    "freetextitems": transform_freetextitems,
    "processitems": transform_processitems,
    "procedureorderitems": transform_procedureorderitems,
}


@dataclass(frozen=True)
class PreMedsConfig:
    """Inputs and outputs for one pre-MEDS extraction run."""

    raw_data_dir: Path
    pre_meds_dir: Path
    audit_dir: Path
    epoch_map: dict[str, str]
    dataset: str = "AmsterdamUMCdb"
    partition_rows: int = 5_000_000
    max_rows: int | None = None
    num_patients: int | None = None
    raw_shards_dir: Path | None = None
    build_raw_shards: bool = True
    rebuild_raw_shards: bool = False
    raw_shard_rows: int | None = None
    split_path: Path | None = None
    split_outputs: bool = False
    split_train_frac: float = 0.8
    split_val_frac: float = 0.1
    split_test_frac: float = 0.1
    split_seed: int = 20260618
    vocab_path: Path | None = None
    build_hf_inventory: bool = True
    build_binned_numericitems: bool = True
    hf_inventory_metadata_dir: Path | None = None
    hf_highres_threshold_minutes: float = 45.0
    hf_confidence_level: float = 0.99
    hf_min_groups: int = 30
    hf_patient_batch_size: int = 500
    hf_candidate_limit: int = 0
    hf_seed: int = 20260601
    binning_window_minutes: int = 60
    overwrite: bool = False


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def _log(message: str) -> None:
    print(f"[build_premeds] {message}", flush=True)


def _elapsed(start: float) -> str:
    return f"{time.perf_counter() - start:.1f}s"


def _ensure_split_manifest(config: PreMedsConfig) -> dict[str, Path] | None:
    """Create the subject split manifest for split-aware pre-MEDS runs.

    Split generation is a pre-MEDS substage: downstream pre-MEDS code still
    consumes the stable ``subject_id, split`` artifact, while normal users do
    not need to run a separate split command.
    """
    if not config.split_outputs:
        return None
    if config.split_path is None:
        raise ValueError("split_outputs=true requires paths.split_path")
    if config.split_path.exists():
        _log(f"using existing split manifest: {config.split_path}")
        return {"subject_splits": config.split_path}

    _log(
        "creating subject split manifest "
        f"({config.split_train_frac:.3f}/{config.split_val_frac:.3f}/{config.split_test_frac:.3f}, "
        f"seed={config.split_seed})"
    )
    return write_subject_splits(
        SplitConfig(
            raw_data_dir=config.raw_data_dir,
            metadata_dir=config.split_path.parent,
            split_path=config.split_path,
            train_frac=config.split_train_frac,
            val_frac=config.split_val_frac,
            test_frac=config.split_test_frac,
            seed=config.split_seed,
            overwrite=config.overwrite,
        )
    )


def _preflight(config: PreMedsConfig) -> None:
    if not config.raw_data_dir.is_dir():
        raise FileNotFoundError(
            f"Raw data directory not found: {config.raw_data_dir}"
        )
    missing = [f for f in REQUIRED_RAW_TABLES if not (config.raw_data_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required Amsterdam CSV files in {config.raw_data_dir}: {missing}"
        )
    if config.partition_rows <= 0:
        raise ValueError("partition_rows must be > 0")
    if config.raw_shard_rows is not None and config.raw_shard_rows <= 0:
        raise ValueError("raw_shard_rows must be > 0 when set")
    if config.max_rows is not None and config.max_rows <= 0:
        raise ValueError("max_rows must be > 0 when set")
    if config.num_patients is not None and config.num_patients <= 0:
        raise ValueError("num_patients must be > 0 when set")
    if config.split_outputs:
        if config.split_path is None:
            raise ValueError("split_outputs=true requires paths.split_path")
        if not config.split_path.is_file():
            raise FileNotFoundError(f"Split manifest not found: {config.split_path}")
    if config.build_hf_inventory:
        if not config.split_outputs:
            raise ValueError("build_hf_inventory=true requires split_outputs=true")
        if config.vocab_path is None:
            raise ValueError("build_hf_inventory=true requires paths.vocab_path")
        if not config.vocab_path.is_file():
            raise FileNotFoundError(f"Vocab not found for HF inventory: {config.vocab_path}")
    if config.build_binned_numericitems:
        if not config.build_hf_inventory:
            raise ValueError("build_binned_numericitems=true requires build_hf_inventory=true")
        if config.binning_window_minutes <= 0:
            raise ValueError("binning_window_minutes must be > 0")


def _write_raw_shards(config: PreMedsConfig) -> dict[str, Any]:
    """Build or reuse the source-preserving raw parquet cache for large tables."""
    if not config.build_raw_shards:
        return {"skipped": "run.build_raw_shards=false"}
    if config.raw_shards_dir is None:
        raise ValueError("build_raw_shards=true requires paths.raw_shards_dir")

    return build_raw_shards_for_tables(
        tables=_LARGE_TABLES,
        raw_dir=config.raw_data_dir,
        raw_shards_dir=config.raw_shards_dir,
        partition_rows=config.raw_shard_rows or config.partition_rows,
        max_rows=config.max_rows,
        rebuild=config.rebuild_raw_shards,
    )


def _write_small_table(
    table: str,
    config: PreMedsConfig,
    anchors: pl.DataFrame,
    admission_ids: set[int] | None,
    split_values: list[str],
) -> dict[str, Any]:
    raw_path = config.raw_data_dir / f"{table}.csv"
    df = pd.read_csv(
        raw_path,
        encoding="latin1",
        low_memory=False,
        nrows=config.max_rows,
    )
    raw = pl.from_pandas(df)
    rows_read = raw.height

    if admission_ids is not None:
        raw = raw.filter(pl.col("admissionid").is_in(list(admission_ids)))
    rows_after_patient_filter = raw.height

    transform_fn = _SMALL_TABLE_TRANSFORMS[table]
    result = transform_fn(raw, anchors)

    if len(result) == 3:
        # measured table: (transformed, n_excluded_sentinel, n_missing_join)
        transformed, n_excl, n_miss = result
        anomalies = measurement_time_anomalies(transformed) if not transformed.is_empty() else {}
    else:
        # interval table: (transformed, n_missing_join)
        transformed, n_miss = result
        n_excl = 0
        anomalies = interval_time_anomalies(transformed) if not transformed.is_empty() else {}

    out_path = config.pre_meds_dir / f"{table}.parquet"
    transformed.write_parquet(out_path)

    split_rows_emitted: dict[str, int] = {}
    if config.split_outputs and "split" in transformed.columns:
        for split in split_values:
            split_dir = config.pre_meds_dir / split
            split_dir.mkdir(parents=True, exist_ok=True)
            split_part = transformed.filter(pl.col("split") == split)
            split_part.write_parquet(split_dir / f"{table}.parquet")
            split_rows_emitted[split] = split_part.height

    return {
        "rows_read": rows_read,
        "rows_after_patient_filter": rows_after_patient_filter,
        "rows_excluded_measuredat_minus_1899": n_excl,
        "rows_emitted": transformed.height,
        "split_rows_emitted": split_rows_emitted,
        "missing_admission_join_rows": n_miss,
        "time_anomalies": anomalies,
        "temporal_phase_counts": temporal_phase_counts(transformed),
    }


def _load_split_manifest(split_path: Path | None) -> pd.DataFrame | None:
    if split_path is None:
        return None
    split_df = pd.read_parquet(split_path)
    missing = sorted({"subject_id", "split"} - set(split_df.columns))
    if missing:
        raise ValueError(f"Split manifest is missing columns: {missing}")
    return split_df[["subject_id", "split"]].drop_duplicates()


def _write_hf_inventory(config: PreMedsConfig, split_values: list[str]) -> dict[str, Any]:
    """Build train-derived high-frequency numeric inventory after pre-MEDS write."""
    if not config.build_hf_inventory:
        return {}
    if "train" not in split_values:
        return {"skipped": "train split not present in current bounded pre-MEDS output"}

    metadata_dir = config.hf_inventory_metadata_dir or (config.pre_meds_dir.parent / "metadata")
    cfg = HFInventoryConfig(
        input_path=config.pre_meds_dir / "train" / "numericitems",
        vocab_path=config.vocab_path,  # type: ignore[arg-type]
        output_csv_path=metadata_dir / "hf_numeric_inventory.csv",
        output_json_path=metadata_dir / "hf_numeric_highres_items.json",
        summary_path=metadata_dir / "hf_numeric_inventory_summary.json",
        highres_threshold_minutes=config.hf_highres_threshold_minutes,
        confidence_level=config.hf_confidence_level,
        min_groups=config.hf_min_groups,
        patient_batch_size=config.hf_patient_batch_size,
        candidate_limit=config.hf_candidate_limit,
        seed=config.hf_seed,
    )
    return HFInventoryBuilder(cfg).run()


def _write_binned_numericitems(config: PreMedsConfig, split_values: list[str]) -> dict[str, Any]:
    """Apply train-derived high-frequency inventory to split numericitems.

    Raw ``numericitems`` remains source-preserving. Binned output is written as
    ``numericitems_binned`` beside each split's raw numericitems dataset.
    """
    if not config.build_binned_numericitems:
        return {}

    metadata_dir = config.hf_inventory_metadata_dir or (config.pre_meds_dir.parent / "metadata")
    inventory_path = metadata_dir / "hf_numeric_inventory.csv"
    if not inventory_path.is_file():
        raise FileNotFoundError(f"Missing HF inventory for numeric binning: {inventory_path}")

    summaries: dict[str, Any] = {}
    for split in split_values:
        input_path = config.pre_meds_dir / split / "numericitems"
        if not parquet_exists(input_path):
            (config.pre_meds_dir / split / "numericitems_binned").mkdir(parents=True, exist_ok=True)
            summaries[split] = {"skipped": f"no numericitems parquet for split {split}"}
            continue
        result = CausalMeanBinningTransform(
            CausalMeanBinningConfig(
                input_path=input_path,
                output_path=config.pre_meds_dir / split / "numericitems_binned",
                inventory_path=inventory_path,
                summary_path=metadata_dir / f"hf_numeric_binning_{split}_summary.json",
                split_name=split,
                window_minutes=config.binning_window_minutes,
                overwrite=config.overwrite,
            )
        ).run()
        summaries[split] = result.summary

    manifest = {
        "inventory_path": str(inventory_path),
        "window_minutes": config.binning_window_minutes,
        "splits": summaries,
    }
    manifest_path = metadata_dir / "hf_numeric_binning_summary.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, cls=_JsonEncoder) + "\n")
    return manifest


def write_premeds_outputs(config: PreMedsConfig) -> dict[str, Path]:
    """Run the full pre-MEDS extraction and return a dict of output paths."""

    total_start = time.perf_counter()
    total_steps = 3 + int(config.build_raw_shards) + int(config.build_hf_inventory) + int(config.build_binned_numericitems)
    split_manifest_outputs = _ensure_split_manifest(config)
    _preflight(config)
    config.pre_meds_dir.mkdir(parents=True, exist_ok=True)
    config.audit_dir.mkdir(parents=True, exist_ok=True)

    step_index = 1
    raw_shard_summary: dict[str, Any] = {"skipped": "run.build_raw_shards=false"}
    if config.build_raw_shards:
        step_start = time.perf_counter()
        _log(f"{step_index}/{total_steps} raw shard cache for large tables")
        raw_shard_summary = _write_raw_shards(config)
        actions = {
            table: summary.get("action", "unknown")
            for table, summary in raw_shard_summary.items()
            if isinstance(summary, dict)
        }
        _log(f"{step_index}/{total_steps} raw shard cache done in {_elapsed(step_start)}: {actions}")
        step_index += 1

    epoch_map = load_epoch_map(config.epoch_map)
    split_manifest = _load_split_manifest(config.split_path)

    # Phase 1: admissions (prerequisite for anchor joins in all subsequent phases).
    step_start = time.perf_counter()
    _log(
        f"{step_index}/{total_steps} admissions and patient"
        + (f" (bounded to {config.num_patients} patients)" if config.num_patients else " (all patients)")
    )
    adm_paths, adm_counts = write_admissions_outputs(
        raw_data_dir=config.raw_data_dir,
        pre_meds_dir=config.pre_meds_dir,
        epoch_map=epoch_map,
        num_patients=config.num_patients,
        split_manifest=split_manifest,
        split_outputs=config.split_outputs,
    )
    admissions_for_anchors = pl.read_parquet(config.pre_meds_dir / "admissions.parquet")
    anchors = admissions_for_anchors.select(admission_anchor_columns(admissions_for_anchors))
    split_values = (
        sorted(anchors["split"].drop_nulls().unique().to_list())
        if config.split_outputs and "split" in anchors.columns
        else []
    )
    admission_ids: set[int] | None = (
        set(anchors["admissionid"].to_list()) if config.num_patients is not None else None
    )
    _log(
        f"{step_index}/{total_steps} admissions done in {_elapsed(step_start)}: "
        f"{adm_counts['unique_admissions']} admissions / {adm_counts['unique_patients']} patients"
    )
    step_index += 1

    # Phase 2: small tables (read entirely into memory).
    step_start = time.perf_counter()
    _log(f"{step_index}/{total_steps} small tables: freetextitems, processitems, procedureorderitems")
    small_summaries: dict[str, Any] = {}
    for table in _SMALL_TABLES:
        _log(f"  {table} ...")
        small_summaries[table] = _write_small_table(table, config, anchors, admission_ids, split_values)
        _log(
            f"  {table}: {small_summaries[table]['rows_emitted']:,} rows emitted"
        )
    _log(f"{step_index}/{total_steps} small tables done in {_elapsed(step_start)}")
    step_index += 1

    # Phase 3: large tables (chunked latin1 CSV → partitioned parquet).
    step_start = time.perf_counter()
    _log(f"{step_index}/{total_steps} large tables: numericitems, listitems, drugitems")
    large_summaries: dict[str, Any] = {}
    for table in _LARGE_TABLES:
        _log(f"  {table} ...")
        acc: TableAccumulator = transform_table(
            table=table,
            raw_dir=config.raw_data_dir,
            output_dir=config.pre_meds_dir,
            anchors=anchors,
            partition_rows=config.partition_rows,
            max_rows=config.max_rows,
            overwrite=config.overwrite,
            admission_ids=admission_ids,
            split_values=split_values if config.split_outputs else None,
            raw_shards_dir=config.raw_shards_dir,
        )
        large_summaries[table] = acc.as_summary(config.pre_meds_dir, config.max_rows)
        _log(
            f"  {table}: {acc.rows_emitted:,} rows in {acc.partition_count} partitions"
        )
    _log(f"{step_index}/{total_steps} large tables done in {_elapsed(step_start)}")
    step_index += 1

    # Optional train-derived high-frequency inventory. This is part of
    # pre-MEDS finalization because later binning needs a frozen train artifact.
    hf_inventory_summary: dict[str, Any] = {}
    if config.build_hf_inventory:
        step_start = time.perf_counter()
        _log(f"{step_index}/{total_steps} high-frequency numeric inventory from train split")
        hf_inventory_summary = _write_hf_inventory(config, split_values)
        _log(f"{step_index}/{total_steps} high-frequency inventory done in {_elapsed(step_start)}")
        step_index += 1

    binned_numeric_summary: dict[str, Any] = {}
    if config.build_binned_numericitems:
        step_start = time.perf_counter()
        _log(f"{step_index}/{total_steps} causal mean-binning high-frequency numericitems")
        binned_numeric_summary = _write_binned_numericitems(config, split_values)
        _log(f"{step_index}/{total_steps} numeric binning done in {_elapsed(step_start)}")

    # Summary artifact.
    summary: dict[str, Any] = {
        "dataset": config.dataset,
        "raw_data_dir": str(config.raw_data_dir),
        "pre_meds_dir": str(config.pre_meds_dir),
        "num_patients": config.num_patients,
        "split_path": str(config.split_path) if config.split_path else None,
        "split_outputs": config.split_outputs,
        "split_manifest_outputs": split_manifest_outputs,
        "split_values": split_values,
        "max_rows_per_table": config.max_rows,
        "partition_rows": config.partition_rows,
        "raw_shards_dir": str(config.raw_shards_dir) if config.raw_shards_dir else None,
        "raw_shards": raw_shard_summary,
        "admissions": adm_counts,
        "small_tables": small_summaries,
        "large_tables": large_summaries,
        "hf_inventory": hf_inventory_summary,
        "binned_numericitems": binned_numeric_summary,
        "elapsed_seconds": round(time.perf_counter() - total_start, 1),
    }
    summary_path = config.audit_dir / "premeds_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, cls=_JsonEncoder) + "\n"
    )
    _log(f"done in {_elapsed(total_start)} -> {summary_path}")

    outputs: dict[str, Path] = {
        "admissions": adm_paths["admissions"],
        "patient": adm_paths["patient"],
        "summary": summary_path,
    }
    if split_manifest_outputs:
        outputs.update(split_manifest_outputs)
    for table in _SMALL_TABLES:
        outputs[table] = config.pre_meds_dir / f"{table}.parquet"
    for table in _LARGE_TABLES:
        outputs[table] = config.pre_meds_dir / table
    if config.build_hf_inventory:
        metadata_dir = config.hf_inventory_metadata_dir or (config.pre_meds_dir.parent / "metadata")
        outputs["hf_numeric_inventory"] = metadata_dir / "hf_numeric_inventory.csv"
    if config.build_binned_numericitems:
        metadata_dir = config.hf_inventory_metadata_dir or (config.pre_meds_dir.parent / "metadata")
        outputs["hf_numeric_binning_summary"] = metadata_dir / "hf_numeric_binning_summary.json"
    return outputs
