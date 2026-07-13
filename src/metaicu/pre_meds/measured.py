"""Pre-MEDS transforms for Amsterdam measured event tables.

Covers numericitems, listitems, and freetextitems — all tables that have a
measuredat column and receive the -1899 sentinel filter.

Each transform function returns (transformed_df, n_excluded_sentinel, n_missing_join).
The caller is responsible for recording rows_read before calling the transform.
"""

from __future__ import annotations

import polars as pl

from metaicu.pre_meds.common import (
    add_measurement_times,
    filter_measuredat_sentinel,
    join_admission_anchors,
)


def transform_numericitems(
    raw: pl.DataFrame,
    anchors: pl.DataFrame,
) -> tuple[pl.DataFrame, int, int]:
    filtered, n_excluded = filter_measuredat_sentinel(raw)
    joined, n_missing = join_admission_anchors(filtered, anchors, "numericitems")
    transformed = add_measurement_times(joined).with_columns(
        # code_prefix mirrors the source_vocab.py token prefix rules.
        pl.when(pl.col("fluidout").is_not_null() & (pl.col("fluidout") != 0))
        .then(pl.lit("SUBJECT_FLUID_OUTPUT"))
        .when(pl.col("islabresult") == 1)
        .then(pl.lit("LAB"))
        .otherwise(pl.lit("MEASUREMENT_BEDSIDE"))
        .alias("code_prefix"),
        pl.when(pl.col("fluidout").is_not_null() & (pl.col("fluidout") != 0))
        .then(pl.lit("fluid_output"))
        .when(pl.col("islabresult") == 1)
        .then(pl.lit("lab_result"))
        .otherwise(pl.lit("bedside_vital_monitor"))
        .alias("numeric_category"),
        pl.lit("AmsterdamUMCdb").alias("source_dataset"),
        pl.lit("numericitems").alias("source_table"),
    )
    return transformed, n_excluded, n_missing


def transform_listitems(
    raw: pl.DataFrame,
    anchors: pl.DataFrame,
) -> tuple[pl.DataFrame, int, int]:
    filtered, n_excluded = filter_measuredat_sentinel(raw)
    joined, n_missing = join_admission_anchors(filtered, anchors, "listitems")
    transformed = add_measurement_times(joined).with_columns(
        pl.lit("AmsterdamUMCdb").alias("source_dataset"),
        pl.lit("listitems").alias("source_table"),
    )
    return transformed, n_excluded, n_missing


def transform_freetextitems(
    raw: pl.DataFrame,
    anchors: pl.DataFrame,
) -> tuple[pl.DataFrame, int, int]:
    filtered, n_excluded = filter_measuredat_sentinel(raw)
    joined, n_missing = join_admission_anchors(filtered, anchors, "freetextitems")
    transformed = add_measurement_times(joined).with_columns(
        pl.lit("AmsterdamUMCdb").alias("source_dataset"),
        pl.lit("freetextitems").alias("source_table"),
    )
    return transformed, n_excluded, n_missing
