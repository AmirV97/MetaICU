"""Causal mean-binning for high-frequency Amsterdam numeric pre-MEDS rows.

The transform is reusable, but it is orchestrated by the pre-MEDS workflow.
It reads a frozen train-derived high-frequency inventory and writes a derived
``numericitems_binned`` parquet dataset without modifying raw ``numericitems``.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import polars as pl

from metaicu.aumcdb.common.parquet import parquet_exists, scan_parquet

BINNING_PROVENANCE_COLUMNS = [
    "bin_start_ms",
    "bin_end_ms",
    "raw_rows_in_bin",
    "bin_window_minutes",
    "binning_method",
]


def _unique_preserving_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def percent_reduction(before: int, after: int) -> float | None:
    if before == 0:
        return None
    return round(100.0 * (1.0 - after / before), 6)


def _partition_sink(root: Path, key: str) -> Any:
    """Return the partitioned Parquet sink used by the installed Polars."""
    if hasattr(pl, "PartitionBy"):
        return pl.PartitionBy(root, key=key, include_key=False)
    return pl.PartitionByKey(root, by=key, include_key=False)


@dataclass(frozen=True)
class CausalMeanBinningConfig:
    """Configuration for one numericitems causal mean-binning run."""

    input_path: Path
    output_path: Path
    inventory_path: Path
    summary_path: Path
    split_name: str | None = None
    signal_column: str = "itemid"
    time_column: str = "admission_relative_ms"
    value_column: str = "value"
    grouping_columns: Sequence[str] = field(
        default_factory=lambda: ("patientid", "subject_id", "hadm_id", "stay_id", "admissionid", "itemid")
    )
    metadata_columns: Sequence[str] = field(
        default_factory=lambda: (
            "item",
            "tag",
            "unitid",
            "unit",
            "islabresult",
            "fluidout",
            "code_prefix",
            "numeric_category",
            "admittedat",
            "dischargedat",
            "admittedattime",
            "dischargedattime",
            "source_dataset",
            "source_table",
            "split",
        )
    )
    null_on_binned_columns: Sequence[str] = field(
        default_factory=lambda: (
            "comment",
            "registeredat",
            "registeredby",
            "updatedat",
            "updatedby",
            "registered_admission_relative_ms",
            "updated_admission_relative_ms",
            "registeredattime",
            "updatedattime",
        )
    )
    window_minutes: int = 60
    partition_column: str = "admissionid"
    partition_count: int = 64
    overwrite: bool = False


@dataclass(frozen=True)
class CausalMeanBinningResult:
    """Paths and row-count summary for one binning run."""

    output_path: Path
    summary_path: Path
    summary: dict[str, Any]


class CausalMeanBinningTransform:
    """Replace high-frequency numeric rows with causal mean windows.

    Windowing is causal because each emitted row at ``bin_end`` summarizes only
    raw rows in ``[bin_start, bin_end)``. If a window has no raw rows, no row is
    emitted.
    """

    def __init__(self, config: CausalMeanBinningConfig):
        self.config = config

    @property
    def window_ms(self) -> int:
        return int(self.config.window_minutes * 60 * 1000)

    def run(self) -> CausalMeanBinningResult:
        start = time.perf_counter()
        cfg = self.config
        if cfg.window_minutes <= 0:
            raise ValueError("window_minutes must be > 0")
        if cfg.partition_count <= 0:
            raise ValueError("partition_count must be > 0")
        if not parquet_exists(cfg.input_path):
            raise FileNotFoundError(f"Missing numericitems input for binning: {cfg.input_path}")
        if not cfg.inventory_path.is_file():
            raise FileNotFoundError(f"Missing high-frequency inventory: {cfg.inventory_path}")

        inventory = pl.read_csv(cfg.inventory_path, infer_schema_length=10000)
        if cfg.signal_column not in inventory.columns or "is_high_resolution" not in inventory.columns:
            raise ValueError(
                f"Inventory must contain {cfg.signal_column!r} and 'is_high_resolution' columns"
            )
        highres_ids = (
            inventory.filter(pl.col("is_high_resolution").cast(pl.Boolean, strict=False).fill_null(False))
            .select(pl.col(cfg.signal_column).cast(pl.Int64, strict=False))
            .drop_nulls()
            .to_series()
            .to_list()
        )

        input_schema = self._scan_input().collect_schema()
        input_columns = list(input_schema.names())
        raw_rows = self._row_count(self._scan_input())
        highres_raw_rows = self._row_count(
            self._scan_input().filter(pl.col(cfg.signal_column).is_in(highres_ids))
        ) if highres_ids else 0

        bucket_root = self._write_input_buckets()
        self._prepare_output_path()
        try:
            bucket_files = sorted(bucket_root.rglob("*.parquet"))
            for part_index, bucket_file in enumerate(bucket_files):
                source = pl.scan_parquet(bucket_file)
                if highres_ids:
                    dense = self._binned_dense_frame(
                        source, highres_ids, input_columns
                    )
                    passthrough = self._raw_passthrough_frame(
                        source, highres_ids, input_columns
                    )
                    output = pl.concat(
                        [dense, passthrough], how="vertical_relaxed"
                    )
                else:
                    output = self._raw_passthrough_frame(
                        source, highres_ids, input_columns
                    )
                output = output.select(
                    input_columns + BINNING_PROVENANCE_COLUMNS
                )
                self._write_output_part(output, part_index)
        finally:
            shutil.rmtree(bucket_root, ignore_errors=True)

        written = scan_parquet(cfg.output_path)
        output_rows = self._row_count(written)
        binned_rows = self._lazyframe_count(
            written, pl.col("binning_method") == "causal_mean"
        )
        passthrough_rows = self._lazyframe_count(
            written, pl.col("binning_method") == "raw_passthrough"
        )
        summary = {
            "split": cfg.split_name,
            "input_path": str(cfg.input_path),
            "output_path": str(cfg.output_path),
            "inventory_path": str(cfg.inventory_path),
            "window_minutes": cfg.window_minutes,
            "partition_count": cfg.partition_count,
            "raw_rows": raw_rows,
            "output_rows": output_rows,
            "high_resolution_signal_count": len(highres_ids),
            "high_resolution_raw_rows": highres_raw_rows,
            "high_resolution_binned_rows": binned_rows,
            "raw_passthrough_rows": passthrough_rows,
            "total_reduction_pct": percent_reduction(raw_rows, output_rows),
            "high_resolution_reduction_pct": percent_reduction(highres_raw_rows, binned_rows),
            "elapsed_seconds": round(time.perf_counter() - start, 1),
        }
        cfg.summary_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=_json_default) + "\n")
        return CausalMeanBinningResult(cfg.output_path, cfg.summary_path, summary)

    def _scan_input(self) -> pl.LazyFrame:
        return scan_parquet(self.config.input_path)

    @staticmethod
    def _row_count(frame: pl.LazyFrame) -> int:
        return int(frame.select(pl.len().alias("n")).collect(engine="streaming")["n"][0])

    @staticmethod
    def _lazyframe_count(frame: pl.LazyFrame, predicate: pl.Expr) -> int:
        return int(
            frame.filter(predicate)
            .select(pl.len().alias("n"))
            .collect(engine="streaming")["n"][0]
        )

    def _binned_dense_frame(
        self,
        source: pl.LazyFrame,
        highres_ids: list[Any],
        input_columns: list[str],
    ) -> pl.LazyFrame:
        cfg = self.config
        group_cols = [col for col in _unique_preserving_order(list(cfg.grouping_columns)) if col in input_columns]
        if cfg.signal_column not in group_cols:
            group_cols.append(cfg.signal_column)
        metadata_cols = [
            col
            for col in _unique_preserving_order(list(cfg.metadata_columns))
            if col in input_columns and col not in group_cols and col != cfg.value_column
        ]

        dense = (
            source
            .filter(pl.col(cfg.signal_column).is_in(highres_ids))
            .filter(pl.col(cfg.time_column).is_not_null())
            .filter(pl.col(cfg.value_column).is_not_null())
            .with_columns(
                ((pl.col(cfg.time_column).cast(pl.Int64) // self.window_ms) * self.window_ms).alias("bin_start_ms")
            )
            .with_columns((pl.col("bin_start_ms") + self.window_ms).alias("bin_end_ms"))
            .group_by(group_cols + ["bin_start_ms", "bin_end_ms"])
            .agg(
                [
                    pl.col(cfg.value_column).cast(pl.Float64).mean().alias(cfg.value_column),
                    pl.len().alias("raw_rows_in_bin"),
                ]
                + [pl.col(col).drop_nulls().first().alias(col) for col in metadata_cols]
            )
            .with_columns(
                [
                    pl.col("bin_end_ms").cast(pl.Int64).alias(cfg.time_column),
                    pl.lit(cfg.window_minutes).alias("bin_window_minutes"),
                    pl.lit("causal_mean").alias("binning_method"),
                ]
            )
        )
        dense = self._recompute_measurement_times(dense)
        return self._align_to_input_schema(dense, input_columns)

    def _raw_passthrough_frame(
        self,
        source: pl.LazyFrame,
        highres_ids: list[Any],
        input_columns: list[str],
    ) -> pl.LazyFrame:
        cfg = self.config
        raw = source
        if highres_ids:
            raw = raw.filter(~pl.col(cfg.signal_column).is_in(highres_ids))
        raw = raw.with_columns(
            [
                pl.lit(None).cast(pl.Int64).alias("bin_start_ms"),
                pl.lit(None).cast(pl.Int64).alias("bin_end_ms"),
                pl.lit(1).cast(pl.Int64).alias("raw_rows_in_bin"),
                pl.lit(cfg.window_minutes).cast(pl.Int64).alias("bin_window_minutes"),
                pl.lit("raw_passthrough").alias("binning_method"),
            ]
        )
        return raw.select(input_columns + BINNING_PROVENANCE_COLUMNS)

    def _recompute_measurement_times(self, dense: pl.LazyFrame) -> pl.LazyFrame:
        columns = dense.collect_schema().names()
        out = dense
        if "admittedat" in columns:
            out = out.with_columns((pl.col("admittedat").cast(pl.Int64) + pl.col("bin_end_ms")).alias("measuredat"))
        if "admittedattime" in columns:
            out = out.with_columns(
                (pl.col("admittedattime") + pl.duration(milliseconds=pl.col("bin_end_ms"))).alias("measuredattime")
            )
        if all(col in columns for col in ["admittedat", "dischargedat"]):
            out = out.with_columns(
                pl.when(pl.col("measuredat").is_null() | pl.col("admittedat").is_null() | pl.col("dischargedat").is_null())
                .then(pl.lit("unknown"))
                .when(pl.col("measuredat") < pl.col("admittedat"))
                .then(pl.lit("preadmission"))
                .when(pl.col("measuredat") > pl.col("dischargedat"))
                .then(pl.lit("postadmission"))
                .otherwise(pl.lit("admission"))
                .alias("event_temporal_phase")
            )
        for column in self.config.null_on_binned_columns:
            if column in columns:
                out = out.with_columns(pl.lit(None).alias(column))
        return out

    @staticmethod
    def _align_to_input_schema(frame: pl.LazyFrame, input_columns: list[str]) -> pl.LazyFrame:
        columns = frame.collect_schema().names()
        for column in input_columns:
            if column not in columns:
                frame = frame.with_columns(pl.lit(None).alias(column))
        for column in BINNING_PROVENANCE_COLUMNS:
            if column not in columns:
                frame = frame.with_columns(pl.lit(None).alias(column))
        return frame.select(input_columns + BINNING_PROVENANCE_COLUMNS)

    def _write_input_buckets(self) -> Path:
        cfg = self.config
        schema = self._scan_input().collect_schema()
        if cfg.partition_column not in schema:
            raise ValueError(
                f"Missing binning partition column: {cfg.partition_column}"
            )
        bucket_root = cfg.output_path.with_name(
            f"{cfg.output_path.name}.__tmp_binning_buckets"
        )
        if bucket_root.exists():
            shutil.rmtree(bucket_root)
        bucket_expr = (
            pl.col(cfg.partition_column)
            .cast(pl.Int64)
            .mod(cfg.partition_count)
            .alias("_bin_bucket")
        )
        self._scan_input().with_columns(bucket_expr).sink_parquet(
            _partition_sink(bucket_root, "_bin_bucket"),
            mkdir=True,
            engine="streaming",
        )
        return bucket_root

    def _prepare_output_path(self) -> None:
        path = self.config.output_path
        if path.exists():
            if not self.config.overwrite:
                raise FileExistsError(
                    f"Binned numeric output already exists: {path}"
                )
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        if path.suffix == ".parquet":
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)

    def _write_output_part(
        self, output: pl.LazyFrame, part_index: int
    ) -> None:
        path = self.config.output_path
        if path.suffix == ".parquet":
            if part_index > 0:
                raise ValueError(
                    "File output supports only partition_count=1; use a directory"
                )
            output.sink_parquet(path, mkdir=True, engine="streaming")
        else:
            output.sink_parquet(
                path / f"part-{part_index:05d}.parquet",
                mkdir=True,
                engine="streaming",
            )
