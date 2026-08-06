"""
admission_context raw extraction: seven static/demographic fields (age, weight, height, sex,
adm_urgency, adm_origin, ethnic), with the six available values recovered from admissions.csv per
the manifest's resolved bin-median / category-collapse policies. No itemid-vocabulary matching
applies here (see each feature's manifest Notes -- "source is a static admissions-table column,
not a vocab-matched observation"), so this bypasses grid.build.manifest_parser's generic
keep_matches parsing entirely, the same way treatment_rate_formulas.py hardcodes its own policy
outside the manifest-matching flow. `ethnic` (the 6th iCareFM Table S3 demographic) is emitted as
structurally missing: AmsterdamUMCdb has no reliable ethnicity source (only a nationality field,
judged a conceptual mismatch, not a valid proxy). This preserves a shared demographic interface
without inventing ethnicity values.

`adm_urgency`/`adm_origin` (see MIMIC's extract_static.py docstring for the full cross-cohort
vocabulary reasoning): origin's intra-hospital ward transfer is merged into the shared
"transferred" bucket with MIMIC's inter-facility transfer, a deliberate, accepted looseness to
avoid a perfectly cohort-exclusive category.

Per-admission (not per-hour) values -- one row per admission, not a grid contribution; the
caller folds this into metadata.csv, not the hourly grid. Deliberately does NOT impute
(weight/height/sex blanks stay null): per this session's design decision, mean/median
imputation plus a missing-indicator bit is a model-layer concern (fed into a static-features
MLP at train time), not a dataset-layer one -- consistent with grid.impute only ever
forward-filling real observations, never fabricating a value with none behind it.
"""
import logging

import polars as pl

log = logging.getLogger(__name__)

AGE_BIN_MEDIAN = {
    "18-39": 28.5, "40-49": 44.5, "50-59": 54.5,
    "60-69": 64.5, "70-79": 74.5, "80+": 84.5,
}
WEIGHT_BIN_MEDIAN = {
    "59-": 54.5, "60-69": 64.5, "70-79": 74.5, "80-89": 84.5,
    "90-99": 94.5, "100-109": 104.5, "110+": 114.5,
}
HEIGHT_BIN_MEDIAN = {
    "159-": 154.0, "160-169": 164.5, "170-179": 174.5,
    "180-189": 184.5, "190+": 194.5,
}
# adm splits into two independent categorical dims -- urgency and origin -- rather than one
# combined cross-product, so each is estimated independently and neither leaks cohort identity via
# a category the other cohort can never populate (ward_same_hospital/transfer, see origin below).
# origin collapses to its top-3 raw categories + "Other" (manifest's adm section) -- everything
# not in this dict collapses to "other"; null passes through as null (dedicated missing one-hot
# class, same mechanism as sex). "Verpleegafdeling zelfde ziekenhuis" (intra-hospital ward
# transfer) is merged into the shared "transferred" bucket with MIMIC's inter-facility transfer --
# not the same clinical concept, but a deliberate, accepted merge to avoid a perfectly
# cohort-exclusive category (see MIMIC's extract_static.py docstring for the full reasoning).
ORIGIN_TOP4 = {
    "Verpleegafdeling zelfde ziekenhuis": "transferred",
    "Eerste Hulp afdeling zelfde ziekenhuis": "ed",
    "CCU/IC zelfde ziekenhuis": "icu_ccu",
}
URGENCY_LABEL = {0: "elective", 1: "emergency"}
# Normalize Dutch source labels to the F/M schema shared with MIMIC-IV; blank remains missing.
SEX_LABEL = {"Man": "M", "Vrouw": "F", "": None}

# Fixed one-hot vocabularies for the four categorical static/demographic features, derived from
# reviewed policies rather than empirically observed values -- guarantees a stable schema across
# runs/splits even if a rare category happens not to appear. None of these declare their own
# "missing" string category -- every one relies on encode.py's generic dedicated-missing class for
# real nulls (sex and adm_urgency both have genuine nulls; adm_origin's is now null too, no longer
# a manually-baked "missing" string, so it can't collide with the generic missing column name).
SEX_CATEGORIES = ["F", "M"]
ETHNIC_CATEGORIES = ["ASIAN", "BLACK", "HISPANIC_LATINO", "OTHER", "WHITE"]
ADM_URGENCY_CATEGORIES = ["elective", "emergency"]
ADM_ORIGIN_CATEGORIES = ["ed", "icu_ccu", "other", "transferred"]
STATIC_CATEGORICAL_VOCAB = {
    "sex": SEX_CATEGORIES,
    "adm_urgency": ADM_URGENCY_CATEGORIES,
    "adm_origin": ADM_ORIGIN_CATEGORIES,
    "ethnic": ETHNIC_CATEGORIES,
}


def extract_static_features(admissions):
    """admissions: DataFrame from grid.raw_csv.load_admissions() (or a filtered subset) --
    must still carry the raw admissions.csv columns (agegroup/weightgroup/heightgroup/gender/
    urgency/origin), i.e. called before any column-narrowing. Returns one row per admission:
    admissionid, age, weight, height, sex, adm_urgency, adm_origin, ethnic -- real nulls where the
    manifest says leave-as-missing, no imputation."""
    origin_collapsed = (
        pl.when(pl.col("origin").is_null()).then(pl.lit(None, dtype=pl.Utf8))
        .otherwise(pl.col("origin").replace_strict(ORIGIN_TOP4, default="other", return_dtype=pl.Utf8))
    )
    df = admissions.with_columns(
        pl.col("agegroup").replace_strict(AGE_BIN_MEDIAN, default=None, return_dtype=pl.Float64).alias("age"),
        pl.col("weightgroup").replace_strict(WEIGHT_BIN_MEDIAN, default=None, return_dtype=pl.Float64).alias("weight"),
        pl.col("heightgroup").replace_strict(HEIGHT_BIN_MEDIAN, default=None, return_dtype=pl.Float64).alias("height"),
        pl.col("gender").replace_strict(SEX_LABEL, return_dtype=pl.String).alias("sex"),
        pl.col("urgency").replace_strict(URGENCY_LABEL, default=None, return_dtype=pl.Utf8).alias("adm_urgency"),
        origin_collapsed.alias("adm_origin"),
        pl.lit(None, dtype=pl.String).alias("ethnic"),
    )

    out = df.select(["admissionid", "age", "weight", "height", "sex", "adm_urgency", "adm_origin", "ethnic"])
    for col in ["age", "weight", "height", "sex", "adm_urgency", "adm_origin", "ethnic"]:
        log.info(f"static feature {col}: {out[col].null_count()} nulls out of {out.height}")
    return out
