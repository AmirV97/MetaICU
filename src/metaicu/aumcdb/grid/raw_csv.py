"""
Raw AmsterdamUMCdb CSV ingestion -- replaces the dependency on amsterdam_pipeline's
precomputed pre_meds_full parquet layer (which required running that separate, now-superseded
pipeline first). Reads directly from the user-supplied AmsterdamUMCdb raw CSV directory and
derives the same admission-relative timing columns amsterdam_pipeline's transforms computed
(admission_relative_ms = measuredat - admittedat, etc.) -- confirmed against AUMC_pipeline's
own equivalent derivation (pre_meds/common.py's add_measurement_times/add_interval_times) to
make sure the formulas match a working prior implementation, not just my own assumption. Every
downstream grid.extract_*/grid.sampling module's logic (itemid filtering, formulas, hour
binning) is unchanged -- only this data-access layer differs from the parquet-based version.

Encoding: raw AmsterdamUMCdb CSVs are latin-1 (confirmed via AUMC_pipeline's pandas
`encoding="latin1"` reads). Polars' scan_csv only supports 'utf8'/'utf8-lossy' (no true
latin-1 option -- checked directly against polars._typing.CsvEncoding), so 'utf8-lossy' is
used here: non-ASCII bytes in free-text label/comment columns render as replacement
characters, but no extraction logic in this pipeline reads those columns programmatically
(all label-based decisions were finalized during manifest review) -- only itemid/
ordercategoryid/numeric values/timestamps matter downstream, all pure ASCII regardless.

Known cost: numericitems.csv alone is ~80GB with no column stats/indexing (unlike parquet),
so any itemid-filtered scan of it still has to parse every row -- inherently much heavier
than the parquet-based approach it replaces. Run via sbatch with a generous --time budget,
never on the login node.
"""
import logging
from pathlib import Path

import polars as pl

HOUR_MS = 3_600_000
log = logging.getLogger(__name__)

TABLE_FILES = {
    "admissions": "admissions.csv",
    "numericitems": "numericitems.csv",
    "listitems": "listitems.csv",
    "drugitems": "drugitems.csv",
    "freetextitems": "freetextitems.csv",
    "processitems": "processitems.csv",
    "procedureorderitems": "procedureorderitems.csv",
}

# which raw column each table's "when did this happen" derives from, matching
# AUMC_pipeline's pre_meds/common.py add_measurement_times (measuredat) and
# pre_meds/interval_tables.py's procedureorderitems handling (registeredat)
MEASURED_AT_COL = {
    "numericitems": "measuredat",
    "listitems": "measuredat",
    "freetextitems": "measuredat",
    "procedureorderitems": "registeredat",
}
# interval tables derive both ends, matching pre_meds/common.py's add_interval_times
INTERVAL_COLS = {
    "drugitems": ("start", "stop"),
    "processitems": ("start", "stop"),
}
# AmsterdamUMCdb's "future-leak" placeholder timestamp. Confirmed by direct comparison against
# amsterdam_pipeline's parquet output (regression-checked this session) that only
# numericitems/listitems/freetextitems' transform (utils/pre_meds.py's
# filter_measuredat_sentinel) actually DROPS measuredat==-1899 rows -- processitems/
# procedureorderitems' transforms only COUNT these as an audit metric
# (transforms/process_tables.py's time_anomalies), they never filter them. Replicating that
# exact asymmetry here, not applying the filter uniformly to every table.
SENTINEL = -1899
SENTINEL_FILTERED_TABLES = {"numericitems", "listitems", "freetextitems"}

# Explicit dtype overrides, not inference (job 534384 failed on exactly this: polars'
# scan_csv guesses a column's dtype from the first `infer_schema_length` rows -- numericitems'
# `value` column looked all-integer early in the 80GB file, then hit a genuine float
# (-0.2) later and hard-crashed. AUMC_pipeline avoids this the same way -- explicit per-table
# schemas (pre_meds/common.py's LARGE_TABLE_RAW_SCHEMAS), not relying on inference over a
# huge file. Only columns at real risk of int/float ambiguity are listed; integer id/timestamp
# columns and text columns are left to inference.
SCHEMA_OVERRIDES = {
    "numericitems": {"value": pl.Float64},
    "drugitems": {"rate": pl.Float64, "dose": pl.Float64, "administered": pl.Float64,
                  "solutionadministered": pl.Float64, "fluidin": pl.Float64, "doserateperkg": pl.Float64},
    "admissions": {"dateofdeath": pl.Float64},
}


def admission_filter(admission_ids):
    """Shared by every grid.extract_* module's raw-table scans -- pl.lit(True) (no-op) when
    admission_ids is None (full population), else an is_in() restriction."""
    return pl.col("admissionid").is_in(list(admission_ids)) if admission_ids is not None else pl.lit(True)


def load_admissions(raw_data_dir):
    """Full read of admissions.csv (small, ~2.8MB) -- computes true_los_hours the same way
    amsterdam_pipeline's AdmissionsTransform did: (dischargedat - admittedat) / 3_600_000."""
    path = Path(raw_data_dir) / TABLE_FILES["admissions"]
    df = pl.read_csv(path, encoding="utf8-lossy", schema_overrides=SCHEMA_OVERRIDES.get("admissions"))
    df = df.with_columns(
        ((pl.col("dischargedat") - pl.col("admittedat")) / HOUR_MS).alias("true_los_hours")
    )
    log.info(f"admissions.csv: {df.height} rows, {df['admissionid'].n_unique()} distinct admissions")
    return df


def scan_raw_table(raw_data_dir, table, admissions):
    """admissions: DataFrame from load_admissions(), used to join admittedat onto every event
    row before deriving admission-relative timing. Returns a LazyFrame with the same derived
    columns (admission_relative_ms, or start_/stop_admission_relative_ms) that the previous
    parquet-based code expected from amsterdam_pipeline's pre_meds_full layer -- callers don't
    need to know whether the data came from raw CSV or parquet."""
    path = Path(raw_data_dir) / TABLE_FILES[table]
    lf = pl.scan_csv(path, encoding="utf8-lossy", schema_overrides=SCHEMA_OVERRIDES.get(table))
    anchors = admissions.lazy().select("admissionid", "admittedat")
    lf = lf.join(anchors, on="admissionid", how="inner")

    if table in MEASURED_AT_COL:
        col = MEASURED_AT_COL[table]
        if table in SENTINEL_FILTERED_TABLES:
            lf = lf.filter(pl.col(col).is_null() | (pl.col(col) != SENTINEL))
        lf = lf.with_columns((pl.col(col) - pl.col("admittedat")).alias("admission_relative_ms"))
    elif table in INTERVAL_COLS:
        start_col, stop_col = INTERVAL_COLS[table]
        lf = lf.with_columns(
            (pl.col(start_col) - pl.col("admittedat")).alias("start_admission_relative_ms"),
            (pl.col(stop_col) - pl.col("admittedat")).alias("stop_admission_relative_ms"),
        )
    return lf
