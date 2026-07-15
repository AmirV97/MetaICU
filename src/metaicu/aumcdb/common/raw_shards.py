"""Source-preserving Latin-1 CSV to parquet sharding for large AUMCdb tables."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import polars as pl

from metaicu.aumcdb.common.raw_schema import LARGE_TABLE_RAW_SCHEMAS, cast_raw_schema


def polars_dtypes(frame: pl.DataFrame) -> dict[str, str]:
    return {name: str(dtype) for name, dtype in zip(frame.columns, frame.dtypes)}


def read_latin1_csv_batches(
    table: str,
    raw_path: Path,
    partition_rows: int,
    max_rows: int | None = None,
) -> Iterator[pl.DataFrame]:
    """Read one large raw CSV in bounded, schema-cast Latin-1 batches."""
    for chunk in pd.read_csv(
        raw_path,
        encoding="latin1",
        chunksize=partition_rows,
        nrows=max_rows,
        low_memory=False,
    ):
        yield cast_raw_schema(table, pl.from_pandas(chunk))


def parquet_shards(table_dir: Path) -> list[Path]:
    return sorted(table_dir.glob("*.parquet"))


def raw_shards_exist(raw_shards_dir: Path, table: str) -> bool:
    """Return True when the schema-cast raw shard cache exists for a table."""
    return bool(parquet_shards(raw_shards_dir / table))


@dataclass
class RawShardAccumulator:
    """Audit state for one schema-cast raw parquet cache."""

    table: str
    action: str
    rows_read: int = 0
    shard_count: int = 0
    raw_dtypes: dict[str, str] = field(default_factory=dict)
    shard_dtypes: dict[str, str] = field(default_factory=dict)

    def as_summary(self, raw_shards_dir: Path) -> dict[str, Any]:
        return {
            "table": self.table,
            "dataset": str(raw_shards_dir / self.table),
            "action": self.action,
            "rows_read": self.rows_read,
            "shard_count": self.shard_count,
            "raw_dtypes": self.raw_dtypes,
            "shard_dtypes": self.shard_dtypes,
        }


def build_raw_shards_for_table(
    table: str,
    raw_dir: Path,
    raw_shards_dir: Path,
    partition_rows: int,
    max_rows: int | None,
    rebuild: bool,
) -> RawShardAccumulator:
    """Create or reuse source-preserving parquet shards for one large table."""
    if table not in LARGE_TABLE_RAW_SCHEMAS:
        raise ValueError(f"Unsupported large table: {table!r}")

    table_dir = raw_shards_dir / table
    existing = parquet_shards(table_dir)
    if existing and not rebuild:
        accumulator = RawShardAccumulator(table=table, action="reused")
        accumulator.shard_count = len(existing)
        accumulator.shard_dtypes = polars_dtypes(pl.read_parquet(existing[0]))
        return accumulator

    if table_dir.exists():
        shutil.rmtree(table_dir)
    table_dir.mkdir(parents=True, exist_ok=True)

    accumulator = RawShardAccumulator(table=table, action="rebuilt" if existing else "built")
    batches = read_latin1_csv_batches(
        table,
        raw_dir / f"{table}.csv",
        partition_rows,
        max_rows,
    )
    for shard_index, raw in enumerate(batches):
        if raw.is_empty():
            continue
        accumulator.rows_read += raw.height
        if not accumulator.raw_dtypes:
            accumulator.raw_dtypes = polars_dtypes(raw)
            accumulator.shard_dtypes = accumulator.raw_dtypes
        raw.write_parquet(table_dir / f"part-{shard_index:05d}.parquet")
        accumulator.shard_count += 1
    return accumulator


def build_raw_shards_for_tables(
    tables: list[str],
    raw_dir: Path,
    raw_shards_dir: Path,
    partition_rows: int,
    max_rows: int | None,
    rebuild: bool,
) -> dict[str, dict[str, Any]]:
    """Build or reuse raw shard caches for all requested large tables."""
    summaries: dict[str, dict[str, Any]] = {}
    for table in tables:
        accumulator = build_raw_shards_for_table(
            table=table,
            raw_dir=raw_dir,
            raw_shards_dir=raw_shards_dir,
            partition_rows=partition_rows,
            max_rows=max_rows,
            rebuild=rebuild,
        )
        summaries[table] = accumulator.as_summary(raw_shards_dir)
    return summaries


def read_raw_shard_batches(
    table: str,
    raw_shards_dir: Path,
    max_rows: int | None = None,
    admission_ids: set[int] | None = None,
) -> Iterator[pl.DataFrame]:
    """Yield optionally admission-filtered batches from a raw parquet cache."""
    remaining = max_rows
    for shard_path in parquet_shards(raw_shards_dir / table):
        scan = pl.scan_parquet(shard_path)
        if admission_ids is not None:
            scan = scan.filter(pl.col("admissionid").is_in(list(admission_ids)))
        if remaining is not None:
            scan = scan.head(remaining)
        raw = scan.collect(engine="streaming")
        if raw.is_empty():
            continue
        yield raw
        if remaining is not None:
            remaining -= raw.height
            if remaining <= 0:
                break

