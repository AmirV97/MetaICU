"""
direct_numeric / derived_output_rate / categorical raw extraction: one batched scan per
physical table (chartevents, labevents, outputevents) across ALL matches that table has,
regardless of tag -- essential here since chartevents/labevents go through the expensive
awk-prefiltered path (grid.raw_csv.LARGE_TABLES); scanning once per tag would re-decompress
the whole file per tag instead of once per table. Mirrors AUMC_grid_pipeline/grid/
extract_numeric.py's "single grouped scan" pattern and output shape (numeric_long/
categorical_long), simplified where MIMIC's schema is simpler than AUMC's:
  - No listitems-style indirect value dictionary -- MIMIC's categorical tags (mgcs/vgcs/egcs/
    airway/rass) read chartevents' `value` column directly as the label string, no
    itemid+valueid -> standardized_label lookup needed.
  - Unit-conversion table (grid.unit_conversion_overrides, mirroring AUMC's own module)
    started 2026-07-31 with fio2's fraction/percent conditional fix -- still much smaller
    than AUMC's (target_unit vs each itemid's actual valueuom hasn't been cross-checked
    feature-by-feature beyond what the distribution-diff audit surfaced; flagged for a
    follow-up QC pass covering the rest of the manifest).

Aggregation: median per hour for numeric (direct_numeric/derived_output_rate), mode per hour
for categorical -- same as AUMC. Plausibility bounds (grid.plausibility_bounds, copied
verbatim from AUMC -- tag-keyed physiology bounds, dataset-agnostic) applied post-scan,
pre-aggregation, same step order as AUMC's A.4.1.
"""
import logging

import polars as pl

from .raw_csv import scan_raw_table, admission_filter
from .plausibility_bounds import resolve_bounds
from .unit_conversion_overrides import CONDITIONAL_PERCENT_ITEMIDS, CONDITIONAL_PERCENT_THRESHOLD

HOUR_MS = 3_600_000
log = logging.getLogger(__name__)

# Normalizes the several source_table aliases seen in the manifest (different upstream
# crosswalks/catalogs named the same physical table differently, e.g. "chartevents_main" vs
# "chartevents") to the table name grid.raw_csv.TABLE_FILES actually keys on.
TABLE_ALIASES = {
    "chartevents_main": "chartevents", "chartevents_value": "chartevents", "chartevents": "chartevents",
    "labs": "labevents", "labevents": "labevents",
    "outputevents": "outputevents",
}
# outputevents has no separate valuenum column -- its `value` IS the numeric reading.
VALUE_COLUMN = {"chartevents": "valuenum", "labevents": "valuenum", "outputevents": "value"}


def _collect_matches(matches):
    """Returns numeric_pairs/categorical_pairs: list of (tag, normalized_table, itemid), and
    label_map: dict[(itemid, raw_value) -> standardized_label] for categorical matches that
    declare a raw value/standardized label pair (collapsing multiple raw source values into one
    output category, e.g. airway's O2 Delivery Device(s) values -> Endotracheal tube/Tracheostomy/
    CPAP-NIV/No artificial airway). Matches without a standardized label pass their raw value
    through unchanged."""
    numeric_pairs, categorical_pairs, label_map = [], [], {}
    for tag, info in matches.items():
        rt = info["reconstruction_type"]
        if rt not in ("direct_numeric", "derived_output_rate", "categorical"):
            continue
        for m in info["keep_matches"]:
            table = TABLE_ALIASES.get(m["table"])
            if table is None:
                log.warning(f"SKIPPED (unrecognized table for {rt}): {tag} {m}")
                continue
            itemid = int(m["itemid"])
            (categorical_pairs if rt == "categorical" else numeric_pairs).append((tag, table, itemid))
            if rt == "categorical" and m.get("raw_value") and m.get("standardized_label"):
                label_map[(itemid, m["raw_value"])] = m["standardized_label"]
    return numeric_pairs, categorical_pairs, label_map


def _build_numeric_for_table(raw_data_dir, table, pairs, admissions, admission_ids, bounds, raw_shards_dir=None):
    """pairs: list of (tag, itemid) for this one physical table. A raw itemid can in principle
    feed more than one tag -- fan out via the lookup join, same reasoning as AUMC's
    _build_numeric_from_numericitems."""
    if not pairs:
        return None
    itemids = list({itemid for _, itemid in pairs})
    lookup = pl.DataFrame({"itemid": [i for _, i in pairs], "tag": [t for t, _ in pairs]}, schema={"itemid": pl.Int64, "tag": pl.String}).unique()

    lf = scan_raw_table(raw_data_dir, table, admissions, raw_shards_dir)
    value_col = VALUE_COLUMN[table]
    lf = lf.filter(
        pl.col("itemid").is_in(itemids) & (pl.col("admission_relative_ms") >= 0) & admission_filter(admission_ids)
    ).with_columns((pl.col("admission_relative_ms") // HOUR_MS).alias("hour"))
    df = lf.select(["admissionid", "itemid", "hour", value_col]).collect(engine="streaming")
    df = df.rename({value_col: "value"}).with_columns(pl.col("value").cast(pl.Float64, strict=False))
    df = df.join(lookup, on="itemid", how="inner")
    if df.height == 0:
        return None
    log.info(f"{table} numeric: {df.height} rows across {df['tag'].n_unique()} tags")

    affected = [(t, i) for t, i in pairs if (t, i) in CONDITIONAL_PERCENT_ITEMIDS]
    if affected:
        before_frac = df.filter(
            pl.struct(["tag", "itemid"]).is_in([{"tag": t, "itemid": i} for t, i in affected])
            & (pl.col("value") <= CONDITIONAL_PERCENT_THRESHOLD)
        ).height
        df = df.with_columns(
            pl.when(
                pl.struct(["tag", "itemid"]).is_in([{"tag": t, "itemid": i} for t, i in affected])
                & (pl.col("value") >= 0) & (pl.col("value") <= CONDITIONAL_PERCENT_THRESHOLD)
            ).then(pl.col("value") * 100.0).otherwise(pl.col("value")).alias("value")
        )
        log.info(f"{table} conditional-percent conversion: {before_frac} fraction-scale rows "
                 f"(value<={CONDITIONAL_PERCENT_THRESHOLD}) x100'd for itemids {affected}")

    tag_bounds = {tag: b for tag, b in bounds.items() if any(t == tag for t, _ in pairs)}
    if tag_bounds:
        before = df.height
        lo_map = {t: b[0] for t, b in tag_bounds.items()}
        hi_map = {t: b[1] for t, b in tag_bounds.items()}
        df = df.filter(
            (~pl.col("tag").is_in(list(tag_bounds)))
            | pl.col("value").is_between(
                pl.col("tag").replace_strict(lo_map, default=None, return_dtype=pl.Float64),
                pl.col("tag").replace_strict(hi_map, default=None, return_dtype=pl.Float64),
            )
        )
        log.info(f"{table} plausibility filter: dropped {before - df.height} of {before} rows "
                 f"({len(tag_bounds)} tags bounded)")
    return df.select(["admissionid", "tag", "hour", "value"])


def _build_categorical_for_table(raw_data_dir, table, pairs, admissions, admission_ids, label_map=None, raw_shards_dir=None):
    if not pairs:
        return None
    itemids = list({itemid for _, itemid in pairs})
    lookup = pl.DataFrame({"itemid": [i for _, i in pairs], "tag": [t for t, _ in pairs]}, schema={"itemid": pl.Int64, "tag": pl.String}).unique()

    lf = scan_raw_table(raw_data_dir, table, admissions, raw_shards_dir)
    lf = lf.filter(
        pl.col("itemid").is_in(itemids) & (pl.col("admission_relative_ms") >= 0) & admission_filter(admission_ids)
    ).with_columns((pl.col("admission_relative_ms") // HOUR_MS).alias("hour"))
    df = lf.select(["admissionid", "itemid", "hour", "value"]).collect(engine="streaming")
    df = df.join(lookup, on="itemid", how="inner")
    if df.height == 0:
        return None
    # some MIMIC-IV chartevents string values carry a stray trailing space (e.g. "Trach mask ")
    # -- strip before any raw_value/standardized_label join so those variants aren't silently missed.
    df = df.with_columns(pl.col("value").str.strip_chars())

    table_label_map = {k: v for k, v in (label_map or {}).items() if k[0] in itemids}
    if table_label_map:
        map_df = pl.DataFrame({
            "itemid": [k[0] for k in table_label_map],
            "value": [k[1] for k in table_label_map],
            "std_label": list(table_label_map.values()),
        }, schema={"itemid": pl.Int64, "value": pl.String, "std_label": pl.String})
        df = df.join(map_df, on=["itemid", "value"], how="left")
        df = df.with_columns(pl.coalesce(["std_label", "value"]).alias("value")).drop("std_label")

    log.info(f"{table} categorical: {df.height} rows across {df['tag'].n_unique()} tags")
    return df.select(["admissionid", "tag", "hour", "value"]).rename({"value": "label"})


def extract_numeric_categorical(matches, raw_data_dir, admissions, admission_ids=None, raw_shards_dir=None):
    """matches: tag -> feature info dict, from grid.manifest.parse_manifest(). admissions:
    DataFrame from grid.raw_csv.load_admissions(). admission_ids: optional iterable to restrict
    extraction to (bounded sample runs); None = full population. Returns (numeric_long,
    categorical_long) polars DataFrames, or None for either if that reconstruction-type group
    has no in-scope matches."""
    numeric_pairs, categorical_pairs, label_map = _collect_matches(matches)
    log.info(f"numeric/derived_output_rate match count: {len(numeric_pairs)}, "
             f"categorical match count: {len(categorical_pairs)}")

    bounds = resolve_bounds(matches)
    log.info(f"plausibility bounds resolved for {len(bounds)} tags")

    numeric_parts = []
    for table in sorted({t for _, t, _ in numeric_pairs}):
        pairs = [(tag, itemid) for tag, tb, itemid in numeric_pairs if tb == table]
        part = _build_numeric_for_table(raw_data_dir, table, pairs, admissions, admission_ids, bounds, raw_shards_dir)
        if part is not None:
            numeric_parts.append(part)
    numeric_long = None
    if numeric_parts:
        numeric_long = pl.concat(numeric_parts).group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("value").median().alias("agg_value")
        )
        log.info(f"numeric_long: {numeric_long.height} rows, {numeric_long['tag'].n_unique()} tags")

    categorical_parts = []
    for table in sorted({t for _, t, _ in categorical_pairs}):
        pairs = [(tag, itemid) for tag, tb, itemid in categorical_pairs if tb == table]
        part = _build_categorical_for_table(raw_data_dir, table, pairs, admissions, admission_ids, label_map, raw_shards_dir)
        if part is not None:
            categorical_parts.append(part)
    categorical_long = None
    if categorical_parts:
        # mode().first() alone is nondeterministic on ties under engine="streaming" (which of the
        # tied labels comes "first" depends on parallel scan order, confirmed 2026-08-03: re-running
        # the identical extraction twice flipped 0.01-0.09% of hours per categorical tag). sort()
        # before first() breaks ties alphabetically instead, deterministic regardless of scan order.
        categorical_long = pl.concat(categorical_parts).group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("label").mode().sort().first().alias("agg_label")
        )
        log.info(f"categorical_long: {categorical_long.height} rows, {categorical_long['tag'].n_unique()} tags")

    return numeric_long, categorical_long
