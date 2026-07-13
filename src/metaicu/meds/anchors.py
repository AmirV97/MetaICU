"""Admission sampling and anchor/context event generation.

Produces ICU_ADMISSION, ICU_DISCHARGE, MEDS_DEATH, and demographic static
context tokens (GENDER, AGEGROUP, WEIGHTGROUP, HEIGHTGROUP) from the pre-MEDS
admissions parquet.
"""

from __future__ import annotations

import random
from pathlib import Path

import polars as pl

from metaicu.meds.common import coerce_debug_frame, empty_debug_frame
from metaicu.utils.parquet_datasets import resolve_table_parquet, scan_parquet


def sample_admissions(
    pre_meds_dir: Path,
    mode: str,
    num_patients: int | None,
    seed: int,
) -> pl.DataFrame:
    """Load admissions from pre-MEDS parquet, optionally drawing a seeded subset.

    'full' mode returns all admissions present in the pre-MEDS directory.
    'bounded' mode draws a random sample of num_patients subjects (seeded).
    The pre-MEDS parquet may already be bounded; this is a secondary sample
    within whatever subjects are available.
    """
    admissions = scan_parquet(resolve_table_parquet(pre_meds_dir, "admissions")).collect()
    if mode == "bounded" and num_patients is not None:
        subjects = (
            admissions.select("subject_id")
            .drop_nulls()
            .unique()
            .sort("subject_id")
            .to_series()
            .to_list()
        )
        rng = random.Random(seed)
        rng.shuffle(subjects)
        sampled = subjects[: min(num_patients, len(subjects))]
        admissions = admissions.filter(pl.col("subject_id").is_in(sampled))
    return admissions.sort(["subject_id", "admissioncount", "admissionid"])


def anchor_and_context_events(admissions: pl.DataFrame) -> pl.DataFrame:
    """Generate per-admission anchor and static context events from admissions.

    Emits:
      ICU_ADMISSION  — stream anchor; token_role=static_context
      ICU_DISCHARGE  — outcome token; excluded from predictor streams by phase filter
      MEDS_DEATH     — outcome token; excluded from predictor streams by phase filter
      GENDER//...    — static demographic context
      AGEGROUP//...  — static demographic context
      WEIGHTGROUP//..— static demographic context
      HEIGHTGROUP//..— static demographic context

    Note: ICU_DISCHARGE and MEDS_DEATH carry token_role='outcome' and
    temporal_phase='outcome'. They are written to the debug parquet and sorted
    last in the timeline. Training code must exclude them when outcome=label.
    """
    base = admissions.select([
        "subject_id", "admissionid", "hadm_id", "stay_id",
        "admittedattime", "dischargedattime", "dateofdeathtime",
        "gender", "agegroup", "weightgroup", "heightgroup",
    ])
    frames: list[pl.DataFrame] = []

    frames.append(coerce_debug_frame(
        base.with_columns([
            pl.col("admittedattime").alias("time"),
            pl.lit("ICU_ADMISSION").alias("code"),
            pl.lit("admissions").alias("source_table"),
            pl.lit("static_context").alias("token_role"),
            pl.lit("admission").alias("temporal_phase"),
        ])
    ))
    frames.append(coerce_debug_frame(
        base.filter(pl.col("dischargedattime").is_not_null()).with_columns([
            pl.col("dischargedattime").alias("time"),
            pl.lit("ICU_DISCHARGE").alias("code"),
            pl.lit("admissions").alias("source_table"),
            pl.lit("outcome").alias("token_role"),
            pl.lit("outcome").alias("temporal_phase"),
        ])
    ))
    frames.append(coerce_debug_frame(
        base.filter(pl.col("dateofdeathtime").is_not_null()).with_columns([
            pl.col("dateofdeathtime").alias("time"),
            pl.lit("MEDS_DEATH").alias("code"),
            pl.lit("patient").alias("source_table"),
            pl.lit("outcome").alias("token_role"),
            pl.lit("outcome").alias("temporal_phase"),
        ])
    ))

    for col, prefix in [
        ("gender", "GENDER"),
        ("agegroup", "AGEGROUP"),
        ("weightgroup", "WEIGHTGROUP"),
        ("heightgroup", "HEIGHTGROUP"),
    ]:
        frames.append(coerce_debug_frame(
            base.filter(pl.col(col).is_not_null()).with_columns([
                pl.col("admittedattime").alias("time"),
                (pl.lit(prefix + "//") + pl.col(col).cast(pl.String)).alias("code"),
                pl.lit("admissions").alias("source_table"),
                pl.lit("static_context").alias("token_role"),
                pl.lit("admission").alias("temporal_phase"),
                pl.col(col).cast(pl.String).alias("source_value"),
            ])
        ))

    non_empty = [f for f in frames if not f.is_empty()]
    if not non_empty:
        return empty_debug_frame()
    return pl.concat(non_empty, how="vertical_relaxed")
