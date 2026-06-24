"""External-resource inventory for the cleaned Amsterdam vocabulary pipeline."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl


@dataclass(frozen=True)
class ResourceSpec:
    """Expected external resource file or glob pattern."""

    family: str
    role: str
    root_name: str
    relative_pattern: str
    required: bool
    expected_join_keys: str


RESOURCE_SPECS: list[ResourceSpec] = [
    ResourceSpec("AMSTEL mappings", "standard_mapping", "external_root", "AMSTEL/data/mappings/*.usagi.csv", True, "sourceCode or source_code"),
    ResourceSpec("AMSTEL mappings", "standard_mapping", "external_root", "AMSTEL/data/mappings/source_to_concept_map.csv", True, "source_code + source_vocabulary_id"),
    ResourceSpec("AMSTEL mappings", "value_mapping", "external_root", "AMSTEL/data/mappings/source_to_value_map.csv", True, "source_code + source_vocabulary_id"),
    ResourceSpec("AMSTEL mappings", "source_metadata", "external_root", "AMSTEL/data/mappings/local_vocabularies.yaml", True, "vocabulary metadata"),
    ResourceSpec("AMSTEL source concepts", "source_metadata", "external_root", "AMSTEL/data/source_concepts/*.csv", True, "table-specific source_concept/itemid/valueid/unitid/ordercategoryid"),
    ResourceSpec("AmsterdamUMCdb dictionary", "standard_mapping", "external_root", "AmsterdamUMCdb/amsterdamumcdb/dictionary/dictionary.csv", True, "source_vocabulary_id + source_code"),
    ResourceSpec("AmsterdamUMCdb legacy dictionary", "source_metadata", "external_root", "AmsterdamUMCdb/amsterdamumcdb/dictionary/legacy/dictionary.csv", True, "table + itemid/valueid/unitid/ordercategoryid"),
    ResourceSpec("AmsterdamUMCdb flowsheets", "clinical_grouping", "external_root", "AmsterdamUMCdb/amsterdamumcdb/sql/flowsheets/legacy/get_respiration_flowsheet_itemids.sql", True, "itemid"),
    ResourceSpec("AmsterdamUMCdb flowsheets", "clinical_grouping", "external_root", "AmsterdamUMCdb/amsterdamumcdb/sql/flowsheets/legacy/get_circulation_flowsheet_itemids.sql", True, "itemid"),
    ResourceSpec("AmsterdamUMCdb flowsheets", "clinical_grouping", "external_root", "AmsterdamUMCdb/amsterdamumcdb/sql/flowsheets/legacy/get_nephrology_flowsheet_itemids.sql", True, "itemid"),
    ResourceSpec("AmsterdamUMCdb flowsheets", "clinical_grouping", "external_root", "AmsterdamUMCdb/amsterdamumcdb/sql/flowsheets/legacy/get_neurology_flowsheet_itemids.sql", True, "itemid"),
    ResourceSpec("BlendedICU user input", "clinical_context", "external_root", "BlendedICU/auxillary_files/user_input/timeseries_variables.csv", True, "Amsterdam label"),
    ResourceSpec("BlendedICU user input", "medication_context", "external_root", "BlendedICU/auxillary_files/user_input/medication_ingredients.csv", True, "ingredient name"),
    ResourceSpec("BlendedICU user input", "medication_context", "external_root", "BlendedICU/auxillary_files/user_input/manual_icu_meds.csv", False, "ingredient aliases"),
    ResourceSpec("BlendedICU user input", "unit_context", "external_root", "BlendedICU/auxillary_files/user_input/unit_type_v2.json", False, "unit/care type labels"),
    ResourceSpec("BlendedICU medication assets", "medication_context", "external_root", "BlendedICU/auxillary_files/medication_mapping_files/drugnames.parquet", False, "drugname"),
    ResourceSpec("BlendedICU medication assets", "medication_context", "external_root", "BlendedICU/auxillary_files/medication_mapping_files/amsterdam_medications.csv", False, "drugname"),
    ResourceSpec("BlendedICU medication assets", "medication_context", "external_root", "BlendedICU/auxillary_files/medication_mapping_files/med_concept_ids.parquet", False, "concept_id"),
    ResourceSpec("BlendedICU medication assets", "medication_context", "external_root", "BlendedICU/auxillary_files/medication_mapping_files/ohdsi_icu_medications.csv", False, "ingredient names"),
    ResourceSpec("OMOP Athena", "omop_vocab_metadata", "omop_vocab_dir", "VOCABULARY.csv", True, "vocabulary_id"),
    ResourceSpec("OMOP Athena", "omop_concepts", "omop_vocab_dir", "CONCEPT.csv", True, "concept_id"),
    ResourceSpec("OMOP Athena", "omop_relationships", "omop_vocab_dir", "CONCEPT_RELATIONSHIP.csv", True, "concept_id_1/concept_id_2"),
    ResourceSpec("OMOP Athena", "omop_ancestors", "omop_vocab_dir", "CONCEPT_ANCESTOR.csv", True, "descendant_concept_id/ancestor_concept_id"),
    ResourceSpec("OMOP Athena", "omop_metadata", "omop_vocab_dir", "DOMAIN.csv", True, "domain_id"),
    ResourceSpec("OMOP Athena", "omop_metadata", "omop_vocab_dir", "RELATIONSHIP.csv", True, "relationship_id"),
    ResourceSpec("OMOP Athena", "omop_metadata", "omop_vocab_dir", "CONCEPT_CLASS.csv", True, "concept_class_id"),
    ResourceSpec("OMOP Athena", "omop_synonyms", "omop_vocab_dir", "CONCEPT_SYNONYM.csv", True, "concept_id"),
    ResourceSpec("OMOP Athena", "drug_strength", "omop_vocab_dir", "DRUG_STRENGTH.csv", True, "drug_concept_id"),
    ResourceSpec("YAIB/ricu", "auxiliary_config", "external_root", "YAIB-cohorts/ricu-extensions/configs/*", False, "config concept names"),
    ResourceSpec("YAIB/ricu", "auxiliary_config", "external_root", "ricu/*", False, "ricu files"),
]


RESOURCE_COLUMNS = [
    "resource_family",
    "resource_role",
    "root_name",
    "relative_pattern",
    "path",
    "exists",
    "required",
    "size_bytes",
    "modified_time",
    "file_type",
    "delimiter",
    "header_columns",
    "expected_join_keys",
]


def _root_path(spec: ResourceSpec, external_root: Path, omop_vocab_dir: Path) -> Path:
    return external_root if spec.root_name == "external_root" else omop_vocab_dir


def sniff_delimiter(path: Path) -> str:
    """Return a simple delimiter guess for text tables."""

    if path.suffix.lower() in {".tsv"}:
        return "\t"
    if path.suffix.lower() not in {".csv", ".txt"}:
        return ""
    sample = path.read_text(errors="replace")[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"]).delimiter
    except csv.Error:
        counts = {sep: sample.count(sep) for sep in [",", ";", "\t", "|"]}
        return max(counts, key=counts.get) if counts else ","


def read_header(path: Path, delimiter: str) -> list[str]:
    """Read lightweight schema/header information without scanning full data files."""

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        try:
            return list(pl.scan_parquet(path).collect_schema().names())
        except Exception:
            return []
    if suffix in {".csv", ".tsv", ".txt"}:
        try:
            with path.open(newline="", errors="replace") as handle:
                return next(csv.reader(handle, delimiter=delimiter or ","), [])
        except Exception:
            return []
    if suffix == ".json":
        return ["json"]
    if suffix == ".sql":
        return ["sql_text"]
    return []


def inventory_resources(external_root: Path, omop_vocab_dir: Path) -> pd.DataFrame:
    """Inventory all expected external resources and lightweight schemas."""

    rows: list[dict[str, Any]] = []
    for spec in RESOURCE_SPECS:
        root = _root_path(spec, external_root, omop_vocab_dir)
        matches = sorted(root.glob(spec.relative_pattern))
        if not matches:
            rows.append(
                {
                    "resource_family": spec.family,
                    "resource_role": spec.role,
                    "root_name": spec.root_name,
                    "relative_pattern": spec.relative_pattern,
                    "path": str(root / spec.relative_pattern),
                    "exists": False,
                    "required": spec.required,
                    "size_bytes": 0,
                    "modified_time": "",
                    "file_type": Path(spec.relative_pattern).suffix.lower(),
                    "delimiter": "",
                    "header_columns": "",
                    "expected_join_keys": spec.expected_join_keys,
                }
            )
            continue
        for path in matches:
            delimiter = sniff_delimiter(path) if path.is_file() else ""
            rows.append(
                {
                    "resource_family": spec.family,
                    "resource_role": spec.role,
                    "root_name": spec.root_name,
                    "relative_pattern": spec.relative_pattern,
                    "path": str(path),
                    "exists": path.exists(),
                    "required": spec.required,
                    "size_bytes": path.stat().st_size if path.is_file() else 0,
                    "modified_time": pd.Timestamp(path.stat().st_mtime, unit="s").isoformat() if path.exists() else "",
                    "file_type": path.suffix.lower(),
                    "delimiter": delimiter,
                    "header_columns": "|".join(read_header(path, delimiter)) if path.is_file() else "",
                    "expected_join_keys": spec.expected_join_keys,
                }
            )
    return pd.DataFrame(rows, columns=RESOURCE_COLUMNS)


def summarize_inventory(inventory: pd.DataFrame) -> dict[str, Any]:
    """Summarize required/missing resource status."""

    missing_required = inventory[inventory["required"].astype(bool) & ~inventory["exists"].astype(bool)]
    return {
        "resources": int(len(inventory)),
        "existing_resources": int(inventory["exists"].sum()),
        "required_resources": int(inventory["required"].sum()),
        "missing_required_resources": int(len(missing_required)),
        "missing_required_paths": missing_required["path"].tolist(),
        "families": sorted(inventory["resource_family"].dropna().unique().tolist()),
    }


def write_resource_inventory(external_root: Path, omop_vocab_dir: Path, audit_dir: Path) -> dict[str, Path]:
    """Write resource inventory CSV and summary JSON."""

    audit_dir.mkdir(parents=True, exist_ok=True)
    inventory = inventory_resources(external_root, omop_vocab_dir)
    summary = summarize_inventory(inventory)
    csv_path = audit_dir / "vocab_pipeline_external_resources.csv"
    summary_path = audit_dir / "vocab_pipeline_external_resources_summary.json"
    inventory.to_csv(csv_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return {"resource_inventory": csv_path, "resource_summary": summary_path}
