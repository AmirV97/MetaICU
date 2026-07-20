"""Numeric quality-control corrections ported from the grid pipeline's itemid-level fixes
(grid/build/unit_conversion_overrides.py's SENTINEL_VALUES/CONDITIONAL_PERCENT_ITEMIDS/
UNIT_FACTOR/UNIT_AFFINE, grid/build/plausibility_bounds.py's PLAUSIBLE_RANGE, and the grid
manifest's outright-rejected itemids e.g. `pt`) -- applied here, before quantile-boundary
fitting/application, to the same numericitems raw value grid corrects. Without this, the
tokenized pipeline's quantile-binned tokens inherit the same unit-mislabeling, device-sentinel,
and instrument-artifact contamination that grid found and fixed independently.

Keyed by itemid -- the only key shared between the two pipelines' vocabularies. grid pools
itemids into physiology tags (e.g. "po2"); tokenized keeps each itemid as its own separate
OMOP-mapped token (aumc_supplied_vocab.csv), so there is no tag-name correspondence to rely on.
Reuses grid's correction tables directly (no copy-paste) so a future grid fix stays in sync.

Correction order mirrors grid/build/extract_numeric.py's _build_numeric_from_numericitems
exactly: itemid exclusion -> sentinel drop -> conditional fraction->percent -> factor/affine
conversion -> plausibility bounds (post-conversion, drop-as-missing, same convention as any
other unmeasured reading).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import polars as pl

from metaicu.aumcdb.grid.build.manifest_parser import parse_manifest
from metaicu.aumcdb.grid.build.plausibility_bounds import resolve_bounds
from metaicu.aumcdb.grid.build.unit_conversion_overrides import (
    CONDITIONAL_PERCENT_ITEMIDS,
    CONDITIONAL_PERCENT_THRESHOLD,
    SENTINEL_VALUES,
    UNIT_AFFINE,
    UNIT_FACTOR,
)

log = logging.getLogger(__name__)

NUMERIC_RECONSTRUCTION_TYPES = ("direct_numeric", "derived_output_rate")

# Manifest-rejected as an unrecoverable duplicate/contamination, never resolved as any
# in-scope grid feature, so it never appears in parse_manifest()'s output and needs an
# explicit exclusion here. `pt` (itemid 6789): legacy mislabeled-unit duplicate of inr_pt --
# see aumc_grid_feature_manifest_review.md's `pt` block, match 1 (rejected 2026-07-13).
EXCLUDED_ITEMIDS = frozenset({6789})


def build_itemid_corrections(manifest_path: Path | None = None) -> dict[int, dict]:
    """Returns {itemid: correction} for every numericitems itemid grid has an opinion about.

    correction (non-excluded) has keys: sentinel (frozenset[float]),
    cond_percent_threshold (float|None), affine ((a,b)|None), factor (float),
    lo (float|None), hi (float|None). Excluded itemids map to {"excluded": True} with no
    other keys. itemid absent from the result -> no grid opinion, left uncorrected."""
    in_scope, _report = parse_manifest(manifest_path, reconstruction_types=NUMERIC_RECONSTRUCTION_TYPES)
    bounds = resolve_bounds(in_scope)  # {tag: (lo, hi)}

    itemid_to_tag: dict[int, str] = {}
    for tag, info in in_scope.items():
        for km in info["keep_matches"]:
            if km["table"] == "numericitems" and km["itemid"] is not None:
                itemid_to_tag.setdefault(int(km["itemid"]), tag)

    sentinel_by_itemid: dict[int, set[float]] = {}
    for (_tag, itemid), vals in SENTINEL_VALUES.items():
        sentinel_by_itemid.setdefault(int(itemid), set()).update(vals)
    cond_percent_itemids = {int(itemid) for _tag, itemid in CONDITIONAL_PERCENT_ITEMIDS}

    all_itemids = (
        set(itemid_to_tag)
        | {int(itemid) for _tag, itemid in UNIT_FACTOR}
        | {int(itemid) for _tag, itemid in UNIT_AFFINE}
        | set(sentinel_by_itemid)
        | cond_percent_itemids
        | set(EXCLUDED_ITEMIDS)
    )

    corrections: dict[int, dict] = {}
    for itemid in all_itemids:
        if itemid in EXCLUDED_ITEMIDS:
            corrections[itemid] = {"excluded": True}
            continue

        factor_vals = {f for (_tag, i), f in UNIT_FACTOR.items() if int(i) == itemid}
        affine_vals = {ab for (_tag, i), ab in UNIT_AFFINE.items() if int(i) == itemid}
        if len(factor_vals) > 1 or len(affine_vals) > 1:
            log.warning(f"itemid {itemid}: conflicting unit correction across tags -- left uncorrected")
            continue

        tag = itemid_to_tag.get(itemid)
        lo, hi = bounds.get(tag, (None, None))
        corrections[itemid] = {
            "excluded": False,
            "sentinel": frozenset(sentinel_by_itemid.get(itemid, ())),
            "cond_percent_threshold": CONDITIONAL_PERCENT_THRESHOLD if itemid in cond_percent_itemids else None,
            "affine": next(iter(affine_vals), None),
            "factor": next(iter(factor_vals), 1.0),
            "lo": lo,
            "hi": hi,
        }
    return corrections


@lru_cache(maxsize=1)
def load_itemid_corrections(manifest_path: Path | None = None) -> dict[int, dict]:
    """Cached wrapper -- the grid manifest is parsed once per process, not once per split/phase."""
    return build_itemid_corrections(manifest_path)


def apply_itemid_corrections(df: pl.DataFrame, corrections: dict[int, dict]) -> pl.DataFrame:
    """df: raw numericitems rows with `itemid` and `value` columns (any point before quantile
    boundary fitting/application). Returns a df with the same columns, `value` corrected and
    excluded/implausible/sentinel rows dropped."""
    if not corrections or df.is_empty():
        return df

    itemid_i64 = pl.col("itemid").cast(pl.Int64, strict=False)

    excluded = [itemid for itemid, c in corrections.items() if c.get("excluded")]
    if excluded:
        before = df.height
        df = df.filter(~itemid_i64.is_in(excluded))
        log.info(f"itemid exclusion: dropped {before - df.height} of {before} rows ({len(excluded)} itemids)")

    active = {itemid: c for itemid, c in corrections.items() if not c.get("excluded")}
    if not active or df.is_empty():
        return df

    df = df.with_columns(itemid_i64.alias("itemid"), pl.col("value").cast(pl.Float64, strict=False).alias("value"))

    sentinel_rows = [(itemid, v) for itemid, c in active.items() for v in c["sentinel"]]
    if sentinel_rows:
        before = df.height
        sentinel_df = pl.DataFrame(sentinel_rows, schema=["itemid", "value"], orient="row").with_columns(
            pl.col("itemid").cast(pl.Int64), pl.lit(True).alias("_is_sentinel")
        )
        df = df.join(sentinel_df, on=["itemid", "value"], how="left")
        df = df.filter(pl.col("_is_sentinel").is_null()).drop("_is_sentinel")
        log.info(f"sentinel-value filter: dropped {before - df.height} rows")

    corr_df = pl.DataFrame({
        "itemid": list(active.keys()),
        "_factor": [c["factor"] for c in active.values()],
        "_affine_a": [c["affine"][0] if c["affine"] else None for c in active.values()],
        "_affine_b": [c["affine"][1] if c["affine"] else None for c in active.values()],
        "_cond_thresh": [c["cond_percent_threshold"] for c in active.values()],
        "_lo": [c["lo"] for c in active.values()],
        "_hi": [c["hi"] for c in active.values()],
    }).with_columns(pl.col("itemid").cast(pl.Int64))
    df = df.join(corr_df, on="itemid", how="left")

    df = df.with_columns(
        pl.when(pl.col("_cond_thresh").is_not_null() & (pl.col("value") <= pl.col("_cond_thresh")))
        .then(pl.col("value") * 100.0)
        .otherwise(pl.col("value"))
        .alias("value")
    )
    df = df.with_columns(
        pl.when(pl.col("_affine_a").is_not_null())
        .then(pl.col("value") * pl.col("_affine_a") + pl.col("_affine_b"))
        .otherwise(pl.col("value") * pl.col("_factor").fill_null(1.0))
        .alias("value")
    )

    before = df.height
    df = df.filter(
        (pl.col("_lo").is_null() | (pl.col("value") >= pl.col("_lo")))
        & (pl.col("_hi").is_null() | (pl.col("value") <= pl.col("_hi")))
    )
    log.info(f"plausibility filter: dropped {before - df.height} of {before} rows")

    return df.drop(["_factor", "_affine_a", "_affine_b", "_cond_thresh", "_lo", "_hi"])
