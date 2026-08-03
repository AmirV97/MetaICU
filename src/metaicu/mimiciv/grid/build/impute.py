"""
Imputation per icarefm_preprocessing_reference.md's A.4.3, applied to the dense grid from
grid.assemble: direct_numeric/derived_output_rate/categorical are forward-filled indefinitely
within each admission (never across admissions); treatment_indicator/treatment_rate are never
forward-filled, missing is always 0 (icarefm: "= no medication given"). Ported verbatim from
AUMC_grid_pipeline/grid/impute.py (dataset-agnostic).

Numeric observation columns (direct_numeric/derived_output_rate) additionally get anything
STILL missing after forward-fill (i.e. before an admission's first-ever observation) filled with
0, per A.4.3 -- correct once grid.scale has already standardized these columns (0 = population
mean post-standardization). Categorical's pre-first-observation null is intentionally left as
null (grid.encode's dedicated missing one-hot class is conceptually a null/missing category, not
a value to fill in).

Also ported from MetaICU's grid/build/impute.py (not present in dataset_EDA's own
AUMC_grid_pipeline/grid/impute.py -- found missing during a 2026-07-30 audit against the real
iCareFM_replicate/Data reference output): capture_presence_mask, a f"{tag}__observed" companion
column per direct_numeric/derived_output_rate feature, 1 only at the exact hour of a real raw
measurement and 0 everywhere else (including forward-filled hours) -- lets a model distinguish
"really measured now" from "carried forward" or "never observed yet", which the value column
alone cannot express once imputed. Must run on the grid AFTER assembly/derived-target merge but
BEFORE scale_grid/impute_grid, while the null pattern still reflects real absence.
"""
import logging

import polars as pl

log = logging.getLogger(__name__)


def capture_presence_mask(grid, matches):
    """grid: wide DataFrame from grid.assemble_grid (plus any derived targets already merged --
    see grid.derive_targets), pre-scale/pre-impute so nulls are still the real ones. matches:
    tag -> feature info dict (direct_numeric/derived_output_rate only get a mask -- categorical's
    missingness is already recoverable from its one-hot __missing column, and
    treatment_indicator/treatment_rate's "missing is unconditionally 0" convention makes a mask
    meaningless for those). Returns (grid, mask_cols) -- mask_cols is the list of f"{tag}__observed"
    column names added, for feature_schema.json's presence_mask_column bookkeeping."""
    mask_cols = []
    new_cols = []
    for tag, info in matches.items():
        if tag not in grid.columns:
            continue
        if info["reconstruction_type"] not in ("direct_numeric", "derived_output_rate"):
            continue
        col_name = f"{tag}__observed"
        new_cols.append(pl.col(tag).is_not_null().cast(pl.Int8).alias(col_name))
        mask_cols.append(col_name)
    if new_cols:
        grid = grid.with_columns(new_cols)
        log.info(f"captured presence mask for {len(mask_cols)} direct_numeric/derived_output_rate columns")
    return grid, mask_cols

# supp_o2_vent's reconstruction_type is direct_numeric (correct -- it's a median-per-hour value,
# same mechanics as fio2), but M4's manifest decision text explicitly notes it shares fio2's
# source itemids (same ambiguity AUMC's own construction had) and the intended distinction
# between the two features is the imputation policy: fio2 assumes the last-known ventilator/
# ambient FiO2 persists, supp_o2_vent assumes unrecorded hours mean the supplemental-O2 treatment
# isn't being actively given. Overrides reconstruction_type-based routing below for this one tag,
# matching AUMC's identical override.
ZERO_FILL_TAG_OVERRIDE = {"supp_o2_vent"}


def impute_grid(grid, matches, scaled=True):
    """grid: wide DataFrame from grid.assemble_grid (ideally already passed through
    grid.scale.scale_grid). matches: tag -> feature info dict, from
    grid.manifest.parse_manifest() -- used to look up each column's reconstruction_type.
    scaled: whether numeric observation columns have already been standardized -- controls
    whether their post-forward-fill remaining nulls get the final 0-fill (0 = population mean,
    only valid once scaled). Pass False if calling this on raw, unscaled values (e.g. QA/
    inspection of the pre-scaling grid) to keep those nulls as null instead."""
    grid = grid.sort(["admissionid", "hour"])

    numeric_ffill_cols, categorical_ffill_cols, zerofill_cols = [], [], []
    for tag, info in matches.items():
        if tag not in grid.columns:
            continue
        if tag in ZERO_FILL_TAG_OVERRIDE:
            zerofill_cols.append(tag)
            continue
        rt = info["reconstruction_type"]
        if rt in ("direct_numeric", "derived_output_rate"):
            numeric_ffill_cols.append(tag)
        elif rt == "categorical":
            categorical_ffill_cols.append(tag)
        elif rt in ("treatment_indicator", "treatment_rate"):
            zerofill_cols.append(tag)

    ffill_cols = numeric_ffill_cols + categorical_ffill_cols
    if ffill_cols:
        grid = grid.with_columns([
            pl.col(c).fill_null(strategy="forward").over("admissionid") for c in ffill_cols
        ])
        log.info(f"forward-filled {len(ffill_cols)} observation/categorical columns")

    if zerofill_cols:
        grid = grid.with_columns([pl.col(c).fill_null(0) for c in zerofill_cols])
        log.info(f"zero-filled {len(zerofill_cols)} treatment_indicator/treatment_rate columns")

    if scaled and numeric_ffill_cols:
        grid = grid.with_columns([pl.col(c).fill_null(0) for c in numeric_ffill_cols])
        log.info(f"0-filled {len(numeric_ffill_cols)} numeric observation columns' remaining "
                 f"pre-first-observation nulls (A.4.3, valid since these are already scaled)")

    n_still_null = sum(grid[c].null_count() for c in categorical_ffill_cols)
    log.info(f"remaining nulls in categorical columns (pre-first-observation, left as null -- "
             f"one-hot's dedicated missing class is a separate follow-up): {n_still_null}")
    return grid
