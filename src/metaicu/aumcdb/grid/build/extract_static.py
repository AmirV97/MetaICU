"""
admission_context raw extraction: six static/demographic fields (age, weight, height, sex, adm,
ethnic), with the five available values recovered from admissions.csv per the manifest's resolved
bin-median / category-collapse policies. No itemid-vocabulary matching applies here (see each
feature's manifest Notes -- "source is a static admissions-table column, not a vocab-matched
observation"), so this bypasses grid.build.manifest_parser's generic keep_matches parsing entirely, the
same way treatment_rate_formulas.py hardcodes its own policy outside the manifest-matching
flow. `ethnic` (the 6th iCareFM Table S3 demographic) is emitted as structurally missing:
AmsterdamUMCdb has no reliable ethnicity source (only a nationality field, judged a
conceptual mismatch, not a valid proxy). This preserves a shared demographic interface without
inventing ethnicity values.

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
# adm = urgency (2 states) x origin collapsed to its top-4 raw categories + "Other" (manifest's
# adm section) -- everything not in this dict collapses to "other", non-null-handling below.
ORIGIN_TOP4 = {
    "Verpleegafdeling zelfde ziekenhuis": "ward_same_hospital",
    "Eerste Hulp afdeling zelfde ziekenhuis": "ed",
    "CCU/IC zelfde ziekenhuis": "icu_ccu",
}
URGENCY_LABEL = {0: "elective", 1: "emergency"}
# Normalize Dutch source labels to the F/M schema shared with MIMIC-IV; blank remains missing.
SEX_LABEL = {"Man": "M", "Vrouw": "F", "": None}

# Fixed one-hot vocabularies for the three categorical static/demographic features, derived from
# reviewed policies rather than empirically observed values -- guarantees a
# stable schema across runs/splits even if a rare combination (e.g. an elective ED admission)
# happens not to appear. sex has real nulls (gender left blank in admissions.csv) so it gets the
# usual encode.py dedicated missing class; adm's "missing" origin is already its own category
# label (see origin_collapsed above), so admissions.csv-derived adm values are never actually
# null. adm uses the cross-dataset union vocabulary: transfer is structurally zero in AUMC,
# while ward_same_hospital is structurally zero in MIMIC.
SEX_CATEGORIES = ["F", "M"]
ETHNIC_CATEGORIES = ["ASIAN", "BLACK", "HISPANIC_LATINO", "OTHER", "WHITE"]
ADM_ORIGIN_CATEGORIES = ["ed", "icu_ccu", "missing", "other", "transfer", "ward_same_hospital"]
ADM_CATEGORIES = sorted(
    f"{urgency}_{origin}"
    for urgency in URGENCY_LABEL.values()
    for origin in ADM_ORIGIN_CATEGORIES
)
STATIC_CATEGORICAL_VOCAB = {
    "sex": SEX_CATEGORIES,
    "adm": ADM_CATEGORIES,
    "ethnic": ETHNIC_CATEGORIES,
}


def extract_static_features(admissions):
    """admissions: DataFrame from grid.raw_csv.load_admissions() (or a filtered subset) --
    must still carry the raw admissions.csv columns (agegroup/weightgroup/heightgroup/gender/
    urgency/origin), i.e. called before any column-narrowing. Returns one row per admission:
    admissionid, age, weight, height, sex, adm, ethnic -- real nulls where the manifest says
    leave-as-missing, no imputation."""
    origin_collapsed = (
        pl.when(pl.col("origin").is_null()).then(pl.lit("missing"))
        .otherwise(pl.col("origin").replace_strict(ORIGIN_TOP4, default="other", return_dtype=pl.Utf8))
    )
    df = admissions.with_columns(
        pl.col("agegroup").replace_strict(AGE_BIN_MEDIAN, default=None, return_dtype=pl.Float64).alias("age"),
        pl.col("weightgroup").replace_strict(WEIGHT_BIN_MEDIAN, default=None, return_dtype=pl.Float64).alias("weight"),
        pl.col("heightgroup").replace_strict(HEIGHT_BIN_MEDIAN, default=None, return_dtype=pl.Float64).alias("height"),
        pl.col("gender").replace_strict(SEX_LABEL, return_dtype=pl.String).alias("sex"),
        pl.col("urgency").replace_strict(URGENCY_LABEL, default=None, return_dtype=pl.Utf8).alias("_urgency_label"),
        origin_collapsed.alias("_origin_collapsed"),
        pl.lit(None, dtype=pl.String).alias("ethnic"),
    )
    df = df.with_columns((pl.col("_urgency_label") + "_" + pl.col("_origin_collapsed")).alias("adm"))

    out = df.select(["admissionid", "age", "weight", "height", "sex", "adm", "ethnic"])
    for col in ["age", "weight", "height", "sex", "adm", "ethnic"]:
        log.info(f"static feature {col}: {out[col].null_count()} nulls out of {out.height}")
    return out
