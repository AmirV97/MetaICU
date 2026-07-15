"""Compatibility imports for shared Amsterdam raw-table access.

Grid extraction now uses the same source-preserving raw schemas and parquet
cache as the tokenized pipeline. New shared code belongs under
``metaicu.aumcdb.common``; this module keeps the grid import surface stable.
"""

from metaicu.aumcdb.common.raw_tables import (
    HOUR_MS,
    INTERVAL_COLS,
    MEASURED_AT_COL,
    SENTINEL,
    SENTINEL_FILTERED_TABLES,
    TABLE_FILES,
    admission_filter,
    load_admissions,
    raw_table_input_mode,
    scan_raw_table,
)

__all__ = [
    "HOUR_MS",
    "INTERVAL_COLS",
    "MEASURED_AT_COL",
    "SENTINEL",
    "SENTINEL_FILTERED_TABLES",
    "TABLE_FILES",
    "admission_filter",
    "load_admissions",
    "raw_table_input_mode",
    "scan_raw_table",
]
