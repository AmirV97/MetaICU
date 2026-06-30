"""Chunked CSV reader and partitioned parquet writer for large Amsterdam tables.

Handles numericitems, listitems, and drugitems — tables too large to hold in
memory at once. Reads in 5 M-row latin1 batches via pandas, casts to explicit
Polars schemas, transforms per batch, and writes partitioned parquet datasets.
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

    acc = TableAccumulator(table=table)

    for raw in _read_latin1_csv_batches(table, raw_dir / f"{table}.csv", partition_rows, max_rows):
        if raw.is_empty():
            continue

        if admission_ids is not None:
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
