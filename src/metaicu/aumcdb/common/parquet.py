"""Helpers for single-file and partitioned parquet datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd
import polars as pl


def resolve_table_parquet(pre_meds_dir: Path, table: str) -> Path:
    """Return the parquet file or partition directory for a table."""
    file_path = pre_meds_dir / f"{table}.parquet"
    if file_path.is_file():
        return file_path
    dir_path = pre_meds_dir / table
    if dir_path.is_dir():
        return dir_path
    return file_path


def parquet_exists(path: Path) -> bool:
    """Check whether a parquet file or non-empty partition directory exists."""
    if path.is_file():
        return True
    if path.is_dir():
        return any(path.glob("*.parquet"))
    return False


def scan_parquet(path: Path) -> pl.LazyFrame:
    """Build a Polars lazy scan for a parquet file or partition directory."""
    if path.is_dir():
        return pl.scan_parquet(str(path / "*.parquet"))
    return pl.scan_parquet(path)


def read_parquet(path: Path, columns: Sequence[str] | None = None) -> pd.DataFrame:
    """Read a parquet file or partition directory with pandas."""
    return pd.read_parquet(path, columns=list(columns) if columns else None)


def grouped_counts(
    path: Path,
    group_columns: Sequence[str],
    select_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Return grouped row counts without materializing the full source table."""
    columns = list(select_columns or group_columns)
    frame = (
        scan_parquet(path)
        .select(columns)
        .group_by(list(group_columns))
        .len(name="row_count")
        .collect(engine="streaming")
    )
    return frame.to_pandas()


def parquet_row_count(path: Path) -> int:
    """Count rows in a parquet file or dataset using a lazy scan."""
    if not parquet_exists(path):
        return 0
    result = scan_parquet(path).select(pl.len().alias("n")).collect(engine="streaming")
    return int(result["n"][0])

