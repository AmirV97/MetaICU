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
    ADMISSION_ANCHOR_COLUMNS,
    interval_time_anomalies,
    measurement_time_anomalies,
    temporal_phase_counts,
)
from aumc_pipeline.pre_meds.interval_tables import (
    transform_drugitems,
    transform_procedureorderitems,
    transform_processitems,
)
from aumc_pipeline.pre_meds.large_tables import TableAccumulator, transform_table
from aumc_pipeline.pre_meds.measured import (
    transform_freetextitems,
    transform_listitems,
    transform_numericitems,
)

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
    if config.max_rows is not None and config.max_rows <= 0:
        raise ValueError("max_rows must be > 0 when set")
    if config.num_patients is not None and config.num_patients <= 0:
        raise ValueError("num_patients must be > 0 when set")


def _write_small_table(
    table: str,
    config: PreMedsConfig,
    anchors: pl.DataFrame,
    admission_ids: set[int] | None,
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

    return {
        "rows_read": rows_read,
        "rows_after_patient_filter": rows_after_patient_filter,
        "rows_excluded_measuredat_minus_1899": n_excl,
        "rows_emitted": transformed.height,
        "missing_admission_join_rows": n_miss,
        "time_anomalies": anomalies,
        "temporal_phase_counts": temporal_phase_counts(transformed),
    }


def write_premeds_outputs(config: PreMedsConfig) -> dict[str, Path]:
    """Run the full pre-MEDS extraction and return a dict of output paths."""

    total_start = time.perf_counter()
    _preflight(config)
    config.pre_meds_dir.mkdir(parents=True, exist_ok=True)
    config.audit_dir.mkdir(parents=True, exist_ok=True)

    epoch_map = load_epoch_map(config.epoch_map)

    # Phase 1: admissions (prerequisite for anchor joins in all subsequent phases).
    step_start = time.perf_counter()
    _log(
        f"1/3 admissions and patient"
        + (f" (bounded to {config.num_patients} patients)" if config.num_patients else " (all patients)")
    )
    adm_paths, adm_counts = write_admissions_outputs(
        raw_data_dir=config.raw_data_dir,
        pre_meds_dir=config.pre_meds_dir,
        epoch_map=epoch_map,
        num_patients=config.num_patients,
    )
    anchors = pl.read_parquet(config.pre_meds_dir / "admissions.parquet").select(
        ADMISSION_ANCHOR_COLUMNS
    )
    admission_ids: set[int] | None = (
        set(anchors["admissionid"].to_list()) if config.num_patients is not None else None
    )
    _log(
        f"1/3 admissions done in {_elapsed(step_start)}: "
        f"{adm_counts['unique_admissions']} admissions / {adm_counts['unique_patients']} patients"
    )

    # Phase 2: small tables (read entirely into memory).
    step_start = time.perf_counter()
    _log("2/3 small tables: freetextitems, processitems, procedureorderitems")
    small_summaries: dict[str, Any] = {}
    for table in _SMALL_TABLES:
        _log(f"  {table} ...")
        small_summaries[table] = _write_small_table(table, config, anchors, admission_ids)
        _log(
            f"  {table}: {small_summaries[table]['rows_emitted']:,} rows emitted"
        )
    _log(f"2/3 small tables done in {_elapsed(step_start)}")

    # Phase 3: large tables (chunked latin1 CSV → partitioned parquet).
    step_start = time.perf_counter()
    _log("3/3 large tables: numericitems, listitems, drugitems (chunked)")
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
        )
        large_summaries[table] = acc.as_summary(config.pre_meds_dir, config.max_rows)
        _log(
            f"  {table}: {acc.rows_emitted:,} rows in {acc.partition_count} partitions"
        )
    _log(f"3/3 large tables done in {_elapsed(step_start)}")

    # Summary artifact.
    summary: dict[str, Any] = {
        "dataset": config.dataset,
        "raw_data_dir": str(config.raw_data_dir),
        "pre_meds_dir": str(config.pre_meds_dir),
        "num_patients": config.num_patients,
        "max_rows_per_table": config.max_rows,
        "partition_rows": config.partition_rows,
        "admissions": adm_counts,
        "small_tables": small_summaries,
        "large_tables": large_summaries,
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
    for table in _SMALL_TABLES:
        outputs[table] = config.pre_meds_dir / f"{table}.parquet"
    for table in _LARGE_TABLES:
        outputs[table] = config.pre_meds_dir / table
    return outputs
