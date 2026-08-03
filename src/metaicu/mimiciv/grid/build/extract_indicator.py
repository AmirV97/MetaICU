"""
treatment_indicator raw extraction: inputevents/procedureevents matches contribute [start,stop]
interval overlap with 1h admission-relative bins (hour = ms // 3_600_000); chartevents matches
contribute a point-in-time hour instead (no interval field). Per A.4.3
(icarefm_preprocessing_reference.md, same convention AUMC adopted), treatment indicators are
never forward-filled -- an hour with no covering event is simply Off, not carried-forward
state -- so the only output needed is the DISTINCT set of "On" hours per (tag, admissionid);
grid.assemble pivots this into the dense grid.

procedureevents is treated as an INTERVAL table here (it has starttime/endtime, e.g. "Dialysis -
CRRT" spans the session, not a single instant) -- unlike AUMC's procedureorderitems (point-only,
registeredat only), so this differs from AUMC_grid_pipeline/grid/extract_indicator.py's
POINT_TABLES set, which only had numericitems/listitems/procedureorderitems as point tables.
"""
import logging

import polars as pl

from .raw_csv import scan_raw_table, admission_filter

HOUR_MS = 3_600_000
POINT_TABLES = {"chartevents"}
INTERVAL_TABLES = {"inputevents", "procedureevents"}
TABLE_ALIASES = {
    "chartevents_main": "chartevents", "chartevents_value": "chartevents", "chartevents": "chartevents",
    "inputevents": "inputevents",
    "procedureevents": "procedureevents", "proc_itemid": "procedureevents",
}
log = logging.getLogger(__name__)


def _collect_matches(matches):
    """Returns table -> list[(tag, itemid)] for treatment_indicator matches, grouped by
    normalized physical table."""
    by_table = {}
    for tag, info in matches.items():
        if info["reconstruction_type"] != "treatment_indicator":
            continue
        for m in info["keep_matches"]:
            table = TABLE_ALIASES.get(m["table"])
            if table is None:
                log.warning(f"SKIPPED (unrecognized table for treatment_indicator): {tag} {m}")
                continue
            by_table.setdefault(table, []).append((tag, int(m["itemid"])))
    return by_table


def _point_on_hours(raw_data_dir, table, pairs, admissions, admission_ids, raw_shards_dir=None):
    itemids = list({i for _, i in pairs})
    lookup = pl.DataFrame({"itemid": [i for _, i in pairs], "tag": [t for t, _ in pairs]}, schema={"itemid": pl.Int64, "tag": pl.String}).unique()

    lf = scan_raw_table(raw_data_dir, table, admissions, raw_shards_dir)
    lf = lf.filter(
        pl.col("itemid").is_in(itemids) & (pl.col("admission_relative_ms") >= 0) & admission_filter(admission_ids)
    ).with_columns((pl.col("admission_relative_ms") // HOUR_MS).alias("hour"))
    df = lf.select(["admissionid", "itemid", "hour"]).collect(engine="streaming")
    df = df.join(lookup, on="itemid", how="inner")
    if df.height == 0:
        return None
    log.info(f"{table} (point) treatment_indicator rows: {df.height}")
    return df.select(["admissionid", "tag", "hour"])


def _interval_on_hours(raw_data_dir, table, pairs, admissions, admission_ids, raw_shards_dir=None):
    itemids = list({i for _, i in pairs})
    lookup = pl.DataFrame({"itemid": [i for _, i in pairs], "tag": [t for t, _ in pairs]}, schema={"itemid": pl.Int64, "tag": pl.String}).unique()

    lf = scan_raw_table(raw_data_dir, table, admissions, raw_shards_dir)
    df = lf.filter(
        pl.col("itemid").is_in(itemids) & (pl.col("stop_admission_relative_ms") >= 0) & admission_filter(admission_ids)
    ).collect(engine="streaming")
    df = df.join(lookup, on="itemid", how="inner")
    if df.height == 0:
        return None
    df = df.with_columns(
        pl.max_horizontal(pl.col("start_admission_relative_ms"), 0).alias("start_ms"),
    ).with_columns(
        (pl.col("start_ms") // HOUR_MS).alias("hour_start"),
    )
    df = df.with_columns(
        pl.when((pl.col("tag") == "samp") | (pl.col("stop_admission_relative_ms") <= pl.col("start_ms")))
        .then(pl.col("hour_start") + 1)
        .otherwise((pl.col("stop_admission_relative_ms") + HOUR_MS - 1) // HOUR_MS)
        .alias("hour_stop")
    )
    df = df.with_columns(pl.int_ranges(pl.col("hour_start"), pl.col("hour_stop")).alias("hour")).explode("hour")
    log.info(f"{table} (interval) treatment_indicator rows: {df.height}")
    return df.select(["admissionid", "tag", "hour"])


def extract_treatment_indicator(matches, raw_data_dir, admissions, admission_ids=None, raw_shards_dir=None):
    """matches: tag -> feature info dict, from grid.manifest.parse_manifest(). admissions:
    DataFrame from grid.raw_csv.load_admissions(). admission_ids: optional iterable to restrict
    to; None = full population. Returns a single (admissionid, tag, hour) DataFrame of distinct
    "On" hours, or None if no matches at all."""
    by_table = _collect_matches(matches)
    log.info(f"treatment_indicator tables in scope: {sorted(by_table)}")

    parts = []
    for table, pairs in by_table.items():
        builder = _point_on_hours if table in POINT_TABLES else _interval_on_hours
        part = builder(raw_data_dir, table, pairs, admissions, admission_ids, raw_shards_dir)
        if part is not None:
            parts.append(part)

    if not parts:
        return None
    on_hours = pl.concat(parts).unique()
    log.info(f"treatment_indicator on_hours: {on_hours.height} distinct (tag,admissionid,hour) rows, "
             f"{on_hours['tag'].n_unique()} tags")
    return on_hours
