"""Shared timing and admission-join helpers for Amsterdam pre-MEDS transforms."""

from __future__ import annotations

import polars as pl

from metaicu.aumcdb.common.raw_schema import LARGE_TABLE_RAW_SCHEMAS, cast_raw_schema


# Columns selected from admissions.parquet and joined to every event table.
ADMISSION_ANCHOR_COLUMNS = [
    "admissionid",
    "patientid",
    "subject_id",
    "hadm_id",
    "stay_id",
    "admittedat",
    "dischargedat",
    "admittedattime",
    "dischargedattime",
]


def admission_anchor_columns(anchors: pl.DataFrame) -> list[str]:
    """Return anchor columns available in this admission frame.

    Split-aware pre-MEDS runs add a small ``split`` column to admissions.
    The transform functions should carry it through joins when present, while
    preserving the previous flat-output behavior when it is absent.
    """
    columns = list(ADMISSION_ANCHOR_COLUMNS)
    if "split" in anchors.columns:
        columns.append("split")
    return columns

def filter_measuredat_sentinel(
    df: pl.DataFrame,
    sentinel: int = -1899,
) -> tuple[pl.DataFrame, int]:
    """Drop Amsterdam timing-unknown sentinel rows from measured event tables."""
    filtered = df.filter(
        pl.col("measuredat").is_null() | (pl.col("measuredat") != sentinel)
    )
    return filtered, int(df.height - filtered.height)


def join_admission_anchors(
    df: pl.DataFrame,
    anchors: pl.DataFrame,
    table_name: str,
) -> tuple[pl.DataFrame, int]:
    """Left-join source events to pre-loaded admission anchor columns.

    Missing join rows (null subject_id) are counted but kept; the caller
    decides whether to filter them out in bounded mode.
    """
    del table_name
    joined = df.join(anchors, on="admissionid", how="left")
    missing = int(joined.filter(pl.col("subject_id").is_null()).height)
    return joined, missing


def temporal_phase_expr(
    source_col: str,
    output_col: str = "event_temporal_phase",
) -> pl.Expr:
    """Classify event timing relative to the ICU admission window."""
    return (
        pl.when(
            pl.col(source_col).is_null()
            | pl.col("admittedat").is_null()
            | pl.col("dischargedat").is_null()
        )
        .then(pl.lit("unknown"))
        .when(pl.col(source_col) < pl.col("admittedat"))
        .then(pl.lit("preadmission"))
        .when(pl.col(source_col) > pl.col("dischargedat"))
        .then(pl.lit("postadmission"))
        .otherwise(pl.lit("admission"))
        .alias(output_col)
    )


def temporal_phase_counts(
    df: pl.DataFrame,
    column: str = "event_temporal_phase",
) -> dict[str, int]:
    if column not in df.columns:
        return {}
    return {
        str(row[column]): int(row["count"])
        for row in df.group_by(column).len(name="count").iter_rows(named=True)
    }


def add_measurement_times(df: pl.DataFrame) -> pl.DataFrame:
    """Add relative and synthetic wall-clock times for measured event tables.

    Requires: measuredat, registeredat, updatedat, admittedat, admittedattime.
    """
    return df.with_columns(
        (pl.col("measuredat") - pl.col("admittedat")).alias("admission_relative_ms"),
        (pl.col("registeredat") - pl.col("admittedat")).alias(
            "registered_admission_relative_ms"
        ),
        (pl.col("updatedat") - pl.col("admittedat")).alias(
            "updated_admission_relative_ms"
        ),
    ).with_columns(
        (
            pl.col("admittedattime")
            + pl.duration(milliseconds=pl.col("admission_relative_ms"))
        ).alias("measuredattime"),
        (
            pl.col("admittedattime")
            + pl.duration(milliseconds=pl.col("registered_admission_relative_ms"))
        ).alias("registeredattime"),
        (
            pl.col("admittedattime")
            + pl.duration(milliseconds=pl.col("updated_admission_relative_ms"))
        ).alias("updatedattime"),
        temporal_phase_expr("measuredat"),
    )


def add_interval_times(df: pl.DataFrame) -> pl.DataFrame:
    """Add relative and synthetic wall-clock times for interval event tables.

    Requires: start, stop, admittedat, dischargedat, admittedattime.
    Shared by drugitems and processitems.
    """
    return df.with_columns(
        (pl.col("start") - pl.col("admittedat")).alias("start_admission_relative_ms"),
        (pl.col("stop") - pl.col("admittedat")).alias("stop_admission_relative_ms"),
        temporal_phase_expr("start", "start_temporal_phase"),
        temporal_phase_expr("stop", "stop_temporal_phase"),
        temporal_phase_expr("start"),
    ).with_columns(
        (
            pl.col("admittedattime")
            + pl.duration(milliseconds=pl.col("start_admission_relative_ms"))
        ).alias("starttime"),
        (
            pl.col("admittedattime")
            + pl.duration(milliseconds=pl.col("stop_admission_relative_ms"))
        ).alias("stoptime"),
    )


def measurement_time_anomalies(df: pl.DataFrame) -> dict[str, int]:
    return {
        "negative_admission_relative_ms_rows": int(
            df.filter(pl.col("admission_relative_ms") < 0).height
        ),
        "measured_after_discharge_rows": int(
            df.filter(pl.col("measuredat") > pl.col("dischargedat")).height
        ),
        "null_measuredattime_rows": int(
            df.filter(pl.col("measuredattime").is_null()).height
        ),
    }


def interval_time_anomalies(df: pl.DataFrame) -> dict[str, int]:
    cols = set(df.columns)
    result: dict[str, int] = {}
    # drugitems / processitems have start/stop/starttime/stoptime
    if "start" in cols:
        result["null_start_rows"] = int(df.filter(pl.col("start").is_null()).height)
        result["null_stop_rows"] = int(df.filter(pl.col("stop").is_null()).height)
        result["stop_before_start_rows"] = int(
            df.filter(
                pl.col("start").is_not_null()
                & pl.col("stop").is_not_null()
                & (pl.col("stop") < pl.col("start"))
            ).height
        )
        result["negative_start_admission_relative_ms_rows"] = int(
            df.filter(pl.col("start_admission_relative_ms") < 0).height
        )
        result["null_starttime_rows"] = int(df.filter(pl.col("starttime").is_null()).height)
        result["null_stoptime_rows"] = int(df.filter(pl.col("stoptime").is_null()).height)
    # procedureorderitems uses registeredattime / admission_relative_ms
    if "registeredattime" in cols:
        result["null_registeredattime_rows"] = int(
            df.filter(pl.col("registeredattime").is_null()).height
        )
        result["negative_admission_relative_ms_rows"] = int(
            df.filter(pl.col("admission_relative_ms") < 0).height
        )
    return result
