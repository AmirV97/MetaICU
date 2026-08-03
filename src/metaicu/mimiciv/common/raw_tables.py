"""Shared MIMIC-IV raw-table access with optional large-table parquet caches. Mirrors
metaicu.aumcdb.common.raw_tables's role and interface -- scan_raw_table takes no itemids/
admission_ids: those restrictions now live downstream in each grid.build.extract_* module's own
.filter() call (matches aumcdb's safety property -- a persistent cache built once must never
itself decide which itemids matter, or it silently goes stale on the next manifest revision)."""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

from metaicu.mimiciv.common.raw_shards import raw_shards_exist

HOUR_MS = 3_600_000
log = logging.getLogger(__name__)

# large tables, optionally served from a persistent parquet-shard cache (see raw_shards.py) --
# confirmed via the reviewed manifest that only these 5 have any kept match (raw_schema.py).
TABLE_FILES = {
    "chartevents": "icu/chartevents.csv.gz",
    "labevents": "hosp/labevents.csv.gz",
    "inputevents": "icu/inputevents.csv.gz",
    "outputevents": "icu/outputevents.csv.gz",
    "procedureevents": "icu/procedureevents.csv.gz",
}

# which column each table's "when did this happen" derives from (point-in-time tables), or the
# (start, end) column pair (interval tables)
TIME_COL = {
    "chartevents": "charttime",
    "labevents": "charttime",
    "outputevents": "charttime",
}
INTERVAL_COLS = {
    "inputevents": ("starttime", "endtime"),
    "procedureevents": ("starttime", "endtime"),
}


def admission_filter(admission_ids) -> pl.Expr:
    """Shared by every grid.build.extract_* module's raw-table scans -- pl.lit(True) (no-op)
    when admission_ids is None (full population), else an is_in() restriction on stay_id."""
    return pl.col("admissionid").is_in(list(admission_ids)) if admission_ids is not None else pl.lit(True)


def load_admissions(raw_data_dir: Path) -> pl.DataFrame:
    """One row per ICU stay: admissionid(=stay_id), subject_id, hadm_id, intime, true_los_hours
    (icustays.los is already in days), plus the demographic/admission columns grid.build.
    extract_static needs (admission_type/admission_location/race from admissions.csv.gz,
    gender/year_of_birth from patients.parquet) and hospital_expire_flag (in-hospital mortality
    outcome, grid.build.split's metadata.csv sidecar) -- joined once here so callers get a
    single wide frame. Always a direct small-table read, never cached -- icustays/admissions/
    patients are tiny (MB, not GB) regardless of population size."""

    icustays = pl.read_csv(raw_data_dir / "icu/icustays.csv.gz").with_columns(
        pl.col("intime").str.to_datetime(),
        pl.col("outtime").str.to_datetime(),
        (pl.col("los") * 24.0).alias("true_los_hours"),
    ).rename({"stay_id": "admissionid"})

    admissions = pl.read_csv(raw_data_dir / "hosp/admissions.csv.gz").with_columns(
        pl.col("admittime").str.to_datetime(),
    ).select("subject_id", "hadm_id", "admittime", "admission_type", "admission_location", "race",
             "hospital_expire_flag")

    patients = pl.read_parquet(raw_data_dir / "hosp/patients.parquet").select(
        "subject_id", "gender", "year_of_birth"
    )

    df = icustays.join(admissions, on=["subject_id", "hadm_id"], how="left").join(patients, on="subject_id", how="left")
    log.info(f"icustays: {df.height} rows, {df['admissionid'].n_unique()} distinct stays, "
              f"{df['subject_id'].n_unique()} distinct subjects")
    return df


def raw_table_input_mode(table: str, raw_shards_dir: Path | None) -> str:
    if raw_shards_dir is not None and raw_shards_exist(raw_shards_dir, table):
        return "raw_parquet_shards"
    return "raw_csv_scan"


def _parsed_datetime(lf: pl.LazyFrame, column: str) -> pl.Expr:
    """Shard-cache rows already have this column as pl.Datetime (parsed once at build time,
    see raw_schema.cast_raw_schema); the raw-CSV-scan fallback still has the raw ISO string and
    needs str.to_datetime() here instead."""
    dtype = lf.collect_schema()[column]
    return pl.col(column) if dtype == pl.Datetime else pl.col(column).str.to_datetime(strict=False)


def scan_raw_table(
    raw_data_dir: Path,
    table: str,
    admissions: pl.DataFrame,
    raw_shards_dir: Path | None = None,
) -> pl.LazyFrame:
    """admissions: DataFrame from load_admissions(), used to anchor admission_relative_ms.
    Returns a LazyFrame with admission_relative_ms (point tables) or start_/stop_
    admission_relative_ms (interval tables) -- same shape grid.build.extract_* expects
    regardless of whether this table came through the parquet-shard cache or a direct CSV scan.
    chartevents/labevents (3.5GB/2.6GB compressed) MUST go through the shard cache -- a direct
    pl.scan_csv on either .gz OOM-killed even a schema-only read at 64G (polars can't do true
    seekable/lazy gzip decompression); inputevents/outputevents/procedureevents are small enough
    for either path."""

    if raw_table_input_mode(table, raw_shards_dir) == "raw_parquet_shards":
        lf = pl.scan_parquet(Path(raw_shards_dir) / table)
    else:
        lf = pl.scan_csv(raw_data_dir / TABLE_FILES[table], infer_schema_length=None)

    anchors = admissions.lazy().select("admissionid", "subject_id", "hadm_id", "intime")
    # labevents has no stay_id column (it's a hosp-level table, not ICU-scoped) -- join on
    # (subject_id, hadm_id) only; every other event table carries stay_id directly.
    if "stay_id" in lf.collect_schema().names():
        lf = lf.rename({"stay_id": "admissionid"}).join(anchors, on=["admissionid", "subject_id", "hadm_id"], how="inner")
    else:
        lf = lf.join(anchors, on=["subject_id", "hadm_id"], how="inner")

    if table in TIME_COL:
        lf = lf.with_columns(_parsed_datetime(lf, TIME_COL[table]).alias("_t"))
        lf = lf.with_columns(
            (pl.col("_t") - pl.col("intime")).dt.total_milliseconds().alias("admission_relative_ms")
        )
    elif table in INTERVAL_COLS:
        start_col, stop_col = INTERVAL_COLS[table]
        lf = lf.with_columns(_parsed_datetime(lf, start_col).alias("_start"), _parsed_datetime(lf, stop_col).alias("_stop"))
        lf = lf.with_columns(
            (pl.col("_start") - pl.col("intime")).dt.total_milliseconds().alias("start_admission_relative_ms"),
            (pl.col("_stop") - pl.col("intime")).dt.total_milliseconds().alias("stop_admission_relative_ms"),
        )
    return lf
