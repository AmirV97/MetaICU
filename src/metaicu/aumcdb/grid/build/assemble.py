"""
Combines the long-format outputs from grid.extract_numeric/extract_indicator/extract_rate
into one dense per-admission-hour wide grid: every integer hour in [0, ceil(los_hours)) for
every admission gets a row, with one column per resolved feature tag. Per
icarefm_preprocessing_reference.md's A.4.1 ("No imputation is performed at this stage, time
bins without any data remain empty"), this stage deliberately leaves un-measured feature-
hours as null -- imputation (forward-fill vs zero-fill, per A.4.3) is grid.impute's job, kept
separate so this stage's contract stays simple: "what was actually recorded, hour by hour."

Known v1 scaling limitation: builds the whole wide grid in memory as one polars DataFrame.
Fine at the 1000-admission bounded-test scale this pass targets; a full ~23k-admission run
would want batching by admission range -- a natural place to add it later without changing
this function's per-batch logic, not a reason to add that complexity now.
"""
import logging

import polars as pl

log = logging.getLogger(__name__)


def _dense_admission_hour_skeleton(admissions):
    """admissions: DataFrame with (admissionid, true_los_hours). One row per integer hour in
    [0, ceil(los_hours)) per admission."""
    return admissions.select(
        "admissionid",
        pl.int_ranges(0, pl.col("true_los_hours").ceil().cast(pl.Int64)).alias("hour"),
    ).explode("hour")


def assemble_grid(admissions, numeric_long, categorical_long, indicator_on_hours, rate_long):
    """admissions: (admissionid, true_los_hours) DataFrame, from grid.sampling.load_valid_admissions
    (already restricted to the admissions in scope for this run). The four *_long/on_hours
    args are whatever grid.extract_* returned (each may be None if that reconstruction type
    had no in-scope matches). Returns one wide (admissionid, hour, <every tag>) DataFrame."""
    skeleton = _dense_admission_hour_skeleton(admissions)
    log.info(f"dense skeleton: {skeleton.height} (admissionid,hour) rows across {admissions.height} admissions")

    grid = skeleton
    if numeric_long is not None:
        wide = numeric_long.pivot(index=["admissionid", "hour"], on="tag", values="agg_value")
        grid = grid.join(wide, on=["admissionid", "hour"], how="left")
        log.info(f"joined numeric: +{wide.width - 2} columns")

    if categorical_long is not None:
        wide = categorical_long.pivot(index=["admissionid", "hour"], on="tag", values="agg_label")
        grid = grid.join(wide, on=["admissionid", "hour"], how="left")
        log.info(f"joined categorical: +{wide.width - 2} columns")

    if indicator_on_hours is not None:
        wide = indicator_on_hours.with_columns(pl.lit(1).alias("_on")).pivot(
            index=["admissionid", "hour"], on="tag", values="_on"
        )
        grid = grid.join(wide, on=["admissionid", "hour"], how="left")
        log.info(f"joined treatment_indicator: +{wide.width - 2} columns")

    if rate_long is not None:
        wide = rate_long.pivot(index=["admissionid", "hour"], on="tag", values="agg_value")
        grid = grid.join(wide, on=["admissionid", "hour"], how="left")
        log.info(f"joined treatment_rate: +{wide.width - 2} columns")

    log.info(f"assembled grid: {grid.height} rows x {grid.width} columns")
    return grid
