"""Compatibility imports for shared MIMIC-IV raw-table access.

Grid extraction now uses the persistent parquet-shard cache under metaicu.mimiciv.common
instead of a per-run zcat|awk itemid-prefilter (collect_all_itemids/prefetch_large_table/
_awk_prefilter_to_dataframe are gone -- the shard cache subsumes their purpose at a coarser,
cross-run granularity; itemid scoping now happens downstream in each extract_* module's own
.filter() call, not in this layer). New shared code belongs under metaicu.mimiciv.common; this
module keeps the grid import surface stable, mirroring metaicu.aumcdb.grid.build.raw_csv's own
compatibility-shim role exactly.
"""

import logging

import polars as pl

from metaicu.mimiciv.common.raw_tables import (
    HOUR_MS,
    INTERVAL_COLS,
    TABLE_FILES,
    TIME_COL,
    admission_filter,
    load_admissions,
    raw_table_input_mode,
    scan_raw_table,
)

log = logging.getLogger(__name__)


def load_prescription_intervals(raw_data_dir, admissions, ndc_codes, admission_ids=None):
    """Load NDC-selected hospital prescriptions and anchor them to overlapping ICU stays."""
    raw = (
        pl.scan_csv(
            raw_data_dir / "hosp/prescriptions.csv.gz",
            infer_schema_length=None,
            schema_overrides={"ndc": pl.String},
        )
        .filter(pl.col("ndc").is_in(list(ndc_codes)))
        .select("subject_id", "hadm_id", "ndc", "starttime", "stoptime")
        .collect(engine="streaming")
    )
    log.info(f"prescriptions: {raw.height} NDC-selected source rows")
    anchors = admissions.select(
        "admissionid", "subject_id", "hadm_id", "intime", "true_los_hours"
    )
    joined = raw.join(anchors, on=["subject_id", "hadm_id"], how="inner")
    if admission_ids is not None:
        joined = joined.filter(pl.col("admissionid").is_in(list(admission_ids)))
    joined = joined.with_columns(
        pl.col("starttime").str.to_datetime().alias("_start"),
        pl.col("stoptime").str.to_datetime().alias("_stop"),
    ).with_columns(
        (pl.col("_start") - pl.col("intime")).dt.total_milliseconds()
        .alias("start_admission_relative_ms"),
        (pl.col("_stop") - pl.col("intime")).dt.total_milliseconds()
        .alias("stop_admission_relative_ms"),
        (pl.col("true_los_hours") * HOUR_MS).alias("los_ms"),
    )
    log.info(f"prescriptions: {joined.height} rows after ICU-stay join")
    return joined

__all__ = [
    "HOUR_MS",
    "INTERVAL_COLS",
    "TABLE_FILES",
    "TIME_COL",
    "admission_filter",
    "load_admissions",
    "raw_table_input_mode",
    "scan_raw_table",
    "load_prescription_intervals",
]
