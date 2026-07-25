"""GCS (Glasgow Coma Scale) score-component emission policy.

Two rules, both keyed on a fixed, small set of accepted OMOP concept IDs (not curated per source
token): (1) every ``listitems`` row mapped to one of the six accepted GCS eye/motor/verbal
component concepts is emitted directly as ``dynamic_event/score_component`` -- this supersedes an
earlier policy that expected runtime GCS-total derivation; (2) itemid ``14482`` ("RA_Verbal") is
an isolated, itemid-specific mapping error onto the motor-response concept instead of its own
verbal-response concept, corrected here since every other Verbal-family itemid already resolves
correctly.
"""

from __future__ import annotations

import pandas as pd

GCS_COMPONENT_IDS = {"3016335", "3026019", "3008223", "3026549", "3009094", "3013144"}
SCORE_COMPONENT_ROLE = "dynamic_event/score_component"

RA_VERBAL_ITEMID = "14482"
RA_VERBAL_WRONG_CONCEPT_ID = "3026549"
RA_VERBAL_CORRECT_CONCEPT_ID = "3013144"


def apply_gcs_component_policy(vocab: pd.DataFrame) -> pd.DataFrame:
    fixed = vocab.copy()

    ra_verbal_mask = fixed["source_itemid"].astype(str) == RA_VERBAL_ITEMID
    target_norm = fixed["target_concept_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    ra_verbal_wrong = ra_verbal_mask & target_norm.eq(RA_VERBAL_WRONG_CONCEPT_ID)
    fixed.loc[ra_verbal_wrong, "target_concept_id"] = float(RA_VERBAL_CORRECT_CONCEPT_ID)
    fixed.loc[ra_verbal_wrong, "harmonized_token"] = f"OMOP_CONCEPT//LOINC//{RA_VERBAL_CORRECT_CONCEPT_ID}"
    fixed.loc[ra_verbal_wrong, "target_label"] = RA_VERBAL_CORRECT_CONCEPT_ID

    target_norm = fixed["target_concept_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    is_gcs = fixed["source_table"].eq("listitems") & target_norm.isin(GCS_COMPONENT_IDS)
    emit = fixed["emit_as_model_token"].astype(str).str.lower().isin(["true", "1", "yes"])
    needs_emission_fix = is_gcs & (~emit | (fixed["token_role"] != SCORE_COMPONENT_ROLE))
    fixed.loc[needs_emission_fix, "emit_as_model_token"] = True
    fixed.loc[needs_emission_fix, "token_role"] = SCORE_COMPONENT_ROLE

    return fixed
