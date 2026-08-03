"""Build an iCareFM-style feature manifest for the MIMIC-IV grid pipeline.

Searches MIMIC-IV's own raw item catalogs (icu/d_items.csv.gz, hosp/d_labitems.csv.gz) by
per-tag search terms + a generic feature-name fallback -- mirrors metaicu.aumcdb.grid.manifest's
shape and role, but native to MIMIC: no chaining through dataset_EDA/M4_grid's own
build_mimic_grid_manifest.py (which resolved candidates by walking AUMC_grid_pipeline's already-
reviewed manifest through cross_dataset_harmonization's OMOP concept-map parquet files). That
chain ties correctness to two repos outside MetaICU's own package boundary; this module drops it
per the port plan's Stage 2 decision, keeping only the raw-catalog label-keyword search
M4_grid's builder already used as its tier-3 fallback (there, a last resort behind two
concept-matching tiers; here, promoted to the only mechanism).

TAG_SEARCH_TERMS/TREATMENT_SEARCH_TERMS are intentionally EMPTY -- an extension point mirroring
aumcdb's per-tag override dicts, not filled in here. aumcdb's terms were hand-curated against
Dutch/AUMC vocabulary the author could validate directly; inventing MIMIC-side clinical synonyms
without an equivalent validation pass would be unvalidated guessing. The generic feature-name
search (every tag's `name` column, e.g. "Norepinephrine", "Mean arterial pressure") is what
M4_grid's builder already relied on for its own tier-3 matches, so it is a reasonable default,
not a placeholder -- but a real manual-review pass (same as M4_grid's own history) is expected
before any newly-surfaced candidate is trusted, per this module's write_grid_manifest_outputs
docstring and the port plan's Stage 2 exit criteria. Running this builder does NOT retroactively
re-review or replace the already-reviewed mimic_grid_feature_manifest_review.md shipped in
grid/data/ (ported as-is in Stage 1) -- it only produces a fresh from-scratch candidate list for
comparison against it.

This module only describes feature/source candidates. It does not scan raw MIMIC event-table
rows and does not apply the reconstruction/extraction logic itself (grid.build.*).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

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
    "source_unit_candidates",
    "source_label_examples",
    "mapping_status",
    "notes",
]

CANDIDATE_EXAMPLE_COLUMNS = [
    "tag",
    "name",
    "source_table",
    "source_itemid",
    "source_unit",
    "source_label",
    "matched_by",
]

FEATURE_DECISION_TEMPLATE = "[MTO/OTO]"
MATCH_DECISION_TEMPLATE = "[keep/reject/needs_policy]"


@dataclass(frozen=True)
class GridManifestConfig:
    """Inputs and outputs for the MIMIC-IV grid feature-manifest stage. raw_data_dir points at
    the pre_MEDS export root (icu/d_items.csv.gz, hosp/d_labitems.csv.gz) -- MIMIC's raw item
    catalogs are the candidate universe directly; unlike aumcdb, there is no separate pre-built
    source_vocab/supplied_vocab CSV or OpenICU mapping inventory to also read."""

    output_manifest: Path
    audit_dir: Path
    raw_data_dir: Path
    feature_list: Path | None = None


# age/weight/height/sex/adm/ethnic/tgcs have no itemid-vocabulary candidate search at all --
# fixed source columns (or, for tgcs, no source), ported as MIMIC-native facts from
# dataset_EDA/M4_grid/build_mimic_grid_manifest.py's own ADMISSION_CONTEXT_FIXED/ETHNIC_FIXED/
# TGCS_FIXED (no cross-dataset-harmonization dependency in that logic to begin with).
ADMISSION_CONTEXT_FIXED = {
    "age": dict(
        source_table_candidates="patients|admissions",
        source_itemid_candidates="",
        source_unit_candidates="years",
        source_label_examples="year_of_birth|admittime",
        mapping_status="admission_context",
        notes="age at admission = admittime.year - patients.year_of_birth (MIMIC's de-identified "
              "patients.parquet has no direct anchor_age column in this pre_MEDS export).",
    ),
    "weight": dict(
        source_table_candidates="omr|chartevents",
        source_itemid_candidates="226512|224639",
        source_unit_candidates="kg|lbs",
        source_label_examples="Weight (Lbs)|Admission Weight (Kg)|Daily Weight",
        mapping_status="admission_context",
        notes="omr.result_name='Weight (Lbs)' (outpatient, sparse) or chartevents admission-weight "
              "itemids (226512 Kg, 224639 lbs) -- candidates only, not yet decided which to prefer.",
    ),
    "height": dict(
        source_table_candidates="omr|chartevents",
        source_itemid_candidates="226730",
        source_unit_candidates="in|cm",
        source_label_examples="Height (Inches)|Height (cm)",
        mapping_status="admission_context",
        notes="omr.result_name='Height (Inches)' (outpatient, sparse) or chartevents itemid 226730 "
              "(Height (cm)) -- candidates only, not yet decided which to prefer.",
    ),
    "sex": dict(
        source_table_candidates="patients",
        source_itemid_candidates="",
        source_unit_candidates="categorical",
        source_label_examples="gender",
        mapping_status="admission_context",
        notes="patients.gender (F/M) -- direct column, no collapsing needed.",
    ),
    "adm": dict(
        source_table_candidates="admissions",
        source_itemid_candidates="",
        source_unit_candidates="categorical",
        source_label_examples="admission_type|admission_location",
        mapping_status="admission_context",
        notes="admissions.admission_type (urgency analogue) x admission_location (origin analogue) "
              "-- collapsing policy (top-N + Other) still to be decided, same as AUMC's adm.",
    ),
}

ETHNIC_FIXED = dict(
    source_table_candidates="admissions",
    source_itemid_candidates="",
    source_unit_candidates="categorical",
    source_label_examples="race",
    mapping_status="source_candidates_found",
    notes="MIMIC-IV admissions.race is available (unlike AUMCdb, which had no reliable ethnicity "
          "field) -- this can be resolved, unlike AUMC's 'unavailable'.",
)

TGCS_FIXED = dict(
    source_table_candidates="",
    source_itemid_candidates="",
    source_unit_candidates="categorical",
    source_label_examples="",
    mapping_status="no_source_candidates",
    notes="Same as AUMC: no direct source, derive by summing mgcs+vgcs+egcs-equivalent MIMIC "
          "components (chartevents GCS Motor/Verbal/Eye Opening) once those are individually "
          "resolved.",
)

# Per-tag search-term overrides, mirroring aumcdb's TAG_SEARCH_TERMS/TREATMENT_SEARCH_TERMS --
# see module docstring for why these are empty rather than hand-curated for MIMIC.
TAG_SEARCH_TERMS: dict[str, list[str]] = {}
TREATMENT_SEARCH_TERMS: dict[str, list[str]] = {}


def _reconstruction_type(tag: str, feature_type: str, target_unit: str) -> str:
    """Return the first-stage reconstruction class for an iCareFM tag, MIMIC-native (ported
    from dataset_EDA/M4_grid/mimic_grid_feature_manifest_review.md's own already-reviewed
    classifications for the special-cased tags -- samp/tgcs/ethnic/supp_o2_vent -- not
    re-derived from AUMC's review)."""

    if tag in {"age", "sex", "weight", "height", "adm"}:
        return "admission_context"
    if tag == "ethnic":
        return "unavailable"
    if tag == "tgcs":
        return "derived_score"
    if tag == "urine_rate":
        return "derived_output_rate"
    if tag == "samp":
        return "treatment_indicator"
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
        "samp": "Point-event handling (any kept-match row in an hour = On) is mechanically "
                "identical to other treatment_indicator tags -- no bespoke microbiology type "
                "needed, mirroring AUMC's own review precedent.",
        "urine_rate": "Raw fluid-output rows exist; hourly urine-rate construction is a derived step.",
    }
    if tag in notes:
        return notes[tag]
    if reconstruction_type in {"treatment_rate", "treatment_indicator"}:
        return "Treatment rate/indicator construction is handled in grid.build.extract_rate/extract_indicator from raw drug/procedure/chart intervals."
    return ""


def _candidate_terms(tag: str, name: str, feature_type: str) -> list[str]:
    """Return search terms for source-candidate discovery: any hand-curated override terms for
    this tag, the feature's own descriptive name (the search M4_grid's builder already relied
    on for most of its own tier-3 matches), and -- for tags 3+ characters -- the tag mnemonic
    itself as a standalone term. Many iCareFM tags ARE the clinical abbreviation MIMIC's own
    catalog uses verbatim (e.g. "po2" -> "pO2", "wbc" -> "WBC Count") where the tag's full
    descriptive name ("Partial Pressure Of Oxygen", "White Blood Cell Count") shares no word
    with the catalog label at all. Excluded below 3 characters (hr, pt, k, na, ...): too short
    to be a distinctive substring, matching common English words/fragments instead."""

    terms: list[str] = []
    if feature_type == "treatment":
        terms.extend(TREATMENT_SEARCH_TERMS.get(tag, []))
    terms.extend(TAG_SEARCH_TERMS.get(tag, []))
    terms.append(name)
    base_tag = tag[:-4] if tag.endswith("_ind") else tag
    if len(base_tag) >= 3:
        terms.append(base_tag)
    return [term for term in dict.fromkeys(str(term) for term in terms) if term]


_STOPWORDS = {"the", "of", "and", "or", "on", "in", "per", "a", "an", "for", "with", "to", "hour"}


def _keywords(term: str) -> list[str]:
    """Alphanumeric tokens, digits kept attached to their letters (not split off) -- clinical
    mnemonics like "po2"/"co2" are meaningless once the digit is severed ("po2" -> "po", too
    short to pass the length filter below, silently dropping the whole term)."""
    tokens = re.findall(r"[a-zA-Z0-9]+", term.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _load_raw_catalog(raw_data_dir: Path) -> pl.DataFrame:
    """icu/d_items.csv.gz (every chartevents/inputevents/outputevents/procedureevents/
    datetimeevents/ingredientevents itemid, `linksto` names its home table) union
    hosp/d_labitems.csv.gz (labevents itemids, no linksto column -- tagged "labevents" here).
    Full raw catalogs, not an OMOP-mapped subset, per feedback_check_raw_data_not_just_mappings."""

    d_items = pl.read_csv(raw_data_dir / "icu/d_items.csv.gz", infer_schema_length=None).select(
        ["itemid", "label", "linksto", "unitname"]
    )
    d_labitems = pl.read_csv(raw_data_dir / "hosp/d_labitems.csv.gz", infer_schema_length=None).select(
        ["itemid", "label"]
    ).with_columns(
        pl.lit("labevents").alias("linksto"), pl.lit(None, dtype=pl.String).alias("unitname")
    )
    return pl.concat([d_items, d_labitems.select(d_items.columns)])


def _search_candidates(catalog: pl.DataFrame, terms: list[str]) -> pl.DataFrame:
    """Case-insensitive label keyword search, one pass per term, ranked by how many of that
    term's keyword tokens appear in the label (OR to cast the net -- a token missing from an
    otherwise-real hit shouldn't drop it entirely, e.g. "White Blood Cell Count" vs the
    catalog's "White Blood Cells" is missing "count" -- but ranked so a full-token match sorts
    to the top instead of being buried under every label containing just one common token (a
    flat OR ranked by nothing, M4_grid's own keyword_fallback design, let "Heart Rate" get
    buried under every "...Rate" label -- Respiratory Rate, Medication Infusion Rate, ...).
    Rows are deduplicated by (itemid, linksto), keeping the best-ranked term's match info."""

    frames = []
    for term in terms:
        tokens = _keywords(term)
        if not tokens:
            continue
        label_lower = pl.col("label").str.to_lowercase()
        match_count = pl.sum_horizontal([label_lower.str.contains(re.escape(t)).cast(pl.Int32) for t in tokens])
        hits = catalog.with_columns(match_count.alias("_match_count")).filter(pl.col("_match_count") > 0)
        if hits.height:
            frames.append(hits.with_columns(
                pl.lit(f"term:{term}").alias("matched_by"),
                (pl.col("_match_count") / len(tokens)).alias("_match_frac"),
            ))
    if not frames:
        return catalog.head(0).with_columns(
            pl.lit(None, dtype=pl.String).alias("matched_by"), pl.lit(None, dtype=pl.Float64).alias("_match_frac")
        )
    candidates = pl.concat(frames).sort("_match_frac", descending=True).unique(
        subset=["itemid", "linksto"], keep="first", maintain_order=True
    )
    return candidates


def _allowed_source_tables(reconstruction_type: str) -> set[str]:
    """Source tables plausible for a grid feature class -- mirrors
    grid.build.extract_numeric/extract_indicator/extract_rate's own TABLE_ALIASES scope."""

    if reconstruction_type in {"direct_numeric", "derived_output_rate"}:
        return {"chartevents", "labevents", "outputevents"}
    if reconstruction_type == "categorical":
        return {"chartevents"}
    if reconstruction_type in {"treatment_rate", "treatment_indicator"}:
        return {"inputevents", "procedureevents", "chartevents"}
    return set()


def _pipe_unique(values, limit: int | None = None) -> str:
    unique = [str(v) for v in values if v is not None and str(v) not in ("", "nan", "None")]
    unique = list(dict.fromkeys(unique))
    if limit is not None:
        unique = unique[:limit]
    return "|".join(unique)


def load_feature_seed(path: Path | None = None) -> pl.DataFrame:
    """Load iCareFM Table S3 feature seed rows -- same 129-row, dataset-agnostic list aumcdb
    ships (tag/name/type/organ_system/target_unit are properties of the feature, not the
    dataset); reused verbatim rather than duplicated, per the port plan's Stage 2 notes."""

    feature_path = path or DEFAULT_FEATURE_LIST
    features = pl.read_csv(feature_path)
    if "unit" in features.columns and "target_unit" not in features.columns:
        features = features.rename({"unit": "target_unit"})
    required = ["tag", "name", "type", "organ_system", "target_unit"]
    missing = [c for c in required if c not in features.columns]
    if missing:
        raise ValueError(f"Feature list is missing required columns: {missing}")
    features = features.select(required)
    dupes = features.filter(pl.col("tag").is_duplicated())["tag"].unique().to_list()
    if dupes:
        raise ValueError(f"Feature list has duplicate tags: {sorted(dupes)}")
    return features


def build_feature_manifest(config: GridManifestConfig) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """Build the feature manifest, candidate examples, and summary payload."""

    features = load_feature_seed(config.feature_list)
    catalog = _load_raw_catalog(config.raw_data_dir)

    manifest_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for feature in features.iter_rows(named=True):
        tag, name, feature_type, target_unit = feature["tag"], feature["name"], feature["type"], feature["target_unit"]

        if tag in ADMISSION_CONTEXT_FIXED:
            manifest_rows.append({**feature, "organ_system": feature["organ_system"],
                                   "reconstruction_type": "admission_context", **ADMISSION_CONTEXT_FIXED[tag]})
            continue
        if tag == "ethnic":
            manifest_rows.append({**feature, "reconstruction_type": "unavailable", **ETHNIC_FIXED})
            continue
        if tag == "tgcs":
            manifest_rows.append({**feature, "reconstruction_type": "derived_score", **TGCS_FIXED})
            continue

        reconstruction_type = _reconstruction_type(tag, feature_type, target_unit)
        terms = _candidate_terms(tag, name, feature_type)
        candidates = _search_candidates(catalog, terms)
        allowed = _allowed_source_tables(reconstruction_type)
        candidates = candidates.filter(pl.col("linksto").is_in(list(allowed))) if allowed else candidates.head(0)

        for row in candidates.head(20).iter_rows(named=True):
            candidate_rows.append(dict(
                tag=tag, name=name, source_table=row["linksto"], source_itemid=row["itemid"],
                source_unit=row["unitname"], source_label=row["label"], matched_by=row["matched_by"],
            ))

        mapping_status = "source_candidates_found" if candidates.height else "no_source_candidates"
        manifest_rows.append({
            "tag": tag, "name": name, "type": feature_type, "organ_system": feature["organ_system"],
            "target_unit": target_unit, "reconstruction_type": reconstruction_type,
            "source_table_candidates": _pipe_unique(candidates["linksto"].to_list()) if candidates.height else "",
            "source_itemid_candidates": _pipe_unique(candidates["itemid"].to_list()) if candidates.height else "",
            "source_unit_candidates": _pipe_unique(candidates["unitname"].to_list()) if candidates.height else "",
            "source_label_examples": _pipe_unique(candidates["label"].to_list(), limit=8) if candidates.height else "",
            "mapping_status": mapping_status,
            "notes": _default_note(tag, reconstruction_type),
        })

    manifest = pl.DataFrame(manifest_rows, schema={c: pl.String for c in MANIFEST_COLUMNS}).select(MANIFEST_COLUMNS)
    candidate_examples = pl.DataFrame(
        candidate_rows,
        schema={"tag": pl.String, "name": pl.String, "source_table": pl.String, "source_itemid": pl.Int64,
                "source_unit": pl.String, "source_label": pl.String, "matched_by": pl.String},
    ) if candidate_rows else pl.DataFrame(schema={c: pl.String for c in CANDIDATE_EXAMPLE_COLUMNS})
    summary = summarize_manifest(manifest)
    return manifest, candidate_examples, summary


def summarize_manifest(manifest: pl.DataFrame) -> dict[str, Any]:
    """Return compact manifest audit counts."""

    no_candidates = manifest["mapping_status"].is_in(["no_source_candidates", "unavailable"])
    return {
        "total_features": manifest.height,
        "paper_claimed_total_features": 130,
        "extractable_table_s3_features": manifest.height,
        "feature_count_caveat": "The extractable Table S3 rows are 129 although the supplement prose says 130.",
        "counts_by_type": dict(zip(*manifest["type"].value_counts().to_dict(as_series=False).values())),
        "counts_by_reconstruction_type": dict(zip(*manifest["reconstruction_type"].value_counts().to_dict(as_series=False).values())),
        "counts_by_mapping_status": dict(zip(*manifest["mapping_status"].value_counts().to_dict(as_series=False).values())),
        "features_with_no_source_candidates": int(no_candidates.sum()),
        "unmatched_tags": manifest.filter(no_candidates)["tag"].to_list(),
    }


def _md_value(value) -> str:
    text = "" if value is None else str(value)
    return text if text else "not recorded"


def write_manifest_review_markdown(
    manifest: pl.DataFrame,
    candidate_examples: pl.DataFrame,
    manifest_path: Path,
    candidate_examples_path: Path,
    output_path: Path,
) -> None:
    """Write a human-curation Markdown file with decision placeholders -- same review-cycle role
    as M4_grid's own mimic_grid_feature_manifest_review.md (a fresh candidate list from this
    from-scratch builder, not that file; see module docstring)."""

    lines = [
        "# MIMIC-IV Grid Feature Manifest Candidate Review",
        "",
        f"Source manifest: `{manifest_path}`",
        f"Source candidate examples: `{candidate_examples_path}`",
        "",
        "This file is for manual review of stage-1 candidate matching for the iCareFM-style hourly-grid MIMIC-IV port.",
        "Matches are raw MIMIC-IV item-catalog rows (icu/d_items.csv.gz, hosp/d_labitems.csv.gz), found by label keyword search.",
        "The matches are broad source candidates, not final extraction decisions. A noisy match here means a stricter per-feature source selection is still needed.",
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
        "",
        "match 1:",
        "  - decision: [keep/reject/needs_policy]",
        "  - decision reason: ...",
        "  - table: ...",
        "  - itemid: ...",
        "  - row count: ...",
        "  - matched by: ...",
        "  - raw label/unit: ...",
        "",
        "match 2:",
        "  - ...",
        "```",
        "",
        "ID fields mean MIMIC-IV source identifiers from the raw item catalogs:",
        "",
        "- `itemid`: MIMIC-IV item identifier (icu/d_items.csv.gz or hosp/d_labitems.csv.gz).",
        "- `matched_by`: which search term pulled in the candidate.",
        "",
        f"Total features: {manifest.height}",
        f"Features with recorded match rows: {candidate_examples['tag'].n_unique() if candidate_examples.height else 0}",
        f"Total recorded match rows: {candidate_examples.height}",
        "",
        "Decision labels:",
        "",
        "- `MTO`: many-to-one; multiple MIMIC-IV source candidates may reconstruct the same grid feature.",
        "- `OTO`: one-to-one; one MIMIC-IV source candidate should reconstruct the grid feature.",
        "",
    ]

    grouped = {tag: group for tag, group in candidate_examples.group_by(["tag"], maintain_order=True)} if candidate_examples.height else {}

    for feature in manifest.iter_rows(named=True):
        lines.extend([
            f"### {feature['tag']}, {feature['name']}, {feature['type']}, {feature['organ_system'] or 'not specified'}",
            "",
            f"- Decision: `{FEATURE_DECISION_TEMPLATE}`",
            f"- Target unit: `{_md_value(feature['target_unit'])}`",
            f"- Reconstruction type: `{_md_value(feature['reconstruction_type'])}`",
            f"- Mapping status: `{_md_value(feature['mapping_status'])}`",
        ])
        if feature["notes"]:
            lines.append(f"- Notes: `{feature['notes']}`")
        lines.append("")

        matches = grouped.get((feature["tag"],))
        if matches is None or matches.height == 0:
            lines.extend(["No source-candidate matches recorded.", ""])
            continue

        for idx, match in enumerate(matches.iter_rows(named=True), start=1):
            lines.extend([
                f"match {idx}:",
                f"  - decision: `{MATCH_DECISION_TEMPLATE}`",
                "  - decision reason: ``",
                f"  - table: `{_md_value(match['source_table'])}`",
                f"  - itemid: `{_md_value(match['source_itemid'])}`",
                f"  - matched by: `{_md_value(match['matched_by'])}`",
                f"  - raw label: `{_md_value(match['source_label'])}`",
            ])
            if match["source_unit"]:
                lines.append(f"  - raw unit: `{match['source_unit']}`")
            lines.append("")

    output_path.write_text("\n".join(lines).rstrip() + "\n")


def write_grid_manifest_outputs(config: GridManifestConfig) -> dict[str, Path]:
    """Write grid manifest and audit files."""

    manifest, candidate_examples, summary = build_feature_manifest(config)
    config.output_manifest.parent.mkdir(parents=True, exist_ok=True)
    config.audit_dir.mkdir(parents=True, exist_ok=True)

    manifest.write_csv(config.output_manifest)
    summary_path = config.audit_dir / "grid_manifest_summary.json"
    unmatched_path = config.audit_dir / "grid_manifest_unmatched_features.csv"
    candidates_path = config.audit_dir / "grid_manifest_source_candidate_examples.csv"
    review_markdown_path = config.output_manifest.with_name(f"{config.output_manifest.stem}_review.md")

    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest.filter(pl.col("mapping_status").is_in(["no_source_candidates", "unavailable", "needs_policy"])).write_csv(unmatched_path)
    candidate_examples.write_csv(candidates_path)
    write_manifest_review_markdown(manifest, candidate_examples, config.output_manifest, candidates_path, review_markdown_path)

    return {
        "feature_manifest": config.output_manifest,
        "feature_manifest_review": review_markdown_path,
        "manifest_summary": summary_path,
        "unmatched_features": unmatched_path,
        "source_candidate_examples": candidates_path,
    }
