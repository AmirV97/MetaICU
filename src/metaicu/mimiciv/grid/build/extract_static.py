"""
admission_context raw extraction: the 5 resolved static/demographic features (age, weight,
height, sex, adm) plus ethnic, recovered directly from admissions/patients/icustays columns
(age/sex/adm/ethnic) and a small chartevents admission-weight/height scan (weight/height) --
per the manifest review's ADMISSION_CONTEXT_FIXED notes. No itemid-vocabulary matching applies
to age/sex/adm/ethnic (static admissions-table columns, not vocab-matched observations), same
reasoning as AUMC_grid_pipeline/grid/extract_static.py.

Per-admission (not per-hour) values -- one row per admission, not a grid contribution; the
caller folds this into metadata.csv, not the hourly grid, same convention as AUMC. Deliberately
does NOT impute (weight/height/sex blanks stay null) -- imputation is a model-layer concern,
same design decision AUMC made.

`adm` is collapsed to a bounded urgency x origin scheme (2026-07-30), mirroring AUMC's own
structural pattern (grid.extract_static.STATIC_CATEGORICAL_VOCAB's ADM_CATEGORIES: urgency x
origin, both coarse, small, one-hot-friendly) -- NOT a semantic 1:1 mapping of category NAMES
across datasets, since MIMIC's admission_location (referral source) and AUMC's origin
(within-hospital department transferred from) aren't the same underlying construct. `adm` is
dataset-specific administrative vocabulary, unlike GCS/RASS which are universal clinical scales
that DO need identical category names across datasets (see mgcs/vgcs/egcs/rass manifest blocks).
`ethnic` (MIMIC's admissions.race) is left uncollapsed -- not one-hot encoded, informational only
in metadata.csv, matching AUMC (which has no ethnicity field to collapse at all).
"""
import logging

import polars as pl

from .raw_csv import scan_raw_table, admission_filter

log = logging.getLogger(__name__)

WEIGHT_ITEMID = 226512  # Admission Weight (Kg)
HEIGHT_ITEMID = 226730  # Height (cm)

# admission_type -> urgency bucket (elective/emergency), mirroring AUMC's URGENCY_LABEL
URGENCY_LABEL = {
    "ELECTIVE": "elective", "SURGICAL SAME DAY ADMISSION": "elective",
    "AMBULATORY OBSERVATION": "elective", "DIRECT OBSERVATION": "elective",
    "OBSERVATION ADMIT": "elective",
    "EU OBSERVATION": "emergency", "EW EMER.": "emergency", "DIRECT EMER.": "emergency",
    "URGENT": "emergency",
}

# admission_location -> origin bucket, mirroring AUMC's ORIGIN_TOP4-style collapse (a small,
# bounded set of buckets rather than MIMIC's 11 raw locations)
ORIGIN_COLLAPSED = {
    "EMERGENCY ROOM": "ed",
    "PACU": "icu_ccu",
    "TRANSFER FROM HOSPITAL": "transfer", "TRANSFER FROM SKILLED NURSING FACILITY": "transfer",
    "AMBULATORY SURGERY TRANSFER": "transfer",
    "CLINIC REFERRAL": "other", "PHYSICIAN REFERRAL": "other", "PROCEDURE SITE": "other",
    "WALK-IN/SELF REFERRAL": "other", "INTERNAL TRANSFER TO OR FROM PSYCH": "other",
    "INFORMATION NOT AVAILABLE": "missing",
}

SEX_CATEGORIES = ["F", "M"]
ADM_CATEGORIES = sorted(f"{u}_{o}" for u in set(URGENCY_LABEL.values())
                        for o in set(ORIGIN_COLLAPSED.values()) | {"missing"})
STATIC_CATEGORICAL_VOCAB = {"sex": SEX_CATEGORIES, "adm": ADM_CATEGORIES}


def _extract_weight_height(raw_data_dir, admissions, admission_ids, raw_shards_dir=None):
    lf = scan_raw_table(raw_data_dir, "chartevents", admissions, raw_shards_dir)
    lf = lf.filter(
        pl.col("itemid").is_in([WEIGHT_ITEMID, HEIGHT_ITEMID]) & admission_filter(admission_ids)
    )
    df = lf.select(["admissionid", "itemid", "valuenum"]).collect(engine="streaming")
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
    weight, height, sex, adm, ethnic -- real nulls where genuinely missing, no imputation."""
    urgency = pl.col("admission_type").replace_strict(URGENCY_LABEL, default="emergency", return_dtype=pl.Utf8)
    origin = pl.col("admission_location").replace_strict(ORIGIN_COLLAPSED, default="missing", return_dtype=pl.Utf8)
    df = admissions.with_columns(
        (pl.col("admittime").dt.year() - pl.col("year_of_birth").cast(pl.Int64, strict=False)).alias("age"),
        pl.when(pl.col("gender") == "").then(None).otherwise(pl.col("gender")).alias("sex"),
        (urgency + "_" + origin).alias("adm"),
        pl.col("race").alias("ethnic"),
    )

    wh = _extract_weight_height(raw_data_dir, admissions, admission_ids, raw_shards_dir)
    if wh is not None:
        df = df.join(wh, on="admissionid", how="left")
    else:
        df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias("weight"), pl.lit(None, dtype=pl.Float64).alias("height"))

    out = df.select(["admissionid", "age", "weight", "height", "sex", "adm", "ethnic"])
    for col in ["age", "weight", "height", "sex", "adm", "ethnic"]:
        log.info(f"static feature {col}: {out[col].null_count()} nulls out of {out.height}")
    return out
