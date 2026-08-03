"""Compatibility imports for shared MIMIC-IV raw-table access.

Grid extraction now uses the persistent parquet-shard cache under metaicu.mimiciv.common
instead of a per-run zcat|awk itemid-prefilter (collect_all_itemids/prefetch_large_table/
_awk_prefilter_to_dataframe are gone -- the shard cache subsumes their purpose at a coarser,
cross-run granularity; itemid scoping now happens downstream in each extract_* module's own
.filter() call, not in this layer). New shared code belongs under metaicu.mimiciv.common; this
module keeps the grid import surface stable, mirroring metaicu.aumcdb.grid.build.raw_csv's own
compatibility-shim role exactly.
"""

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

__all__ = [
    "HOUR_MS",
    "INTERVAL_COLS",
    "TABLE_FILES",
    "TIME_COL",
    "admission_filter",
    "load_admissions",
    "raw_table_input_mode",
    "scan_raw_table",
]
