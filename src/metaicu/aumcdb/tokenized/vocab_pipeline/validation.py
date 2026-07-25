"""Structural and semantic contract checks for a constructed supplied vocabulary.

Mirrors the invariants in docs/aumc_vocab_rebuild_handoff.md ("Validation Contract") and
tests/test_supplied_vocab_contract.py. Raises ``AssertionError`` with every violation listed
together (not just the first one found) so a failed build reports its full scope in one pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from metaicu.aumcdb.tokenized.vocab_pipeline.omop_validation import lookup_concept_vocabulary

LEGACY_NAMESPACE_PREFIX = "OMOP//OMOP_CONCEPT//"
LAB_PREFIX = "LAB//"
LAB_ROLE = "dynamic_event/lab"
GCS_COMPONENT_IDS = {"3016335", "3026019", "3008223", "3026549", "3009094", "3013144"}
SCORE_COMPONENT_ROLE = "dynamic_event/score_component"
RA_VERBAL_CORRECT_CONCEPT_ID = "3013144"


def _is_true(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.lower().isin(["true", "1", "yes"])


def validate_supplied_vocab(
    source_vocab: pd.DataFrame,
    final_vocab: pd.DataFrame,
    omop_vocab_dir: Path,
    strict: bool = True,
) -> dict[str, Any]:
    """Check the constructed vocabulary against the supplied-vocabulary contract.

    Returns a JSON-serializable report on success; raises AssertionError listing every violation
    on failure. ``strict=False`` skips checks that only make sense for a full official
    AmsterdamUMCdb release (e.g. "at least one Metoprolol row is emitted") -- use it for bounded
    or synthetic-fixture builds, matching ``allow_unresolved_source_tokens``.
    """

    violations: list[str] = []
    emit = _is_true(final_vocab["emit_as_model_token"])
    emitted = final_vocab[emit]

    if len(final_vocab) != len(source_vocab):
        violations.append(f"row count changed: {len(source_vocab)} source tokens -> {len(final_vocab)} final rows")
    if final_vocab["source_token"].nunique() != len(final_vocab):
        violations.append("source_token is not unique")
    if final_vocab["source_token"].eq("").any():
        violations.append("empty source_token present")

    identity_cols = ["source_table", "source_itemid", "source_valueid", "source_unitid", "source_ordercategoryid", "row_count"]
    identity_cols = [c for c in identity_cols if c in source_vocab.columns and c in final_vocab.columns]
    joined = source_vocab.set_index("source_token")[identity_cols].join(
        final_vocab.set_index("source_token")[identity_cols], lsuffix="_source", rsuffix="_final", how="inner"
    )
    for col in identity_cols:
        mismatched = joined[f"{col}_source"].astype(str) != joined[f"{col}_final"].astype(str)
        if mismatched.any():
            violations.append(f"{int(mismatched.sum())} rows changed identity column {col!r}")

    if emitted["harmonized_token"].eq("").any():
        violations.append("emitted row(s) with empty harmonized_token")
    if emitted["token_role"].eq("").any():
        violations.append("emitted row(s) with empty token_role")

    zero_target = final_vocab["target_concept_id"].astype(str).str.replace(r"\.0$", "", regex=True).eq("0")
    if (emit & zero_target).any():
        violations.append("emitted row(s) with target_concept_id==0")

    legacy_emitted = emitted["harmonized_token"].astype(str).str.startswith(LEGACY_NAMESPACE_PREFIX)
    if legacy_emitted.any():
        violations.append(f"{int(legacy_emitted.sum())} emitted row(s) still in legacy OMOP//OMOP_CONCEPT// namespace")

    excluded_tables = final_vocab["source_table"].isin(["freetextitems", "procedureorderitems"])
    if (emit & excluded_tables).any():
        violations.append("emitted freetextitems or procedureorderitems row(s)")

    is_lab = final_vocab["source_token"].str.startswith(LAB_PREFIX, na=False)
    lab_role = final_vocab["token_role"].eq(LAB_ROLE)
    if (emit & is_lab & ~lab_role).any():
        violations.append("emitted LAB// row(s) missing dynamic_event/lab role")
    if (lab_role & ~is_lab).any():
        violations.append("non-LAB// row(s) carry dynamic_event/lab role")

    target_norm = final_vocab["target_concept_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    is_gcs = final_vocab["source_table"].eq("listitems") & target_norm.isin(GCS_COMPONENT_IDS)
    if (is_gcs & (~emit | final_vocab["token_role"].ne(SCORE_COMPONENT_ROLE))).any():
        violations.append("accepted GCS component row(s) not emitted as dynamic_event/score_component")

    ra_verbal = final_vocab[final_vocab["source_label"].eq("RA_Verbal")]
    if not ra_verbal.empty and not (target_norm.loc[ra_verbal.index] == RA_VERBAL_CORRECT_CONCEPT_ID).all():
        violations.append("RA_Verbal does not resolve to concept 3013144")

    conflict_rows = final_vocab[final_vocab["source_label"].str.contains("Metoprolol|Selokeen", case=False, na=False)]
    conflict_emitted = conflict_rows[_is_true(conflict_rows["emit_as_model_token"])]
    if conflict_emitted.empty:
        if strict:
            violations.append("no emitted Metoprolol row(s) found (expected at least one)")
    else:
        joined_text = "|".join(conflict_emitted["harmonized_token"].tolist() + conflict_emitted["target_label"].tolist())
        if "pantoprazole" in joined_text.lower():
            violations.append("Metoprolol/pantoprazole conflict present")

    numeric_ids = target_norm[emit & target_norm.str.match(r"^\d+$", na=False)].astype(int).unique().tolist()
    concept_vocab_by_id = lookup_concept_vocabulary(numeric_ids, omop_vocab_dir)
    unresolved_ids = sorted(set(numeric_ids) - set(concept_vocab_by_id))
    if unresolved_ids:
        violations.append(f"{len(unresolved_ids)} emitted target_concept_id(s) not found in local Athena export: {unresolved_ids[:20]}")

    if violations:
        raise AssertionError("Supplied-vocabulary contract violations:\n- " + "\n- ".join(violations))

    return {
        "source_tokens": int(len(final_vocab)),
        "emitted_source_tokens": int(emit.sum()),
        "emitted_rows": int(pd.to_numeric(emitted["row_count"], errors="coerce").fillna(0).sum()),
        "unique_emitted_destinations": int(emitted["harmonized_token"].nunique()),
        "violations": [],
    }
