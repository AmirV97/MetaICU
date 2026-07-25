"""OMOP target_concept_id==0 normalization -- a deterministic rule, not a curated decision.

``0`` is OMOP's own "no matching concept" sentinel (see evidence_normalization.py's own rule:
retain it as evidence, never convert it into a real target). Any row that reaches this layer
with target_concept_id==0 is a leftover sentinel and must be nulled out and demoted to
non-emitted metadata -- see docs/policy_decisions.md's target_concept_id quirk note.
"""

from __future__ import annotations

import pandas as pd

NON_EMITTED_ROLE = "metadata_only"


def apply_zero_sentinel_normalization(vocab: pd.DataFrame) -> pd.DataFrame:
    fixed = vocab.copy()
    target = fixed["target_concept_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    is_zero = target.eq("0")
    fixed.loc[is_zero, ["harmonized_token", "target_vocabulary", "target_concept_id", "target_code", "target_label"]] = ""
    fixed.loc[is_zero, "emit_as_model_token"] = False
    fixed.loc[is_zero, "token_role"] = NON_EMITTED_ROLE
    fixed.loc[is_zero, "mapping_confidence"] = "unmapped"
    return fixed
