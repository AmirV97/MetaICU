"""Compatibility exports for the shared parquet helpers.

New code should import from :mod:`metaicu.aumcdb.common.parquet`.
"""

from metaicu.aumcdb.common.parquet import (
    grouped_counts,
    parquet_exists,
    parquet_row_count,
    read_parquet,
    resolve_table_parquet,
    scan_parquet,
)

__all__ = [
    "grouped_counts",
    "parquet_exists",
    "parquet_row_count",
    "read_parquet",
    "resolve_table_parquet",
    "scan_parquet",
]
