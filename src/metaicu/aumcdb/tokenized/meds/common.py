"""Shared schema, expressions, and frame helpers for the MEDS conversion pipeline."""

from __future__ import annotations

from typing import Sequence

import polars as pl

# Columns written to the predictor-facing output parquet.
CORE_COLUMNS = [
    "subject_id",
    "time",
    "code",
    "numeric_value",
    "text_value",
    "hadm_id",
    "icustay_id",
]

# Full debug column set; includes provenance metadata stripped from core output.
DEBUG_COLUMNS = CORE_COLUMNS + [
    "source_table",
    "source_token",
    "base_harmonized_token",
    "token_role",
    "temporal_phase",
    "interval_boundary",
    "admissionid",
    "itemid",
    "valueid",
    "unitid",
    "ordercategoryid",
    "source_label",
    "source_value",
    "source_unit",
    "quantile_bin",
    "binning_method",
    "raw_rows_in_bin",
    "raw_numeric_value",
    "exclusion_reason",
]

DEBUG_SCHEMA: dict[str, pl.DataType] = {
    "subject_id": pl.Int64,
    "time": pl.Datetime("us"),
    "code": pl.String,
    "numeric_value": pl.Float64,
    "text_value": pl.String,
    "hadm_id": pl.Int64,
    "icustay_id": pl.Int64,
    "source_table": pl.String,
    "source_token": pl.String,
    "base_harmonized_token": pl.String,
    "token_role": pl.String,
    "temporal_phase": pl.String,
    "interval_boundary": pl.String,
    "admissionid": pl.Int64,
    "itemid": pl.Int64,
    "valueid": pl.Int64,
    "unitid": pl.Int64,
    "ordercategoryid": pl.Int64,
    "source_label": pl.String,
    "source_value": pl.String,
    "source_unit": pl.String,
    "quantile_bin": pl.Int64,
    "binning_method": pl.String,
    "raw_rows_in_bin": pl.Int64,
    "raw_numeric_value": pl.Float64,
    "exclusion_reason": pl.String,
}


def empty_debug_frame() -> pl.DataFrame:
    return pl.DataFrame(schema=DEBUG_SCHEMA)


def runtime_phase_expr(relative_column: str) -> pl.Expr:
    """Compute temporal_phase from an admission-relative millisecond column.

    preadmission: before admittedat (rel_ms < 0)
    admission:    within the ICU stay
    postadmission: after dischargedat
    unknown:      null relative time
    """
    los_ms = pl.col("dischargedat").cast(pl.Int64) - pl.col("admittedat").cast(pl.Int64)
    return (
        pl.when(pl.col(relative_column).is_null())
        .then(pl.lit("unknown"))
        .when(pl.col(relative_column).cast(pl.Int64) < 0)
        .then(pl.lit("preadmission"))
        .when(pl.col(relative_column).cast(pl.Int64) > los_ms)
        .then(pl.lit("postadmission"))
        .otherwise(pl.lit("admission"))
    )


def string_bool_expr(column: str) -> pl.Expr:
    """Parse string True/False/1/yes columns from the vocab CSV."""
    return pl.col(column).cast(pl.String).str.strip_chars().str.to_lowercase().is_in(["true", "1", "yes"])


def meds_event_order_expr() -> pl.Expr:
    """Deterministic tie-break ordering for same-timestamp events.

    Admission anchor and demographic static context sort first.
    Outcome tokens (ICU_DISCHARGE, MEDS_DEATH) sort last so each timeline
    reads as ending at discharge/death rather than in alphabetic code order.
    """
    code = pl.col("code").cast(pl.String)
    interval_boundary = pl.col("interval_boundary").cast(pl.String)
    token_role = pl.col("token_role").cast(pl.String)
    return (
        pl.when(code == "ICU_ADMISSION").then(pl.lit(0))
        .when(code.str.starts_with("GENDER//")).then(pl.lit(10))
        .when(code.str.starts_with("AGEGROUP//")).then(pl.lit(20))
        .when(code.str.starts_with("WEIGHTGROUP//")).then(pl.lit(30))
        .when(code.str.starts_with("HEIGHTGROUP//")).then(pl.lit(40))
        .when(token_role.str.starts_with("static_context")).then(pl.lit(50))
        .when(interval_boundary == "START").then(pl.lit(100))
        .when(interval_boundary == "END").then(pl.lit(900))
        .when(code == "ICU_DISCHARGE").then(pl.lit(1000))
        .when(code == "MEDS_DEATH").then(pl.lit(1010))
        .otherwise(pl.lit(500))
    )


def sort_meds_events(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df
    return (
        df.with_columns(meds_event_order_expr().alias("_event_order"))
        .sort(["subject_id", "hadm_id", "time", "_event_order", "code"], nulls_last=True)
        .drop("_event_order")
    )


def validate_meds_event_invariants(df: pl.DataFrame) -> None:
    """Fail fast on impossible model-event rows before writing outputs.

    Only called on the full debug frame (including outcome rows). Outcome rows
    have non-null token_role='outcome' and temporal_phase='outcome', so they pass.
    """
    if df.is_empty():
        return
    checks = df.select([
        (pl.col("code").is_null() | (pl.col("code").cast(pl.String).str.strip_chars() == "")).sum().alias("blank_code"),
        pl.col("time").is_null().sum().alias("null_time"),
        pl.col("subject_id").is_null().sum().alias("null_subject_id"),
        pl.col("hadm_id").is_null().sum().alias("null_hadm_id"),
        pl.col("icustay_id").is_null().sum().alias("null_icustay_id"),
        pl.col("token_role").is_null().sum().alias("null_token_role"),
        pl.col("temporal_phase").is_null().sum().alias("null_temporal_phase"),
        (
            (pl.col("source_table") == "numericitems") & pl.col("quantile_bin").is_null()
        ).sum().alias("numeric_missing_quantile"),
        (
            (pl.col("source_table") == "numericitems") & ~pl.col("code").str.contains("//Q")
        ).sum().alias("numeric_missing_q_suffix"),
    ]).row(0, named=True)
    failures = {k: int(v) for k, v in checks.items() if int(v) > 0}
    if failures:
        raise ValueError(f"Invalid MEDS event rows before write: {failures}")


def coerce_debug_frame(df: pl.DataFrame) -> pl.DataFrame:
    """Cast all debug columns to schema types, fill missing columns with null,
    and return in DEBUG_COLUMNS order."""
    if df.is_empty():
        return empty_debug_frame()
    # stay_id → icustay_id rename (pre-MEDS uses stay_id; MEDS uses icustay_id)
    if "stay_id" in df.columns and "icustay_id" not in df.columns:
        df = df.rename({"stay_id": "icustay_id"})
    # harmonized_token → base_harmonized_token for provenance
    if "harmonized_token" in df.columns and "base_harmonized_token" not in df.columns:
        df = df.with_columns(pl.col("harmonized_token").cast(pl.String).alias("base_harmonized_token"))
    # Add missing columns as null
    for col, dtype in DEBUG_SCHEMA.items():
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).cast(dtype).alias(col))
    # Cast to target dtypes
    df = df.with_columns([pl.col(col).cast(dtype) for col, dtype in DEBUG_SCHEMA.items()])
    return df.select(DEBUG_COLUMNS)


def record_join_exclusions(
    table: str,
    rows: pl.DataFrame,
    include_phases: Sequence[str],
) -> list[dict]:
    """Count unmatched, non-emitted, phase-excluded, and matched-emitted rows for audit."""
    if rows.is_empty():
        return []
    total = rows.height
    unmatched = rows.filter(pl.col("source_token").is_null()).height if "source_token" in rows.columns else total
    non_emitted = (
        rows.filter(pl.col("source_token").is_not_null() & ~pl.col("_emit")).height
        if "_emit" in rows.columns else 0
    )
    phase_excluded = (
        rows.filter(pl.col("_emit") & ~pl.col("temporal_phase").is_in(list(include_phases))).height
        if "temporal_phase" in rows.columns else 0
    )
    matched_emitted = total - unmatched - non_emitted
    records = []
    for reason, count in [
        ("unmatched_vocab_source_key", unmatched),
        ("non_emitted", non_emitted),
        ("temporal_phase_excluded", phase_excluded),
        ("matched_emitted_before_phase_filter", matched_emitted),
    ]:
        if count:
            records.append({"source_table": table, "exclusion_reason": reason, "row_count": int(count)})
    return records


def counts_dict(df: pl.DataFrame, column: str) -> dict[str, int]:
    if df.is_empty() or column not in df.columns:
        return {}
    return {
        str(r[column]): int(r["count"])
        for r in df.group_by(column).len(name="count").sort("count", descending=True).iter_rows(named=True)
    }
