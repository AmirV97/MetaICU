"""Build an iCareFM-style feature manifest for the AUMC grid fork.

This module only describes feature/source candidates. It does not scan raw
Amsterdam CSV rows and does not apply tokenization emit/drop policy.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_FEATURE_LIST = PACKAGE_ROOT / "data/icarefm_table_s3_features.csv"

MANIFEST_COLUMNS = [
    "tag",
    "name",
    "type",
    "organ_system",
    "target_unit",
    "reconstruction_type",
    "source_table_candidates",
    "source_itemid_candidates",
    "source_valueid_candidates",
    "source_ordercategoryid_candidates",
    "source_unit_candidates",
    "source_label_examples",
    "source_value_examples",
    "evidence_sources",
    "openicu_mapping_file",
    "openicu_omop_concept_ids",
    "mapping_status",
    "notes",
]

CANDIDATE_EXAMPLE_COLUMNS = [
    "tag",
    "name",
    "source_table",
    "source_itemid",
    "source_valueid",
    "source_ordercategoryid",
    "source_unit",
    "source_label",
    "source_value",
    "source_token",
    "row_count",
    "evidence_source",
    "matched_by",
]

FEATURE_DECISION_TEMPLATE = "[MTO/OTO]"
MATCH_DECISION_TEMPLATE = "[keep/reject/needs_policy]"


@dataclass(frozen=True)
class GridManifestConfig:
    """Inputs and outputs for the grid feature-manifest stage."""

    output_manifest: Path
    audit_dir: Path
    feature_list: Path | None = None
    source_vocab: Path | None = None
    supplied_vocab: Path | None = None
    openicu_root: Path | None = None


def _norm_text(value: object) -> str:
    """Normalize text for broad source-candidate search."""

    if value is None or pd.isna(value):
        return ""
    text = str(value).casefold()
    replacements = {
        "o2": " oxygen ",
        "co2": " carbon dioxide ",
        "fio2": " fraction inspired oxygen ",
        "spo2": " oxygen saturation ",
        "sao2": " arterial oxygen saturation ",
        "pulmonaal": " pulmonary ",
        "pulmonal": " pulmonary ",
        "cvp": " cvd central venous pressure ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _read_optional_csv(path: Path | None) -> pd.DataFrame:
    """Read a CSV if present; otherwise return an empty frame."""

    if path is None or not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False).fillna("")


def load_feature_seed(path: Path | None = None) -> pd.DataFrame:
    """Load iCareFM Table S3 feature seed rows."""

    feature_path = path or DEFAULT_FEATURE_LIST
    features = pd.read_csv(feature_path).fillna("")
    if "unit" in features.columns and "target_unit" not in features.columns:
        features = features.rename(columns={"unit": "target_unit"})
    required = ["tag", "name", "type", "organ_system", "target_unit"]
    missing = [col for col in required if col not in features.columns]
    if missing:
        raise ValueError(f"Feature list is missing required columns: {missing}")
    features = features[required].copy()
    features["tag"] = features["tag"].astype(str)
    if features["tag"].duplicated().any():
        dupes = sorted(features.loc[features["tag"].duplicated(), "tag"].unique())
        raise ValueError(f"Feature list has duplicate tags: {dupes}")
    return features


def _openicu_mapping_inventory(openicu_root: Path | None) -> dict[str, dict[str, str]]:
    """Parse OpenICU AUMC mapping files for concept IDs and file provenance."""

    if openicu_root is None:
        return {}
    mapping_dir = openicu_root / "config/datasets/aumc/1.5.0/mappings"
    if not mapping_dir.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    for path in sorted(mapping_dir.glob("*.yml")):
        text = path.read_text(errors="replace")
        concept_ids = sorted(set(re.findall(r"(?<!\d)(\d{6,})(?!\d)", text)))
        rows[path.stem.casefold()] = {
            "file": str(path.relative_to(openicu_root)),
            "concept_ids": "|".join(concept_ids),
        }
    return rows


OPENICU_TAG_TO_STEM = {
    "alb": "albumin",
    "alp": "alkaline_phosphatase",
    "alt": "alanine_aminotransferase",
    "ast": "aspartate_aminotransferase",
    "basos": "basophils",
    "be": "base_excess",
    "bicar": "bicarbonate",
    "bili": "total_bilirubin",
    "bili_dir": "bilirubin_direct",
    "bnd": "band_form_neutrophils",
    "bun": "blood_urea_nitrogen",
    "ca": "calcium",
    "cai": "calcium_ionized",
    "ck": "creatine_kinase",
    "ckmb": "creatine_kinase_MB",
    "cl": "chloride",
    "crea": "creatinine",
    "crp": "C_reactive_protein",
    "dbp": "diastolic_blood_pressure",
    "egcs": "GCS_eye",
    "eos": "eosinophils",
    "esr": "erythrocyte_sedimentation_rate",
    "etco2": "endtidal_CO2",
    "fgn": "fibrinogen",
    "fio2": "fraction_of_inspired_oxygen",
    "glu": "glucose",
    "hba1c": "Hemoglobin_A1C",
    "hbco": "carboxyhemoglobin",
    "hct": "hematocrit",
    "hgb": "hemoglobin",
    "hr": "heart_rate",
    "inr_pt": "prothrombin_time_international_normalized_ratio",
    "k": "potassium",
    "lact": "lactate",
    "lymph": "lymphocytes",
    "map": "mean_arterial_pressure",
    "methb": "methemoglobin",
    "mg": "magnesium",
    "mgcs": "GCS_motor",
    "na": "sodium",
    "pco2": "CO2_partial_pressure",
    "ph": "pH_of_blood",
    "phos": "phosphate",
    "plt": "platelet_count",
    "po2": "O2_partial_pressure",
    "pt": "prothrombine_time",
    "ptt": "partial_thromboplastin_time",
    "rass": "Richmond_agitation_sedation_scale",
    "rbc": "red_blood_cell_count",
    "resp": "respiratory_rate",
    "sao2": "arterial_oxygen_saturation",
    "sbp": "systolic_blood_pressure",
    "spo2": "oxygen_saturation",
    "temp": "temperature",
    "tnt": "troponin_t",
    "vgcs": "GCS_verbal",
    "wbc": "white_blood_cell_count",
}


TAG_SEARCH_TERMS = {
    "adm": ["NICE Opname type", "ADMISSION_TYPE", "urgency", "specialty"],
    "airway": ["Artificial airway", "Tracheostomy", "Tube", "Beademingstoestel"],
    "cvp": ["CVD", "CVDm-gekoppeld", "central venous"],
    "ethnic": [],
    "hbco": ["FCOHb", "Carboxyhemoglobin", "20563-3"],
    "map": ["Gemiddelde bloeddruk", "ABP gemiddeld", "mean arterial"],
    "mpap": ["AP gemiddeld", "Pulmonalis", "PAP gemiddeld"],
    "pcwp": ["PCWP", "wedge", "wiggedruk"],
    "ps": ["Pressure Support", "MCA_PS", "PS above PEEP", "drukondersteuning"],
    "samp": ["kweek", "Bloedkweek", "microbiology", "Body Fluid Sampling"],
    "sao2": ["O2-Saturatie (bloed)", "arterial saturation"],
    "spo2": ["Saturatie (Monitor)", "O2_pulseoxymetry_saturation"],
    "supp_o2_vent": ["FiO2", "A_FiO2", "MCA_FiO2"],
    "tgcs": ["Glasgow coma score total", "GCS total", "EMV totaal"],
    "urine_rate": ["UrineCAD", "UrineSupraPubis", "Diurese", "SUBJECT_FLUID_OUTPUT"],
}


TREATMENT_SEARCH_TERMS = {
    "abx": ["Antimicrobiele", "Antibiotic", "MEDICATION//J01"],
    "adh": ["Vasopressin", "Vasopressine", "Argipressin", "Argipressine", "Pitressin"],
    "anti_arrhythm": ["Amiodaron", "Sotalol", "Procainamide", "Flecainide"],
    "anti_coag": ["Nadroparine", "Dalteparine", "Enoxaparine", "Heparine"],
    "anti_delir": ["Haloperidol", "Quetiapine", "Olanzapine"],
    "benzdia": ["Midazolam", "Lorazepam", "Diazepam", "Oxazepam", "Benzodiazepine"],
    "dobu": ["Dobutamine"],
    "dopa": ["Dopamine"],
    "epi": ["Adrenaline", "Epinephrine"],
    "ffp": ["Fresh Frozen Plasma", "FFP", "BLOOD_PRODUCT"],
    "fluid": ["Infuus", "NaCl", "Glucose", "Ringer", "FLUID//"],
    "hep": ["Heparine", "Heparin"],
    "inf_alb": ["Albumine", "Albumin"],
    "inf_rbc": ["Erytrocyten", "Packed Red", "BLOOD_PRODUCT"],
    "ins_ind": ["Insuline", "Insulin"],
    "levo": ["Levosimendan", "Simdax"],
    "loop_diur": ["Furosemide", "Bumetanide", "Torasemide", "Lasix"],
    "milrin": ["Milrinone", "Milrinon", "Corotrope", "Primacor"],
    "nonop_pain": ["Paracetamol", "Diclofenac", "Metamizol", "Ibuprofen"],
    "op_pain": ["Fentanyl", "Sufentanil", "Morfine", "Morphine", "Oxycodon"],
    "oth_diur": ["Diuretic", "Spironolacton", "Hydrochloorthiazide", "Chloorthalidon"],
    "paral": ["Rocuronium", "Cisatracurium", "Atracurium", "Suxamethonium"],
    "plat": ["Trombocyten", "Platelets", "BLOOD_PRODUCT"],
    "prop": ["Propofol"],
    "sed": ["Propofol", "Midazolam", "Dexmedetomidine", "sedative"],
    "teophyllin": ["Theofylline", "Theophylline", "Aminofylline"],
    "ufilt": ["MFT_UF totaal", "Ultrafiltration", "MFT_Filtraat", "MFT_Postdilutie", "MFT_Predilutie"],
    "ufilt_ind": ["MFT_Behandeling", "CVVH", "CVVHDF", "SCUF", "DEVICE//CRRT"],
    "vasod": ["Nitroglycerine", "Nitroprusside", "Nicardipine", "Amlodipine", "vasodilator"],
}


for _tag, _terms in list(TREATMENT_SEARCH_TERMS.items()):
    if not _tag.endswith("_ind"):
        TREATMENT_SEARCH_TERMS.setdefault(f"{_tag}_ind", _terms)


def _reconstruction_type(tag: str, feature_type: str, target_unit: str) -> str:
    """Return the first-stage reconstruction class for an iCareFM tag."""

    if tag in {"age", "sex", "weight", "height", "adm"}:
        return "admission_context"
    if tag == "ethnic":
        return "unavailable"
    if tag == "samp":
        return "microbiology"
    if tag == "tgcs":
        return "derived_score"
    if tag == "urine_rate":
        return "derived_output_rate"
    if feature_type == "treatment":
        if tag == "supp_o2_vent":
            return "direct_numeric"
        return "treatment_indicator" if tag.endswith("_ind") or target_unit == "indicator" else "treatment_rate"
    if target_unit == "categorical":
        return "categorical"
    return "direct_numeric"


def _default_note(tag: str, reconstruction_type: str) -> str:
    """Human-readable notes for intentionally special features."""

    notes = {
        "ethnic": "No ethnicity column is present in raw AmsterdamUMCdb admissions.",
        "samp": "Raw culture/order material exists, but structured culture-positive feature extraction needs a microbiology policy.",
        "tgcs": "GCS total should be derived from complete component rows if no direct total is available.",
        "urine_rate": "Raw fluid-output rows exist; hourly urine-rate construction is a derived step.",
        "supp_o2_vent": "Although Table S3 marks this as treatment, source candidates are ventilator FiO2 numeric settings.",
    }
    if tag in notes:
        return notes[tag]
    if reconstruction_type in {"treatment_rate", "treatment_indicator"}:
        return "Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals."
    return ""


def _candidate_terms(tag: str, name: str, feature_type: str) -> list[str]:
    """Return broad search terms for source-candidate discovery."""

    terms: list[str] = []
    if feature_type == "treatment":
        terms.extend(TREATMENT_SEARCH_TERMS.get(tag, []))
    terms.extend(TAG_SEARCH_TERMS.get(tag, []))
    if feature_type != "treatment":
        terms.append(name)
    return [term for term in dict.fromkeys(str(term) for term in terms) if term]


def _prepare_evidence_frame(source_vocab: pd.DataFrame, supplied_vocab: pd.DataFrame) -> pd.DataFrame:
    """Build the source-token candidate universe and attach mapping evidence.

    Matches are Amsterdam source-vocab rows. Supplied-vocab rows are not separate
    matches; they only enrich the source rows with target/mapping text.
    """

    columns = [
        "source_table",
        "source_itemid",
        "source_valueid",
        "source_ordercategoryid",
        "source_unit",
        "source_label",
        "source_value",
        "source_token",
        "row_count",
        "target_concept_id",
        "evidence_source",
    ]
    if source_vocab.empty:
        return pd.DataFrame(columns=columns + ["search_text", "search_norm", "target_concept_id_key"])

    evidence = source_vocab.copy()
    for column in columns:
        if column not in evidence.columns:
            evidence[column] = ""
    evidence["evidence_source"] = "source_vocab"

    supplied_text_columns = ["source_token", "target_concept_id", "harmonized_token", "target_label", "target_code", "token_role", "non_drug_drugitem_class"]
    supplied_available = supplied_vocab.copy() if not supplied_vocab.empty else pd.DataFrame(columns=supplied_text_columns)
    for column in supplied_text_columns:
        if column not in supplied_available.columns:
            supplied_available[column] = ""
    supplied_available = supplied_available[supplied_text_columns].drop_duplicates("source_token", keep="first")
    supplied_available = supplied_available.rename(
        columns={
            "target_concept_id": "supplied_target_concept_id",
            "harmonized_token": "supplied_harmonized_token",
            "target_label": "supplied_target_label",
            "target_code": "supplied_target_code",
            "token_role": "supplied_token_role",
            "non_drug_drugitem_class": "supplied_non_drug_drugitem_class",
        }
    )
    evidence = evidence.merge(supplied_available, on="source_token", how="left").fillna("")
    has_supplied = evidence["supplied_harmonized_token"].astype(str).ne("") | evidence["supplied_target_concept_id"].astype(str).ne("")
    evidence.loc[has_supplied, "evidence_source"] = "source_vocab|supplied_vocab"
    evidence["target_concept_id"] = evidence["target_concept_id"].where(
        evidence["target_concept_id"].astype(str).ne(""),
        evidence["supplied_target_concept_id"],
    )
    text_columns = [
        "source_table",
        "source_itemid",
        "source_label",
        "source_value",
        "source_unit",
        "source_token",
        "target_concept_id",
        "supplied_harmonized_token",
        "supplied_target_label",
        "supplied_target_code",
        "supplied_token_role",
        "supplied_non_drug_drugitem_class",
    ]
    evidence["search_text"] = evidence[text_columns].astype(str).agg(" | ".join, axis=1)
    evidence["search_norm"] = evidence["search_text"].map(_norm_text)
    evidence["target_concept_id_key"] = evidence["target_concept_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    evidence["row_count"] = pd.to_numeric(evidence["row_count"], errors="coerce").fillna(0).astype(int)
    return evidence[columns + ["search_text", "search_norm", "target_concept_id_key"]]


def _search_candidates(
    evidence: pd.DataFrame,
    terms: list[str],
    openicu_concept_ids: list[str],
) -> pd.DataFrame:
    """Collect broad source candidates by OpenICU ID and text terms."""

    frames: list[pd.DataFrame] = []
    if not evidence.empty and openicu_concept_ids:
        matched = evidence[evidence["target_concept_id_key"].isin(openicu_concept_ids)].copy()
        if not matched.empty:
            matched["matched_by"] = "openicu_omop_id"
            frames.append(matched)
    for term in terms:
        if evidence.empty:
            continue
        if term.startswith(("MEDICATION//", "FLUID//", "BLOOD_PRODUCT", "DEVICE//", "SUBJECT_FLUID_OUTPUT")):
            mask = evidence["search_text"].str.contains(re.escape(term), case=False, na=False)
        else:
            normalized_term = _norm_text(term)
            if not normalized_term:
                continue
            mask = evidence["search_norm"].str.contains(re.escape(normalized_term), na=False)
        matched = evidence[mask].copy()
        if not matched.empty:
            matched["matched_by"] = f"term:{term}"
            frames.append(matched)
    if not frames:
        return pd.DataFrame(columns=list(evidence.columns) + ["matched_by"])
    candidates = pd.concat(frames, ignore_index=True).fillna("")
    candidates = candidates.sort_values(["row_count", "source_token"], ascending=[False, True])
    return candidates.drop_duplicates(["source_token", "evidence_source"]).copy()


def _allowed_source_tables(reconstruction_type: str) -> set[str]:
    """Return source tables that are plausible for a grid feature class."""

    if reconstruction_type in {"direct_numeric", "derived_output_rate"}:
        return {"numericitems"}
    if reconstruction_type in {"categorical", "derived_score"}:
        return {"listitems"}
    if reconstruction_type == "microbiology":
        return {"numericitems", "listitems", "freetextitems"}
    if reconstruction_type in {"treatment_rate", "treatment_indicator"}:
        return {"drugitems", "processitems", "numericitems", "listitems"}
    return set()


def _filter_candidates_by_feature_class(candidates: pd.DataFrame, reconstruction_type: str) -> pd.DataFrame:
    """Remove source tables that cannot represent the requested feature class."""

    allowed = _allowed_source_tables(reconstruction_type)
    if not allowed or candidates.empty:
        return candidates.iloc[0:0].copy()
    return candidates[candidates["source_table"].isin(allowed)].copy()


def _pipe_unique(values: pd.Series, limit: int | None = None) -> str:
    """Pipe-join unique non-empty values for compact manifest cells."""

    unique = [str(value) for value in values.astype(str).tolist() if str(value) not in {"", "nan", "None"}]
    unique = list(dict.fromkeys(unique))
    if limit is not None:
        unique = unique[:limit]
    return "|".join(unique)


def build_feature_manifest(config: GridManifestConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build the feature manifest, candidate examples, and summary payload."""

    features = load_feature_seed(config.feature_list)
    source_vocab = _read_optional_csv(config.source_vocab)
    supplied_vocab = _read_optional_csv(config.supplied_vocab)
    evidence = _prepare_evidence_frame(source_vocab, supplied_vocab)
    openicu = _openicu_mapping_inventory(config.openicu_root)

    manifest_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for feature in features.itertuples(index=False):
        tag = str(feature.tag)
        name = str(feature.name)
        feature_type = str(feature.type)
        target_unit = str(feature.target_unit)
        reconstruction_type = _reconstruction_type(tag, feature_type, target_unit)
        openicu_stem = OPENICU_TAG_TO_STEM.get(tag, "").casefold()
        openicu_info = openicu.get(openicu_stem, {}) if openicu_stem else {}
        openicu_ids = [value for value in str(openicu_info.get("concept_ids", "")).split("|") if value]
        candidates = _filter_candidates_by_feature_class(
            _search_candidates(evidence, _candidate_terms(tag, name, feature_type), openicu_ids),
            reconstruction_type,
        )

        if reconstruction_type == "unavailable":
            mapping_status = "unavailable"
        elif reconstruction_type == "admission_context":
            mapping_status = "admission_context"
        elif reconstruction_type in {"microbiology", "needs_policy"}:
            mapping_status = "needs_policy"
        elif candidates.empty:
            mapping_status = "no_source_candidates"
        else:
            mapping_status = "source_candidates_found"

        for candidate in candidates.head(20).itertuples(index=False):
            candidate_rows.append(
                {
                    "tag": tag,
                    "name": name,
                    "source_table": candidate.source_table,
                    "source_itemid": candidate.source_itemid,
                    "source_valueid": candidate.source_valueid,
                    "source_ordercategoryid": candidate.source_ordercategoryid,
                    "source_unit": candidate.source_unit,
                    "source_label": candidate.source_label,
                    "source_value": candidate.source_value,
                    "source_token": candidate.source_token,
                    "row_count": candidate.row_count,
                    "evidence_source": candidate.evidence_source,
                    "matched_by": candidate.matched_by,
                }
            )

        manifest_rows.append(
            {
                "tag": tag,
                "name": name,
                "type": feature_type,
                "organ_system": str(feature.organ_system),
                "target_unit": target_unit,
                "reconstruction_type": reconstruction_type,
                "source_table_candidates": _pipe_unique(candidates["source_table"]) if not candidates.empty else "",
                "source_itemid_candidates": _pipe_unique(candidates["source_itemid"]) if not candidates.empty else "",
                "source_valueid_candidates": _pipe_unique(candidates["source_valueid"]) if not candidates.empty else "",
                "source_ordercategoryid_candidates": _pipe_unique(candidates["source_ordercategoryid"]) if not candidates.empty else "",
                "source_unit_candidates": _pipe_unique(candidates["source_unit"]) if not candidates.empty else "",
                "source_label_examples": _pipe_unique(candidates["source_label"], limit=8) if not candidates.empty else "",
                "source_value_examples": _pipe_unique(candidates["source_value"], limit=8) if not candidates.empty else "",
                "evidence_sources": _pipe_unique(candidates["evidence_source"]) if not candidates.empty else "",
                "openicu_mapping_file": openicu_info.get("file", ""),
                "openicu_omop_concept_ids": openicu_info.get("concept_ids", ""),
                "mapping_status": mapping_status,
                "notes": _default_note(tag, reconstruction_type),
            }
        )

    manifest = pd.DataFrame(manifest_rows, columns=MANIFEST_COLUMNS)
    candidate_examples = pd.DataFrame(candidate_rows, columns=CANDIDATE_EXAMPLE_COLUMNS)
    summary = summarize_manifest(manifest)
    return manifest, candidate_examples, summary


def summarize_manifest(manifest: pd.DataFrame) -> dict[str, Any]:
    """Return compact manifest audit counts."""

    no_candidates = manifest["mapping_status"].isin(["no_source_candidates", "unavailable"])
    needs_policy = manifest["mapping_status"].eq("needs_policy") | manifest["reconstruction_type"].eq("needs_policy")
    return {
        "total_features": int(len(manifest)),
        "paper_claimed_total_features": 130,
        "extractable_table_s3_features": int(len(manifest)),
        "feature_count_caveat": "The extractable Table S3 rows are 129 although the supplement prose says 130.",
        "counts_by_type": manifest["type"].value_counts().to_dict(),
        "counts_by_reconstruction_type": manifest["reconstruction_type"].value_counts().to_dict(),
        "counts_by_mapping_status": manifest["mapping_status"].value_counts().to_dict(),
        "features_with_no_source_candidates": int(no_candidates.sum()),
        "features_needing_policy": int(needs_policy.sum()),
        "unmatched_tags": manifest.loc[no_candidates, "tag"].tolist(),
        "needs_policy_tags": manifest.loc[needs_policy, "tag"].tolist(),
    }


def _md_value(value: object) -> str:
    """Format a value for the human review Markdown."""

    text = "" if value is None or pd.isna(value) else str(value)
    return text if text else "not recorded"


def write_manifest_review_markdown(
    manifest: pd.DataFrame,
    candidate_examples: pd.DataFrame,
    manifest_path: Path,
    candidate_examples_path: Path,
    output_path: Path,
) -> None:
    """Write a human-curation Markdown file with decision placeholders."""

    lines = [
        "# AUMC Grid Feature Manifest Candidate Review",
        "",
        f"Source manifest: `{manifest_path}`",
        f"Source candidate examples: `{candidate_examples_path}`",
        "",
        "This file is for manual review of stage-1 candidate matching for the iCareFM-style hourly-grid fork.",
        "Matches are Amsterdam source-vocab rows. Mapping tables such as supplied vocab and OpenICU are evidence routes for finding those source rows, not separate duplicate matches.",
        "The matches are broad source candidates, not final extraction decisions. A noisy match here means stage 2 needs stricter per-feature source selection.",
        "",
        "## Format Template",
        "",
        "```text",
        "### tag, name, type, organ system",
        "Decision: [MTO/OTO]",
        "Target unit: ...",
        "Reconstruction type: ...",
        "Mapping status: ...",
        "Notes: ...",
        "OpenICU evidence: mapping file and OMOP concept IDs, if available",
        "",
        "match 1:",
        "  - decision: [keep/reject/needs_policy]",
        "  - decision reason: ...",
        "  - table: ...",
        "  - itemid/valueid/ordercategoryid: ...",
        "  - source token: ...",
        "  - row count: ...",
        "  - evidence: ...",
        "  - matched by: ...",
        "  - raw label/value/unit: ...",
        "",
        "match 2:",
        "  - ...",
        "```",
        "",
        "ID fields mean Amsterdam source identifiers from the raw/source vocabulary:",
        "",
        "- `itemid`: Amsterdam item identifier.",
        "- `valueid`: Amsterdam categorical value identifier when present.",
        "- `ordercategoryid`: Amsterdam drug/order category identifier when present.",
        "- `source token`: current source-token key from the vocabulary pipeline.",
        "- `row count`: rows represented by that source token in the source vocabulary.",
        "- `matched_by`: why the broad matcher pulled in the candidate, e.g. OpenICU OMOP ID or a text term.",
        "",
        f"Total features: {len(manifest)}",
        f"Features with recorded match rows: {candidate_examples['tag'].nunique() if not candidate_examples.empty else 0}",
        f"Total recorded match rows: {len(candidate_examples)}",
        "",
        "Decision labels:",
        "",
        "- `MTO`: many-to-one; multiple Amsterdam source candidates may reconstruct the same grid feature.",
        "- `OTO`: one-to-one; one Amsterdam source candidate should reconstruct the grid feature.",
        "",
    ]

    grouped_candidates = {
        tag: group.reset_index(drop=True)
        for tag, group in candidate_examples.groupby("tag", sort=False)
    }

    for feature in manifest.itertuples(index=False):
        lines.extend(
            [
                f"### {feature.tag}, {feature.name}, {feature.type}, {feature.organ_system or 'not specified'}",
                "",
                f"- Decision: `{FEATURE_DECISION_TEMPLATE}`",
                f"- Target unit: `{_md_value(feature.target_unit)}`",
                f"- Reconstruction type: `{_md_value(feature.reconstruction_type)}`",
                f"- Mapping status: `{_md_value(feature.mapping_status)}`",
            ]
        )
        if str(feature.notes):
            lines.append(f"- Notes: `{feature.notes}`")
        openicu_parts = []
        if str(feature.openicu_mapping_file):
            openicu_parts.append(f"mapping file `{feature.openicu_mapping_file}`")
        if str(feature.openicu_omop_concept_ids):
            openicu_parts.append(f"OMOP concept IDs `{feature.openicu_omop_concept_ids}`")
        if openicu_parts:
            lines.append(f"- OpenICU evidence: {'; '.join(openicu_parts)}")
        lines.append("")

        matches = grouped_candidates.get(feature.tag, pd.DataFrame(columns=CANDIDATE_EXAMPLE_COLUMNS))
        if matches.empty:
            lines.extend(["No source-candidate matches recorded.", ""])
            continue

        for idx, match in enumerate(matches.itertuples(index=False), start=1):
            lines.extend(
                [
                    f"match {idx}:",
                    f"  - decision: `{MATCH_DECISION_TEMPLATE}`",
                    "  - decision reason: ``",
                    f"  - table: `{_md_value(match.source_table)}`",
                    f"  - itemid: `{_md_value(match.source_itemid)}`",
                ]
            )
            if str(match.source_valueid):
                lines.append(f"  - valueid: `{match.source_valueid}`")
            if str(match.source_ordercategoryid):
                lines.append(f"  - ordercategoryid: `{match.source_ordercategoryid}`")
            lines.extend(
                [
                    f"  - source token: `{_md_value(match.source_token)}`",
                    f"  - row count: `{_md_value(match.row_count)}`",
                    f"  - evidence: `{_md_value(match.evidence_source)}`",
                    f"  - matched by: `{_md_value(match.matched_by)}`",
                    f"  - raw label: `{_md_value(match.source_label)}`",
                ]
            )
            if str(match.source_value):
                lines.append(f"  - raw value: `{match.source_value}`")
            if str(match.source_unit):
                lines.append(f"  - raw unit: `{match.source_unit}`")
            lines.append("")

    output_path.write_text("\n".join(lines).rstrip() + "\n")


def write_grid_manifest_outputs(config: GridManifestConfig) -> dict[str, Path]:
    """Write grid manifest and audit files."""

    manifest, candidate_examples, summary = build_feature_manifest(config)
    config.output_manifest.parent.mkdir(parents=True, exist_ok=True)
    config.audit_dir.mkdir(parents=True, exist_ok=True)

    manifest.to_csv(config.output_manifest, index=False)
    summary_path = config.audit_dir / "grid_manifest_summary.json"
    unmatched_path = config.audit_dir / "grid_manifest_unmatched_features.csv"
    candidates_path = config.audit_dir / "grid_manifest_source_candidate_examples.csv"
    review_markdown_path = config.output_manifest.with_name(f"{config.output_manifest.stem}_review.md")

    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest[
        manifest["mapping_status"].isin(["no_source_candidates", "unavailable", "needs_policy"])
    ].to_csv(unmatched_path, index=False)
    candidate_examples.to_csv(candidates_path, index=False)
    write_manifest_review_markdown(manifest, candidate_examples, config.output_manifest, candidates_path, review_markdown_path)

    return {
        "feature_manifest": config.output_manifest,
        "feature_manifest_review": review_markdown_path,
        "manifest_summary": summary_path,
        "unmatched_features": unmatched_path,
        "source_candidate_examples": candidates_path,
    }
