"""Numericitems → quantile-coded MEDS events.

Prefers pre-MEDS ``numericitems_binned`` when present, otherwise falls back
to raw ``numericitems``. Joins numeric rows to the vocab by (itemid, unitid), applies
temporal phase filtering, and assigns Q1-Q10 quantile bins per
source_token/unit using the current run's data.

Train-split note: this port fits quantile boundaries on the supplied cohort
(bounded sample for QC, full run for production). Freezing boundaries on
the train split and reusing for val/test/inference is a hard requirement
before final tokenization — implement as a separate fit/apply step.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import polars as pl

from aumc_pipeline.meds.common import (
    coerce_debug_frame,
    empty_debug_frame,
    record_join_exclusions,
    runtime_phase_expr,
)
from aumc_pipeline.meds.vocab import table_vocab
from aumc_pipeline.utils.parquet_datasets import parquet_exists, resolve_table_parquet, scan_parquet


def quantile_code_numeric(
    df: pl.DataFrame,
    bins: int = 10,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Assign Q1-Q{bins} bin codes per (source_token, unit) using finite values.

    Returns (events_df with quantile_bin column, boundaries_df in long form).
    Rows where value is null or non-finite are dropped before binning.

    Bin assignment: Q1 = lowest decile, Q10 = highest. A value exactly at
    the q1 boundary falls in Q2 (bin is 1 + count of boundaries exceeded).
    """
    if df.is_empty():
        return pl.DataFrame(), pl.DataFrame()

    unit_key = "_unit_quantile_key"
    group_cols = ["source_token", unit_key, "harmonized_token"]
    q_cols = [f"q{q}" for q in range(1, bins)]
    aggs = [pl.len().alias("source_rows")] + [
        pl.col("value_num").quantile(q / bins, interpolation="nearest").alias(f"q{q}")
        for q in range(1, bins)
    ]

    numeric = df.with_columns([
        pl.col("value").cast(pl.Float64, strict=False).alias("value_num"),
        pl.col("source_unit").cast(pl.String).fill_null("<NULL>").alias(unit_key),
    ]).filter(pl.col("value_num").is_finite())

    if numeric.is_empty():
        return pl.DataFrame(), pl.DataFrame()

    bounds_wide = numeric.group_by(group_cols).agg(aggs)
    events = numeric.join(bounds_wide, on=group_cols, how="left")

    bin_expr = pl.lit(1)
    for col_name in q_cols:
        bin_expr = bin_expr + (pl.col("value_num") > pl.col(col_name)).cast(pl.Int64)
    events = events.with_columns(bin_expr.alias("quantile_bin")).drop(q_cols + ["source_rows", unit_key])

    boundary_frames = [
        bounds_wide.select([
            pl.col("source_token"),
            pl.when(pl.col(unit_key) == "<NULL>")
            .then(pl.lit(None).cast(pl.String))
            .otherwise(pl.col(unit_key))
            .alias("source_unit"),
            pl.col("harmonized_token"),
            pl.lit(q / bins).alias("quantile"),
            pl.col(f"q{q}").alias("boundary_value"),
            pl.col("source_rows"),
        ])
        for q in range(1, bins)
    ]
    boundaries = pl.concat(boundary_frames, how="vertical_relaxed") if boundary_frames else pl.DataFrame()
    return events, boundaries


def numeric_events(
    admission_ids: Sequence[int],
    pre_meds_dir: Path,
    vocab: pl.DataFrame,
    include_phases: Sequence[str],
    bins: int,
    audit_dir: Path,
    max_rows: int | None = None,
) -> tuple[pl.DataFrame, list[dict]]:
    """Join numericitems to vocab, quantile-code values, return MEDS events + exclusion records.

    Data shape:
      in:  numericitems parquet — one row per measurement (itemid, unitid, value, measuredattime, ...)
      out: debug frame — one row per emitted quantile event; code = harmonized_token//Q{bin}
    Rows dropped: unmatched vocab join, non-emitted (_emit=False), out-of-phase, non-finite value.
    """
    numeric_path = resolve_table_parquet(pre_meds_dir, "numericitems_binned")
    if not parquet_exists(numeric_path):
        numeric_path = resolve_table_parquet(pre_meds_dir, "numericitems")
    if not parquet_exists(numeric_path):
        return empty_debug_frame(), []

    tv = table_vocab(vocab, "numericitems", {"_itemid_i64": "itemid", "_unitid_i64": "unitid"})

    scan = scan_parquet(numeric_path).filter(pl.col("admissionid").is_in(list(admission_ids)))
    if max_rows is not None:
        scan = scan.limit(max_rows)
    raw = (
        scan
        .join(tv.lazy(), on=["itemid", "unitid"], how="left")
        .with_columns(runtime_phase_expr("admission_relative_ms").alias("temporal_phase"))
        .collect(engine="streaming")
    )

    exclusions = record_join_exclusions("numericitems", raw, list(include_phases))
    emitted = raw.filter(pl.col("_emit") & pl.col("temporal_phase").is_in(list(include_phases)))
    if emitted.is_empty():
        return empty_debug_frame(), exclusions

    events, boundaries = quantile_code_numeric(emitted, bins=bins)
    dropped = emitted.height - events.height
    if dropped > 0:
        exclusions.append({
            "source_table": "numericitems",
            "exclusion_reason": "numeric_value_missing_or_nonfinite",
            "row_count": int(dropped),
        })

    if not boundaries.is_empty():
        audit_dir.mkdir(parents=True, exist_ok=True)
        boundaries.write_csv(audit_dir / "meds_numeric_quantile_boundaries.csv")
        (
            events.group_by(["source_token", "quantile_bin"])
            .len(name="event_count")
            .sort(["source_token", "quantile_bin"])
            .write_csv(audit_dir / "meds_numeric_quantile_assignments.csv")
        )

    binning_method_expr = (
        pl.col("binning_method").cast(pl.String).fill_null("raw")
        if "binning_method" in events.columns
        else pl.lit("raw")
    )
    raw_rows_expr = (
        pl.col("raw_rows_in_bin").cast(pl.Int64).fill_null(1)
        if "raw_rows_in_bin" in events.columns
        else pl.lit(1).cast(pl.Int64)
    )

    return coerce_debug_frame(
        events.with_columns([
            pl.col("measuredattime").alias("time"),
            (pl.col("harmonized_token") + pl.lit("//Q") + pl.col("quantile_bin").cast(pl.String)).alias("code"),
            pl.lit(None).cast(pl.Float64).alias("numeric_value"),
            pl.col("value").cast(pl.Float64, strict=False).alias("raw_numeric_value"),
            pl.col("comment").cast(pl.String).alias("text_value"),
            pl.lit("numericitems").alias("source_table"),
            pl.col("item").cast(pl.String).alias("source_label"),
            pl.col("unit").cast(pl.String).alias("source_unit"),
            binning_method_expr.alias("binning_method"),
            raw_rows_expr.alias("raw_rows_in_bin"),
        ])
    ), exclusions
