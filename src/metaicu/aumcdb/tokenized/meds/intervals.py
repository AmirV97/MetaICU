"""Drugitems and processitems → START/END boundary MEDS events.

Each source row produces up to two events:
  {harmonized_token}//START  at starttime  (when start phase is included)
  {harmonized_token}//END    at stoptime   (when stop is valid and stop phase is included)

End events are dropped when: stop is null, stop < start, or stop phase is excluded.
All counts are recorded in the interval audit.
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
from metaicu.aumcdb.tokenized.meds.vocab import table_vocab
from metaicu.aumcdb.tokenized.utils.parquet_datasets import parquet_exists, resolve_table_parquet, scan_parquet


def interval_events(
    admission_ids: Sequence[int],
    pre_meds_dir: Path,
    vocab: pl.DataFrame,
    table: str,
    include_phases: Sequence[str],
) -> tuple[pl.DataFrame, list[dict], dict]:
    """Emit START/END boundary events for drugitems or processitems.

    Data shape:
      in:  pre-MEDS parquet with starttime/stoptime and *_admission_relative_ms columns
      out: debug frame — up to 2 rows per source row (START + optional END)
    Returns (events_df, exclusion_records, interval_audit_dict).

    drugitems join key: (itemid, ordercategoryid)
    processitems join key: (itemid,)
    """
    if table == "drugitems":
        join_key_renames = {
            "_itemid_i64": "itemid",
            "_ordercategoryid_i64": "ordercategoryid",
        }
        start_rel = "start_admission_relative_ms"
        stop_rel = "stop_admission_relative_ms"
        label_col = "item"
        value_col = "ordercategory"
    elif table == "processitems":
        join_key_renames = {"_itemid_i64": "itemid"}
        start_rel = "start_admission_relative_ms"
        stop_rel = "stop_admission_relative_ms"
        label_col = "item"
        value_col = "item"
    else:
        raise ValueError(f"interval_events only supports drugitems/processitems, got: {table!r}")

    table_path = resolve_table_parquet(pre_meds_dir, table)
    if not parquet_exists(table_path):
        return empty_debug_frame(), [], {}

    tv = table_vocab(vocab, table, join_key_renames)
    join_keys = list(join_key_renames.values())

    raw = (
        scan_parquet(table_path)
        .filter(pl.col("admissionid").is_in(list(admission_ids)))
        .join(tv.lazy(), on=join_keys, how="left")
        .with_columns([
            runtime_phase_expr(start_rel).alias("_start_phase"),
            runtime_phase_expr(stop_rel).alias("_stop_phase"),
        ])
        .collect(engine="streaming")
    )

    exclusions = record_join_exclusions(table, raw, list(include_phases))
    emitted = raw.filter(pl.col("_emit"))
    if emitted.is_empty():
        return empty_debug_frame(), exclusions, {}

    start_rows = emitted.filter(
        pl.col("_start_phase").is_in(list(include_phases))
    ).with_columns([
        pl.col("starttime").alias("time"),
        (pl.col("harmonized_token") + pl.lit("//START")).alias("code"),
        pl.col("_start_phase").alias("temporal_phase"),
        pl.lit("START").alias("interval_boundary"),
        pl.col(label_col).cast(pl.String).alias("source_label"),
        pl.col(value_col).cast(pl.String).alias("source_value"),
        pl.lit(table).alias("source_table"),
        pl.lit(None).cast(pl.Float64).alias("numeric_value"),
        pl.lit(None).cast(pl.String).alias("text_value"),
    ])

    # Valid end: stop not null, stop >= start, stop phase included
    valid_end_mask = (
        pl.col("stoptime").is_not_null()
        & pl.col(stop_rel).is_not_null()
        & pl.col(start_rel).is_not_null()
        & (pl.col(stop_rel) >= pl.col(start_rel))
        & pl.col("_stop_phase").is_in(list(include_phases))
    )
    end_rows = emitted.filter(valid_end_mask).with_columns([
        pl.col("stoptime").alias("time"),
        (pl.col("harmonized_token") + pl.lit("//END")).alias("code"),
        pl.col("_stop_phase").alias("temporal_phase"),
        pl.lit("END").alias("interval_boundary"),
        pl.col(label_col).cast(pl.String).alias("source_label"),
        pl.col(value_col).cast(pl.String).alias("source_value"),
        pl.lit(table).alias("source_table"),
        pl.lit(None).cast(pl.Float64).alias("numeric_value"),
        pl.lit(None).cast(pl.String).alias("text_value"),
    ])

    invalid_end = emitted.filter(
        pl.col("stoptime").is_null()
        | pl.col(stop_rel).is_null()
        | pl.col(start_rel).is_null()
        | (pl.col(stop_rel) < pl.col(start_rel))
    ).height
    phase_excluded_end = emitted.height - end_rows.height - invalid_end

    audit = {
        "source_table": table,
        "source_rows": int(emitted.height),
        "start_events": int(start_rows.height),
        "end_events": int(end_rows.height),
        "invalid_or_missing_end_rows": int(invalid_end),
        "phase_excluded_end_rows": int(max(phase_excluded_end, 0)),
    }

    non_empty = [coerce_debug_frame(f) for f in [start_rows, end_rows] if not f.is_empty()]
    if not non_empty:
        return empty_debug_frame(), exclusions, audit
    return pl.concat(non_empty, how="vertical_relaxed"), exclusions, audit
