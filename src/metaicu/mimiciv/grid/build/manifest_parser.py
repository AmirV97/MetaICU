"""
Parses mimic_grid_feature_manifest_review.md into a structured tag -> {reconstruction_type,
target_unit, keep_matches} dict, mirroring AUMC_grid_pipeline/grid/manifest.py's role and
output shape (so grid.extract_* keeps the same interface) but reading THIS pipeline's own
review-file format (### tag, name, type, organ_system header; Mapping status/Reconstruction
type/Target unit/Match method/Notes fields; `match N:` blocks with decision/table/itemid/
raw label/stats) rather than AUMC's field names.

Scope, v1: only the 5 mechanically-derivable reconstruction_types AUMC's parser covers
(direct_numeric, derived_output_rate, categorical, treatment_indicator, treatment_rate).
admission_context/unavailable/derived_score tags (age/weight/height/sex/adm/ethnic/tgcs)
bypass this parser entirely -- grid.extract_static reads their raw source columns directly,
same as AUMC_grid_pipeline/grid/extract_static.py's docstring reasoning.

Known v1 gap: `prescriptions`-table matches (NDC-keyed drug-class fan-outs, e.g. most of abx's
antibiotics) are DROPPED here, not extracted -- prescriptions has no itemid column and needs a
dedicated NDC-based raw_csv reader this pipeline doesn't have yet (AUMC's own grid never had an
NDC-granularity source to begin with). Logged per-tag so it's visible, not silent. Tags that
lose ALL their candidates this way fall out of `in_scope` (same as AUMC's skipped_zero_keep).
"""
import logging
import re
from importlib.resources import files
from pathlib import Path

log = logging.getLogger(__name__)

ALL_RECONSTRUCTION_TYPES = frozenset({
    "direct_numeric", "derived_output_rate", "categorical", "treatment_indicator", "treatment_rate",
})
DROPPED_TABLES = {"prescriptions", "diagnoses", "procedures_icd"}

DEFAULT_REVIEWED_MANIFEST = Path(
    str(files("metaicu.mimiciv.grid").joinpath("data/mimic_grid_feature_manifest_review.md"))
)


def _field(text, name):
    m = re.search(rf"- {name}: `([^`]*)`", text)
    return m.group(1) if m else None


def _parse_match_block(m_text):
    return {
        "decision": _field(m_text, "decision"),
        "table": _field(m_text, "table"),
        "itemid": _field(m_text, "itemid"),
        "raw_label": _field(m_text, "raw label"),
        "raw_value": _field(m_text, "raw value"),
        "standardized_label": _field(m_text, "standardized label"),
    }


def _parse_feature_block(block_text):
    rt = re.search(r"- Reconstruction type: `([^`]*)`", block_text)
    rt_value = rt.group(1) if rt else None
    tu = re.search(r"- Target unit: `([^`]*)`", block_text)
    mapping_status = re.search(r"- Mapping status: `([^`]*)`", block_text)
    match_blocks = re.split(r"\nmatch \d+[^\n:]*:\n", block_text)[1:]
    matches = [_parse_match_block(mb) for mb in match_blocks]
    keep_matches = [m for m in matches if m["decision"] == "keep" and m["table"] not in DROPPED_TABLES]
    dropped_bulk = [m for m in matches if m["decision"] == "keep" and m["table"] in DROPPED_TABLES]
    return {
        "reconstruction_type": rt_value,
        "target_unit": tu.group(1) if tu else None,
        "mapping_status": mapping_status.group(1) if mapping_status else None,
        "n_matches_total": len(matches),
        "n_keep": len(keep_matches),
        "keep_matches": keep_matches,
        "n_dropped_bulk": len(dropped_bulk),
    }


def parse_manifest(review_md_path=None, reconstruction_types=None):
    """Returns (in_scope: dict[tag -> feature info], report: dict) -- report has
    skipped_wrong_type / skipped_zero_keep / dropped_bulk_tables lists for logging by the caller."""
    reconstruction_types = set(reconstruction_types or ALL_RECONSTRUCTION_TYPES)
    text = open(review_md_path or DEFAULT_REVIEWED_MANIFEST).read()
    blocks = re.split(r"\n(?=### )", text)

    features = {}
    for b in blocks:
        m = re.match(r"### (\S+?),", b)
        if not m or m.group(1) == "tag":
            continue
        features[m.group(1)] = _parse_feature_block(b)

    in_scope, skipped_wrong_type, skipped_zero_keep, dropped_bulk_tables = {}, [], [], []
    for tag, info in features.items():
        rt = info["reconstruction_type"]
        if rt not in reconstruction_types:
            skipped_wrong_type.append((tag, rt))
            continue
        if info["n_dropped_bulk"]:
            dropped_bulk_tables.append((tag, info["n_dropped_bulk"]))
        if info["n_keep"] == 0:
            skipped_zero_keep.append(tag)
            continue
        in_scope[tag] = info

    report = {
        "n_total_blocks": len(features),
        "skipped_wrong_type": skipped_wrong_type,
        "skipped_zero_keep": skipped_zero_keep,
        "dropped_bulk_tables": dropped_bulk_tables,
    }
    return in_scope, report


def log_report(report):
    log.info(f"Parsed {report['n_total_blocks']} feature blocks.")
    log.info(f"In scope: {report['n_total_blocks'] - len(report['skipped_wrong_type']) - len(report['skipped_zero_keep'])}")
    log.info(f"Skipped (reconstruction_type outside scope -- admission_context/unavailable/"
             f"derived_score, {len(report['skipped_wrong_type'])}): "
             f"{sorted(set(rt for _, rt in report['skipped_wrong_type']), key=lambda x: (x is None, x))}")
    log.info(f"Skipped (0 keep matches after dropping prescriptions/diagnoses/procedures_icd, "
             f"{len(report['skipped_zero_keep'])}): {report['skipped_zero_keep']}")
    if report["dropped_bulk_tables"]:
        log.warning(f"Tags with dropped bulk (prescriptions/diagnoses/procedures_icd) matches "
                    f"(itemid-based candidates for these tags, if any, are still extracted -- "
                    f"only the bulk-table rows are dropped): {report['dropped_bulk_tables']}")
