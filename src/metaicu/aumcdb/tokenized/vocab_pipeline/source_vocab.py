"""Source-vocabulary extraction helpers for Amsterdam raw/pre-MEDS inputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl

from metaicu.aumcdb.common.parquet import parquet_row_count, resolve_table_parquet, scan_parquet
from metaicu.aumcdb.tokenized.vocab_pipeline.policy_common import norm_key


SOURCE_VOCAB_COLUMNS = [
    "dataset",
    "source_table",
    "source_itemid",
    "source_valueid",
    "source_unitid",
    "source_ordercategoryid",
    "source_label",
    "source_value",
    "source_unit",
    "source_token",
    "row_count",
]

SOURCE_TABLES = [
    "numericitems",
    "listitems",
    "drugitems",
    "freetextitems",
    "processitems",
    "procedureorderitems",
]

RAW_CSV_CHUNK_ROWS = 1_000_000

EXPECTED_PREFIXES = {
    "numericitems": {"LAB", "MEASUREMENT_BEDSIDE", "SUBJECT_FLUID_OUTPUT"},
    "listitems": {"MEASUREMENT_CATEGORICAL"},
    "drugitems": {"DRUG"},
    "freetextitems": {"FREETEXT"},
    "processitems": {"PROCESS_INTERVAL"},
    "procedureorderitems": {"ORDER_INTENT"},
}

FREETEXT_PSEUDO_VALUE_ID = "1"


@dataclass(frozen=True)
class SourceVocabConfig:
    """Inputs and output locations for source-vocabulary extraction."""

    pre_meds_dir: Path | None
    audit_dir: Path
    max_rows_per_table: int | None = None
    reference_vocab: Path | None = None
    dataset: str = "AmsterdamUMCdb"
    input_format: str = "raw"
    raw_data_dir: Path | None = None


def _limited_scan(pre_meds_dir: Path, table: str, max_rows: int | None) -> pl.LazyFrame:
    frame = scan_parquet(resolve_table_parquet(pre_meds_dir, table))
    if max_rows is not None:
        return frame.limit(max_rows)
    return frame


def _input_scan(config: SourceVocabConfig, table: str) -> pl.LazyFrame:
    if config.input_format == "pre_meds":
        if config.pre_meds_dir is None:
            raise ValueError("source_vocab.input_format=pre_meds requires paths.pre_meds_dir")
        return _limited_scan(config.pre_meds_dir, table, config.max_rows_per_table)
    raise ValueError(f"_input_scan only supports pre_meds input, not {config.input_format!r}")


def _text_expr(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Utf8)


def _id_expr(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Int64).cast(pl.Utf8)


def _null_text() -> pl.Expr:
    return pl.lit(None, dtype=pl.Utf8)


def _count_vocab(frame: pl.LazyFrame, group_exprs: list[pl.Expr]) -> pl.DataFrame:
    return (
        frame.group_by(group_exprs)
        .len(name="row_count")
        .collect(engine="streaming")
    )


def _count_raw_vocab(
    config: SourceVocabConfig,
    table: str,
    group_columns: list[str],
    add_numeric_prefix: bool = False,
) -> pl.DataFrame:
    """Count raw source-key combinations in bounded, Latin-1-preserving chunks."""

    if config.raw_data_dir is None:
        raise ValueError("source_vocab.input_format=raw requires paths.raw_data_dir")
    path = config.raw_data_dir / f"{table}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Raw Amsterdam table not found: {path}")

    usecols = list(group_columns)
    if add_numeric_prefix:
        usecols.extend(["islabresult", "fluidout"])
    count_columns = group_columns + (["code_prefix"] if add_numeric_prefix else [])

    combined: pd.DataFrame | None = None
    for chunk in pd.read_csv(
        path,
        encoding="latin1",
        usecols=usecols,
        dtype=str,
        keep_default_na=False,
        chunksize=RAW_CSV_CHUNK_ROWS,
        nrows=config.max_rows_per_table,
        low_memory=False,
    ):
        if add_numeric_prefix:
            is_lab = pd.to_numeric(chunk["islabresult"], errors="coerce").eq(1)
            is_fluid_out = pd.to_numeric(chunk["fluidout"], errors="coerce").eq(1)
            chunk["code_prefix"] = "MEASUREMENT_BEDSIDE"
            chunk.loc[is_fluid_out, "code_prefix"] = "SUBJECT_FLUID_OUTPUT"
            chunk.loc[is_lab, "code_prefix"] = "LAB"
        batch_counts = (
            chunk.groupby(count_columns, dropna=False, sort=False)
            .size()
            .rename("row_count")
            .reset_index()
        )
        if combined is None:
            combined = batch_counts
        else:
            combined = pd.concat([combined, batch_counts], ignore_index=True)
            combined = (
                combined.groupby(count_columns, dropna=False, sort=False)["row_count"]
                .sum()
                .reset_index()
            )

    if combined is None:
        return pl.DataFrame({column: [] for column in [*count_columns, "row_count"]})
    return pl.from_pandas(combined)


def _grouped_count(
    config: SourceVocabConfig,
    table: str,
    group_columns: list[str],
    add_numeric_prefix: bool = False,
) -> pl.DataFrame:
    if config.input_format == "raw":
        return _count_raw_vocab(config, table, group_columns, add_numeric_prefix)
    frame = _input_scan(config, table)
    expressions = [pl.col(column) for column in group_columns]
    if add_numeric_prefix:
        expressions.append(pl.col("code_prefix"))
    return _count_vocab(frame, expressions)


NULL_TEXT_LITERALS = ["none", "nan", "null", "<na>"]


def _is_null_text_expr(column: str) -> pl.Expr:
    """True for an actually-null value, an empty/whitespace string, or a literal null-text
    token (e.g. the raw AmsterdamUMCdb export encodes some missing ``unit`` cells as the literal
    text "None", not an empty field). Mirrors the historical pipeline's ``normalize_code``/this
    package's ``policy_common.norm_key`` null-literal convention.
    """

    text = _text_expr(column)
    return text.is_null() | (text.str.strip_chars() == "") | (text.str.strip_chars().str.to_lowercase().is_in(NULL_TEXT_LITERALS))


def _numeric_vocab(config: SourceVocabConfig) -> pd.DataFrame:
    unit_token = pl.when(_is_null_text_expr("unit"))
    unit_token = unit_token.then(pl.lit("UNKNOWN")).otherwise(_text_expr("unit"))
    grouped = _grouped_count(
        config,
        "numericitems",
        ["itemid", "item", "unitid", "unit"],
        add_numeric_prefix=True,
    )
    out = grouped.select(
        pl.lit(config.dataset).alias("dataset"),
        pl.lit("numericitems").alias("source_table"),
        _id_expr("itemid").alias("source_itemid"),
        _null_text().alias("source_valueid"),
        _id_expr("unitid").alias("source_unitid"),
        _null_text().alias("source_ordercategoryid"),
        _text_expr("item").alias("source_label"),
        _null_text().alias("source_value"),
        _text_expr("unit").alias("source_unit"),
        (pl.col("code_prefix").cast(pl.Utf8) + "//" + _id_expr("itemid") + "//" + unit_token).alias("source_token"),
        pl.col("row_count").cast(pl.Int64),
    )
    return out.to_pandas()


def _list_vocab(config: SourceVocabConfig) -> pd.DataFrame:
    grouped = _grouped_count(config, "listitems", ["itemid", "item", "valueid", "value"])
    out = grouped.select(
        pl.lit(config.dataset).alias("dataset"),
        pl.lit("listitems").alias("source_table"),
        _id_expr("itemid").alias("source_itemid"),
        _id_expr("valueid").alias("source_valueid"),
        _null_text().alias("source_unitid"),
        _null_text().alias("source_ordercategoryid"),
        _text_expr("item").alias("source_label"),
        _text_expr("value").alias("source_value"),
        _null_text().alias("source_unit"),
        (pl.lit("MEASUREMENT_CATEGORICAL//") + _id_expr("itemid") + "//" + _id_expr("valueid")).alias("source_token"),
        pl.col("row_count").cast(pl.Int64),
    )
    return out.to_pandas()


def _drug_vocab(config: SourceVocabConfig) -> pd.DataFrame:
    grouped = _grouped_count(
        config,
        "drugitems",
        ["itemid", "item", "ordercategoryid", "ordercategory"],
    )
    out = grouped.select(
        pl.lit(config.dataset).alias("dataset"),
        pl.lit("drugitems").alias("source_table"),
        _id_expr("itemid").alias("source_itemid"),
        _null_text().alias("source_valueid"),
        _null_text().alias("source_unitid"),
        _id_expr("ordercategoryid").alias("source_ordercategoryid"),
        _text_expr("item").alias("source_label"),
        _text_expr("ordercategory").alias("source_value"),
        _null_text().alias("source_unit"),
        (pl.lit("DRUG//START//") + _id_expr("ordercategoryid") + "//" + _id_expr("itemid")).alias("source_token"),
        pl.col("row_count").cast(pl.Int64),
    )
    return out.to_pandas()


def _freetext_vocab(config: SourceVocabConfig) -> pd.DataFrame:
    grouped = _grouped_count(config, "freetextitems", ["itemid", "item"])
    # Freetext is grouped at item level only; this stable pseudo-value ID keeps
    # the token shape compatible with item/value source tokens without using raw text.
    out = grouped.select(
        pl.lit(config.dataset).alias("dataset"),
        pl.lit("freetextitems").alias("source_table"),
        _id_expr("itemid").alias("source_itemid"),
        _null_text().alias("source_valueid"),
        _null_text().alias("source_unitid"),
        _null_text().alias("source_ordercategoryid"),
        _text_expr("item").alias("source_label"),
        _null_text().alias("source_value"),
        _null_text().alias("source_unit"),
        (pl.lit("FREETEXT//") + _id_expr("itemid") + "//" + pl.lit(FREETEXT_PSEUDO_VALUE_ID)).alias("source_token"),
        pl.col("row_count").cast(pl.Int64),
    )
    return out.to_pandas()


def _process_vocab(config: SourceVocabConfig) -> pd.DataFrame:
    grouped = _grouped_count(config, "processitems", ["itemid", "item"])
    out = grouped.select(
        pl.lit(config.dataset).alias("dataset"),
        pl.lit("processitems").alias("source_table"),
        _id_expr("itemid").alias("source_itemid"),
        _null_text().alias("source_valueid"),
        _null_text().alias("source_unitid"),
        _null_text().alias("source_ordercategoryid"),
        _text_expr("item").alias("source_label"),
        _null_text().alias("source_value"),
        _null_text().alias("source_unit"),
        (pl.lit("PROCESS_INTERVAL//") + _id_expr("itemid")).alias("source_token"),
        pl.col("row_count").cast(pl.Int64),
    )
    return out.to_pandas()


def _procedure_vocab(config: SourceVocabConfig) -> pd.DataFrame:
    grouped = _grouped_count(
        config,
        "procedureorderitems",
        ["itemid", "item", "ordercategoryid", "ordercategoryname"],
    )
    out = grouped.select(
        pl.lit(config.dataset).alias("dataset"),
        pl.lit("procedureorderitems").alias("source_table"),
        _id_expr("itemid").alias("source_itemid"),
        _null_text().alias("source_valueid"),
        _null_text().alias("source_unitid"),
        _id_expr("ordercategoryid").alias("source_ordercategoryid"),
        _text_expr("item").alias("source_label"),
        _text_expr("ordercategoryname").alias("source_value"),
        _null_text().alias("source_unit"),
        (pl.lit("ORDER_INTENT//") + _id_expr("ordercategoryid") + "//" + _id_expr("itemid")).alias("source_token"),
        pl.col("row_count").cast(pl.Int64),
    )
    return out.to_pandas()


EXTRACTORS = {
    "numericitems": _numeric_vocab,
    "listitems": _list_vocab,
    "drugitems": _drug_vocab,
    "freetextitems": _freetext_vocab,
    "processitems": _process_vocab,
    "procedureorderitems": _procedure_vocab,
}


def extract_source_vocab(config: SourceVocabConfig) -> pd.DataFrame:
    """Extract canonical source-token rows from all supported Amsterdam tables."""

    frames = [EXTRACTORS[table](config) for table in SOURCE_TABLES]
    vocab = pd.concat(frames, ignore_index=True)
    vocab = vocab[SOURCE_VOCAB_COLUMNS].copy()
    vocab["row_count"] = pd.to_numeric(vocab["row_count"], errors="raise").astype("int64")
    vocab = vocab.sort_values(["source_table", "row_count", "source_token"], ascending=[True, False, True])
    return vocab.reset_index(drop=True)


def _prefixes(series: pd.Series) -> set[str]:
    return set(series.fillna("").astype(str).str.split("//").str[0])


def validate_source_vocab(vocab: pd.DataFrame, config: SourceVocabConfig) -> dict[str, Any]:
    """Return source-vocabulary validation and row-accounting details."""

    empty_token_count = int(vocab["source_token"].fillna("").astype(str).str.strip().eq("").sum())
    duplicate_count = int(vocab["source_token"].duplicated().sum())
    nonpositive_row_count = int((pd.to_numeric(vocab["row_count"], errors="coerce") <= 0).sum())
    tables: dict[str, Any] = {}
    for table in SOURCE_TABLES:
        table_vocab = vocab[vocab["source_table"].eq(table)].copy()
        if config.input_format == "raw":
            # Raw extraction is unfiltered. The grouped counts are accumulated while
            # reading every input chunk, so their sum is the input row count.
            scanned_rows = int(table_vocab["row_count"].sum())
        else:
            if config.pre_meds_dir is None:
                raise ValueError("source_vocab.input_format=pre_meds requires paths.pre_meds_dir")
            parquet_path = resolve_table_parquet(config.pre_meds_dir, table)
            scanned_rows = (
                min(parquet_row_count(parquet_path), config.max_rows_per_table)
                if config.max_rows_per_table is not None
                else parquet_row_count(parquet_path)
            )
        row_count_sum = int(table_vocab["row_count"].sum())
        prefixes = _prefixes(table_vocab["source_token"])
        unexpected_prefixes = sorted(prefixes - EXPECTED_PREFIXES[table])
        tables[table] = {
            "source_tokens": int(len(table_vocab)),
            "row_count_sum": row_count_sum,
            "input_rows_scanned": int(scanned_rows),
            "row_count_matches_input_rows": bool(row_count_sum == scanned_rows),
            "prefixes": sorted(prefixes),
            "unexpected_prefixes": unexpected_prefixes,
        }
    return {
        "source_tokens": int(len(vocab)),
        "row_count_sum": int(vocab["row_count"].sum()),
        "empty_source_tokens": empty_token_count,
        "duplicate_source_tokens": duplicate_count,
        "nonpositive_row_counts": nonpositive_row_count,
        "tables": tables,
    }


def compare_to_reference(extracted: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Compare extracted source vocab against a supplied reference vocabulary.

    This optional regression audit is intentionally simple at current vocab scale.
    """

    compare_columns = SOURCE_VOCAB_COLUMNS
    left = extracted[compare_columns].copy()
    right = reference[compare_columns].copy()
    for frame in [left, right]:
        for col in compare_columns:
            if col != "row_count":
                frame[col] = frame[col].map(norm_key)
        frame["row_count"] = pd.to_numeric(frame["row_count"], errors="coerce").fillna(-1).astype("int64")
    merged = left.merge(right, on="source_token", how="outer", suffixes=("_extracted", "_reference"), indicator=True)
    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        token = row["source_token"]
        if row["_merge"] == "left_only":
            rows.append({"source_token": token, "diff_type": "extra_in_extracted"})
            continue
        if row["_merge"] == "right_only":
            rows.append({"source_token": token, "diff_type": "missing_in_extracted"})
            continue
        mismatched = []
        for col in compare_columns:
            if col == "source_token":
                continue
            if row[f"{col}_extracted"] != row[f"{col}_reference"]:
                mismatched.append(col)
        if mismatched:
            rows.append(
                {
                    "source_token": token,
                    "diff_type": "field_mismatch",
                    "mismatched_fields": ";".join(mismatched),
                }
            )
    return pd.DataFrame(rows, columns=["source_token", "diff_type", "mismatched_fields"])


def write_source_vocab_outputs(config: SourceVocabConfig) -> dict[str, Path]:
    """Extract source vocab and write CSV/JSON audit outputs."""

    config.audit_dir.mkdir(parents=True, exist_ok=True)
    vocab = extract_source_vocab(config)
    summary = validate_source_vocab(vocab, config)
    source_vocab_path = config.audit_dir / "vocab_pipeline_source_vocab.csv"
    summary_path = config.audit_dir / "vocab_pipeline_source_vocab_summary.json"
    vocab.to_csv(source_vocab_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    outputs = {"source_vocab": source_vocab_path, "summary": summary_path}
    if config.reference_vocab is not None:
        reference = pd.read_csv(config.reference_vocab, low_memory=False)
        diffs = compare_to_reference(vocab, reference)
        diff_path = config.audit_dir / "vocab_pipeline_source_vocab_vs_reference.csv"
        diffs.to_csv(diff_path, index=False)
        outputs["reference_diff"] = diff_path
    return outputs
