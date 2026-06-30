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
    ADMISSION_ANCHOR_COLUMNS,
    LARGE_TABLE_RAW_SCHEMAS,
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
) -> TableAccumulator:
    """Read, transform, and write one large table as a partitioned parquet dataset.

    When admission_ids is supplied (bounded mode), each batch is pre-filtered
    to the selected admissions before joining and transforming.
    """
    if table not in LARGE_TABLE_RAW_SCHEMAS:
        raise ValueError(f"Unsupported large table: {table!r}")

    # Anchors for bounded mode contain only the selected admissions; for full
    # mode they contain all admissions. Either way, pass them as-is.
    bounded_anchors = anchors.select(ADMISSION_ANCHOR_COLUMNS)

    table_dir = _prepare_output_dir(output_dir, table, overwrite)
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

    return acc
