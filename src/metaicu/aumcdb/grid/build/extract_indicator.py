"""
treatment_indicator raw extraction: drugitems/processitems matches contribute [start,stop]
interval overlap with 1h admission-relative bins (hour = ms // 3_600_000); numericitems/
listitems/procedureorderitems matches contribute a point-in-time hour instead, since none of
those three have an interval field. Per A.4.3 (icarefm_preprocessing_reference.md), treatment
indicators are never forward-filled -- an hour with no covering event is simply Off, not
carried-forward state -- so the only output needed is the DISTINCT set of "On" hours per
(tag, admissionid); grid.assemble pivots this into the dense grid (On for these hours, Off/0
elsewhere) without needing a separately-materialized dense frame here.

Refactor of ../extract_treatment_indicator.py into plain functions taking explicit params
(matches dict, raw_data_dir, admissions, optional admission_ids filter) instead of module-
level globals + a __main__ script. Adds procedureorderitems as a third point-event table
(needed for `samp`, reclassified from a bespoke 'microbiology' type to treatment_indicator
this session -- its 14 kept matches are all procedureorderitems, exactly the same "any row in
this hour = On" semantics as the existing numericitems/listitems point matches, just no
value/valueid column to carry -- procedureorderitems only has
admissionid/itemid/admission_relative_ms). Logic is otherwise unchanged from the parquet-based
version -- only the data-access layer (grid.raw_csv instead of utils.parquet_datasets)
differs, regression-checked against the original script's treatment_indicator_on_hours.parquet
output for the pre-existing 25 features.
"""
import logging

import polars as pl

from .raw_csv import scan_raw_table, admission_filter as _admission_filter

HOUR_MS = 3_600_000
POINT_TABLES = ("numericitems", "listitems", "procedureorderitems")
log = logging.getLogger(__name__)


def _load_matches(matches):
    """matches: tag -> feature info dict, from grid.manifest.parse_manifest()."""
    drugitems_matches, processitems_matches, point_matches = [], [], []
    for tag, info in matches.items():
        if info["reconstruction_type"] != "treatment_indicator":
            continue
        for m in info["keep_matches"]:
            if m["table"] == "drugitems":
                ocid = int(float(m["ordercategoryid"])) if m["ordercategoryid"] else None
                drugitems_matches.append((tag, int(m["itemid"]), ocid))
            elif m["table"] == "processitems":
                processitems_matches.append((tag, int(m["itemid"])))
            elif m["table"] in POINT_TABLES:
                point_matches.append((tag, m["table"], int(m["itemid"])))
            else:
                log.warning(f"SKIPPED (unexpected table for treatment_indicator): {tag} {m}")
    return drugitems_matches, processitems_matches, point_matches


def _interval_on_hours(df, tag_expr):
    """df must have start_admission_relative_ms/stop_admission_relative_ms + tag column."""
    df = df.filter(pl.col("stop_admission_relative_ms") >= 0)
    df = df.with_columns(
        pl.max_horizontal(pl.col("start_admission_relative_ms"), 0).alias("start_ms"),
    ).with_columns(
        (pl.col("start_ms") // HOUR_MS).alias("hour_start"),
        (pl.col("stop_admission_relative_ms") // HOUR_MS).alias("hour_end"),
    )
    df = df.with_columns(
        pl.int_ranges(pl.col("hour_start"), pl.col("hour_end") + 1).alias("hour")
    )
    return df.select(["admissionid", tag_expr, "hour"]).explode("hour")


def _build_drugitems_on_hours(
    matches, raw_data_dir, admissions, admission_ids, raw_shards_dir=None
):
    """An (itemid,ordercategoryid) pair can legitimately feed more than one indicator (e.g.
    Propofol under Spuitpompen counts for both prop_ind and the broader sed indicator) --
    join() fans this out into one row per tag automatically, no 1:1 assumption needed."""
    if not matches:
        return None
    itemids = list({itemid for _, itemid, _ in matches})
    lookup = pl.DataFrame(
        {"itemid": [itemid for _, itemid, _ in matches],
         "ordercategoryid": [ocid for _, _, ocid in matches],
         "tag": [tag for tag, _, _ in matches]}
    ).unique().with_columns(pl.col("ordercategoryid").cast(pl.Int64))

    lf = scan_raw_table(raw_data_dir, "drugitems", admissions, raw_shards_dir).filter(
        pl.col("itemid").is_in(itemids) & _admission_filter(admission_ids)
    ).select(["admissionid", "itemid", "ordercategoryid", "start_admission_relative_ms", "stop_admission_relative_ms"])
    df = lf.collect(engine="streaming")
    log.info(f"drugitems rows scanned (post-itemid-filter): {df.height}")

    df = df.join(lookup, on=["itemid", "ordercategoryid"], how="inner")
    return _interval_on_hours(df, "tag")


def _build_processitems_on_hours(
    matches, raw_data_dir, admissions, admission_ids, raw_shards_dir=None
):
    if not matches:
        return None
    itemid_to_tag = {}
    for tag, itemid in matches:
        itemid_to_tag.setdefault(itemid, set()).add(tag)
    for itemid, tags in itemid_to_tag.items():
        if len(tags) > 1:
            raise ValueError(f"processitems itemid {itemid} maps to multiple tags {tags}")
    itemid_to_tag = {k: next(iter(v)) for k, v in itemid_to_tag.items()}
    itemids = list(itemid_to_tag.keys())

    lf = scan_raw_table(raw_data_dir, "processitems", admissions, raw_shards_dir).filter(
        pl.col("itemid").is_in(itemids) & _admission_filter(admission_ids)
    ).select(["admissionid", "itemid", "start_admission_relative_ms", "stop_admission_relative_ms"])
    df = lf.collect(engine="streaming")
    log.info(f"processitems rows scanned (post-itemid-filter): {df.height}")

    df = df.with_columns(
        pl.col("itemid").replace_strict(itemid_to_tag, default=None, return_dtype=pl.Utf8).alias("tag")
    )
    return _interval_on_hours(df, "tag")


def _build_point_on_hours(
    matches, raw_data_dir, admissions, admission_ids, raw_shards_dir=None
):
    if not matches:
        return None
    by_table = {t: {} for t in POINT_TABLES}
    for tag, table, itemid in matches:
        by_table[table].setdefault(itemid, set()).add(tag)
    parts = []
    for table, itemid_to_tags in by_table.items():
        if not itemid_to_tags:
            continue
        for itemid, tags in itemid_to_tags.items():
            if len(tags) > 1:
                raise ValueError(f"{table} itemid {itemid} maps to multiple tags {tags}")
        itemid_to_tag = {k: next(iter(v)) for k, v in itemid_to_tags.items()}
        itemids = list(itemid_to_tag.keys())
        lf = scan_raw_table(raw_data_dir, table, admissions, raw_shards_dir).filter(
            pl.col("itemid").is_in(itemids) & (pl.col("admission_relative_ms") >= 0) & _admission_filter(admission_ids)
        ).select(["admissionid", "itemid", "admission_relative_ms"])
        df = lf.collect(engine="streaming")
        log.info(f"{table} (point-event indicator) rows scanned: {df.height}")
        df = df.with_columns(
            pl.col("itemid").replace_strict(itemid_to_tag, default=None, return_dtype=pl.Utf8).alias("tag"),
            (pl.col("admission_relative_ms") // HOUR_MS).alias("hour"),
        )
        parts.append(df.select(["admissionid", "tag", "hour"]))
    return pl.concat(parts) if parts else None


def extract_treatment_indicator(
    matches,
    raw_data_dir,
    admissions,
    admission_ids=None,
    raw_shards_dir=None,
):
    """matches: tag -> feature info dict, from grid.manifest.parse_manifest(). admissions:
    DataFrame from grid.raw_csv.load_admissions(). admission_ids: optional iterable to
    restrict extraction to; None = full population. Returns a single (admissionid, tag, hour)
    DataFrame of distinct "On" hours, or None if no matches at all."""
    drugitems_matches, processitems_matches, point_matches = _load_matches(matches)
    log.info(f"drugitems match count: {len(drugitems_matches)}, "
             f"processitems match count: {len(processitems_matches)}, "
             f"point ({'/'.join(POINT_TABLES)}) match count: {len(point_matches)}")

    parts = [p for p in [
        _build_drugitems_on_hours(
            drugitems_matches, raw_data_dir, admissions, admission_ids, raw_shards_dir
        ),
        _build_processitems_on_hours(
            processitems_matches, raw_data_dir, admissions, admission_ids, raw_shards_dir
        ),
        _build_point_on_hours(
            point_matches, raw_data_dir, admissions, admission_ids, raw_shards_dir
        ),
    ] if p is not None]
    if not parts:
        return None
    on_hours = pl.concat(parts).unique()
    log.info(f"treatment_indicator on_hours: {on_hours.height} distinct (tag,admissionid,hour) rows, "
             f"{on_hours['tag'].n_unique()} tags")
    return on_hours
