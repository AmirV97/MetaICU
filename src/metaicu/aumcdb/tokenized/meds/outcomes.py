"""Death-event assignment and cohort metadata for Amsterdam MEDS outputs."""

from __future__ import annotations

from pathlib import Path

import polars as pl

DEATH_TOKEN_WINDOW_HOURS = 24.0


def assign_death_outcomes(admissions: pl.DataFrame) -> pl.DataFrame:
    """Assign each recorded death to at most one ICU admission.

    Death dates in AmsterdamUMCdb are coarse and can precede ICU admission by
    less than one day. A death from 24 hours before admission through ICU
    discharge is therefore treated as occurring during that stay and emitted at
    the administrative discharge timestamp. Otherwise, the death is assigned to
    the latest preceding ICU stay. It is emitted only when the recorded death
    time is no more than 24 hours after discharge.
    """
    if admissions.is_empty():
        return admissions.with_columns(
            [
                pl.lit(None).cast(pl.Datetime("us")).alias("assigned_death_time"),
                pl.lit("no_death_recorded").alias("death_relation"),
                pl.lit(None).cast(pl.Float64).alias("hours_discharge_to_death"),
                pl.lit(False).alias("death_token_emitted"),
                pl.lit(None).cast(pl.Datetime("us")).alias("death_token_time"),
            ]
        )

    required = {
        "subject_id",
        "hadm_id",
        "admittedattime",
        "dischargedattime",
        "dateofdeathtime",
    }
    missing = sorted(required - set(admissions.columns))
    if missing:
        raise ValueError(f"Admissions are missing death-assignment columns: {missing}")

    base = admissions.with_columns(
        [
            pl.col("subject_id").cast(pl.Int64),
            pl.col("hadm_id").cast(pl.Int64),
            pl.col("admittedattime").cast(pl.Datetime("us")),
            pl.col("dischargedattime").cast(pl.Datetime("us")),
            pl.col("dateofdeathtime").cast(pl.Datetime("us")),
        ]
    )
    subject_deaths = base.group_by("subject_id").agg(
        pl.col("dateofdeathtime").drop_nulls().min().alias("assigned_death_time")
    )
    candidates = base.join(subject_deaths, on="subject_id", how="left")

    during = (
        candidates.filter(
            pl.col("assigned_death_time").is_not_null()
            & pl.col("admittedattime").is_not_null()
            & pl.col("dischargedattime").is_not_null()
            & (
                pl.col("assigned_death_time")
                >= pl.col("admittedattime") - pl.duration(hours=24)
            )
            & (pl.col("assigned_death_time") <= pl.col("dischargedattime"))
        )
        .sort(["subject_id", "admittedattime", "hadm_id"])
        .unique(subset=["subject_id"], keep="last", maintain_order=True)
        .select(
            [
                "subject_id",
                "hadm_id",
                "assigned_death_time",
                "dischargedattime",
            ]
        )
        .with_columns(
            [
                pl.lit("during_icu").alias("death_relation"),
                (
                    (
                        pl.col("assigned_death_time") - pl.col("dischargedattime")
                    ).dt.total_seconds()
                    / 3600
                ).alias("hours_discharge_to_death"),
                pl.lit(True).alias("death_token_emitted"),
                pl.col("dischargedattime").alias("death_token_time"),
            ]
        )
    )

    during_subjects = during.select("subject_id")
    after = (
        candidates.join(during_subjects, on="subject_id", how="anti")
        .filter(
            pl.col("assigned_death_time").is_not_null()
            & pl.col("dischargedattime").is_not_null()
            & (pl.col("assigned_death_time") > pl.col("dischargedattime"))
        )
        .sort(["subject_id", "dischargedattime", "hadm_id"])
        .unique(subset=["subject_id"], keep="last", maintain_order=True)
        .select(
            [
                "subject_id",
                "hadm_id",
                "assigned_death_time",
                "dischargedattime",
            ]
        )
        .with_columns(
            (
                (
                    pl.col("assigned_death_time") - pl.col("dischargedattime")
                ).dt.total_seconds()
                / 3600
            ).alias("hours_discharge_to_death")
        )
        .with_columns(
            [
                pl.when(pl.col("hours_discharge_to_death") <= DEATH_TOKEN_WINDOW_HOURS)
                .then(pl.lit("within_24h_after_discharge"))
                .otherwise(pl.lit("more_than_24h_after_discharge"))
                .alias("death_relation"),
                (pl.col("hours_discharge_to_death") <= DEATH_TOKEN_WINDOW_HOURS).alias(
                    "death_token_emitted"
                ),
                pl.when(pl.col("hours_discharge_to_death") <= DEATH_TOKEN_WINDOW_HOURS)
                .then(pl.col("assigned_death_time"))
                .otherwise(pl.lit(None).cast(pl.Datetime("us")))
                .alias("death_token_time"),
            ]
        )
    )

    assignments = pl.concat([during, after], how="diagonal_relaxed").select(
        [
            "subject_id",
            "hadm_id",
            "assigned_death_time",
            "death_relation",
            "hours_discharge_to_death",
            "death_token_emitted",
            "death_token_time",
        ]
    )
    return base.join(
        assignments, on=["subject_id", "hadm_id"], how="left"
    ).with_columns(
        [
            pl.col("death_relation").fill_null("no_death_recorded"),
            pl.col("death_token_emitted").fill_null(False),
        ]
    )


def build_admissions_metadata(admissions: pl.DataFrame) -> pl.DataFrame:
    """Build one metadata row per ICU admission."""
    assigned = assign_death_outcomes(admissions)
    los = (
        pl.col("true_los_hours").cast(pl.Float64)
        if "true_los_hours" in assigned.columns
        else (
            (pl.col("dischargedattime") - pl.col("admittedattime")).dt.total_seconds()
            / 3600
        )
    )
    optional = {
        "admissioncount": pl.Int64,
        "weightgroup": pl.String,
        "heightgroup": pl.String,
        "split": pl.String,
    }
    for column, dtype in optional.items():
        if column not in assigned.columns:
            assigned = assigned.with_columns(pl.lit(None).cast(dtype).alias(column))
    return assigned.select(
        [
            pl.col("subject_id").cast(pl.Int64),
            pl.col("hadm_id").cast(pl.Int64),
            pl.col("stay_id").cast(pl.Int64).alias("icustay_id"),
            pl.col("admissioncount").cast(pl.Int64).alias("admission_count"),
            pl.col("split").cast(pl.String),
            pl.col("admittedattime").cast(pl.Datetime("us")).alias("admission_time"),
            pl.col("dischargedattime").cast(pl.Datetime("us")).alias("discharge_time"),
            los.alias("icu_los_hours"),
            pl.col("weightgroup").cast(pl.String),
            pl.col("heightgroup").cast(pl.String),
            pl.col("assigned_death_time").alias("death_time"),
            pl.col("death_relation"),
            pl.col("hours_discharge_to_death").cast(pl.Float64),
            pl.col("death_token_emitted").cast(pl.Boolean),
            pl.col("death_token_time"),
        ]
    ).sort(["subject_id", "admission_count", "admission_time", "hadm_id"])


def build_subjects_metadata(
    admissions: pl.DataFrame,
    patients: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Build one metadata row per subject, retaining all recorded death dates."""
    assigned = assign_death_outcomes(admissions)
    first_context = (
        assigned.sort(["subject_id", "admittedattime", "hadm_id"])
        .unique(subset=["subject_id"], keep="first", maintain_order=True)
        .select(
            [
                "subject_id",
                pl.col("split").cast(pl.String)
                if "split" in assigned.columns
                else pl.lit(None).cast(pl.String).alias("split"),
                pl.col("gender").cast(pl.String)
                if "gender" in assigned.columns
                else pl.lit(None).cast(pl.String).alias("gender"),
                pl.col("agegroup").cast(pl.String)
                if "agegroup" in assigned.columns
                else pl.lit(None).cast(pl.String).alias("agegroup"),
            ]
        )
    )
    summary = (
        assigned.group_by("subject_id")
        .agg(
            [
                pl.col("dateofdeathtime").drop_nulls().min().alias("dateofdeath"),
                pl.col("admittedattime").min().alias("first_admission_time"),
                pl.col("dischargedattime").max().alias("last_discharge_time"),
                pl.len().alias("n_admissions"),
            ]
        )
        .join(first_context, on="subject_id", how="left")
    )

    if patients is not None and not patients.is_empty():
        patient_columns = ["subject_id"]
        for column in ["dateofbirth", "dateofbirth_is_approx"]:
            if column in patients.columns:
                patient_columns.append(column)
        patient_context = patients.select(patient_columns).unique(
            subset=["subject_id"], keep="first"
        )
        summary = summary.join(patient_context, on="subject_id", how="left")

    if "dateofbirth" not in summary.columns:
        summary = summary.with_columns(
            pl.lit(None).cast(pl.Datetime("us")).alias("dateofbirth")
        )
    if "dateofbirth_is_approx" not in summary.columns:
        summary = summary.with_columns(
            pl.lit(None).cast(pl.Boolean).alias("dateofbirth_is_approx")
        )
    return summary.select(
        [
            pl.col("subject_id").cast(pl.Int64),
            pl.col("split").cast(pl.String),
            pl.col("gender").cast(pl.String),
            pl.col("agegroup").cast(pl.String),
            pl.col("dateofbirth").cast(pl.Datetime("us")),
            pl.col("dateofbirth_is_approx").cast(pl.Boolean),
            pl.col("dateofdeath").cast(pl.Datetime("us")),
            pl.col("first_admission_time").cast(pl.Datetime("us")),
            pl.col("last_discharge_time").cast(pl.Datetime("us")),
            pl.col("n_admissions").cast(pl.Int64),
        ]
    ).sort("subject_id")


def write_cohort_metadata(
    admissions: pl.DataFrame,
    metadata_dir: Path,
    patients: pl.DataFrame | None = None,
) -> dict[str, Path]:
    """Write canonical subject- and admission-level Parquet metadata."""
    metadata_dir.mkdir(parents=True, exist_ok=True)
    subjects_path = metadata_dir / "subjects.parquet"
    admissions_path = metadata_dir / "admissions.parquet"
    build_subjects_metadata(admissions, patients).write_parquet(subjects_path)
    build_admissions_metadata(admissions).write_parquet(admissions_path)
    return {"subjects_metadata": subjects_path, "admissions_metadata": admissions_path}
