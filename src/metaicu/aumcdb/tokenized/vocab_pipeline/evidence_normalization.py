"""Normalize external mapping/context evidence for Amsterdam vocabulary construction."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from metaicu.aumcdb.tokenized.vocab_pipeline.policy_common import norm_key
from metaicu.aumcdb.tokenized.vocab_pipeline.resources import sniff_delimiter


EVIDENCE_COLUMNS = [
    "evidence_id",
    "evidence_family",
    "evidence_source",
    "evidence_file",
    "evidence_role",
    "source_table",
    "source_itemid",
    "source_valueid",
    "source_unitid",
    "source_ordercategoryid",
    "source_code",
    "source_vocabulary",
    "source_label",
    "source_value",
    "source_unit",
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


@dataclass(frozen=True)
class EvidenceConfig:
    """Inputs and output locations for evidence normalization."""

    external_root: Path
    omop_vocab_dir: Path
    audit_dir: Path


def _read_table(path: Path, nrows: int | None = None) -> pd.DataFrame:
    delimiter = "\t" if path.parent.name == "omop_vocab" else sniff_delimiter(path)
    return pd.read_csv(path, sep=delimiter or ",", dtype=str, keep_default_na=False, nrows=nrows, engine="python")


def _source_table_from_name(name: str) -> str:
    for table in ["numericitems", "listitems", "drugitems", "freetextitems", "processitems", "procedureorderitems"]:
        if name.startswith(table):
            return table
    return ""


def _parse_source_code(source_code: object, source_table: str, evidence_source: str) -> dict[str, str]:
    text = norm_key(source_code)
    parts = text.split("-") if text else []
    out = {
        "source_itemid": "",
        "source_valueid": "",
        "source_unitid": "",
        "source_ordercategoryid": "",
        "join_key_status": "unparsed",
    }
    if not parts:
        return out
    if parts[0].isdigit():
        out["source_itemid"] = parts[0]
        out["join_key_status"] = "itemid"
    if len(parts) >= 2 and parts[1].isdigit():
        suffix = parts[1]
        stem = evidence_source.lower()
        if source_table == "drugitems":
            out["source_ordercategoryid"] = suffix
            out["join_key_status"] = "itemid_ordercategoryid"
        elif "value" in stem or source_table in {"listitems", "freetextitems"}:
            out["source_valueid"] = suffix
            out["join_key_status"] = "itemid_valueid"
        elif "unit" in stem or source_table == "numericitems":
            out["source_unitid"] = suffix
            out["join_key_status"] = "itemid_unitid"
        else:
            out["join_key_status"] = "itemid_suffix_untyped"
    return out


def _blank_row(**kwargs: Any) -> dict[str, str]:
    row = {col: "" for col in EVIDENCE_COLUMNS}
    row.update({k: norm_key(v) for k, v in kwargs.items() if k in row})
    return row


def _with_ids(rows: list[dict[str, str]]) -> pd.DataFrame:
    for idx, row in enumerate(rows, start=1):
        row["evidence_id"] = f"EVIDENCE:{idx:09d}"
    return pd.DataFrame(rows, columns=EVIDENCE_COLUMNS)


def _normalize_usagi_files(external_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((external_root / "AMSTEL/data/mappings").glob("*.usagi.csv")):
        df = _read_table(path)
        source_table = _source_table_from_name(path.stem)
        for rec in df.to_dict("records"):
            parsed = _parse_source_code(rec.get("sourceCode", ""), source_table, path.stem)
            rows.append(
                _blank_row(
                    evidence_family="AMSTEL mappings",
                    evidence_source=path.stem,
                    evidence_file=str(path),
                    evidence_role="standard_mapping",
                    source_table=source_table,
                    source_code=rec.get("sourceCode", ""),
                    source_label=rec.get("sourceName", ""),
                    target_concept_id=rec.get("conceptId", ""),
                    target_label=rec.get("conceptName", ""),
                    mapping_status=rec.get("mappingStatus", ""),
                    equivalence=rec.get("equivalence", ""),
                    match_type="usagi",
                    evidence_text="; ".join(filter(None, [rec.get("comment", ""), rec.get("matchScore", "")])),
                    **parsed,
                )
            )
    return rows


def _normalize_source_to_concept(external_root: Path) -> list[dict[str, str]]:
    path = external_root / "AMSTEL/data/mappings/source_to_concept_map.csv"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    df = _read_table(path)
    for rec in df.to_dict("records"):
        vocab = rec.get("source_vocabulary_id", "")
        source_table = _source_table_from_name(vocab.lower().replace("aumc ", ""))
        parsed = _parse_source_code(rec.get("source_code", ""), source_table, vocab)
        rows.append(
            _blank_row(
                evidence_family="AMSTEL mappings",
                evidence_source="source_to_concept_map",
                evidence_file=str(path),
                evidence_role="standard_mapping",
                source_table=source_table,
                source_code=rec.get("source_code", ""),
                source_vocabulary=vocab,
                source_label=rec.get("source_code_description", ""),
                target_vocabulary=rec.get("target_vocabulary_id", ""),
                target_concept_id=rec.get("target_concept_id", ""),
                mapping_status="invalid_reason=" + rec.get("invalid_reason", ""),
                match_type="source_to_concept_map",
                **parsed,
            )
        )
    return rows


def _normalize_source_to_value(external_root: Path) -> list[dict[str, str]]:
    path = external_root / "AMSTEL/data/mappings/source_to_value_map.csv"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    df = _read_table(path)
    for rec in df.to_dict("records"):
        vocab = rec.get("SOURCE_VOCABULARY_ID", "")
        source_table = _source_table_from_name(vocab.lower().replace("aumc ", ""))
        parsed = _parse_source_code(rec.get("SOURCE_CODE", ""), source_table, vocab)
        rows.append(
            _blank_row(
                evidence_family="AMSTEL mappings",
                evidence_source="source_to_value_map",
                evidence_file=str(path),
                evidence_role="value_mapping",
                source_table=source_table,
                source_code=rec.get("SOURCE_CODE", ""),
                source_vocabulary=vocab,
                source_label=rec.get("SOURCE_CODE_DESCRIPTION", ""),
                source_value=rec.get("VALUE", ""),
                match_type="source_to_value_map",
                evidence_text="row=" + rec.get("ROW", ""),
                **parsed,
            )
        )
    return rows


def _normalize_amstel_source_concepts(external_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((external_root / "AMSTEL/data/source_concepts").glob("*.csv")):
        df = _read_table(path)
        for rec in df.to_dict("records"):
            table = rec.get("table", "") or _source_table_from_name(path.stem)
            rows.append(
                _blank_row(
                    evidence_family="AMSTEL source concepts",
                    evidence_source=path.stem,
                    evidence_file=str(path),
                    evidence_role="source_metadata",
                    source_table=table,
                    source_itemid=rec.get("itemid", "") or _parse_source_code(rec.get("source_concept_id", ""), table, path.stem)["source_itemid"],
                    source_valueid=rec.get("valueid", ""),
                    source_unitid=rec.get("unitid", ""),
                    source_ordercategoryid=rec.get("ordercategoryid", ""),
                    source_code=rec.get("source_concept_id", ""),
                    source_vocabulary=rec.get("vocabulary_id", ""),
                    source_label=rec.get("source_concept", "") or rec.get("item", ""),
                    source_value=rec.get("value", ""),
                    source_unit=rec.get("unit", ""),
                    target_vocabulary=rec.get("vocabulary_id", ""),
                    target_concept_id=rec.get("concept_id", ""),
                    target_code=rec.get("vocabulary_concept_code", ""),
                    target_label=rec.get("concept_name", "") or rec.get("vocabulary_concept_name", ""),
                    mapping_status="source_concept_metadata",
                    match_type="amstel_source_concept",
                    evidence_text="|".join(filter(None, [rec.get("category", ""), rec.get("ordercategory", ""), rec.get("ucum_code", "")])),
                    join_key_status="explicit_columns",
                )
            )
    return rows


def _normalize_amsterdam_dictionary(external_root: Path) -> list[dict[str, str]]:
    path = external_root / "AmsterdamUMCdb/amsterdamumcdb/dictionary/dictionary.csv"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    df = _read_table(path)
    for rec in df.to_dict("records"):
        source_vocab = rec.get("source_vocabulary_id", "")
        source_table = _source_table_from_name(source_vocab.lower().replace("aumc ", ""))
        parsed = _parse_source_code(rec.get("source_code", ""), source_table, source_vocab)
        rows.append(
            _blank_row(
                evidence_family="AmsterdamUMCdb dictionary",
                evidence_source="current_dictionary",
                evidence_file=str(path),
                evidence_role="standard_mapping",
                source_table=source_table,
                source_code=rec.get("source_code", ""),
                source_vocabulary=source_vocab,
                source_label=rec.get("source_code_description", ""),
                source_value=rec.get("value_of_source_code", ""),
                target_vocabulary=rec.get("vocabulary_id", ""),
                target_concept_id=rec.get("concept_id", ""),
                target_code=rec.get("concept_code", ""),
                target_label=rec.get("concept_name", ""),
                mapping_status=rec.get("mapping_status", ""),
                equivalence=rec.get("equivalence", ""),
                match_type="amsterdamumcdb_dictionary",
                evidence_text="value_of_concept_id=" + rec.get("value_of_concept_id", ""),
                **parsed,
            )
        )
    return rows


def _normalize_legacy_dictionary(external_root: Path) -> list[dict[str, str]]:
    path = external_root / "AmsterdamUMCdb/amsterdamumcdb/dictionary/legacy/dictionary.csv"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    df = _read_table(path)
    for rec in df.to_dict("records"):
        rows.append(
            _blank_row(
                evidence_family="AmsterdamUMCdb legacy dictionary",
                evidence_source="legacy_dictionary",
                evidence_file=str(path),
                evidence_role="source_metadata",
                source_table=rec.get("table", ""),
                source_itemid=rec.get("itemid", ""),
                source_valueid=rec.get("valueid", ""),
                source_unitid=rec.get("unitid", ""),
                source_ordercategoryid=rec.get("ordercategoryid", ""),
                source_code=rec.get("itemid", ""),
                source_vocabulary=rec.get("vocabulary_id", ""),
                source_label=rec.get("item", ""),
                source_value=rec.get("value", ""),
                source_unit=rec.get("unit", ""),
                target_vocabulary=rec.get("vocabulary_id", ""),
                target_code=rec.get("vocabulary_concept_code", ""),
                target_label=rec.get("vocabulary_concept_name", ""),
                mapping_status="legacy_source_metadata",
                match_type="legacy_dictionary",
                evidence_text="|".join(filter(None, [rec.get("item_en", ""), rec.get("category", ""), rec.get("category_en", ""), rec.get("ucum_code", "")])),
                join_key_status="explicit_columns",
            )
        )
    return rows


def _split_sql_values(text: str) -> list[str]:
    reader = csv.reader([text], quotechar="'", skipinitialspace=True)
    return [part.strip() for part in next(reader)]


def _normalize_flowsheets(external_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sql_dir = external_root / "AmsterdamUMCdb/amsterdamumcdb/sql/flowsheets/legacy"
    pattern = re.compile(r"INSERT\s+INTO\s+fs\s+VALUES\s*\((.*?)\)\s*;", re.IGNORECASE | re.DOTALL)
    for path in sorted(sql_dir.glob("get_*_flowsheet_itemids.sql")):
        domain = path.name.replace("get_", "").replace("_flowsheet_itemids.sql", "")
        text = path.read_text(errors="replace")
        for match in pattern.finditer(text):
            values = _split_sql_values(match.group(1).replace("\n", " "))
            if len(values) < 7:
                continue
            itemid, item, item_en, category, categoryid, label, item_type = values[:7]
            table = {"numeric": "numericitems", "list": "listitems", "freetext": "freetextitems"}.get(item_type, "")
            rows.append(
                _blank_row(
                    evidence_family="AmsterdamUMCdb flowsheets",
                    evidence_source=f"{domain}_flowsheet",
                    evidence_file=str(path),
                    evidence_role="clinical_grouping",
                    source_table=table,
                    source_itemid=itemid,
                    source_code=itemid,
                    source_label=item,
                    mapping_status="flowsheet_grouping",
                    match_type="flowsheet_sql",
                    evidence_text="|".join([domain, item_en, category, categoryid, label, item_type]),
                    join_key_status="itemid",
                )
            )
    return rows


def _normalize_blendedicu(external_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    user_dir = external_root / "BlendedICU/auxillary_files/user_input"
    ts_path = user_dir / "timeseries_variables.csv"
    if ts_path.exists():
        df = _read_table(ts_path)
        for rec in df.to_dict("records"):
            rows.append(
                _blank_row(
                    evidence_family="BlendedICU user input",
                    evidence_source="timeseries_variables",
                    evidence_file=str(ts_path),
                    evidence_role="clinical_context",
                    source_label=rec.get("amsterdam", ""),
                    source_value=rec.get("blended", ""),
                    target_concept_id=rec.get("concept_id", ""),
                    target_label=rec.get("blended", ""),
                    mapping_status="curated_context",
                    match_type="label_context",
                    evidence_text="|".join(filter(None, [rec.get("categories", ""), rec.get("unit_concept_id", ""), rec.get("agg_method", "")])),
                    join_key_status="label_only",
                )
            )
    ing_path = user_dir / "medication_ingredients.csv"
    if ing_path.exists():
        df = _read_table(ing_path)
        for rec in df.to_dict("records"):
            rows.append(
                _blank_row(
                    evidence_family="BlendedICU user input",
                    evidence_source="medication_ingredients",
                    evidence_file=str(ing_path),
                    evidence_role="medication_context",
                    source_label=rec.get("ingredient", ""),
                    mapping_status="ingredient_context",
                    match_type="ingredient_list",
                    join_key_status="label_only",
                )
            )
    manual_path = user_dir / "manual_icu_meds.csv"
    if manual_path.exists():
        df = _read_table(manual_path)
        for col in df.columns:
            for value in df[col].dropna().astype(str):
                value = value.strip()
                if value:
                    rows.append(
                        _blank_row(
                            evidence_family="BlendedICU user input",
                            evidence_source="manual_icu_meds",
                            evidence_file=str(manual_path),
                            evidence_role="medication_context",
                            source_label=value,
                            source_value=col,
                            mapping_status="manual_medication_alias",
                            match_type="label_context",
                            join_key_status="label_only",
                        )
                    )
    med_dir = external_root / "BlendedICU/auxillary_files/medication_mapping_files"
    drugnames = med_dir / "drugnames.parquet"
    if drugnames.exists():
        df = pd.read_parquet(drugnames)
        for rec in df.to_dict("records"):
            rows.append(
                _blank_row(
                    evidence_family="BlendedICU medication assets",
                    evidence_source="drugnames",
                    evidence_file=str(drugnames),
                    evidence_role="medication_context",
                    source_label=rec.get("drugname", ""),
                    source_value=rec.get("dataset", ""),
                    mapping_status="drugname_context",
                    match_type="label_context",
                    evidence_text="count=" + norm_key(rec.get("count", "")),
                    join_key_status="label_only",
                )
            )
    ams_meds = med_dir / "amsterdam_medications.csv"
    if ams_meds.exists():
        df = _read_table(ams_meds)
        for rec in df.to_dict("records"):
            label = rec.get("drugname", "") or next(iter(rec.values()), "")
            rows.append(
                _blank_row(
                    evidence_family="BlendedICU medication assets",
                    evidence_source="amsterdam_medications",
                    evidence_file=str(ams_meds),
                    evidence_role="medication_context",
                    source_label=label,
                    source_value=rec.get("count", ""),
                    mapping_status="amsterdam_medication_context",
                    match_type="label_context",
                    join_key_status="label_only",
                )
            )
    med_concepts = med_dir / "med_concept_ids.parquet"
    if med_concepts.exists():
        df = pd.read_parquet(med_concepts)
        for rec in df.to_dict("records"):
            rows.append(
                _blank_row(
                    evidence_family="BlendedICU medication assets",
                    evidence_source="med_concept_ids",
                    evidence_file=str(med_concepts),
                    evidence_role="medication_context",
                    target_concept_id=rec.get("concept_id", ""),
                    mapping_status="icu_medication_concept_context",
                    match_type="concept_id_list",
                    join_key_status="target_concept_id_only",
                )
            )
    return rows


def _normalize_omop_vocab_versions(omop_vocab_dir: Path) -> list[dict[str, str]]:
    path = omop_vocab_dir / "VOCABULARY.csv"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    for rec in df.to_dict("records"):
        rows.append(
            _blank_row(
                evidence_family="OMOP Athena",
                evidence_source="VOCABULARY",
                evidence_file=str(path),
                evidence_role="omop_vocab_metadata",
                target_vocabulary=rec.get("vocabulary_id", ""),
                target_concept_id=rec.get("vocabulary_concept_id", ""),
                target_label=rec.get("vocabulary_name", ""),
                mapping_status="vocabulary_version",
                match_type="omop_vocabulary_metadata",
                evidence_text="|".join(filter(None, [rec.get("vocabulary_reference", ""), rec.get("vocabulary_version", "")])),
                join_key_status="target_vocabulary_only",
            )
        )
    return rows


def normalize_mapping_evidence(config: EvidenceConfig) -> pd.DataFrame:
    """Normalize external evidence into one long auditable table."""

    rows: list[dict[str, str]] = []
    for adapter in [
        _normalize_usagi_files,
        _normalize_source_to_concept,
        _normalize_source_to_value,
        _normalize_amstel_source_concepts,
        _normalize_amsterdam_dictionary,
        _normalize_legacy_dictionary,
        _normalize_flowsheets,
        _normalize_blendedicu,
    ]:
        rows.extend(adapter(config.external_root))
    rows.extend(_normalize_omop_vocab_versions(config.omop_vocab_dir))
    evidence = _with_ids(rows)
    for col in EVIDENCE_COLUMNS:
        evidence[col] = evidence[col].fillna("").astype(str)
    return evidence


def summarize_evidence(evidence: pd.DataFrame) -> dict[str, Any]:
    """Return row counts by evidence family and role."""

    by_family = evidence.groupby("evidence_family", dropna=False).size().to_dict()
    by_role = evidence.groupby("evidence_role", dropna=False).size().to_dict()
    missing_provenance = evidence[
        evidence["evidence_family"].eq("") | evidence["evidence_file"].eq("") | evidence["evidence_role"].eq("")
    ]
    target_ids = evidence["target_concept_id"].replace("", pd.NA).dropna()
    bad_target_ids = [value for value in target_ids.astype(str) if not value.isdigit()]
    return {
        "evidence_rows": int(len(evidence)),
        "families": {str(k): int(v) for k, v in by_family.items()},
        "roles": {str(k): int(v) for k, v in by_role.items()},
        "rows_missing_provenance": int(len(missing_provenance)),
        "non_integer_target_concept_ids": int(len(bad_target_ids)),
        "sample_bad_target_concept_ids": bad_target_ids[:20],
    }


def write_mapping_evidence(config: EvidenceConfig) -> dict[str, Path]:
    """Write normalized evidence CSV and summary JSON."""

    config.audit_dir.mkdir(parents=True, exist_ok=True)
    evidence = normalize_mapping_evidence(config)
    summary = summarize_evidence(evidence)
    evidence_path = config.audit_dir / "vocab_pipeline_mapping_evidence.csv"
    summary_path = config.audit_dir / "vocab_pipeline_mapping_evidence_summary.json"
    by_family_path = config.audit_dir / "vocab_pipeline_mapping_evidence_by_family.csv"
    evidence.to_csv(evidence_path, index=False)
    pd.DataFrame(
        [
            {"group_type": "family", "group": k, "rows": v}
            for k, v in summary["families"].items()
        ]
        + [
            {"group_type": "role", "group": k, "rows": v}
            for k, v in summary["roles"].items()
        ]
    ).to_csv(by_family_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return {
        "mapping_evidence": evidence_path,
        "mapping_evidence_summary": summary_path,
        "mapping_evidence_by_family": by_family_path,
    }
