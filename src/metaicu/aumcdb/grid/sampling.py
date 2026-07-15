"""
Admission subsampling for bounded test runs. Returns either a concrete set of admissionids
(bounded run) or None (meaning "no restriction, full population" -- kept as a distinct value
rather than "all valid ids" so callers can skip the is_in() filter entirely on a full run
instead of materializing a ~23k-element IN-list).

Valid-LOS filter matches the one used throughout this session (true_los_hours not null and
> 0) -- admissions failing it were never included in any of this session's diagnostics either.
This is deliberately looser than iCareFM's actual LOS>=4h inclusion criterion (see
apply_inclusion_criteria below) -- kept as the cheap pre-extraction floor; the real >=4h/
>=4 measurements/max-gap<=48h filter needs extracted data and runs later.
"""
import logging
import random

import polars as pl

from .raw_csv import load_admissions

log = logging.getLogger(__name__)


def load_valid_admissions(raw_data_dir):
    """Full admissions table (grid.raw_csv.load_admissions -- admissionid, patientid,
    admittedat, dateofdeath, true_los_hours, etc.), restricted to admissions with a valid
    (non-null, positive) LOS. Kept as the one DataFrame downstream code needs throughout:
    the admittedat join-anchor for grid.raw_csv.scan_raw_table, true_los_hours for
    grid.assemble, and patientid/dateofdeath for the metadata.csv sidecar."""
    df = load_admissions(raw_data_dir)
    df = df.filter(df["true_los_hours"].is_not_null() & (df["true_los_hours"] > 0))
    log.info(f"admissions with valid LOS: {df.height}")
    return df


def get_admission_ids(raw_data_dir, sample_size=None, seed=42, admission_ids_file=None):
    """Precedence: admission_ids_file > sample_size > None (full population).
    admission_ids_file: a text file with one admissionid per line."""
    valid = load_valid_admissions(raw_data_dir)
    valid_ids = set(valid["admissionid"].to_list())

    if admission_ids_file is not None:
        requested = {int(line.strip()) for line in open(admission_ids_file) if line.strip()}
        ids = requested & valid_ids
        missing = requested - valid_ids
        if missing:
            log.warning(f"{len(missing)} requested admission ids have no valid LOS or don't exist, dropped: "
                        f"{sorted(missing)[:20]}{'...' if len(missing) > 20 else ''}")
        log.info(f"Using {len(ids)} admissions from --admission-ids-file")
        return ids

    if sample_size is not None:
        if sample_size >= len(valid_ids):
            log.info(f"--sample-size {sample_size} >= population {len(valid_ids)}, using full population")
            return None
        rng = random.Random(seed)
        ids = set(rng.sample(sorted(valid_ids), sample_size))
        log.info(f"Sampled {len(ids)} admissions (seed={seed}) out of {len(valid_ids)} valid-LOS admissions")
        return ids

    log.info(f"No sampling requested, using full population ({len(valid_ids)} admissions)")
    return None


# iCareFM A.2.2 inclusion criteria defaults (icarefm_preprocessing_reference.md) -- LoS>=4h,
# >=4 measurements, max gap between measurements <=48h.
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
    """iCareFM's A.2.2 inclusion criteria, adopted 2026-07-15 -- see
    icarefm_preprocessing_reference.md's A.2.2 section for the full validation. "Measurements"
    means direct_numeric/derived_output_rate hours ONLY (numeric vitals/labs) -- empirically
    the closest match to the paper's reported UMCdb cohort size (Table S1: 22,883) by a wide
    margin over pooling every reconstruction type (off by ~7000 admissions) or observations
    including categorical (same). Matches A.2.4's own description of numeric physiological
    data as "observed continuously... with high frequency and density", unlike sparser
    categorical scores or event-driven treatments.

    admissions: DataFrame with admissionid/true_los_hours (already valid-LOS>0 filtered by
    load_valid_admissions). numeric_long: from grid.extract_numeric.extract_numeric_categorical
    (admissionid/tag/hour/agg_value) -- must be extracted BEFORE calling this (needs real
    per-hour data, not just admission metadata), and before grid.split.assign_splits (splits
    must be computed on the final, post-inclusion-criteria cohort, not before). matches: tag ->
    info dict from grid.manifest.parse_manifest().

    Returns admissions filtered to only the admissions passing all 3 criteria (LOS check +
    measurement count + max gap)."""
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
             f"admissions ({before - admissions.height} excluded)")
    return admissions
