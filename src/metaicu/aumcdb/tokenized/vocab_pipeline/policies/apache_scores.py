"""Resolve Amsterdam numeric APACHE scores to current standard OMOP concepts."""

from __future__ import annotations

import pandas as pd

APACHE_SCORE_OVERRIDES = {
    "13081": ("LOINC", "3008138", "9264-3", "Apache II score"),
    "14453": ("LOINC", "3008138", "9264-3", "Apache II score"),
    "16624": ("LOINC", "3008138", "9264-3", "Apache II score"),
    "19499": ("LOINC", "3008138", "9264-3", "Apache II score"),
    "19500": (
        "SNOMED",
        "1450877",
        "1351474005",
        "APACHE IV (Acute Physiology and Chronic Health Evaluation IV) score",
    ),
    "19750": ("LOINC", "3015511", "9265-0", "Apache III score"),
}


def apply_apache_score_policy(vocab: pd.DataFrame) -> pd.DataFrame:
    """Apply itemid-specific APACHE II, III, and IV mappings.

    The Amsterdam legacy dictionary identifies itemids 13081, 14453, 16624,
    and 19499 as APACHE II, including the otherwise ambiguous MCA and Research
    labels. Item-specific mappings avoid inferring score versions from values.
    """

    fixed = vocab.copy()
    itemids = fixed["source_itemid"].astype(str).str.replace(r"\.0$", "", regex=True)

    for itemid, (vocabulary, concept_id, code, label) in APACHE_SCORE_OVERRIDES.items():
        mask = fixed["source_table"].eq("numericitems") & itemids.eq(itemid)
        fixed.loc[mask, "harmonized_token"] = f"OMOP_CONCEPT//{vocabulary}//{concept_id}"
        fixed.loc[mask, "token_role"] = "dynamic_event"
        fixed.loc[mask, "emit_as_model_token"] = "True"
        fixed.loc[mask, "target_vocabulary"] = vocabulary
        fixed.loc[mask, "target_concept_id"] = concept_id
        fixed.loc[mask, "target_code"] = code
        fixed.loc[mask, "target_label"] = label
        fixed.loc[mask, "mapping_source"] = "manual_omop_override"
        fixed.loc[mask, "match_strength"] = "exact_itemid"
        fixed.loc[mask, "mapping_confidence"] = "high"

    return fixed
