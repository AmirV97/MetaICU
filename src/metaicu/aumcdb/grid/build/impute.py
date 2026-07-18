"""
Imputation per icarefm_preprocessing_reference.md's A.4.3, applied to the dense grid from
grid.assemble: direct_numeric/derived_output_rate/categorical are forward-filled indefinitely
within each admission (never across admissions); treatment_indicator/treatment_rate are never
forward-filled, missing is always 0 (icarefm: "= no medication given").

Numeric observation columns (direct_numeric/derived_output_rate) additionally get anything
STILL missing after forward-fill (i.e. before an admission's first-ever observation) filled
with 0, per A.4.3 -- correct now that grid.scale has already standardized these columns (0 =
population mean post-standardization). This was deliberately deferred in v1 (see git history)
until grid.scale existed; run_extraction.py's default pipeline now always scales before
imputing, so this fill is unconditional for those columns. Categorical's pre-first-observation
null is intentionally left as null (the paper's own "dedicated missing one-hot class" is
conceptually a null/missing category, not a value to fill in -- one-hot encoding is a separate,
not-yet-implemented follow-up).
"""
import logging

import polars as pl

log = logging.getLogger(__name__)

# supp_o2_vent's reconstruction_type is direct_numeric (correct -- it's a median-per-hour
# numericitems value, same mechanics as fio2), but its manifest decision text explicitly calls
# for zero-fill, not forward-fill: it shares fio2's exact source itemids by design (iCareFM
# labels it a "treatment" concept with no distinct AmsterdamUMCdb channel), and the only
# intended difference between the two features is the imputation policy -- fio2 assumes the
# last-known ventilator/ambient FiO2 persists, supp_o2_vent assumes unrecorded hours mean the
# supplemental-O2 treatment isn't being actively given. Found 2026-07-14: this override was
# never implemented, so both columns forward-filled identically, making them indistinguishable
# everywhere instead of only where there's a direct reading. Overrides reconstruction_type-based
# routing below for this one tag; add more tags here if the same treatment-labeled-but-numeric
# pattern shows up elsewhere.
ZERO_FILL_TAG_OVERRIDE = {"supp_o2_vent"}


def capture_presence_mask(grid, matches):
    """Must be called on grid.assemble_grid's (or grid.scale.scale_grid's) output, BEFORE
    impute_grid destroys the null pattern that distinguishes a genuine hourly measurement from
    an imputed/carried-forward one. Only direct_numeric/derived_output_rate tags need this:
    categorical missingness is already exactly recoverable from one-hot's dedicated
    f"{tag}__missing" column (grid.build.encode), and treatment_indicator/treatment_rate draw no
    unknown-vs-confirmed-absent distinction at all (A.4.3: missing is unconditionally 0, "no
    medication given") -- a mask would be meaningless noise for those.

    Returns (grid, mask_cols): grid gets one new Int8 column f"{tag}__observed" per continuous/
    derived-rate tag (1 = real ground-truth value this hour, 0 = null here, about to be forward-
    or zero-filled by impute_grid). mask_cols is the list of new column names, in the order
    added."""
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
        log.info(f"captured presence mask for {len(mask_cols)} continuous/derived-rate columns")
    return grid, mask_cols


def impute_grid(grid, matches, scaled=True):
    """grid: wide DataFrame from grid.assemble_grid (ideally already passed through
    grid.scale.scale_grid). matches: tag -> feature info dict, from
    grid.build.manifest_parser.parse_manifest() -- used to look up each column's reconstruction_type.
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
