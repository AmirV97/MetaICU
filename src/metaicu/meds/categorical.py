"""Listitems → MEDS events.

Handles two event classes from listitems:

1. Static context (token_role starts with 'static_context'):
   Includes static_context/diagnosis_context (D_*, DMC_*, NICE, APACHE rows)
   and static_context/admission_type (NICE Opname type). Both use the same
   dedup policy: drop identical (admissionid, itemid, valueid) duplicates per
   admission; anchor the first fact(s) at admittedattime; emit later unique
   facts at measuredattime.

   Detection uses token_role after the vocab join, NOT raw item string prefixes.
   This correctly covers all v11 diagnosis-context and admission-type rows.

   GCS eye/motor/verbal component rows (token_role=dynamic_event/score_component)
   are NOT static context — they pass through as ordinary dynamic events with
   code=harmonized_token, time=measuredattime.

   BPS component rows are non-emitted in the vocab (_emit=False). BPS total
   derivation is out of scope for this port: components are filtered out before
   the MEDS row assembly step, making reconstruction impossible here. A future
   extension should read BPS components before the _emit filter.

2. Ordinary dynamic events (all other emitted token_roles):
   code=harmonized_token, time=measuredattime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import polars as pl

from metaicu.meds.common import (
    coerce_debug_frame,
    empty_debug_frame,
    record_join_exclusions,
    runtime_phase_expr,
)
from metaicu.meds.vocab import table_vocab
from metaicu.utils.parquet_datasets import parquet_exists, resolve_table_parquet, scan_parquet


def static_context_events(raw: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Dedup and emit all token_role='static_context/*' rows from listitems.

    Data shape:
      in:  filtered+joined listitems rows where token_role starts with 'static_context'
      out: debug frame with deduplicated static context events

    Dedup key: (admissionid, itemid, valueid)
      — same source fact repeated across the stay is collapsed to first occurrence.
    Time assignment:
      — rows with the earliest admission_relative_ms per admission → time=admittedattime
      — all other deduplicated rows → time=measuredattime, token_role overridden
        to 'dynamic_event/clinical_context_update'
    """
    static = raw.filter(pl.col("token_role").cast(pl.String).str.starts_with("static_context"))
    if static.is_empty():
        return empty_debug_frame(), {}

    before = static.height
    deduped = static.sort(
        ["admissionid", "itemid", "valueid", "admission_relative_ms"]
    ).unique(
        subset=["admissionid", "itemid", "valueid"],
        keep="first",
        maintain_order=True,
    )

    # Earliest admission_relative_ms per admission → those rows anchor at admittedattime
    first_per_adm = deduped.group_by("admissionid").agg(
        pl.col("admission_relative_ms").min().alias("_first_rel_ms")
    )
    out = deduped.join(first_per_adm, on="admissionid", how="left").with_columns([
        pl.when(pl.col("admission_relative_ms") == pl.col("_first_rel_ms"))
        .then(pl.col("admittedattime"))
        .otherwise(pl.col("measuredattime"))
        .alias("time"),
        # Later unique facts are treated as context updates, not static context
        pl.when(pl.col("admission_relative_ms") == pl.col("_first_rel_ms"))
        .then(pl.col("token_role"))
        .otherwise(pl.lit("dynamic_event/clinical_context_update"))
        .alias("token_role"),
    ]).drop("_first_rel_ms")

    audit = {
        "source_rows": int(before),
        "deduplicated_rows": int(deduped.height),
        "suppressed_duplicate_facts": int(before - deduped.height),
    }
    return coerce_debug_frame(
        out.with_columns([
            pl.col("harmonized_token").alias("code"),
            pl.lit(None).cast(pl.Float64).alias("numeric_value"),
            pl.col("value").cast(pl.String).alias("text_value"),
            pl.lit("listitems").alias("source_table"),
            pl.col("item").cast(pl.String).alias("source_label"),
            pl.col("value").cast(pl.String).alias("source_value"),
        ])
    ), audit


def list_events(
    admission_ids: Sequence[int],
    pre_meds_dir: Path,
    vocab: pl.DataFrame,
    include_phases: Sequence[str],
    max_rows: int | None = None,
) -> tuple[pl.DataFrame, list[dict], dict]:
    """Join listitems to vocab and emit static context + dynamic events.

    Data shape:
      in:  listitems parquet — one row per categorical measurement (itemid, valueid)
      out: debug frame — one row per emitted event
    Rows dropped: unmatched vocab join, non-emitted, out-of-phase, diagnosis dedup.
    Returns (events_df, exclusion_records, static_context_audit_dict).
    """
    list_path = resolve_table_parquet(pre_meds_dir, "listitems")
    if not parquet_exists(list_path):
        return empty_debug_frame(), [], {}

    tv = table_vocab(vocab, "listitems", {"_itemid_i64": "itemid", "_valueid_i64": "valueid"})

    scan = (
        scan_parquet(list_path)
        .filter(pl.col("admissionid").is_in(list(admission_ids)))
    )
    if max_rows is not None:
        scan = scan.limit(max_rows)
    raw = (
        scan
        .join(tv.lazy(), on=["itemid", "valueid"], how="left")
        .with_columns(runtime_phase_expr("admission_relative_ms").alias("temporal_phase"))
        .collect(engine="streaming")
    )

    exclusions = record_join_exclusions("listitems", raw, list(include_phases))
    filtered = raw.filter(pl.col("_emit") & pl.col("temporal_phase").is_in(list(include_phases)))
    if filtered.is_empty():
        return empty_debug_frame(), exclusions, {}

    static_df, static_audit = static_context_events(filtered)

    dynamic = filtered.filter(
        ~pl.col("token_role").cast(pl.String).str.starts_with("static_context")
    )
    if dynamic.is_empty():
        ordinary_df = empty_debug_frame()
    else:
        ordinary_df = coerce_debug_frame(
            dynamic.with_columns([
                pl.col("measuredattime").alias("time"),
                pl.col("harmonized_token").alias("code"),
                pl.lit(None).cast(pl.Float64).alias("numeric_value"),
                pl.col("value").cast(pl.String).alias("text_value"),
                pl.lit("listitems").alias("source_table"),
                pl.col("item").cast(pl.String).alias("source_label"),
                pl.col("value").cast(pl.String).alias("source_value"),
            ])
        )

    non_empty = [f for f in [static_df, ordinary_df] if not f.is_empty()]
    if not non_empty:
        return empty_debug_frame(), exclusions, static_audit
    return pl.concat(non_empty, how="vertical_relaxed"), exclusions, static_audit
