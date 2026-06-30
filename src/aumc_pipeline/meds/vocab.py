"""Vocabulary loading and typed join-key preparation.

Consumes aumc_supplied_vocab.csv as the policy source of truth.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from aumc_pipeline.meds.common import string_bool_expr


def load_vocab(vocab_path: Path) -> pl.DataFrame:
    """Load aumc_supplied_vocab.csv with typed join keys for all tables."""
    vocab = pl.read_csv(vocab_path, infer_schema_length=10000)
    return vocab.with_columns([
        string_bool_expr("emit_as_model_token").alias("_emit"),
        pl.col("source_itemid").cast(pl.Int64, strict=False).alias("_itemid_i64"),
        pl.col("source_valueid").cast(pl.Int64, strict=False).alias("_valueid_i64"),
        pl.col("source_unitid").cast(pl.Int64, strict=False).alias("_unitid_i64"),
        pl.col("source_ordercategoryid").cast(pl.Int64, strict=False).alias("_ordercategoryid_i64"),
    ])


def table_vocab(
    vocab: pl.DataFrame,
    source_table: str,
    join_key_renames: dict[str, str],
) -> pl.DataFrame:
    """Filter vocab for one source table and rename typed ID columns to join key names.

    join_key_renames maps typed alias column → target pre-MEDS column name.
    Example for numericitems: {"_itemid_i64": "itemid", "_unitid_i64": "unitid"}
    """
    select_cols = list(join_key_renames.keys()) + [
        "source_token", "harmonized_token", "token_role", "_emit",
        "source_label", "source_value", "source_unit",
    ]
    return (
        vocab
        .filter(pl.col("source_table") == source_table)
        .select(select_cols)
        .rename(join_key_renames)
    )
