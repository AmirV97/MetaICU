"""Source-vocabulary extraction helpers for Amsterdam raw/pre-MEDS inputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl

from metaicu.utils.parquet_datasets import parquet_row_count, resolve_table_parquet, scan_parquet
from metaicu.vocab_pipeline.policy_common import norm_key


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


def _scan_raw_csv(raw_data_dir: Path, table: str, max_rows: int | None) -> pl.LazyFrame:
    path = raw_data_dir / f"{table}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Raw Amsterdam table not found: {path}")
    frame = pl.scan_csv(path, encoding="utf8-lossy", infer_schema_length=0, null_values=[])
    if max_rows is not None:
        return frame.limit(max_rows)
    return frame


def _input_scan(config: SourceVocabConfig, table: str) -> pl.LazyFrame:
    if config.input_format == "raw":
        if config.raw_data_dir is None:
            raise ValueError("source_vocab.input_format=raw requires paths.raw_data_dir")
        return _scan_raw_csv(config.raw_data_dir, table, config.max_rows_per_table)
    if config.input_format == "pre_meds":
        if config.pre_meds_dir is None:
            raise ValueError("source_vocab.input_format=pre_meds requires paths.pre_meds_dir")
        return _limited_scan(config.pre_meds_dir, table, config.max_rows_per_table)
    raise ValueError(f"Unsupported source vocab input_format: {config.input_format!r}")


def _numeric_code_prefix_expr() -> pl.Expr:
    is_lab = pl.col("islabresult").cast(pl.Utf8).str.strip_chars().eq("1")
    is_fluid_out = pl.col("fluidout").cast(pl.Utf8).str.strip_chars().eq("1")
    return (
        pl.when(is_lab)
        .then(pl.lit("LAB"))
        .when(is_fluid_out)
        .then(pl.lit("SUBJECT_FLUID_OUTPUT"))
        .otherwise(pl.lit("MEASUREMENT_BEDSIDE"))
    )


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


def _numeric_vocab(config: SourceVocabConfig) -> pd.DataFrame:
    frame = _input_scan(config, "numericitems")
    if config.input_format == "raw":
        frame = frame.with_columns(_numeric_code_prefix_expr().alias("code_prefix"))
    unit_token = pl.when(_text_expr("unit").is_null() | (_text_expr("unit").str.strip_chars() == ""))
    unit_token = unit_token.then(pl.lit("UNKNOWN")).otherwise(_text_expr("unit"))
    grouped = _count_vocab(
        frame,
        [
            pl.col("itemid"),
            pl.col("item"),
            pl.col("unitid"),
            pl.col("unit"),
            pl.col("code_prefix"),
        ],
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
    frame = _input_scan(config, "listitems")
    grouped = _count_vocab(frame, [pl.col("itemid"), pl.col("item"), pl.col("valueid"), pl.col("value")])
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
    frame = _input_scan(config, "drugitems")
    grouped = _count_vocab(
        frame,
        [pl.col("itemid"), pl.col("item"), pl.col("ordercategoryid"), pl.col("ordercategory")],
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
    frame = _input_scan(config, "freetextitems")
    grouped = _count_vocab(frame, [pl.col("itemid"), pl.col("item")])
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
    frame = _input_scan(config, "processitems")
    grouped = _count_vocab(frame, [pl.col("itemid"), pl.col("item")])
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
    frame = _input_scan(config, "procedureorderitems")
    grouped = _count_vocab(
        frame,
        [pl.col("itemid"), pl.col("item"), pl.col("ordercategoryid"), pl.col("ordercategoryname")],
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
            scanned_rows = _input_scan(config, table).select(pl.len()).collect(engine="streaming").item()
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
