"""Source-preserving UTF-8 gzip-CSV to parquet sharding for large MIMIC-IV tables. Mirrors
metaicu.aumcdb.common.raw_shards's role; differs only where MIMIC's own source files differ --
UTF-8 (not Latin-1, which polars' CSV reader cannot decode natively -- aumcdb's own raw_shards.py
stays on pandas for that reason), gzip-compressed .csv.gz (not plain .csv; polars' native reader
decompresses .csv.gz directly, no separate zcat/gzip step needed)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import polars as pl

from metaicu.mimiciv.common.raw_schema import LARGE_TABLE_RAW_SCHEMAS, cast_raw_schema


def polars_dtypes(frame: pl.DataFrame) -> dict[str, str]:
    return {name: str(dtype) for name, dtype in zip(frame.columns, frame.dtypes)}


def read_gzip_csv_batches(
    table: str,
    raw_path: Path,
    partition_rows: int,
    max_rows: int | None = None,
) -> Iterator[pl.DataFrame]:
    """Read one large raw .csv.gz in bounded, schema-cast batches, natively via polars (multi-
    threaded Rust CSV parser + built-in gzip decompression) -- no pandas round-trip.

    schema_overrides={every column: pl.String}: reads every column as a plain string, deferring
    all real type conversion (including "None"/"NA"/"NULL" string-vs-null handling) to
    cast_raw_schema's own explicit per-column .cast(...)/.str.to_datetime(...) calls -- the exact
    same division of labor the pandas version used (pandas' keep_default_na=False + na_values=[""]
    was itself only there to match polars' own default null semantics: only a genuinely empty
    field is null, e.g. chartevents' literal string "None" meaning "no O2 delivery device" must
    survive as data, not become null). null_values="": explicit for clarity, since a missing
    schema_overrides entry (a raw column not in LARGE_TABLE_RAW_SCHEMAS) would otherwise fall back
    to polars' own type inference on that column."""
    schema_overrides = {column: pl.String for column in LARGE_TABLE_RAW_SCHEMAS[table]}
    reader = pl.read_csv_batched(
        raw_path,
        schema_overrides=schema_overrides,
        null_values="",
        batch_size=partition_rows,
    )
    rows_read = 0
    while max_rows is None or rows_read < max_rows:
        batches = reader.next_batches(1)
        if not batches:
            break
        chunk = batches[0]
        if max_rows is not None and rows_read + chunk.height > max_rows:
            chunk = chunk.head(max_rows - rows_read)
        rows_read += chunk.height
        yield cast_raw_schema(table, chunk)


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
    raw_data_dir: Path,
    table_file: str,
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
    batches = read_gzip_csv_batches(table, raw_data_dir / table_file, partition_rows, max_rows)
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
    tables: dict[str, str],
    raw_data_dir: Path,
    raw_shards_dir: Path,
    partition_rows: int,
    max_rows: int | None,
    rebuild: bool,
) -> dict[str, dict[str, Any]]:
    """Build or reuse raw shard caches for all requested large tables. tables: table name ->
    table_file (relative path under raw_data_dir, e.g. "icu/chartevents.csv.gz")."""
    summaries: dict[str, dict[str, Any]] = {}
    for table, table_file in tables.items():
        accumulator = build_raw_shards_for_table(
            table=table,
            raw_data_dir=raw_data_dir,
            table_file=table_file,
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
            scan = scan.filter(pl.col("stay_id").is_in(list(admission_ids)))
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
