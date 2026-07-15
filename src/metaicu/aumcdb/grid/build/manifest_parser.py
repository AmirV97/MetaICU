"""
Parse a reviewed AUMC grid feature manifest into a structured feature -> {
reconstruction_type, target_unit, keep_matches} dict, covering all 5 mechanically-derivable
reconstruction types: direct_numeric, categorical, treatment_indicator, derived_output_rate,
treatment_rate. (samp was reclassified from a bespoke 'microbiology' type to
treatment_indicator this session -- it flows through this same parser now, no special case.)

Only `keep`-decision matches are extracted (needs_policy/reject/unsure excluded). Refactor of
the earlier standalone parser: same parsing logic, now a plain importable function instead of
a script with hardcoded globals, so the grid dataset CLI (or a notebook) can call it directly.
"""
import logging
import re
from importlib.resources import files
from pathlib import Path

EXPECTED_TABLE = {
    "direct_numeric": "numericitems",
    "derived_output_rate": "numericitems",
    "categorical": "listitems",
    "treatment_indicator": "drugitems",
    "treatment_rate": "drugitems",
}
ALL_RECONSTRUCTION_TYPES = frozenset(EXPECTED_TABLE)

# Every table each reconstruction type's extractor actually consumes (not just its primary/
# most-common one, EXPECTED_TABLE above) -- used to tell a genuinely unhandled cross-table
# match from one that's already intentionally supported elsewhere in the codebase. Kept in
# sync manually with grid/extract_*.py; a match whose table isn't in this set for its type is
# the only thing that should still surface as a real anomaly.
SUPPORTED_TABLES = {
    # listitems only when a CATEGORICAL_CONSTANT override exists (unit_conversion_overrides.py) --
    # see extract_numeric._build_numeric_from_listitems_const
    "direct_numeric": {"numericitems", "listitems"},
    "derived_output_rate": {"numericitems", "listitems"},
    "categorical": {"listitems"},
    # drugitems/processitems contribute [start,stop] intervals; numericitems/listitems/
    # procedureorderitems contribute point-in-time hours -- see extract_indicator.py's
    # POINT_TABLES and _build_processitems_on_hours
    "treatment_indicator": {"drugitems", "processitems", "numericitems", "listitems", "procedureorderitems"},
    # numericitems only for ufilt, whose source is a fluid-output measurement, not a drugitems
    # administration record -- see treatment_rate_formulas.py's "raw_value_numericitems" formula
    "treatment_rate": {"drugitems", "numericitems"},
}

log = logging.getLogger(__name__)

DEFAULT_REVIEWED_MANIFEST = Path(
    str(files("metaicu.aumcdb.grid").joinpath("data/aumc_grid_feature_manifest_review.md"))
)


def _parse_match_block(m_text):
    def field(name):
        mm = re.search(rf"- {name}: `([^`]*)`", m_text)
        return mm.group(1) if mm else None
    return {
        "decision": field("decision"),
        "table": field("table"),
        "itemid": field("itemid"),
        "ordercategoryid": field("ordercategoryid"),
        "valueid": field("valueid"),
        "raw_label": field("raw label") or field("raw value"),
        "standardized_label": field("standardized label"),
    }


def _parse_feature_block(block_text):
    rt = re.search(r"Reconstruction type: `([^`]*)`", block_text)
    tu = re.search(r"Target unit: `([^`]*)`", block_text)
    dec = re.search(r"^- Decision: `([^`]*)`", block_text, re.MULTILINE)
    match_blocks = re.split(r"\nmatch \d+:\n", block_text)[1:]
    matches = [_parse_match_block(mb) for mb in match_blocks]
    keep_matches = [m for m in matches if m["decision"] == "keep"]
    return {
        "reconstruction_type": rt.group(1) if rt else None,
        "target_unit": tu.group(1) if tu else None,
        "feature_decision": dec.group(1) if dec else None,
        "n_matches_total": len(matches),
        "n_keep": len(keep_matches),
        "keep_matches": keep_matches,
    }


def parse_manifest(manifest_path: Path | None = None, reconstruction_types=None):
    """Returns (in_scope: dict[tag -> feature info], report: dict) where report has
    skipped_wrong_type / skipped_zero_keep / anomalies lists for logging by the caller."""
    reconstruction_types = set(reconstruction_types or ALL_RECONSTRUCTION_TYPES)
    path = manifest_path or DEFAULT_REVIEWED_MANIFEST
    text = Path(path).read_text()
    blocks = re.split(r"\n(?=### )", text)

    features = {}
    for b in blocks:
        m = re.match(r"### (\S+?),", b)
        if not m or m.group(1) == "tag":
            continue
        features[m.group(1)] = _parse_feature_block(b)

    in_scope, skipped_wrong_type, skipped_zero_keep, anomalies = {}, [], [], []
    for tag, info in features.items():
        rt = info["reconstruction_type"]
        if rt not in reconstruction_types:
            skipped_wrong_type.append((tag, rt))
            continue
        if info["n_keep"] == 0:
            skipped_zero_keep.append(tag)
            continue
        supported = SUPPORTED_TABLES[rt]
        for km in info["keep_matches"]:
            if km["table"] not in supported:
                anomalies.append((tag, rt, km["table"], km["itemid"], km["raw_label"]))
        in_scope[tag] = info

    report = {
        "n_total_blocks": len(features),
        "skipped_wrong_type": skipped_wrong_type,
        "skipped_zero_keep": skipped_zero_keep,
        "anomalies": anomalies,
    }
    return in_scope, report


def log_report(report):
    log.info(f"Parsed {report['n_total_blocks']} feature blocks.")
    log.info(f"Skipped (reconstruction_type outside scope, {len(report['skipped_wrong_type'])}): "
             f"{sorted(set(rt for _, rt in report['skipped_wrong_type']), key=lambda x: (x is None, x))}")
    log.info(f"Skipped (in-scope type but 0 keep matches -- {len(report['skipped_zero_keep'])}): "
             f"{report['skipped_zero_keep']}")
    log.info(f"Cross-table anomalies flagged ({len(report['anomalies'])}) -- table not in "
             f"SUPPORTED_TABLES for this reconstruction_type, i.e. genuinely unhandled by "
             f"grid/extract_*.py, NOT auto-fixed:")
    for tag, rt, table, itemid, label in report["anomalies"]:
        log.info(f"  {tag} ({rt}): kept match table={table} itemid={itemid} label={label!r} "
                 f"-- primary table for this type={EXPECTED_TABLE[rt]}")
