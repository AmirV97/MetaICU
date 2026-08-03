"""
Derived TTE (time-to-event) target features, ported from MetaICU's grid/build/derive_targets.py
(not present in dataset_EDA's own AUMC_grid_pipeline -- found missing during a 2026-07-30 audit
against the real iCareFM_replicate/Data reference output, which materializes these directly in
the grid, not just in a separate tte_targets.json sidecar).

Both derived tags are computed on RAW, pre-scaling values -- must run AFTER assemble_grid but
BEFORE grid.impute.capture_presence_mask/grid.scale.scale_grid, same ordering MetaICU uses
(assemble_grid -> add_derived_tte_targets -> capture_presence_mask -> scale_grid -> impute_grid).
Both are registered as "direct_numeric" in DERIVED_TARGET_MATCHES so they flow through the same
presence-mask/scale/impute machinery as any real direct_numeric feature (grid.scale.py's
LOG_TRANSFORM_TAGS already has log1p entries for both).

MIMIC_K35_TTE_TARGETS is MIMIC's own TTE-target list -- the same K=34 list AUMCdb's grid uses
(iCareFM_replicate/Data/tte_targets.json), PLUS bili_dir: MIMIC-IV has direct bilirubin available
(unlike AmsterdamUMCdb, where it's absent and AUMCdb's own tte_targets.json excludes it), so no
forced parity is needed here -- decided 2026-07-29 (metaicu_familiarization.md), applied 2026-08-03.
bili_dir is already a kept, in-scope direct_numeric tag (2 keep matches) with its own
scale.py::LOG_TRANSFORM_TAGS log1p entry, so no other wiring is needed to include it.
"""
import logging

import polars as pl

log = logging.getLogger(__name__)

MIMIC_K35_TTE_TARGETS = [
    "lact", "map", "sbp", "hr", "tnt", "po2", "pco2", "fio2", "spo2", "resp", "pf_ratio",
    "crea", "bun", "urine_rate", "urine_rate_per_weight", "bili", "bili_dir", "ast", "alt", "plt",
    "wbc", "rbc", "hct", "inr_pt", "temp", "crp", "ph", "na", "k", "ca", "mg", "cl", "glu", "ck",
    "ckmb",
]

DERIVED_TARGET_SOURCES = {"pf_ratio": ["po2", "fio2"], "urine_rate_per_weight": ["urine_rate", "weight"]}
DERIVED_TARGET_MATCHES = {
    "pf_ratio": {"reconstruction_type": "direct_numeric", "target_unit": "mm Hg", "keep_matches": []},
    "urine_rate_per_weight": {"reconstruction_type": "direct_numeric", "target_unit": "mL/kg/hr", "keep_matches": []},
}


def add_derived_tte_targets(grid, admissions):
    """grid: wide DataFrame from grid.assemble_grid (pre-scale, pre-impute -- po2/fio2/urine_rate
    still raw). admissions: DataFrame carrying raw (unscaled) weight, from
    grid.extract_static.extract_static_features already joined on. Returns (grid,
    derived_target_matches) -- derived_target_matches is DERIVED_TARGET_MATCHES filtered to only
    the targets whose source columns actually exist in this run's grid (so a caller merging this
    into their manifest-derived matches dict doesn't register a target with no real source)."""
    available = {}

    if "po2" in grid.columns and "fio2" in grid.columns:
        grid = grid.with_columns(
            pl.when(pl.col("po2").is_not_null() & pl.col("fio2").is_not_null() & (pl.col("fio2") > 0))
            .then(pl.col("po2") / (pl.col("fio2") / 100.0))
            .otherwise(None)
            .alias("pf_ratio")
        )
        available["pf_ratio"] = DERIVED_TARGET_MATCHES["pf_ratio"]
        log.info("derived pf_ratio = po2 / (fio2/100)")
    else:
        log.warning("po2/fio2 not both present -- pf_ratio not derived")

    if "urine_rate" in grid.columns and "weight" in admissions.columns:
        weight_raw = admissions.select(["admissionid", "weight"])
        grid = grid.join(weight_raw, on="admissionid", how="left")
        grid = grid.with_columns(
            pl.when(pl.col("urine_rate").is_not_null() & pl.col("weight").is_not_null() & (pl.col("weight") > 0))
            .then(pl.col("urine_rate") / pl.col("weight"))
            .otherwise(None)
            .alias("urine_rate_per_weight")
        ).drop("weight")
        available["urine_rate_per_weight"] = DERIVED_TARGET_MATCHES["urine_rate_per_weight"]
        log.info("derived urine_rate_per_weight = urine_rate / weight")
    else:
        log.warning("urine_rate/weight not both present -- urine_rate_per_weight not derived")

    return grid, available
