"""Numericitems -> quantile-coded MEDS events.

Prefers pre-MEDS ``numericitems_binned`` when present, otherwise falls back
to raw ``numericitems``. Split-aware conversion fits Q1-Q10 boundaries once
on the train split, saves them as metadata, then applies the same boundaries
to train, val, and test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import polars as pl

from metaicu.aumcdb.tokenized.meds.common import (
    coerce_debug_frame,
    empty_debug_frame,
    record_join_exclusions,
    runtime_phase_expr,
)
from metaicu.aumcdb.tokenized.meds.numeric_qc import apply_itemid_corrections, load_itemid_corrections
from metaicu.aumcdb.tokenized.meds.vocab import table_vocab
from metaicu.aumcdb.common.parquet import parquet_exists, resolve_table_parquet, scan_parquet

NULL_UNIT_KEY = "<NULL>"


def numeric_input_table_name(pre_meds_dir: Path) -> str:
    """Return the numeric table consumed by MEDS conversion for this split."""

    if parquet_exists(resolve_table_parquet(pre_meds_dir, "numericitems_binned")):
        return "numericitems_binned"
    return "numericitems"


def _numeric_input_path(pre_meds_dir: Path) -> Path:
    return resolve_table_parquet(pre_meds_dir, numeric_input_table_name(pre_meds_dir))


def _q_cols(bins: int) -> list[str]:
    return [f"q{q}" for q in range(1, bins)]


def _unit_key_expr(source_unit_col: str = "source_unit") -> pl.Expr:
    return pl.col(source_unit_col).cast(pl.String).fill_null(NULL_UNIT_KEY).alias("source_unit_key")


def _empty_boundaries(bins: int) -> pl.DataFrame:
    schema = {
        "source_token": pl.String,
        "source_unit": pl.String,
        "source_unit_key": pl.String,
        "harmonized_token": pl.String,
        "source_rows": pl.Int64,
        "fit_split": pl.String,
    }
    schema.update({col: pl.Float64 for col in _q_cols(bins)})
    return pl.DataFrame(schema=schema)


def _admission_ids(pre_meds_dir: Path) -> list[int]:
    path = resolve_table_parquet(pre_meds_dir, "admissions")
    if not parquet_exists(path):
        return []
    return (
        scan_parquet(path)
        .select(pl.col("admissionid").cast(pl.Int64))
        .collect(engine="streaming")
        .to_series()
        .to_list()
    )


def _load_joined_numeric_rows(
    admission_ids: Sequence[int],
    pre_meds_dir: Path,
    vocab: pl.DataFrame,
    include_phases: Sequence[str],
    max_rows: int | None = None,
) -> tuple[pl.DataFrame, list[dict], str]:
    """Load numeric rows, join vocab, and apply phase filtering before quantiles."""

    numeric_path = _numeric_input_path(pre_meds_dir)
    numeric_table = numeric_input_table_name(pre_meds_dir)
    if not parquet_exists(numeric_path):
        return pl.DataFrame(), [], numeric_table

    tv = table_vocab(vocab, "numericitems", {"_itemid_i64": "itemid", "_unitid_i64": "unitid"})
    scan = scan_parquet(numeric_path).filter(pl.col("admissionid").is_in(list(admission_ids)))
    if max_rows is not None:
        scan = scan.limit(max_rows)

    raw = (
        scan.join(tv.lazy(), on=["itemid", "unitid"], how="left")
        .with_columns(runtime_phase_expr("admission_relative_ms").alias("temporal_phase"))
        .collect(engine="streaming")
    )
    # grid-ported itemid-level unit/sentinel/plausibility corrections -- see numeric_qc.py.
    # Applied before phase filtering so it affects both boundary fitting and event coding.
    raw = apply_itemid_corrections(raw, load_itemid_corrections())

    exclusions = record_join_exclusions("numericitems", raw, list(include_phases))
    emitted = raw.filter(pl.col("_emit") & pl.col("temporal_phase").is_in(list(include_phases)))
    return emitted, exclusions, numeric_table


def fit_numeric_quantile_boundaries_from_frame(
    df: pl.DataFrame,
    bins: int = 10,
    fit_split: str = "cohort",
) -> tuple[pl.DataFrame, int]:
    """Fit frozen-boundary schema from an already-filtered numeric frame."""

    if df.is_empty():
        return _empty_boundaries(bins), 0

    numeric = (
        df.with_columns([
            pl.col("value").cast(pl.Float64, strict=False).alias("value_num"),
            _unit_key_expr(),
        ])
        .filter(pl.col("value_num").is_finite())
    )
    dropped = df.height - numeric.height
    if numeric.is_empty():
        return _empty_boundaries(bins), dropped

    aggs = [pl.len().alias("source_rows")]
    aggs.extend([
        pl.col("value_num").quantile(q / bins, interpolation="nearest").alias(f"q{q}")
        for q in range(1, bins)
    ])
    boundaries = (
        numeric.group_by(["source_token", "source_unit_key", "source_unit", "harmonized_token"])
        .agg(aggs)
        .with_columns(pl.lit(fit_split).alias("fit_split"))
        .select(_empty_boundaries(bins).columns)
        .sort(["source_token", "source_unit_key", "harmonized_token"])
    )
    return boundaries, dropped


def fit_numeric_quantile_boundaries(
    train_pre_meds_dir: Path,
    vocab: pl.DataFrame,
    include_phases: Sequence[str],
    bins: int = 10,
    max_rows: int | None = None,
) -> tuple[pl.DataFrame, list[dict]]:
    """Fit numeric quantile boundaries on the train split after vocab/phase filtering."""

    admission_ids = _admission_ids(train_pre_meds_dir)
    if not admission_ids:
        return _empty_boundaries(bins), []

    emitted, exclusions, _ = _load_joined_numeric_rows(
        admission_ids, train_pre_meds_dir, vocab, include_phases, max_rows=max_rows
    )
    boundaries, dropped = fit_numeric_quantile_boundaries_from_frame(emitted, bins=bins, fit_split="train")
    if dropped > 0:
        exclusions.append({
            "source_table": "numericitems",
            "exclusion_reason": "numeric_value_missing_or_nonfinite",
            "row_count": int(dropped),
        })
    return boundaries, exclusions


def apply_numeric_quantile_boundaries(
    df: pl.DataFrame,
    boundaries: pl.DataFrame,
    bins: int = 10,
) -> tuple[pl.DataFrame, int, int]:
    """Assign Q1-Q{bins} with frozen boundaries.

    Returns (events, missing_boundary_count, nonfinite_count).
    """

    if df.is_empty():
        return pl.DataFrame(), 0, 0
    nonfinite_count = df.height - df.with_columns(
        pl.col("value").cast(pl.Float64, strict=False).alias("value_num")
    ).filter(pl.col("value_num").is_finite()).height
    if boundaries.is_empty():
        finite_count = df.height - nonfinite_count
        return pl.DataFrame(), finite_count, nonfinite_count

    q_cols = _q_cols(bins)
    numeric = (
        df.with_columns([
            pl.col("value").cast(pl.Float64, strict=False).alias("value_num"),
            _unit_key_expr(),
        ])
        .filter(pl.col("value_num").is_finite())
    )
    if numeric.is_empty():
        return pl.DataFrame(), 0, nonfinite_count

    join_cols = ["source_token", "source_unit_key", "harmonized_token"]
    boundary_cols = join_cols + q_cols
    joined = numeric.join(boundaries.select(boundary_cols), on=join_cols, how="left")
    missing = joined.filter(pl.col(q_cols[0]).is_null()).height if q_cols else 0
    joined = joined.filter(pl.col(q_cols[0]).is_not_null()) if q_cols else joined
    if joined.is_empty():
        return pl.DataFrame(), missing, nonfinite_count

    bin_expr = pl.lit(1)
    for col_name in q_cols:
        bin_expr = bin_expr + (pl.col("value_num") > pl.col(col_name)).cast(pl.Int64)
    events = joined.with_columns(bin_expr.alias("quantile_bin")).drop(q_cols + ["source_unit_key"])
    return events, missing, nonfinite_count


def quantile_code_numeric(
    df: pl.DataFrame,
    bins: int = 10,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Backward-compatible cohort-fit quantile coding helper."""

    boundaries, _ = fit_numeric_quantile_boundaries_from_frame(df, bins=bins)
    events, _, _ = apply_numeric_quantile_boundaries(df, boundaries, bins=bins)
    return events, boundaries


def numeric_events(
    admission_ids: Sequence[int],
    pre_meds_dir: Path,
    vocab: pl.DataFrame,
    include_phases: Sequence[str],
    bins: int,
    audit_dir: Path,
    max_rows: int | None = None,
    quantile_boundaries: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, list[dict]]:
    """Join numericitems to vocab, quantile-code values, return MEDS events and exclusions."""

    emitted, exclusions, _ = _load_joined_numeric_rows(
        admission_ids, pre_meds_dir, vocab, include_phases, max_rows=max_rows
    )
    if emitted.is_empty():
        return empty_debug_frame(), exclusions

    if quantile_boundaries is None:
        boundaries, nonfinite_dropped = fit_numeric_quantile_boundaries_from_frame(emitted, bins=bins)
    else:
        boundaries = quantile_boundaries
        nonfinite_dropped = 0

    events, missing_boundaries, apply_nonfinite = apply_numeric_quantile_boundaries(emitted, boundaries, bins=bins)
    nonfinite_total = nonfinite_dropped or apply_nonfinite
    if nonfinite_total > 0:
        exclusions.append({
            "source_table": "numericitems",
            "exclusion_reason": "numeric_value_missing_or_nonfinite",
            "row_count": int(nonfinite_total),
        })
    if missing_boundaries > 0:
        exclusions.append({
            "source_table": "numericitems",
            "exclusion_reason": "numeric_missing_train_quantile_boundary",
            "row_count": int(missing_boundaries),
        })

    audit_dir.mkdir(parents=True, exist_ok=True)
    if not boundaries.is_empty():
        boundaries.write_csv(audit_dir / "meds_numeric_quantile_boundaries.csv")
    if not events.is_empty():
        (
            events.group_by(["source_token", "quantile_bin"])
            .len(name="event_count")
            .sort(["source_token", "quantile_bin"])
            .write_csv(audit_dir / "meds_numeric_quantile_assignments.csv")
        )

    if events.is_empty():
        return empty_debug_frame(), exclusions

    binning_method_expr = (
        pl.col("binning_method").cast(pl.String).fill_null("raw")
        if "binning_method" in events.columns
        else pl.lit("raw")
    )
    raw_rows_expr = (
        pl.col("raw_rows_in_bin").cast(pl.Int64).fill_null(1)
        if "raw_rows_in_bin" in events.columns
        else pl.lit(1).cast(pl.Int64)
    )

    return coerce_debug_frame(
        events.with_columns([
            pl.col("measuredattime").alias("time"),
            (pl.col("harmonized_token") + pl.lit("//Q") + pl.col("quantile_bin").cast(pl.String)).alias("code"),
            pl.lit(None).cast(pl.Float64).alias("numeric_value"),
            pl.col("value").cast(pl.Float64, strict=False).alias("raw_numeric_value"),
            pl.col("comment").cast(pl.String).alias("text_value"),
            pl.lit("numericitems").alias("source_table"),
            pl.col("item").cast(pl.String).alias("source_label"),
            pl.col("unit").cast(pl.String).alias("source_unit"),
            binning_method_expr.alias("binning_method"),
            raw_rows_expr.alias("raw_rows_in_bin"),
        ])
    ), exclusions
