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


def canonical_column_order(grid_columns, matches_with_derived, encoding_schema, presence_mask_cols,
                           demo_cols, keys=("admissionid", "hour")):
    """Return deterministic physical columns and each manifest tag's actual columns."""
    if len(set(grid_columns)) != len(grid_columns):
        raise ValueError("grid has duplicate column names; refusing to guess an order")
    available = set(grid_columns)
    onehot_by_tag = {}
    for row in encoding_schema or []:
        onehot_by_tag.setdefault(row["feature"], []).append(row)
    onehot_by_tag = {
        tag: [row["column_name"] for row in sorted(rows, key=lambda row: row["position_global"])]
        for tag, rows in onehot_by_tag.items()
    }
    statics = [column for column in demo_cols if column in available]
    claimed = set(keys) | set(statics)
    tag_to_physical, feature_columns = {}, []
    for tag in matches_with_derived:
        columns = [
            column for column in onehot_by_tag.get(tag, [tag])
            if column in available and column not in claimed
        ]
        tag_to_physical[tag] = columns
        feature_columns.extend(columns)
        claimed.update(columns)
    mask_columns = []
    wanted_masks = set(presence_mask_cols)
    for tag in matches_with_derived:
        column = f"{tag}__observed"
        if column in available and column in wanted_masks and column not in claimed:
            mask_columns.append(column)
            claimed.add(column)
    ordered = [column for column in keys if column in available] + statics + feature_columns + mask_columns
    leftovers = sorted(available - set(ordered))
    ordered += leftovers
    if len(ordered) != len(available) or len(set(ordered)) != len(ordered):
        raise ValueError("canonical order is not a permutation of the grid columns")
    return ordered, tag_to_physical
