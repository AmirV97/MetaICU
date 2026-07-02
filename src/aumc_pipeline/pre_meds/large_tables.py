"""Chunked readers and partitioned parquet writers for large Amsterdam tables.

Handles numericitems, listitems, and drugitems — tables too large to hold in
memory at once. The first run can cache schema-cast raw CSV chunks as parquet
shards; later pre-MEDS runs transform those shards instead of rescanning raw CSV.
"""

from __future__ import annotations

import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import polars as pl

from aumc_pipeline.pre_meds.common import (
    LARGE_TABLE_RAW_SCHEMAS,
    admission_anchor_columns,
    cast_raw_schema,
    interval_time_anomalies,
    measurement_time_anomalies,
    temporal_phase_counts,
)
from aumc_pipeline.pre_meds.interval_tables import transform_drugitems
from aumc_pipeline.pre_meds.measured import transform_listitems, transform_numericitems


@dataclass
class TableAccumulator:
    """Incremental audit state for one large-table extraction."""

    table: str
    input_mode: str = "raw_csv_chunks"
    rows_read: int = 0
    rows_excluded_sentinel: int = 0
    rows_emitted: int = 0
    missing_join_rows: int = 0
    partition_count: int = 0
    split_partition_counts: Counter = field(default_factory=Counter)
    split_rows_emitted: Counter = field(default_factory=Counter)
    raw_dtypes: dict[str, str] = field(default_factory=dict)
    output_dtypes: dict[str, str] = field(default_factory=dict)
    anomaly_counts: Counter = field(default_factory=Counter)
    phase_counts: Counter = field(default_factory=Counter)

    def as_summary(self, output_dir: Path, max_rows: int | None) -> dict[str, Any]:
        return {
            "table": self.table,
            "output_dataset": str(output_dir / self.table),
            "input_mode": self.input_mode,
            "max_rows": max_rows,
            "partition_count": self.partition_count,
            "split_partition_counts": dict(self.split_partition_counts),
            "split_rows_emitted": dict(self.split_rows_emitted),
            "raw_dtypes": self.raw_dtypes,
            "output_dtypes": self.output_dtypes,
            "row_counts": {
                "rows_read": self.rows_read,
                "rows_excluded_measuredat_minus_1899": self.rows_excluded_sentinel,
                "rows_after_exclusions": self.rows_read - self.rows_excluded_sentinel,
                "rows_emitted": self.rows_emitted,
                "missing_admission_join_rows": self.missing_join_rows,
            },
            "time_anomalies": dict(self.anomaly_counts),
            "temporal_phase_counts": dict(self.phase_counts),
        }


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


def _polars_dtypes(df: pl.DataFrame) -> dict[str, str]:
    return {name: str(dtype) for name, dtype in zip(df.columns, df.dtypes)}


def _read_latin1_csv_batches(
    table: str,
    raw_path: Path,
    partition_rows: int,
    max_rows: int | None,
) -> Iterator[pl.DataFrame]:
    for chunk in pd.read_csv(
        raw_path,
        encoding="latin1",
        chunksize=partition_rows,
        nrows=max_rows,
        low_memory=False,
    ):
        yield cast_raw_schema(table, pl.from_pandas(chunk))


def _parquet_shards(table_dir: Path) -> list[Path]:
    return sorted(table_dir.glob("*.parquet"))


def raw_shards_exist(raw_shards_dir: Path, table: str) -> bool:
    """Return True when the schema-cast raw shard cache exists for a table."""
    return bool(_parquet_shards(raw_shards_dir / table))


def build_raw_shards_for_table(
    table: str,
    raw_dir: Path,
    raw_shards_dir: Path,
    partition_rows: int,
    max_rows: int | None,
    rebuild: bool,
) -> RawShardAccumulator:
    """Create or reuse schema-cast raw parquet shards for a large Amsterdam table.

    This is intentionally source-preserving: no patient filtering, no sentinel
    drops, no time derivation, and no vocabulary logic are applied here.
    """
    if table not in LARGE_TABLE_RAW_SCHEMAS:
        raise ValueError(f"Unsupported large table: {table!r}")

    table_dir = raw_shards_dir / table
    existing = _parquet_shards(table_dir)
    if existing and not rebuild:
        acc = RawShardAccumulator(table=table, action="reused")
        acc.shard_count = len(existing)
        first = pl.read_parquet(existing[0])
        acc.shard_dtypes = _polars_dtypes(first)
        return acc

    if table_dir.exists():
        shutil.rmtree(table_dir)
    table_dir.mkdir(parents=True, exist_ok=True)

    acc = RawShardAccumulator(table=table, action="rebuilt" if existing else "built")
    for shard_idx, raw in enumerate(
        _read_latin1_csv_batches(table, raw_dir / f"{table}.csv", partition_rows, max_rows)
    ):
        if raw.is_empty():
            continue
        acc.rows_read += raw.height
        if not acc.raw_dtypes:
            acc.raw_dtypes = _polars_dtypes(raw)
            acc.shard_dtypes = acc.raw_dtypes
        raw.write_parquet(table_dir / f"part-{shard_idx:05d}.parquet")
        acc.shard_count += 1

    return acc


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
        acc = build_raw_shards_for_table(
            table=table,
            raw_dir=raw_dir,
            raw_shards_dir=raw_shards_dir,
            partition_rows=partition_rows,
            max_rows=max_rows,
            rebuild=rebuild,
        )
        summaries[table] = acc.as_summary(raw_shards_dir)
    return summaries


def _read_raw_shard_batches(
    table: str,
    raw_shards_dir: Path,
    max_rows: int | None,
    admission_ids: set[int] | None,
) -> Iterator[pl.DataFrame]:
    remaining = max_rows
    for shard_path in _parquet_shards(raw_shards_dir / table):
        scan = pl.scan_parquet(shard_path)
        if admission_ids is not None:
            scan = scan.filter(pl.col("admissionid").is_in(list(admission_ids)))
        if remaining is not None:
            scan = scan.head(remaining)
        raw = scan.collect()
        if raw.is_empty():
            continue
        yield raw
        if remaining is not None:
            remaining -= raw.height
            if remaining <= 0:
                break


def _prepare_output_dir(output_dir: Path, table: str, overwrite: bool) -> Path:
    table_dir = output_dir / table
    if table_dir.exists() and any(table_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"{table_dir} already contains files. "
                "Set run.overwrite=true to replace."
            )
        shutil.rmtree(table_dir)
    table_dir.mkdir(parents=True, exist_ok=True)
    return table_dir


def _accumulate_anomalies(
    table: str,
    transformed: pl.DataFrame,
    acc: TableAccumulator,
) -> None:
    if table in {"numericitems", "listitems"}:
        acc.anomaly_counts.update(measurement_time_anomalies(transformed))
    else:
        acc.anomaly_counts.update(interval_time_anomalies(transformed))
    acc.phase_counts.update(temporal_phase_counts(transformed))


def transform_table(
    table: str,
    raw_dir: Path,
    output_dir: Path,
    anchors: pl.DataFrame,
    partition_rows: int,
    max_rows: int | None,
    overwrite: bool,
    admission_ids: set[int] | None = None,
    split_values: list[str] | None = None,
    raw_shards_dir: Path | None = None,
) -> TableAccumulator:
    """Read, transform, and write one large table as a partitioned parquet dataset.

    When admission_ids is supplied (bounded mode), each batch is pre-filtered
    to the selected admissions before joining and transforming.
    """
    if table not in LARGE_TABLE_RAW_SCHEMAS:
        raise ValueError(f"Unsupported large table: {table!r}")

    # Anchors for bounded mode contain only the selected admissions; for full
    # mode they contain all admissions. Split-aware runs carry the split label
    # through the admission join when present.
    bounded_anchors = anchors.select(admission_anchor_columns(anchors))

    table_dir = _prepare_output_dir(output_dir, table, overwrite)
    split_dirs: dict[str, Path] = {}
    if split_values:
        for split in split_values:
            split_dirs[split] = _prepare_output_dir(output_dir / split, table, overwrite)

    use_raw_shards = raw_shards_dir is not None and raw_shards_exist(raw_shards_dir, table)
    input_mode = "raw_parquet_shards" if use_raw_shards else "raw_csv_chunks"
    acc = TableAccumulator(table=table, input_mode=input_mode)

    if use_raw_shards:
        raw_batches = _read_raw_shard_batches(table, raw_shards_dir, max_rows, admission_ids)
    else:
        raw_batches = _read_latin1_csv_batches(table, raw_dir / f"{table}.csv", partition_rows, max_rows)

    for raw in raw_batches:
        if raw.is_empty():
            continue

        if admission_ids is not None and not use_raw_shards:
            raw = raw.filter(pl.col("admissionid").is_in(list(admission_ids)))
        if raw.is_empty():
            continue

        acc.rows_read += raw.height
        if not acc.raw_dtypes:
            acc.raw_dtypes = _polars_dtypes(raw)

        if table == "numericitems":
            transformed, n_excl, n_miss = transform_numericitems(raw, bounded_anchors)
        elif table == "listitems":
            transformed, n_excl, n_miss = transform_listitems(raw, bounded_anchors)
        else:
            transformed, n_miss = transform_drugitems(raw, bounded_anchors)
            n_excl = 0

        acc.rows_excluded_sentinel += n_excl
        acc.rows_emitted += transformed.height
        acc.missing_join_rows += n_miss

        if not acc.output_dtypes:
            acc.output_dtypes = _polars_dtypes(transformed)

        _accumulate_anomalies(table, transformed, acc)

        part_path = table_dir / f"part-{acc.partition_count:05d}.parquet"
        transformed.write_parquet(part_path)
        acc.partition_count += 1

        if split_dirs and "split" in transformed.columns:
            for split, split_dir in split_dirs.items():
                split_part = transformed.filter(pl.col("split") == split)
                if split_part.is_empty():
                    continue
                split_part_path = split_dir / f"part-{acc.split_partition_counts[split]:05d}.parquet"
                split_part.write_parquet(split_part_path)
                acc.split_partition_counts[split] += 1
                acc.split_rows_emitted[split] += split_part.height

    return acc
