"""Candidate-map construction for the Amsterdam vocabulary pipeline.

This module joins canonical source-token rows to normalized external evidence.
It deliberately stops before ranking, semantic policy, or OMOP validation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from aumc_pipeline.vocab_pipeline.evidence_normalization import EVIDENCE_COLUMNS
from aumc_pipeline.vocab_pipeline.source_vocab import SOURCE_VOCAB_COLUMNS


CANDIDATE_EXTRA_COLUMNS = [
    "candidate_id",
    "candidate_match_method",
    "candidate_match_specificity",
    "candidate_match_scope",
]

EVIDENCE_OUTPUT_COLUMNS = [
    "evidence_id",
    "evidence_family",
    "evidence_source",
    "evidence_file",
    "evidence_role",
    "source_code",
    "source_vocabulary",
    "target_vocabulary",
    "target_concept_id",
    "target_code",
    "target_label",
    "mapping_status",
    "equivalence",
    "match_type",
    "evidence_text",
    "join_key_status",
]

CANDIDATE_COLUMNS = SOURCE_VOCAB_COLUMNS + CANDIDATE_EXTRA_COLUMNS + EVIDENCE_OUTPUT_COLUMNS

SOURCE_KEY_COLUMNS = [
    "source_table",
    "source_itemid",
    "source_valueid",
    "source_unitid",
    "source_ordercategoryid",
]


@dataclass(frozen=True)
class CandidateMapConfig:
    """Inputs and output location for candidate-map construction."""

    source_vocab: Path
    mapping_evidence: Path
    audit_dir: Path


def _norm(value: object) -> str:
    """Normalize typed source keys for deterministic equality joins."""

    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        try:
            return str(int(float(text)))
        except ValueError:
            return text
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _label_norm(value: object) -> str:
    """Normalize labels for exact context matching only."""

    return " ".join(_norm(value).casefold().split())


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    return frame


def load_source_vocab(path: Path) -> pd.DataFrame:
    """Load Step 2 source vocabulary with normalized key columns."""

    source = _read_csv(path, SOURCE_VOCAB_COLUMNS)
    for col in SOURCE_VOCAB_COLUMNS:
        if col != "row_count":
            source[col] = source[col].map(_norm)
    source["row_count"] = pd.to_numeric(source["row_count"], errors="raise").astype("int64")
    source["_label_key"] = source["source_label"].map(_label_norm)
    return source


def load_mapping_evidence(path: Path) -> pd.DataFrame:
    """Load Step 3 normalized evidence with normalized key columns."""

    evidence = _read_csv(path, EVIDENCE_COLUMNS)
    for col in EVIDENCE_COLUMNS:
        evidence[col] = evidence[col].map(_norm)
    evidence["_label_key"] = evidence["source_label"].map(_label_norm)
    return evidence


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _no_other_keys(evidence: pd.DataFrame, except_keys: set[str]) -> pd.Series:
    mask = pd.Series(True, index=evidence.index)
    for col in ["source_valueid", "source_unitid", "source_ordercategoryid"]:
        if col not in except_keys:
            mask &= evidence[col].eq("")
    return mask


def _join_candidates(
    source: pd.DataFrame,
    evidence: pd.DataFrame,
    source_mask: pd.Series,
    evidence_mask: pd.Series,
    keys: list[str],
    method: str,
    specificity: int,
    scope: str,
) -> pd.DataFrame:
    left = source.loc[source_mask, SOURCE_VOCAB_COLUMNS].copy()
    right = evidence.loc[evidence_mask, keys + EVIDENCE_OUTPUT_COLUMNS].copy()
    if left.empty or right.empty:
        return _empty(CANDIDATE_COLUMNS)
    right = right.drop_duplicates(keys + EVIDENCE_OUTPUT_COLUMNS)
    merged = left.merge(right, on=keys, how="inner")
    if merged.empty:
        return _empty(CANDIDATE_COLUMNS)
    merged["candidate_match_method"] = method
    merged["candidate_match_specificity"] = specificity
    merged["candidate_match_scope"] = scope
    merged["candidate_id"] = ""
    return merged[CANDIDATE_COLUMNS]


def _typed_candidate_frames(source: pd.DataFrame, evidence: pd.DataFrame) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    table = source["source_table"]
    ev_table = evidence["source_table"]

    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("numericitems"),
            ev_table.eq("numericitems") & evidence["source_itemid"].ne("") & evidence["source_unitid"].ne(""),
            ["source_table", "source_itemid", "source_unitid"],
            "numeric_item_unit",
            100,
            "typed_key",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("numericitems"),
            ev_table.eq("numericitems")
            & evidence["source_itemid"].ne("")
            & evidence["source_unitid"].eq("")
            & _no_other_keys(evidence, set()),
            ["source_table", "source_itemid"],
            "numeric_item",
            70,
            "typed_item",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("listitems"),
            ev_table.eq("listitems") & evidence["source_itemid"].ne("") & evidence["source_valueid"].ne(""),
            ["source_table", "source_itemid", "source_valueid"],
            "list_item_value",
            100,
            "typed_key",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("listitems"),
            ev_table.eq("listitems")
            & evidence["source_itemid"].ne("")
            & evidence["source_valueid"].eq("")
            & _no_other_keys(evidence, set()),
            ["source_table", "source_itemid"],
            "list_item",
            70,
            "typed_item",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("drugitems"),
            ev_table.eq("drugitems")
            & evidence["source_itemid"].ne("")
            & evidence["source_ordercategoryid"].ne(""),
            ["source_table", "source_itemid", "source_ordercategoryid"],
            "drug_item_ordercategory",
            100,
            "typed_key",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("drugitems"),
            ev_table.eq("drugitems")
            & evidence["source_itemid"].ne("")
            & evidence["source_ordercategoryid"].eq("")
            & _no_other_keys(evidence, set()),
            ["source_table", "source_itemid"],
            "drug_item",
            70,
            "typed_item",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("drugitems"),
            ev_table.eq("drugitems")
            & evidence["source_itemid"].eq("")
            & evidence["source_ordercategoryid"].ne("")
            & evidence["source_valueid"].eq("")
            & evidence["source_unitid"].eq(""),
            ["source_table", "source_ordercategoryid"],
            "drug_ordercategory",
            50,
            "category_context",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("freetextitems"),
            ev_table.eq("freetextitems") & evidence["source_itemid"].ne("") & _no_other_keys(evidence, set()),
            ["source_table", "source_itemid"],
            "freetext_item",
            70,
            "typed_item",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("processitems"),
            ev_table.eq("processitems") & evidence["source_itemid"].ne("") & _no_other_keys(evidence, set()),
            ["source_table", "source_itemid"],
            "process_item",
            70,
            "typed_item",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("procedureorderitems"),
            ev_table.eq("procedureorderitems")
            & evidence["source_itemid"].ne("")
            & evidence["source_ordercategoryid"].ne(""),
            ["source_table", "source_itemid", "source_ordercategoryid"],
            "procedure_item_ordercategory",
            100,
            "typed_key",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("procedureorderitems"),
            ev_table.eq("procedureorderitems")
            & evidence["source_itemid"].ne("")
            & evidence["source_ordercategoryid"].eq("")
            & _no_other_keys(evidence, set()),
            ["source_table", "source_itemid"],
            "procedure_item",
            70,
            "typed_item",
        )
    )
    frames.append(
        _join_candidates(
            source,
            evidence,
            table.eq("procedureorderitems"),
            ev_table.eq("procedureorderitems")
            & evidence["source_itemid"].eq("")
            & evidence["source_ordercategoryid"].ne("")
            & evidence["source_valueid"].eq("")
            & evidence["source_unitid"].eq(""),
            ["source_table", "source_ordercategoryid"],
            "procedure_ordercategory",
            50,
            "category_context",
        )
    )
    return frames


def _label_candidate_frame(source: pd.DataFrame, evidence: pd.DataFrame) -> pd.DataFrame:
    context_roles = {"clinical_context", "medication_context", "unit_context"}
    evidence_mask = (
        evidence["source_itemid"].eq("")
        & evidence["source_valueid"].eq("")
        & evidence["source_unitid"].eq("")
        & evidence["source_ordercategoryid"].eq("")
        & evidence["source_label"].ne("")
        & evidence["evidence_role"].isin(context_roles)
        & ~evidence["evidence_family"].eq("OMOP Athena")
    )
    left = source.loc[source["_label_key"].ne(""), SOURCE_VOCAB_COLUMNS + ["_label_key"]].copy()
    right = evidence.loc[evidence_mask & evidence["_label_key"].ne(""), ["_label_key"] + EVIDENCE_OUTPUT_COLUMNS].copy()
    if left.empty or right.empty:
        return _empty(CANDIDATE_COLUMNS)
    right = right.drop_duplicates(["_label_key"] + EVIDENCE_OUTPUT_COLUMNS)
    merged = left.merge(right, on="_label_key", how="inner").drop(columns=["_label_key"])
    if merged.empty:
        return _empty(CANDIDATE_COLUMNS)
    merged["candidate_match_method"] = "label_exact_context"
    merged["candidate_match_specificity"] = 20
    merged["candidate_match_scope"] = "label_context"
    merged["candidate_id"] = ""
    return merged[CANDIDATE_COLUMNS]


def _deduplicate_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    sorted_candidates = candidates.sort_values(
        [
            "source_table",
            "row_count",
            "source_token",
            "evidence_id",
            "candidate_match_specificity",
            "candidate_match_method",
        ],
        ascending=[True, False, True, True, False, True],
    )
    deduped = sorted_candidates.drop_duplicates(["source_token", "evidence_id"], keep="first").copy()
    deduped = deduped.sort_values(
        [
            "source_table",
            "row_count",
            "source_token",
            "candidate_match_specificity",
            "evidence_family",
            "evidence_id",
        ],
        ascending=[True, False, True, False, True, True],
    ).reset_index(drop=True)
    deduped["candidate_id"] = [f"CANDIDATE:{i:09d}" for i in range(1, len(deduped) + 1)]
    deduped["candidate_match_specificity"] = deduped["candidate_match_specificity"].astype("int64")
    return deduped[CANDIDATE_COLUMNS]


def construct_candidate_map(source_vocab: pd.DataFrame, mapping_evidence: pd.DataFrame) -> pd.DataFrame:
    """Join source tokens to all exact typed/label evidence candidates."""

    source = source_vocab.copy()
    evidence = mapping_evidence.copy()
    for col in SOURCE_VOCAB_COLUMNS:
        if col != "row_count":
            source[col] = source[col].map(_norm)
    for col in EVIDENCE_COLUMNS:
        evidence[col] = evidence[col].map(_norm)
    source["row_count"] = pd.to_numeric(source["row_count"], errors="raise").astype("int64")
    source["_label_key"] = source["source_label"].map(_label_norm)
    evidence["_label_key"] = evidence["source_label"].map(_label_norm)

    frames = _typed_candidate_frames(source, evidence)
    frames.append(_label_candidate_frame(source, evidence))
    nonempty = [frame for frame in frames if not frame.empty]
    if not nonempty:
        return _empty(CANDIDATE_COLUMNS)
    candidates = pd.concat(nonempty, ignore_index=True)
    return _deduplicate_candidates(candidates)


def _nonzero_target_mask(candidates: pd.DataFrame) -> pd.Series:
    target = candidates["target_concept_id"].fillna("").astype(str).str.strip()
    return target.ne("") & target.ne("0")


def unmatched_source_tokens(source_vocab: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    """Return canonical source rows that did not receive any candidate evidence."""

    matched = set(candidates["source_token"]) if not candidates.empty else set()
    unmatched = source_vocab[~source_vocab["source_token"].isin(matched)].copy()
    return unmatched[SOURCE_VOCAB_COLUMNS].reset_index(drop=True)


def summarize_candidates(source_vocab: pd.DataFrame, candidates: pd.DataFrame) -> dict[str, Any]:
    """Build a JSON-serializable summary for Step 4 outputs."""

    source_tokens = int(source_vocab["source_token"].nunique())
    matched_tokens = int(candidates["source_token"].nunique()) if not candidates.empty else 0
    nonzero_mask = _nonzero_target_mask(candidates) if not candidates.empty else pd.Series([], dtype=bool)
    target = candidates["target_concept_id"].fillna("").astype(str).str.strip() if not candidates.empty else pd.Series([], dtype=str)
    return {
        "source_tokens": source_tokens,
        "source_rows": int(pd.to_numeric(source_vocab["row_count"], errors="coerce").fillna(0).sum()),
        "candidate_rows": int(len(candidates)),
        "source_tokens_with_candidates": matched_tokens,
        "source_tokens_without_candidates": int(source_tokens - matched_tokens),
        "source_tokens_with_nonzero_target_concepts": int(candidates.loc[nonzero_mask, "source_token"].nunique()) if not candidates.empty else 0,
        "candidate_rows_with_nonzero_target_concepts": int(nonzero_mask.sum()) if not candidates.empty else 0,
        "candidate_rows_with_target_concept_zero": int(target.eq("0").sum()) if not candidates.empty else 0,
        "candidate_rows_without_target_concept_id": int(target.eq("").sum()) if not candidates.empty else 0,
        "candidate_rows_by_match_method": candidates["candidate_match_method"].value_counts().sort_index().to_dict() if not candidates.empty else {},
        "candidate_rows_by_evidence_family": candidates["evidence_family"].value_counts().sort_index().to_dict() if not candidates.empty else {},
        "candidate_rows_by_source_table": candidates["source_table"].value_counts().sort_index().to_dict() if not candidates.empty else {},
    }


def summarize_candidates_by_table(source_vocab: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    """Return table-level source/candidate coverage counts."""

    source_summary = (
        source_vocab.groupby("source_table", dropna=False)
        .agg(source_tokens=("source_token", "nunique"), source_rows=("row_count", "sum"))
        .reset_index()
    )
    if candidates.empty:
        source_summary["candidate_rows"] = 0
        source_summary["source_tokens_with_candidates"] = 0
        source_summary["source_tokens_without_candidates"] = source_summary["source_tokens"]
        source_summary["source_tokens_with_nonzero_target_concepts"] = 0
        return source_summary
    nonzero = candidates[_nonzero_target_mask(candidates)]
    candidate_summary = (
        candidates.groupby("source_table", dropna=False)
        .agg(candidate_rows=("candidate_id", "count"), source_tokens_with_candidates=("source_token", "nunique"))
        .reset_index()
    )
    target_summary = (
        nonzero.groupby("source_table", dropna=False)
        .agg(source_tokens_with_nonzero_target_concepts=("source_token", "nunique"))
        .reset_index()
    )
    out = source_summary.merge(candidate_summary, on="source_table", how="left").merge(
        target_summary, on="source_table", how="left"
    )
    for col in ["candidate_rows", "source_tokens_with_candidates", "source_tokens_with_nonzero_target_concepts"]:
        out[col] = out[col].fillna(0).astype("int64")
    out["source_tokens_without_candidates"] = out["source_tokens"] - out["source_tokens_with_candidates"]
    return out.sort_values("source_table").reset_index(drop=True)


def write_candidate_map_outputs(config: CandidateMapConfig) -> dict[str, Path]:
    """Construct candidate-map outputs and write CSV/JSON audits."""

    config.audit_dir.mkdir(parents=True, exist_ok=True)
    source = load_source_vocab(config.source_vocab)
    evidence = load_mapping_evidence(config.mapping_evidence)
    candidates = construct_candidate_map(source, evidence)
    unmatched = unmatched_source_tokens(source, candidates)
    summary = summarize_candidates(source, candidates)
    by_table = summarize_candidates_by_table(source, candidates)

    candidates_path = config.audit_dir / "vocab_pipeline_candidates.csv"
    summary_path = config.audit_dir / "vocab_pipeline_candidates_summary.json"
    by_table_path = config.audit_dir / "vocab_pipeline_candidates_by_table.csv"
    unmatched_path = config.audit_dir / "vocab_pipeline_candidate_unmatched_source_tokens.csv"

    candidates.to_csv(candidates_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    by_table.to_csv(by_table_path, index=False)
    unmatched.to_csv(unmatched_path, index=False)
    return {
        "candidates": candidates_path,
        "candidate_summary": summary_path,
        "candidates_by_table": by_table_path,
        "unmatched_source_tokens": unmatched_path,
    }
