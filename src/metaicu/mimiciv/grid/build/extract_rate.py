"""
treatment_rate raw extraction. Much simpler than AUMC_grid_pipeline/grid/extract_rate.py: MIMIC's
inputevents carries a native `rate` column directly (no dose/duration-reconstruction formula
table needed, unlike AUMC's treatment_rate_formulas.py) -- explode each row's [starttime,
endtime] interval across every hour it covers, mean-aggregate per icarefm_preprocessing_
reference.md's A.4.1 ("continuous treatment (infusion rates) -> mean aggregation per bin"),
same as AUMC's convention.

`ufilt` is chartevents-sourced (a periodic point measurement -- Ultrafiltrate Output volume,
not an infusion rate), so it's handled like a direct_numeric value (median per hour), same
special-case AUMC gave its own chartevents-sourced treatment_rate exception (ufilt's raw
fluid-output measurement there too).

Per-kg-of-bodyweight rate rows, combined per-kg/time rows (aminophylline), and wrong-time-base
rows (vasopressin) are converted to each tag's absolute target unit via the explicit maps in
grid.unit_conversion_overrides. Everything else is still the known v1 gap (target_unit vs each
itemid's actual rateuom hasn't been fully cross-checked beyond that sweep).
"""
import logging

import polars as pl

from .raw_csv import scan_raw_table, admission_filter
from .unit_conversion_overrides import (
    PER_KG_RATE_MASS_SCALE,
    PER_KG_RATE_TIME_SCALE,
    RATE_TIME_SCALE,
)

HOUR_MS = 3_600_000
log = logging.getLogger(__name__)


def _apply_rate_unit_conversions(df):
    """df: inputevents treatment_rate rows with rate/rateuom/patientweight columns, already
    tag-joined. Rows matching a (tag, itemid, rateuom) key in PER_KG_RATE_MASS_SCALE are rescaled
    to the tag's absolute target unit (rate * mass_scale * patientweight); rows matching a key in
    RATE_TIME_SCALE are rescaled by a flat factor (rate * scale, no patientweight). Every other
    row passes through unchanged."""
    for (tag, itemid), scale_map in PER_KG_RATE_MASS_SCALE.items():
        for rateuom, mass_scale in scale_map.items():
            mask = (pl.col("tag") == tag) & (pl.col("itemid") == itemid) & (pl.col("rateuom") == rateuom)
            n = df.filter(mask).height
            if n:
                df = df.with_columns(
                    pl.when(mask).then(pl.col("rate") * mass_scale * pl.col("patientweight"))
                    .otherwise(pl.col("rate")).alias("rate")
                )
                log.info(f"{tag} itemid {itemid}: converted {n} per-kg rows (rateuom={rateuom}, "
                         f"mass_scale={mass_scale}) to absolute rate via x patientweight")
    for (tag, itemid), scale_map in PER_KG_RATE_TIME_SCALE.items():
        for rateuom, rate_scale in scale_map.items():
            mask = (pl.col("tag") == tag) & (pl.col("itemid") == itemid) & (pl.col("rateuom") == rateuom)
            n = df.filter(mask).height
            if n:
                df = df.with_columns(
                    pl.when(mask).then(pl.col("rate") * rate_scale * pl.col("patientweight"))
                    .otherwise(pl.col("rate")).alias("rate")
                )
                log.info(f"{tag} itemid {itemid}: converted {n} per-kg/time rows "
                         f"(rateuom={rateuom}, rate_scale={rate_scale}) via x patientweight")
    for (tag, itemid), scale_map in RATE_TIME_SCALE.items():
        for rateuom, scale in scale_map.items():
            mask = (pl.col("tag") == tag) & (pl.col("itemid") == itemid) & (pl.col("rateuom") == rateuom)
            n = df.filter(mask).height
            if n:
                df = df.with_columns(
                    pl.when(mask).then(pl.col("rate") * scale).otherwise(pl.col("rate")).alias("rate")
                )
                log.info(f"{tag} itemid {itemid}: converted {n} rows (rateuom={rateuom}, "
                         f"scale={scale}) to target time base")
    return df


def _collect_matches(matches):
    """Returns (inputevents_pairs, chartevents_pairs): list of (tag, itemid) each."""
    inputevents_pairs, chartevents_pairs = [], []
    for tag, info in matches.items():
        if info["reconstruction_type"] != "treatment_rate":
            continue
        for m in info["keep_matches"]:
            table = m["table"]
            itemid = int(m["itemid"])
            if table == "inputevents":
                inputevents_pairs.append((tag, itemid))
            elif table in ("chartevents", "chartevents_main", "chartevents_value"):
                chartevents_pairs.append((tag, itemid))
            else:
                log.warning(f"SKIPPED (unrecognized table for treatment_rate): {tag} {m}")
    return inputevents_pairs, chartevents_pairs


def _extract_inputevents_rate(raw_data_dir, pairs, admissions, admission_ids, raw_shards_dir=None):
    if not pairs:
        return None
    itemids = list({i for _, i in pairs})
    lookup = pl.DataFrame({"itemid": [i for _, i in pairs], "tag": [t for t, _ in pairs]}, schema={"itemid": pl.Int64, "tag": pl.String}).unique()

    lf = scan_raw_table(raw_data_dir, "inputevents", admissions, raw_shards_dir)
    df = lf.filter(
        pl.col("itemid").is_in(itemids) & (pl.col("stop_admission_relative_ms") >= 0) & admission_filter(admission_ids)
    ).select(
        ["admissionid", "itemid", "rate", "rateuom", "patientweight",
         "start_admission_relative_ms", "stop_admission_relative_ms"]
    ).collect(engine="streaming")
    df = df.filter(pl.col("rate").is_not_null()).join(lookup, on="itemid", how="inner")
    if df.height == 0:
        return None
    log.info(f"inputevents treatment_rate rows (post rate-not-null filter): {df.height}")

    df = _apply_rate_unit_conversions(df)

    df = df.with_columns(
        pl.max_horizontal(pl.col("start_admission_relative_ms"), 0).alias("start_ms"),
    ).with_columns(
        (pl.col("start_ms") // HOUR_MS).alias("hour_start"),
    )
    df = df.with_columns(
        pl.when(pl.col("stop_admission_relative_ms") <= pl.col("start_ms"))
        .then(pl.col("hour_start") + 1)
        .otherwise((pl.col("stop_admission_relative_ms") + HOUR_MS - 1) // HOUR_MS)
        .alias("hour_stop")
    )
    df = df.with_columns(pl.int_ranges(pl.col("hour_start"), pl.col("hour_stop")).alias("hour")).explode("hour")
    return df.select(["admissionid", "tag", "hour", pl.col("rate").alias("value")])


def _extract_chartevents_rate(raw_data_dir, pairs, admissions, admission_ids, raw_shards_dir=None):
    if not pairs:
        return None
    itemids = list({i for _, i in pairs})
    lookup = pl.DataFrame({"itemid": [i for _, i in pairs], "tag": [t for t, _ in pairs]}, schema={"itemid": pl.Int64, "tag": pl.String}).unique()

    lf = scan_raw_table(raw_data_dir, "chartevents", admissions, raw_shards_dir)
    lf = lf.filter(
        pl.col("itemid").is_in(itemids) & (pl.col("admission_relative_ms") >= 0) & admission_filter(admission_ids)
    ).with_columns((pl.col("admission_relative_ms") // HOUR_MS).alias("hour"))
    df = lf.select(["admissionid", "itemid", "hour", "valuenum"]).collect(engine="streaming")
    df = df.join(lookup, on="itemid", how="inner")
    if df.height == 0:
        return None
    log.info(f"chartevents treatment_rate rows: {df.height}")
    return df.select(["admissionid", "tag", "hour", pl.col("valuenum").alias("value")])


def extract_treatment_rate(matches, raw_data_dir, admissions, admission_ids=None, raw_shards_dir=None):
    """matches: tag -> feature info dict, from grid.manifest.parse_manifest(). admissions:
    DataFrame from grid.raw_csv.load_admissions(). admission_ids: optional iterable to restrict
    to; None = full population. Returns one long-format (admissionid, tag, hour, agg_value)
    DataFrame -- mean aggregation for inputevents-sourced rates (icarefm A.4.1's continuous-
    treatment rule), median for chartevents-sourced point measurements (ufilt)."""
    inputevents_pairs, chartevents_pairs = _collect_matches(matches)
    log.info(f"inputevents treatment_rate match count: {len(inputevents_pairs)}, "
             f"chartevents treatment_rate match count: {len(chartevents_pairs)}")

    parts = []
    input_raw = _extract_inputevents_rate(raw_data_dir, inputevents_pairs, admissions, admission_ids, raw_shards_dir)
    if input_raw is not None:
        parts.append(input_raw.group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("value").mean().alias("agg_value")
        ))

    chart_raw = _extract_chartevents_rate(raw_data_dir, chartevents_pairs, admissions, admission_ids, raw_shards_dir)
    if chart_raw is not None:
        parts.append(chart_raw.group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("value").median().alias("agg_value")
        ))

    if not parts:
        return None
    rate_long = pl.concat(parts)
    log.info(f"treatment_rate: {rate_long.height} rows, {rate_long['tag'].n_unique()} tags")
    return rate_long
