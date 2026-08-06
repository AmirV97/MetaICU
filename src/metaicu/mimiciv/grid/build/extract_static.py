"""
admission_context raw extraction: seven resolved static/demographic features (age, weight,
height, sex, adm_urgency, adm_origin, ethnic), recovered directly from admissions/patients/
icustays columns (age/sex/adm_urgency/adm_origin/ethnic) and a small chartevents admission-
weight/height scan (weight/height) -- per the manifest review's ADMISSION_CONTEXT_FIXED notes.
No itemid-vocabulary matching applies to these (static admissions-table columns, not
vocab-matched observations), same reasoning as AUMC_grid_pipeline/grid/extract_static.py.

Per-admission (not per-hour) values -- one row per admission, not a grid contribution; the
caller folds this into metadata.csv, not the hourly grid, same convention as AUMC. Deliberately
does NOT impute (weight/height/sex blanks stay null) -- imputation is a model-layer concern,
same design decision AUMC made.

`adm` splits into two independent categorical dims -- `adm_urgency` and `adm_origin` -- rather
than one combined urgency x origin cross-product, so each is estimated independently and a rare
combination doesn't dilute either dim's statistics. Both use a shared fixed output vocabulary for
dimensional parity, but `adm_origin` is not treated as a fully unified clinical concept: MIMIC's
admission_location is a hospital referral source, whereas AUMC's origin is the preceding
department within the same hospital. `ed` and `other` use shared names. Both expose `icu_ccu`,
with the recorded caveat that MIMIC derives it from PACU while AUMC derives it from an actual
ICU/CCU. AUMC's intra-hospital ward transfer and MIMIC's inter-facility transfer are merged into
one shared `transferred` bucket -- a deliberate, accepted looseness (they are not the same
clinical event) made specifically to avoid a perfectly cohort-exclusive category; kept separate
would let a model infer cohort identity directly from this one dim. This differs from universal
clinical scales such as GCS/RASS, whose labels are directly harmonized without any such merge.
`ethnic` (MIMIC's admissions.race) is collapsed to five broad reported groups plus missing.
The mapping enumerates every reviewed source label so new labels fail visibly during extraction.
"""
import logging

import polars as pl

from .raw_csv import scan_raw_table, admission_filter

log = logging.getLogger(__name__)

WEIGHT_ITEMID = 226512  # Admission Weight (Kg)
HEIGHT_ITEMID = 226730  # Height (cm)
WEIGHT_VALID_RANGE_KG = (30.0, 300.0)
HEIGHT_VALID_RANGE_CM = (100.0, 250.0)

# admission_type -> urgency bucket (elective/emergency), mirroring AUMC's URGENCY_LABEL
URGENCY_LABEL = {
    "ELECTIVE": "elective", "SURGICAL SAME DAY ADMISSION": "elective",
    "AMBULATORY OBSERVATION": "elective", "DIRECT OBSERVATION": "elective",
    "OBSERVATION ADMIT": "elective",
    "EU OBSERVATION": "emergency", "EW EMER.": "emergency", "DIRECT EMER.": "emergency",
    "URGENT": "emergency",
}

# admission_location -> origin bucket, mirroring AUMC's ORIGIN_TOP4-style collapse (a small,
# bounded set of buckets rather than MIMIC's 11 raw locations). transfer categories are merged
# into the shared "transferred" bucket with AUMC's intra-hospital ward transfer -- not the same
# clinical concept (see module docstring), but a deliberate, accepted merge to avoid a perfectly
# cohort-exclusive category. "INFORMATION NOT AVAILABLE" is deliberately absent: it now falls
# through to the replace_strict default of null, same as any other unmapped value, rather than a
# manually-baked "missing" string (which would collide with encode.py's generic missing column).
ORIGIN_COLLAPSED = {
    "EMERGENCY ROOM": "ed",
    "PACU": "icu_ccu",
    "TRANSFER FROM HOSPITAL": "transferred", "TRANSFER FROM SKILLED NURSING FACILITY": "transferred",
    "AMBULATORY SURGERY TRANSFER": "transferred",
    "CLINIC REFERRAL": "other", "PHYSICIAN REFERRAL": "other", "PROCEDURE SITE": "other",
    "WALK-IN/SELF REFERRAL": "other", "INTERNAL TRANSFER TO OR FROM PSYCH": "other",
}

SEX_CATEGORIES = ["F", "M"]
ADM_URGENCY_CATEGORIES = ["elective", "emergency"]
ADM_ORIGIN_CATEGORIES = ["ed", "icu_ccu", "other", "transferred"]
ETHNIC_CATEGORIES = ["ASIAN", "BLACK", "HISPANIC_LATINO", "OTHER", "WHITE"]
RACE_GROUP_BY_SOURCE_LABEL = {
    None: None,
    "UNKNOWN": None,
    "UNABLE TO OBTAIN": None,
    "PATIENT DECLINED TO ANSWER": None,
    "WHITE": "WHITE",
    "WHITE - OTHER EUROPEAN": "WHITE",
    "WHITE - RUSSIAN": "WHITE",
    "WHITE - EASTERN EUROPEAN": "WHITE",
    "WHITE - BRAZILIAN": "WHITE",
    "BLACK/AFRICAN AMERICAN": "BLACK",
    "BLACK/CAPE VERDEAN": "BLACK",
    "BLACK/CARIBBEAN ISLAND": "BLACK",
    "BLACK/AFRICAN": "BLACK",
    "HISPANIC OR LATINO": "HISPANIC_LATINO",
    "HISPANIC/LATINO - PUERTO RICAN": "HISPANIC_LATINO",
    "HISPANIC/LATINO - DOMINICAN": "HISPANIC_LATINO",
    "HISPANIC/LATINO - GUATEMALAN": "HISPANIC_LATINO",
    "HISPANIC/LATINO - SALVADORAN": "HISPANIC_LATINO",
    "HISPANIC/LATINO - CUBAN": "HISPANIC_LATINO",
    "HISPANIC/LATINO - COLUMBIAN": "HISPANIC_LATINO",
    "HISPANIC/LATINO - MEXICAN": "HISPANIC_LATINO",
    "HISPANIC/LATINO - HONDURAN": "HISPANIC_LATINO",
    "HISPANIC/LATINO - CENTRAL AMERICAN": "HISPANIC_LATINO",
    "ASIAN": "ASIAN",
    "ASIAN - CHINESE": "ASIAN",
    "ASIAN - SOUTH EAST ASIAN": "ASIAN",
    "ASIAN - ASIAN INDIAN": "ASIAN",
    "ASIAN - KOREAN": "ASIAN",
    "OTHER": "OTHER",
    "PORTUGUESE": "OTHER",
    "AMERICAN INDIAN/ALASKA NATIVE": "OTHER",
    "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER": "OTHER",
    "SOUTH AMERICAN": "OTHER",
    "MULTIPLE RACE/ETHNICITY": "OTHER",
}
STATIC_CATEGORICAL_VOCAB = {
    "sex": SEX_CATEGORIES,
    "adm_urgency": ADM_URGENCY_CATEGORIES,
    "adm_origin": ADM_ORIGIN_CATEGORIES,
    "ethnic": ETHNIC_CATEGORIES,
}


def _filter_plausible_weight_height(rows: pl.DataFrame) -> pl.DataFrame:
    """Reject implausible raw measurements before calculating each stay's median."""
    return rows.filter(
        (
            (pl.col("itemid") == WEIGHT_ITEMID)
            & pl.col("valuenum").is_between(*WEIGHT_VALID_RANGE_KG, closed="both")
        )
        | (
            (pl.col("itemid") == HEIGHT_ITEMID)
            & pl.col("valuenum").is_between(*HEIGHT_VALID_RANGE_CM, closed="both")
        )
    )


def _extract_weight_height(raw_data_dir, admissions, admission_ids, raw_shards_dir=None):
    lf = scan_raw_table(raw_data_dir, "chartevents", admissions, raw_shards_dir)
    lf = lf.filter(
        pl.col("itemid").is_in([WEIGHT_ITEMID, HEIGHT_ITEMID]) & admission_filter(admission_ids)
    )
    df = lf.select(["admissionid", "itemid", "valuenum"]).collect(engine="streaming")
    df = _filter_plausible_weight_height(df)
    if df.height == 0:
        return None
    wide = df.group_by(["admissionid", "itemid"]).agg(pl.col("valuenum").median().alias("value")).pivot(
        index="admissionid", on="itemid", values="value"
    )
    rename = {}
    if WEIGHT_ITEMID in wide.columns or str(WEIGHT_ITEMID) in wide.columns:
        rename[WEIGHT_ITEMID if WEIGHT_ITEMID in wide.columns else str(WEIGHT_ITEMID)] = "weight"
    if HEIGHT_ITEMID in wide.columns or str(HEIGHT_ITEMID) in wide.columns:
        rename[HEIGHT_ITEMID if HEIGHT_ITEMID in wide.columns else str(HEIGHT_ITEMID)] = "height"
    wide = wide.rename(rename)
    for col in ["weight", "height"]:
        if col not in wide.columns:
            wide = wide.with_columns(pl.lit(None, dtype=pl.Float64).alias(col))
    return wide.select(["admissionid", "weight", "height"])


def extract_static_features(raw_data_dir, admissions, admission_ids=None, raw_shards_dir=None):
    """admissions: DataFrame from grid.raw_csv.load_admissions() (or a filtered subset) --
    must still carry admittime/year_of_birth/gender/admission_type/admission_location/race,
    i.e. called before any column-narrowing. Returns one row per admission: admissionid, age,
    weight, height, sex, adm_urgency, adm_origin, ethnic -- real nulls where genuinely missing, no
    imputation. admission_type is a small closed enum in practice, so the default="emergency"
    fallback below is not expected to ever fire; kept for parity with the original mapping."""
    urgency = pl.col("admission_type").replace_strict(URGENCY_LABEL, default="emergency", return_dtype=pl.Utf8)
    origin = pl.col("admission_location").replace_strict(ORIGIN_COLLAPSED, default=None, return_dtype=pl.Utf8)
    df = admissions.with_columns(
        (pl.col("admittime").dt.year() - pl.col("year_of_birth").cast(pl.Int64, strict=False)).alias("age"),
        pl.when(pl.col("gender") == "").then(None).otherwise(pl.col("gender")).alias("sex"),
        urgency.alias("adm_urgency"),
        origin.alias("adm_origin"),
        pl.col("race").replace_strict(
            RACE_GROUP_BY_SOURCE_LABEL, return_dtype=pl.String
        ).alias("ethnic"),
    )

    wh = _extract_weight_height(raw_data_dir, admissions, admission_ids, raw_shards_dir)
    if wh is not None:
        df = df.join(wh, on="admissionid", how="left")
    else:
        df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias("weight"), pl.lit(None, dtype=pl.Float64).alias("height"))

    out = df.select(["admissionid", "age", "weight", "height", "sex", "adm_urgency", "adm_origin", "ethnic"])
    for col in ["age", "weight", "height", "sex", "adm_urgency", "adm_origin", "ethnic"]:
        log.info(f"static feature {col}: {out[col].null_count()} nulls out of {out.height}")
    return out
