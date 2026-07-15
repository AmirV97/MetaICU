"""Shared Amsterdam raw-table access with optional large-table parquet caches."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd
import polars as pl

from metaicu.aumcdb.common.parquet import scan_parquet
from metaicu.aumcdb.common.raw_schema import LARGE_TABLE_RAW_SCHEMAS
from metaicu.aumcdb.common.raw_shards import raw_shards_exist


HOUR_MS = 3_600_000
SENTINEL = -1899
log = logging.getLogger(__name__)

TABLE_FILES = {
    "admissions": "admissions.csv",
    "numericitems": "numericitems.csv",
    "listitems": "listitems.csv",
    "drugitems": "drugitems.csv",
    "freetextitems": "freetextitems.csv",
    "processitems": "processitems.csv",
    "procedureorderitems": "procedureorderitems.csv",
}

MEASURED_AT_COL = {
    "numericitems": "measuredat",
    "listitems": "measuredat",
    "freetextitems": "measuredat",
    "procedureorderitems": "registeredat",
}
INTERVAL_COLS = {
    "drugitems": ("start", "stop"),
    "processitems": ("start", "stop"),
}
SENTINEL_FILTERED_TABLES = {"numericitems", "listitems", "freetextitems"}


def admission_filter(admission_ids: Iterable[int] | None) -> pl.Expr:
    """Return a no-op expression for full runs or an admission restriction."""
    if admission_ids is None:
        return pl.lit(True)
    return pl.col("admissionid").is_in(list(admission_ids))


def load_admissions(raw_data_dir: Path) -> pl.DataFrame:
    """Read Latin-1 admissions and derive ICU length of stay in hours."""
    path = Path(raw_data_dir) / TABLE_FILES["admissions"]
    frame = pl.from_pandas(pd.read_csv(path, encoding="latin1", low_memory=False))
    frame = frame.with_columns(
        pl.col("admittedat").cast(pl.Int64, strict=False),
        pl.col("dischargedat").cast(pl.Int64, strict=False),
        pl.col("dateofdeath").cast(pl.Float64, strict=False),
    ).with_columns(
        ((pl.col("dischargedat") - pl.col("admittedat")) / HOUR_MS).alias("true_los_hours")
    )
    log.info(
        "admissions.csv: %d rows, %d distinct admissions",
        frame.height,
        frame["admissionid"].n_unique(),
    )
    return frame


def raw_table_input_mode(table: str, raw_shards_dir: Path | None) -> str:
    if raw_shards_dir is not None and raw_shards_exist(raw_shards_dir, table):
        return "raw_parquet_shards"
    return "raw_csv_scan"


def scan_raw_table(
    raw_data_dir: Path,
    table: str,
    admissions: pl.DataFrame,
    raw_shards_dir: Path | None = None,
) -> pl.LazyFrame:
    """Scan a raw table and attach admission-relative timing columns.

    Large tables prefer the shared Latin-1-preserving parquet cache. Direct CSV
    scanning remains a compatibility fallback for bounded tests and small tables.
    """
    if raw_table_input_mode(table, raw_shards_dir) == "raw_parquet_shards":
        frame = scan_parquet(Path(raw_shards_dir) / table)
    else:
        path = Path(raw_data_dir) / TABLE_FILES[table]
        frame = pl.scan_csv(
            path,
            encoding="utf8-lossy",
            schema_overrides=LARGE_TABLE_RAW_SCHEMAS.get(table),
        )

    anchors = admissions.lazy().select("admissionid", "admittedat")
    frame = frame.join(anchors, on="admissionid", how="inner")
    if table in MEASURED_AT_COL:
        source_column = MEASURED_AT_COL[table]
        if table in SENTINEL_FILTERED_TABLES:
            frame = frame.filter(
                pl.col(source_column).is_null() | (pl.col(source_column) != SENTINEL)
            )
        frame = frame.with_columns(
            (pl.col(source_column) - pl.col("admittedat")).alias("admission_relative_ms")
        )
    elif table in INTERVAL_COLS:
        start_column, stop_column = INTERVAL_COLS[table]
        frame = frame.with_columns(
            (pl.col(start_column) - pl.col("admittedat")).alias("start_admission_relative_ms"),
            (pl.col(stop_column) - pl.col("admittedat")).alias("stop_admission_relative_ms"),
        )
    return frame
