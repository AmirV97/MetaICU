"""Memory-safe token vocabulary inventory from split-aware pre-MEDS data.

This module exists for vocabulary materialization without constructing the
full MEDS event table. It applies the same source joins, phase inclusion,
interval boundaries, quantile decomposition, and tokenizer special tokens as
the regular MEDS/tokenization path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from metaicu.aumcdb.common.parquet import resolve_table_parquet, scan_parquet
from metaicu.aumcdb.tokenized.meds.vocab import load_vocab, table_vocab
from metaicu.aumcdb.tokenized.tokenization.build_workflow import (
    DEFAULT_TIME_INTERVALS_SPEC,
    TIMELINE_END,
)
from metaicu.aumcdb.tokenized.tokenization.vocabulary import build_lexicographic_vocab

INCLUDED_PHASES = ("preadmission", "admission")
QUANTILE_TOKENS = tuple(f"Q{index}" for index in range(1, 11))


@dataclass(frozen=True)
class VocabInventoryConfig:
    """Inputs and outputs for full-cohort token vocabulary inventory."""

    pre_meds_dir: Path
    supplied_vocab: Path
    split_manifest: Path
    output_dir: Path
    unknown_token: str = "UNK"


def _scope_admissions(
    admissions: pl.LazyFrame,
    split_manifest: pl.LazyFrame,
    scope: str,
) -> pl.LazyFrame:
    if scope == "full_data":
        return admissions
    if scope != "train_only":
        raise ValueError("scope must be 'train_only' or 'full_data'")
    train_subjects = split_manifest.filter(pl.col("split") == "train").select("subject_id")
    return admissions.join(train_subjects, on="subject_id", how="semi")


def _admission_ids(scope_admissions: pl.LazyFrame) -> pl.LazyFrame:
    return scope_admissions.select(pl.col("admissionid").cast(pl.Int64)).unique()


def _phase_filter(column: str = "event_temporal_phase") -> pl.Expr:
    return pl.col(column).cast(pl.String).is_in(INCLUDED_PHASES)


def _collect_unique_codes(frame: pl.LazyFrame, code_column: str) -> set[str]:
    return set(
        frame.select(pl.col(code_column).cast(pl.String).alias("code"))
        .drop_nulls()
        .unique()
        .collect(engine="streaming")
        .get_column("code")
        .to_list()
    )


def _anchor_codes(scope_admissions: pl.LazyFrame) -> set[str]:
    codes = {"ICU_ADMISSION", "ICU_DISCHARGE"}
    death_rows = (
        scope_admissions.filter(pl.col("dateofdeathtime").is_not_null())
        .select(pl.len().alias("n"))
        .collect(engine="streaming")
        .item()
    )
    if death_rows:
        codes.add("MEDS_DEATH")
    for column, prefix in (
        ("gender", "GENDER"),
        ("agegroup", "AGEGROUP"),
        ("weightgroup", "WEIGHTGROUP"),
        ("heightgroup", "HEIGHTGROUP"),
    ):
        values = (
            scope_admissions.select(pl.col(column).cast(pl.String))
            .drop_nulls()
            .unique()
            .collect(engine="streaming")
            .get_column(column)
            .to_list()
        )
        codes.update(f"{prefix}//{value}" for value in values)
    return codes


def _measurement_codes(
    pre_meds_dir: Path,
    admission_ids: pl.LazyFrame,
    vocab: pl.DataFrame,
    table: str,
) -> set[str]:
    if table == "numericitems":
        joins = {"_itemid_i64": "itemid", "_unitid_i64": "unitid"}
    elif table == "listitems":
        joins = {"_itemid_i64": "itemid", "_valueid_i64": "valueid"}
    else:
        raise ValueError(f"Unsupported measurement table: {table}")
    tv = table_vocab(vocab, table, joins).filter(pl.col("_emit"))
    rows = (
        scan_parquet(resolve_table_parquet(pre_meds_dir, table))
        .join(admission_ids, on="admissionid", how="semi")
        .filter(_phase_filter())
        .join(tv.lazy(), on=list(joins.values()), how="inner")
    )
    return _collect_unique_codes(rows, "harmonized_token")


def _interval_codes(
    pre_meds_dir: Path,
    admission_ids: pl.LazyFrame,
    vocab: pl.DataFrame,
    table: str,
) -> set[str]:
    if table == "drugitems":
        joins = {
            "_itemid_i64": "itemid",
            "_ordercategoryid_i64": "ordercategoryid",
        }
    elif table == "processitems":
        joins = {"_itemid_i64": "itemid"}
    else:
        raise ValueError(f"Unsupported interval table: {table}")
    tv = table_vocab(vocab, table, joins).filter(pl.col("_emit"))
    rows = (
        scan_parquet(resolve_table_parquet(pre_meds_dir, table))
        .join(admission_ids, on="admissionid", how="semi")
        .join(tv.lazy(), on=list(joins.values()), how="inner")
    )
    starts = _collect_unique_codes(
        rows.filter(_phase_filter("start_temporal_phase")).with_columns(
            (pl.col("harmonized_token") + "//START").alias("_code")
        ),
        "_code",
    )
    valid_end = (
        pl.col("stoptime").is_not_null()
        & pl.col("stop_admission_relative_ms").is_not_null()
        & pl.col("start_admission_relative_ms").is_not_null()
        & (pl.col("stop_admission_relative_ms") >= pl.col("start_admission_relative_ms"))
        & _phase_filter("stop_temporal_phase")
    )
    ends = _collect_unique_codes(
        rows.filter(valid_end).with_columns(
            (pl.col("harmonized_token") + "//END").alias("_code")
        ),
        "_code",
    )
    return starts | ends


def inventory_scope(config: VocabInventoryConfig, scope: str) -> Path:
    """Write one lexicographically stable vocabulary for the requested scope."""

    vocab = load_vocab(config.supplied_vocab)
    admissions = scan_parquet(resolve_table_parquet(config.pre_meds_dir, "admissions"))
    split_manifest = pl.scan_parquet(config.split_manifest)
    scoped_admissions = _scope_admissions(admissions, split_manifest, scope)
    scoped_ids = _admission_ids(scoped_admissions)
    train_admissions = _scope_admissions(admissions, split_manifest, "train_only")
    train_ids = _admission_ids(train_admissions)

    codes = _anchor_codes(scoped_admissions)
    numeric_codes = _measurement_codes(
        config.pre_meds_dir, train_ids, vocab, "numericitems"
    )
    codes.update(numeric_codes)
    if numeric_codes:
        codes.update(QUANTILE_TOKENS)
    codes.update(_measurement_codes(config.pre_meds_dir, scoped_ids, vocab, "listitems"))
    codes.update(_interval_codes(config.pre_meds_dir, scoped_ids, vocab, "drugitems"))
    codes.update(_interval_codes(config.pre_meds_dir, scoped_ids, vocab, "processitems"))
    codes.update(DEFAULT_TIME_INTERVALS_SPEC)
    codes.add(TIMELINE_END)
    if config.unknown_token:
        codes.add(config.unknown_token)

    token_vocab = build_lexicographic_vocab(list(codes))
    config.output_dir.mkdir(parents=True, exist_ok=True)
    artifact_scope = "full" if scope == "full_data" else "train_only"
    output = config.output_dir / f"aumc_token_vocab_{artifact_scope}_t{len(token_vocab)}.csv"
    pl.DataFrame({"code": token_vocab.codes}).write_csv(output, include_header=False)
    return output


def write_scoped_vocabularies(config: VocabInventoryConfig) -> dict[str, Path]:
    """Materialize both requested vocabulary scopes."""

    return {
        scope: inventory_scope(config, scope)
        for scope in ("train_only", "full_data")
    }
