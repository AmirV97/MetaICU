"""
ICU-stay subsampling for bounded test runs -- mirrors AUMC_grid_pipeline/grid/sampling.py's
role and interface (get_admission_ids returns a concrete set of admissionids for a bounded
run, or None meaning "no restriction, full population"), adapted to MIMIC-IV's icustays.

Valid-LOS filter: true_los_hours not null and > 0 (same cheap floor AUMC used) -- the real
iCareFM inclusion criteria (LOS>=4h, >=4 measurements, max gap<=48h) needs extracted data and
runs later via apply_inclusion_criteria, same division of labor as AUMC's module.
"""
import logging
import random

import polars as pl

from .raw_csv import load_admissions

log = logging.getLogger(__name__)


def load_valid_admissions(raw_data_dir):
    """Full icustays-joined frame (grid.raw_csv.load_admissions -- admissionid=stay_id,
    subject_id, hadm_id, intime, true_los_hours, demographic columns), restricted to stays
    with a valid (non-null, positive) LOS."""
    df = load_admissions(raw_data_dir)
    df = df.filter(df["true_los_hours"].is_not_null() & (df["true_los_hours"] > 0))
    log.info(f"stays with valid LOS: {df.height}")
    return df


def get_admission_ids(raw_data_dir, sample_size=None, seed=42, admission_ids_file=None):
    """Precedence: admission_ids_file > sample_size > None (full population).
    admission_ids_file: a text file with one stay_id per line."""
    valid = load_valid_admissions(raw_data_dir)
    valid_ids = set(valid["admissionid"].to_list())

    if admission_ids_file is not None:
        requested = {int(line.strip()) for line in open(admission_ids_file) if line.strip()}
        ids = requested & valid_ids
        missing = requested - valid_ids
        if missing:
            log.warning(f"{len(missing)} requested stay ids have no valid LOS or don't exist, dropped: "
                        f"{sorted(missing)[:20]}{'...' if len(missing) > 20 else ''}")
        log.info(f"Using {len(ids)} stays from --admission-ids-file")
        return ids

    if sample_size is not None:
        if sample_size >= len(valid_ids):
            log.info(f"--sample-size {sample_size} >= population {len(valid_ids)}, using full population")
            return None
        rng = random.Random(seed)
        ids = set(rng.sample(sorted(valid_ids), sample_size))
        log.info(f"Sampled {len(ids)} stays (seed={seed}) out of {len(valid_ids)} valid-LOS stays")
        return ids

    log.info(f"No sampling requested, using full population ({len(valid_ids)} stays)")
    return None


# iCareFM A.2.2 inclusion criteria defaults, same as AUMC_grid_pipeline/grid/sampling.py
MIN_LOS_HOURS = 4.0
MIN_MEASUREMENTS = 4
MAX_GAP_HOURS = 48.0


def _max_gap_hours(sorted_hours):
    vals = [h for h in sorted_hours if h is not None]
    if len(vals) <= 1:
        return 0
    return int(max(b - a for a, b in zip(vals, vals[1:])))


def apply_inclusion_criteria(admissions, numeric_long, matches,
                              min_los_hours=MIN_LOS_HOURS, min_measurements=MIN_MEASUREMENTS,
                              max_gap_hours=MAX_GAP_HOURS):
    """Same iCareFM A.2.2 criteria as AUMC's version -- "measurements" means
    direct_numeric/derived_output_rate hours only. admissions: DataFrame with
    admissionid/true_los_hours (already valid-LOS>0 filtered by load_valid_admissions).
    numeric_long: from grid.extract_numeric.extract_numeric_categorical -- must be extracted
    BEFORE calling this. matches: tag -> info dict from grid.manifest.parse_manifest()."""
    numeric_lab_tags = {t for t, v in matches.items()
                         if v["reconstruction_type"] in ("direct_numeric", "derived_output_rate")}
    relevant = numeric_long.filter(pl.col("tag").is_in(numeric_lab_tags)).select(["admissionid", "hour"]).unique()

    per_adm = relevant.group_by("admissionid").agg(
        pl.col("hour").len().alias("n_measurements"),
        pl.col("hour").sort().alias("hours"),
    )
    max_gap = per_adm["hours"].map_elements(_max_gap_hours, return_dtype=pl.Int64)
    per_adm = per_adm.with_columns(max_gap.alias("max_gap_hours"))

    qualifying_ids = set(
        per_adm.filter(
            (pl.col("n_measurements") >= min_measurements) & (pl.col("max_gap_hours") <= max_gap_hours)
        )["admissionid"].to_list()
    )

    before = admissions.height
    admissions = admissions.filter(
        (pl.col("true_los_hours") >= min_los_hours) & pl.col("admissionid").is_in(list(qualifying_ids))
    )
    log.info(f"iCareFM inclusion criteria (LOS>={min_los_hours}h, >={min_measurements} numeric "
             f"vital/lab measurements, max gap<={max_gap_hours}h): {before} -> {admissions.height} "
             f"stays ({before - admissions.height} excluded)")
    return admissions
