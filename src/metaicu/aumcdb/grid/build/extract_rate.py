"""
treatment_rate raw extraction -- new module (this reconstruction type never had a real
extractor; ../check_treatment_rate_v1.py was diagnostic only, plotting raw per-row segments,
not the hour-level aggregate the actual grid needs). Applies each match's decided formula
(treatment_rate_formulas.py: raw_rate / dose_over_duration variants + cross-drug factor),
the documented implausible-duration filter (drop duration<=0 rows -- data corruption, not a
statistical outlier judgment call, so in scope for v1), then aggregates to 1h admission-
relative bins with MEAN (per icarefm_preprocessing_reference.md's A.4.1: "continuous
treatment (infusion rates) -> mean aggregation per bin"), exploding each drugitems row's
[start,stop] interval across every hour it covers first (a continuous-infusion row can span
many hours; the grid needs one value per hour, not one value per raw row).

`ufilt` is a special case within this reconstruction type: its source is a numericitems fluid-
output measurement, not a drugitems administration record, so it has no dose/duration
formula at all -- just the raw `value`, median-aggregated per hour exactly like a
direct_numeric feature (see treatment_rate_formulas.py's "raw_value_numericitems" formula).

Output: one long-format (admissionid, tag, hour, agg_value) DataFrame, analogous to
grid.extract_numeric's numeric_long but for treatment_rate.
"""
import logging

import polars as pl

from .raw_csv import scan_raw_table, admission_filter as _admission_filter
from .treatment_rate_formulas import TREATMENT_RATE_MATCHES, MIN_DURATION_SECONDS, RATE_CEILING

HOUR_MS = 3_600_000
log = logging.getLogger(__name__)

_FORMULA_EXPR = (
    pl.when(pl.col("formula") == "raw_rate").then(pl.col("rate") * pl.col("factor"))
    .when(pl.col("formula") == "dose_over_duration").then(pl.col("dose") / (pl.col("duration") / 60) * pl.col("factor"))
    .when(pl.col("formula") == "dose_over_duration_x60")
    .then(pl.col("dose") / (pl.col("duration") / 60) * 60 * pl.col("factor"))
    .when(pl.col("formula") == "dose_over_duration_x1000")
    .then(pl.col("dose") / (pl.col("duration") / 60) * 1000 * pl.col("factor"))
    .otherwise(None)
)


def _explode_interval_mean(df):
    """df has start_h/stop_h/converted_value/tag/match_key columns already -- explode each
    row's interval into one entry per covered hour."""
    df = df.with_columns(
        pl.col("start_h").floor().cast(pl.Int64).alias("hour_start"),
        pl.col("stop_h").floor().cast(pl.Int64).alias("hour_end"),
    )
    df = df.with_columns(pl.int_ranges(pl.col("hour_start"), pl.col("hour_end") + 1).alias("hour"))
    return df.select(["admissionid", "tag", "match_key", "hour", "converted_value"]).explode("hour")


def _extract_drugitems_matches(
    raw_data_dir, admissions, admission_ids, in_scope_tags, raw_shards_dir=None
):
    """Batched: one scan of drugitems.csv across every in-scope tag's drugitems-sourced matches
    (matches the one-scan-per-table pattern already used in extract_numeric.py/
    extract_indicator.py) -- previously did one scan per match (15 separate scans of the same
    818MB file), now does one. Fan-out from (itemid,ordercategoryid) to tag/formula/factor is a
    join, same reasoning as extract_indicator.py's drugitems join (an itemid can in principle
    feed more than one tag)."""
    match_rows = [
        {"itemid": m["itemid"], "ordercategoryid": m["ordercategoryid"], "tag": tag,
         "formula": m["formula"], "factor": m["factor"], "match_key": f"{m['itemid']}_{m['ordercategoryid']}",
         "min_duration": MIN_DURATION_SECONDS.get(tag, 0.0)}
        for tag, matches in TREATMENT_RATE_MATCHES.items() if tag in in_scope_tags
        for m in matches if m["table"] == "drugitems"
    ]
    if not match_rows:
        return None
    lookup = pl.DataFrame(match_rows).with_columns(pl.col("ordercategoryid").cast(pl.Int64))
    itemids = lookup["itemid"].unique().to_list()

    lf = scan_raw_table(raw_data_dir, "drugitems", admissions, raw_shards_dir).filter(
        pl.col("itemid").is_in(itemids) & _admission_filter(admission_ids)
    ).select(["admissionid", "itemid", "ordercategoryid", "start_admission_relative_ms",
              "stop_admission_relative_ms", "duration", "rate", "dose"])
    df = lf.collect(engine="streaming")
    log.info(f"drugitems rows scanned (post-itemid-filter, batched across {lookup.height} matches): {df.height}")

    df = df.join(lookup, on=["itemid", "ordercategoryid"], how="inner")
    # duration>0 (data-validity) for every tag by default (min_duration=0.0); benzdia/hep/
    # loop_diur/prop additionally require duration>60s (root cause 3's amplification fix --
    # see treatment_rate_formulas.py's MIN_DURATION_SECONDS comment)
    df = df.filter(pl.col("duration") > pl.col("min_duration"))
    df = df.with_columns(
        (pl.col("start_admission_relative_ms") / HOUR_MS).alias("start_h"),
        (pl.col("stop_admission_relative_ms") / HOUR_MS).alias("stop_h"),
        _FORMULA_EXPR.alias("converted_value"),
    )

    # rate-ceiling filter (drop as missing, not clip -- same convention as
    # grid/plausibility_bounds.py): generous per-drug backstop for benzdia/hep/loop_diur/prop,
    # see treatment_rate_formulas.py's RATE_CEILING comment for sourcing.
    if RATE_CEILING:
        before = df.height
        hi_map = {tag: ceil for tag, ceil in RATE_CEILING.items()}
        df = df.filter(
            (~pl.col("tag").is_in(list(hi_map)))
            | pl.col("converted_value").is_between(
                0.0, pl.col("tag").replace_strict(hi_map, default=None, return_dtype=pl.Float64)
            )
        )
        log.info(f"rate ceiling filter: dropped {before - df.height} of {before} rows "
                 f"outside [0, ceiling] for their tag")

    counts = df.group_by(["tag", "itemid", "ordercategoryid", "formula", "factor"]).len()
    seen = set()
    for row in counts.iter_rows(named=True):
        seen.add((row["tag"], row["itemid"], row["ordercategoryid"]))
        log.info(f"{row['tag']}: itemid={row['itemid']} ocid={row['ordercategoryid']} formula={row['formula']} "
                 f"factor={row['factor']} -> {row['len']} rows")
    for m in match_rows:
        key = (m["tag"], m["itemid"], m["ordercategoryid"])
        if key not in seen:
            log.warning(f"{m['tag']}: itemid={m['itemid']} ocid={m['ordercategoryid']} -- 0 rows")

    return _explode_interval_mean(df)


def _extract_ufilt(raw_data_dir, admissions, admission_ids, raw_shards_dir=None):
    """No route filter -- see treatment_rate_formulas.py's ufilt entry for why (the raw CSV
    has no column that reproduces amsterdam_pipeline's SUBJECT_FLUID_OUTPUT/MEASUREMENT_BEDSIDE
    split; pooling unfiltered is an accepted, quantified tradeoff)."""
    m = TREATMENT_RATE_MATCHES["ufilt"][0]
    df = scan_raw_table(raw_data_dir, "numericitems", admissions, raw_shards_dir).filter(
        (pl.col("itemid") == m["itemid"]) & _admission_filter(admission_ids)
    ).select(["admissionid", "value", "admission_relative_ms"]).collect(engine="streaming")
    log.info(f"ufilt: itemid={m['itemid']} (unfiltered, see docstring) -> {df.height} rows")
    if df.height == 0:
        return None

    # negative-value floor (drop as missing, not clip): checked 2026-07-14
    # (grid/_check_open_flags.py) -- only 6 of 98383 raw rows (0.006%) are negative, min -228,
    # across 6 admissions. Too small to matter either way, but a fluid-output rate has no
    # physical negative reading, so dropped for consistency with the rest of the pipeline's
    # missing-not-clipped convention.
    before = df.height
    df = df.filter(pl.col("value") >= 0.0)
    log.info(f"ufilt: dropped {before - df.height} rows with negative value")
    hour = (df["admission_relative_ms"] / HOUR_MS).floor().cast(pl.Int64)
    return df.with_columns(
        hour.alias("hour"), pl.col("value").alias("converted_value"),
        pl.lit("ufilt").alias("tag"), pl.lit("8805_fluidoutput").alias("match_key"),
    ).select(["admissionid", "tag", "match_key", "hour", "converted_value"])


def extract_treatment_rate(
    raw_data_dir,
    admissions,
    admission_ids=None,
    tags=None,
    raw_shards_dir=None,
):
    """Ignores the manifest's matches dict -- treatment_rate's formulas are hand-curated in
    treatment_rate_formulas.py (the manifest's per-match decision-reason text is prose, not a
    structured formula; TREATMENT_RATE_MATCHES is the executable transcription of it, already
    regression-checked against the manifest's kept-match list). admissions: DataFrame from
    grid.raw_csv.load_admissions(). admission_ids: optional iterable to restrict extraction
    to; None = full population. tags: optional subset of treatment_rate tags to extract
    (mirrors the CLI's --features filter for the other reconstruction types, which don't
    route through this hardcoded table); None = all 10. Returns one long-format
    (admissionid, tag, hour, agg_value) DataFrame -- mean aggregation for drugitems-sourced
    rate matches (icarefm A.4.1's continuous-treatment rule), median for ufilt's raw value."""
    in_scope_tags = set(TREATMENT_RATE_MATCHES) if tags is None else set(tags) & set(TREATMENT_RATE_MATCHES)

    rate_long = None
    drugitems_long = _extract_drugitems_matches(
        raw_data_dir,
        admissions,
        admission_ids,
        in_scope_tags - {"ufilt"},
        raw_shards_dir,
    )
    if drugitems_long is not None:
        rate_long = drugitems_long.group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("converted_value").mean().alias("agg_value")
        )
        log.info(f"treatment_rate (drugitems-sourced): {rate_long.height} rows, "
                 f"{rate_long['tag'].n_unique()} tags")

    ufilt_raw = (
        _extract_ufilt(raw_data_dir, admissions, admission_ids, raw_shards_dir)
        if "ufilt" in in_scope_tags
        else None
    )
    ufilt_long = None
    if ufilt_raw is not None:
        ufilt_long = ufilt_raw.group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("converted_value").median().alias("agg_value")
        )
        log.info(f"ufilt: {ufilt_long.height} rows")

    parts_out = [p for p in [rate_long, ufilt_long] if p is not None]
    return pl.concat(parts_out) if parts_out else None
