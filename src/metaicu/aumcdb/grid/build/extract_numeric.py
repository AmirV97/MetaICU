"""
direct_numeric / derived_output_rate / categorical raw extraction: single grouped scan of
numericitems + listitems for every kept match, aggregated into 1h admission-relative bins --
the same bin formula used by transforms/causal_mean_binning.py: hour = admission_relative_ms
// 3_600_000. Refactor of ../extract_numeric_categorical.py into plain functions taking
explicit params (matches dict, raw_data_dir, admissions, optional admission_ids filter)
instead of module-level globals + a __main__ script, so run_extraction.py can call it directly
with a sample-scoped admission set. Logic is otherwise unchanged from the parquet-based
version -- only the data-access layer (grid.raw_csv instead of utils.parquet_datasets) differs,
regression-checked against the original script's numeric_long.parquet/categorical_long.parquet
output.

Returns two long-format DataFrames:
  numeric_long:      (admissionid, tag, hour, agg_value)   -- median per hour
  categorical_long:  (admissionid, tag, hour, agg_label)   -- mode per hour, keyed by each
                      match's manifest standardized_label (not raw valueid -- different
                      itemids under one feature use unrelated valueid numbering, verified for
                      mgcs/airway; pooling raw valueid across itemids would silently mix
                      unrelated categories)
"""
import logging

import polars as pl

from .raw_csv import scan_raw_table, admission_filter as _admission_filter
from .plausibility_bounds import resolve_bounds
from .unit_conversion_overrides import (
    UNIT_FACTOR, UNIT_AFFINE, CATEGORICAL_CONSTANT, EXCLUDE_FROM_POOLING,
    CONDITIONAL_PERCENT_ITEMIDS, CONDITIONAL_PERCENT_THRESHOLD, SENTINEL_VALUES,
)

HOUR_MS = 3_600_000
log = logging.getLogger(__name__)


def _load_matches(matches):
    """matches: tag -> feature info dict (from grid.manifest.parse_manifest), restricted to
    direct_numeric/derived_output_rate/categorical entries by the caller or filtered here."""
    numeric_numericitems, numeric_listitems_const, categorical_listitems = [], [], []
    for tag, info in matches.items():
        rt = info["reconstruction_type"]
        for m in info["keep_matches"]:
            key = (tag, m["itemid"])
            if rt in ("direct_numeric", "derived_output_rate"):
                if key in EXCLUDE_FROM_POOLING:
                    log.info(f"EXCLUDED from pooling (flagged anomaly): {tag} itemid={m['itemid']}")
                    continue
                if m["table"] == "numericitems":
                    numeric_numericitems.append((tag, m["itemid"]))
                elif m["table"] == "listitems":
                    ckey = (tag, m["itemid"], m["valueid"])
                    if ckey in CATEGORICAL_CONSTANT:
                        numeric_listitems_const.append((tag, m["itemid"], m["valueid"], CATEGORICAL_CONSTANT[ckey]))
                    else:
                        log.warning(f"SKIPPED (listitems match with no constant-value override): {tag} {m}")
                else:
                    log.warning(f"SKIPPED (unexpected table for direct_numeric/derived_output_rate): {tag} {m}")
            elif rt == "categorical":
                if m["table"] == "listitems":
                    label = m["standardized_label"] or m["valueid"]
                    categorical_listitems.append((tag, m["itemid"], m["valueid"], label))
                else:
                    log.warning(f"SKIPPED (unexpected table for categorical): {tag} {m}")
    return numeric_numericitems, numeric_listitems_const, categorical_listitems


def _build_numeric_from_numericitems(
    pairs, raw_data_dir, admissions, admission_ids, bounds, raw_shards_dir=None
):
    """A raw itemid can legitimately feed more than one output feature (e.g. itemid 12279
    'O2 concentratie' is kept by both fio2 and supp_o2_vent) -- fan out via a join (one
    lookup row per (itemid,tag)) rather than assuming a 1:1 itemid->tag mapping.

    bounds: {tag: (lo, hi)} from grid.plausibility_bounds.resolve_bounds(); a tag absent from
    bounds is left unfiltered (currently just `pt`, see that module's docstring)."""
    if not pairs:
        return None
    itemids = list({int(itemid) for _, itemid in pairs})
    lookup = pl.DataFrame({"itemid": [int(itemid) for _, itemid in pairs], "tag": [tag for tag, _ in pairs]}).unique()

    lf = scan_raw_table(raw_data_dir, "numericitems", admissions, raw_shards_dir).filter(
        pl.col("itemid").is_in(itemids) & (pl.col("admission_relative_ms") >= 0) & _admission_filter(admission_ids)
    ).select(["admissionid", "itemid", "value", "admission_relative_ms"])

    df = lf.collect(engine="streaming")
    log.info(f"numericitems rows scanned (post-itemid-filter): {df.height}")

    df = df.with_columns((pl.col("admission_relative_ms") // HOUR_MS).alias("hour"))
    df = df.join(lookup, on="itemid", how="inner")

    # sentinel-value exclusion (raw device/error codes disguised as data -- see
    # unit_conversion_overrides.py's SENTINEL_VALUES docstring). Applied to the raw "value"
    # before any conversion, same drop-as-missing convention as the plausibility filter below.
    sentinel_rows = [(tag, int(itemid), float(v))
                      for (tag, itemid), vals in SENTINEL_VALUES.items() for v in vals]
    if sentinel_rows:
        sentinel_df = pl.DataFrame(
            sentinel_rows, schema=["tag", "itemid", "value"], orient="row"
        ).with_columns(pl.lit(True).alias("_is_sentinel"))
        before = df.height
        df = df.join(sentinel_df, on=["tag", "itemid", "value"], how="left")
        df = df.filter(pl.col("_is_sentinel").is_null()).drop("_is_sentinel")
        log.info(f"sentinel-value filter: dropped {before - df.height} of {before} rows "
                 f"({len(SENTINEL_VALUES)} tags with a sentinel value)")

    # conditional fraction->percent fix (value-dependent, not a flat per-itemid factor -- see
    # unit_conversion_overrides.py's CONDITIONAL_PERCENT_ITEMIDS docstring). Applied to "value"
    # itself so the already-% rows and the newly-x100'd rows both flow through the factor/affine
    # logic below unchanged (these itemids aren't in UNIT_FACTOR/UNIT_AFFINE).
    cond_keys = {f"{tag}||{itemid}" for tag, itemid in CONDITIONAL_PERCENT_ITEMIDS}
    if cond_keys:
        df = df.with_columns(
            pl.when(
                pl.concat_str([pl.col("tag"), pl.col("itemid").cast(pl.Utf8)], separator="||").is_in(cond_keys)
                & (pl.col("value") <= CONDITIONAL_PERCENT_THRESHOLD)
            )
            .then(pl.col("value") * 100.0)
            .otherwise(pl.col("value"))
            .alias("value")
        )

    factor_map = {str(itemid): f for (t, itemid), f in UNIT_FACTOR.items() if int(itemid) in itemids}
    affine_map = {str(itemid): ab for (t, itemid), ab in UNIT_AFFINE.items() if int(itemid) in itemids}
    df = df.with_columns(pl.col("itemid").cast(pl.Utf8).alias("itemid_str"))
    df = df.with_columns(
        pl.when(pl.col("itemid_str").is_in(list(affine_map.keys())))
        .then(pl.col("value") * pl.col("itemid_str").replace_strict(
            {k: v[0] for k, v in affine_map.items()}, default=1.0, return_dtype=pl.Float64
        ) + pl.col("itemid_str").replace_strict(
            {k: v[1] for k, v in affine_map.items()}, default=0.0, return_dtype=pl.Float64
        ))
        .otherwise(pl.col("value") * pl.col("itemid_str").replace_strict(
            factor_map, default=1.0, return_dtype=pl.Float64
        ))
        .alias("converted_value")
    )

    # plausibility filter (post-conversion, pre-hourly-aggregation, per
    # icarefm_preprocessing_reference.md's A.4.1 step order) -- drop rows outside this tag's
    # generous plausible range; they simply don't contribute to that hour's median, same as
    # any other unmeasured reading. Tags absent from `bounds` are left unfiltered.
    tag_bounds = {tag: b for tag, b in bounds.items() if any(t == tag for t, _ in pairs)}
    if tag_bounds:
        before = df.height
        lo_map = {tag: b[0] for tag, b in tag_bounds.items()}
        hi_map = {tag: b[1] for tag, b in tag_bounds.items()}
        df = df.filter(
            (~pl.col("tag").is_in(list(tag_bounds)))
            | pl.col("converted_value").is_between(
                pl.col("tag").replace_strict(lo_map, default=None, return_dtype=pl.Float64),
                pl.col("tag").replace_strict(hi_map, default=None, return_dtype=pl.Float64),
            )
        )
        log.info(f"plausibility filter: dropped {before - df.height} of {before} rows "
                 f"outside their tag's bound ({len(tag_bounds)} tags bounded)")

    return df.select(["admissionid", "tag", "hour", "converted_value"])


def _build_numeric_from_listitems_const(
    triples, raw_data_dir, admissions, admission_ids, raw_shards_dir=None
):
    if not triples:
        return None
    itemids = list({int(t[1]) for t in triples})
    const_map = {(str(tag), str(itemid), str(valueid)): const for tag, itemid, valueid, const in triples}

    lf = scan_raw_table(raw_data_dir, "listitems", admissions, raw_shards_dir).filter(
        pl.col("itemid").is_in(itemids) & (pl.col("admission_relative_ms") >= 0) & _admission_filter(admission_ids)
    ).select(["admissionid", "itemid", "valueid", "admission_relative_ms"])
    df = lf.collect(engine="streaming")
    log.info(f"listitems (numeric-constant) rows scanned: {df.height}")

    df = df.with_columns((pl.col("admission_relative_ms") // HOUR_MS).alias("hour"))
    rows = []
    for (tag, itemid, valueid), const in const_map.items():
        sub = df.filter((pl.col("itemid") == int(itemid)) & (pl.col("valueid") == int(valueid)))
        rows.append(sub.select(["admissionid", "hour"]).with_columns(
            pl.lit(tag).alias("tag"), pl.lit(const).alias("converted_value")
        ).select(["admissionid", "tag", "hour", "converted_value"]))
    return pl.concat(rows) if rows else None


def _build_categorical(
    quads, raw_data_dir, admissions, admission_ids, raw_shards_dir=None
):
    """quads: (tag, itemid, valueid, standardized_label). Different itemids under the same
    feature use unrelated valueid numbering, so the join key is (itemid,valueid) -> label,
    not itemid -> tag alone -- pooling raw valueid across itemids would silently mix
    unrelated categories (verified against the manifest for mgcs/airway)."""
    if not quads:
        return None
    itemids = list({int(q[1]) for q in quads})
    # A raw (itemid,valueid) can legitimately feed more than one output feature (e.g.
    # itemid 6735/valueid 8 = "Intubated" for vgcs's verbal component AND "Endotracheal
    # tube" for airway) -- join() fans this out into one row per (tag,label) automatically.
    lookup = pl.DataFrame({
        "itemid": [int(q[1]) for q in quads],
        "valueid": [int(float(q[2])) for q in quads],
        "tag": [q[0] for q in quads],
        "label": [q[3] for q in quads],
    })

    lf = scan_raw_table(raw_data_dir, "listitems", admissions, raw_shards_dir).filter(
        pl.col("itemid").is_in(itemids) & (pl.col("admission_relative_ms") >= 0) & _admission_filter(admission_ids)
    ).select(["admissionid", "itemid", "valueid", "admission_relative_ms"])
    df = lf.collect(engine="streaming")
    log.info(f"listitems (categorical) rows scanned: {df.height}")

    df = df.with_columns((pl.col("admission_relative_ms") // HOUR_MS).alias("hour"))
    df = df.join(lookup, on=["itemid", "valueid"], how="inner")
    return df.select(["admissionid", "tag", "hour", "label"])


def extract_numeric_categorical(
    matches,
    raw_data_dir,
    admissions,
    admission_ids=None,
    raw_shards_dir=None,
):
    """matches: tag -> feature info dict, from grid.manifest.parse_manifest(). admissions:
    DataFrame from grid.raw_csv.load_admissions(), used for the admittedat join. admission_ids:
    optional iterable to restrict extraction to (for the bounded sample runs); None = full
    population. Returns (numeric_long, categorical_long) polars DataFrames, or None for either
    if that reconstruction-type group has no in-scope matches."""
    numeric_numericitems, numeric_listitems_const, categorical_listitems = _load_matches(matches)
    log.info(f"numeric-via-numericitems match count: {len(numeric_numericitems)}")
    log.info(f"numeric-via-listitems-constant match count: {len(numeric_listitems_const)}")
    log.info(f"categorical-via-listitems match count: {len(categorical_listitems)}")

    bounds = resolve_bounds(matches)
    log.info(f"plausibility bounds resolved for {len(bounds)} tags")

    numeric_long = None
    numeric_parts = [p for p in [
        _build_numeric_from_numericitems(
            numeric_numericitems,
            raw_data_dir,
            admissions,
            admission_ids,
            bounds,
            raw_shards_dir,
        ),
        _build_numeric_from_listitems_const(
            numeric_listitems_const,
            raw_data_dir,
            admissions,
            admission_ids,
            raw_shards_dir,
        ),
    ] if p is not None]
    if numeric_parts:
        numeric_long = pl.concat(numeric_parts).group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("converted_value").median().alias("agg_value")
        )
        log.info(f"numeric_long: {numeric_long.height} rows, {numeric_long['tag'].n_unique()} tags")

    categorical_long = None
    categorical_raw = _build_categorical(
        categorical_listitems,
        raw_data_dir,
        admissions,
        admission_ids,
        raw_shards_dir,
    )
    if categorical_raw is not None:
        categorical_long = categorical_raw.group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("label").mode().first().alias("agg_label")
        )
        log.info(f"categorical_long: {categorical_long.height} rows, {categorical_long['tag'].n_unique()} tags")

    return numeric_long, categorical_long
