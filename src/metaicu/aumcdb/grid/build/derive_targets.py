"""
Derived TTE pretraining target channels (Supplement B.2.1's K=35 list, iCareFM_replicate's
context.md sec 5.2) that aren't raw AmsterdamUMCdb concepts and so have no manifest entry:
pf_ratio = po2 / (fio2/100) (fio2 is stored on a 0-100 % scale but the P/F ratio needs it as a
0.21-1.0 fraction), urine_rate_per_weight = urine_rate / weight.

Computed here, directly in raw physical units, right after grid.assemble_grid and BEFORE
grid.scale/grid.impute run -- avoids computing them downstream from the already-scaled grid,
which would require an unscale-then-rescale round trip and inherit its ordering/precision risk.
Both are null wherever either constituent isn't itself a real measurement at that hour
(assemble_grid's raw nulls propagate through the division automatically) or the denominator is
non-positive.

Once computed, these two columns are handed to grid.impute.capture_presence_mask/grid.scale.
scale_grid/grid.impute.impute_grid exactly like any other direct_numeric grid feature -- see
DERIVED_TARGET_MATCHES below, merged into `matches` only for those three calls, never into the
real manifest-derived `matches` dict itself (these aren't real AmsterdamUMCdb concepts and
shouldn't appear in manifest-driven bookkeeping like config.features filtering or
grid_build_summary.json's "features" list).
"""
import logging

import polars as pl

log = logging.getLogger(__name__)

DERIVED_TARGET_MATCHES = {
    "pf_ratio": {"reconstruction_type": "direct_numeric", "target_unit": "ratio"},
    "urine_rate_per_weight": {"reconstruction_type": "direct_numeric", "target_unit": "mL/h/kg"},
}

DERIVED_TARGET_SOURCES = {
    "pf_ratio": ["po2", "fio2"],
    "urine_rate_per_weight": ["urine_rate", "weight"],
}

# K=35 TTE pretraining target set (Supplement B.2.1; iCareFM_replicate/context.md sec 5.2),
# minus bili_dir (not present in AmsterdamUMCdb -- context.md's Q3, resolved 2026-07-16). Order
# fixes the canonical column order a Dataset class should use for its Ztargets tensor.
K34_TTE_TARGETS = [
    "lact", "map", "sbp", "hr", "tnt", "po2", "pco2", "fio2", "spo2", "resp",
    "pf_ratio",
    "crea", "bun", "urine_rate", "urine_rate_per_weight",
    "bili", "ast", "alt", "plt", "wbc", "rbc", "hct", "inr_pt", "temp", "crp",
    "ph", "na", "k", "ca", "mg", "cl", "glu", "ck", "ckmb",
]


def add_derived_tte_targets(grid, admissions):
    """grid: wide DataFrame from grid.assemble_grid (still has raw physical values, true nulls
    where an hour was never observed). admissions: DataFrame carrying raw (unscaled) `weight`
    (grid.build.extract_static.extract_static_features). Skips a derived target gracefully (with
    a warning, not a crash) if its source columns aren't present -- e.g. a bounded run via
    run.features that excludes po2/fio2/urine_rate.

    Returns (grid, new_matches): grid with whichever of "pf_ratio"/"urine_rate_per_weight" could
    be computed added as new columns; new_matches is the matching subset of
    DERIVED_TARGET_MATCHES, for the caller to merge into `matches` for scale_grid/impute_grid/
    capture_presence_mask only."""
    new_matches = {}

    if "po2" in grid.columns and "fio2" in grid.columns:
        # fio2 is stored on a 0-100 PERCENT scale (feature_schema target_unit "%"); the P/F ratio
        # needs FiO2 as a FRACTION (0.21-1.0), so divide by 100 before dividing po2 by it. Matches
        # iCareFM_replicate/src/labels.py's respiratory_failure/sofa_respiratory fix (2026-07-18);
        # the earlier version divided by raw percent, making pf_ratio ~100x too small.
        grid = grid.with_columns(
            pl.when(pl.col("po2").is_not_null() & pl.col("fio2").is_not_null() & (pl.col("fio2") > 0))
            .then(pl.col("po2") / (pl.col("fio2") / 100.0))
            .otherwise(None)
            .alias("pf_ratio")
        )
        new_matches["pf_ratio"] = DERIVED_TARGET_MATCHES["pf_ratio"]
    else:
        log.warning("pf_ratio: po2 and/or fio2 not in grid -- skipped")

    if "urine_rate" in grid.columns and "weight" in admissions.columns:
        weight_raw = admissions.select(["admissionid", "weight"])
        grid = grid.join(weight_raw, on="admissionid", how="left")
        grid = grid.with_columns(
            pl.when(pl.col("urine_rate").is_not_null() & pl.col("weight").is_not_null() & (pl.col("weight") > 0))
            .then(pl.col("urine_rate") / pl.col("weight"))
            .otherwise(None)
            .alias("urine_rate_per_weight")
        ).drop("weight")
        new_matches["urine_rate_per_weight"] = DERIVED_TARGET_MATCHES["urine_rate_per_weight"]
    else:
        log.warning("urine_rate_per_weight: urine_rate and/or weight not available -- skipped")

    if new_matches:
        log.info(f"derived TTE targets computed: {sorted(new_matches)}")
    return grid, new_matches
