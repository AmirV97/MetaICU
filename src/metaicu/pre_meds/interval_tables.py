"""Pre-MEDS transforms for Amsterdam interval event tables.

Covers drugitems, processitems, and procedureorderitems — tables that record
start/stop offsets or a registeredat offset rather than measuredat. No -1899
sentinel filter is applied here.

Each transform function returns (transformed_df, n_missing_join).
"""

from __future__ import annotations

import polars as pl

from metaicu.pre_meds.common import (
    add_interval_times,
    join_admission_anchors,
    temporal_phase_expr,
)


def transform_drugitems(
    raw: pl.DataFrame,
    anchors: pl.DataFrame,
) -> tuple[pl.DataFrame, int]:
    joined, n_missing = join_admission_anchors(raw, anchors, "drugitems")
    transformed = add_interval_times(joined).with_columns(
        pl.lit("AmsterdamUMCdb").alias("source_dataset"),
        pl.lit("drugitems").alias("source_table"),
    )
    return transformed, n_missing


def transform_processitems(
    raw: pl.DataFrame,
    anchors: pl.DataFrame,
) -> tuple[pl.DataFrame, int]:
    joined, n_missing = join_admission_anchors(raw, anchors, "processitems")
    transformed = add_interval_times(joined).with_columns(
        pl.lit("AmsterdamUMCdb").alias("source_dataset"),
        pl.lit("processitems").alias("source_table"),
    )
    return transformed, n_missing


def transform_procedureorderitems(
    raw: pl.DataFrame,
    anchors: pl.DataFrame,
) -> tuple[pl.DataFrame, int]:
    # procedureorderitems has registeredat (not start/stop), so time derivation
    # differs from drugitems/processitems.
    joined, n_missing = join_admission_anchors(raw, anchors, "procedureorderitems")
    transformed = joined.with_columns(
        (pl.col("registeredat") - pl.col("admittedat")).alias("admission_relative_ms"),
        temporal_phase_expr("registeredat"),
    ).with_columns(
        (
            pl.col("admittedattime")
            + pl.duration(milliseconds=pl.col("admission_relative_ms"))
        ).alias("registeredattime"),
        pl.lit("AmsterdamUMCdb").alias("source_dataset"),
        pl.lit("procedureorderitems").alias("source_table"),
    )
    return transformed, n_missing
