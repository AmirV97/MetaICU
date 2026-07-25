"""Compact supplied-vocabulary schema shared by resolution, policy, and validation stages."""

from __future__ import annotations

IDENTITY_COLUMNS = [
    "dataset",
    "source_table",
    "source_itemid",
    "source_valueid",
    "source_unitid",
    "source_ordercategoryid",
    "source_label",
    "source_value",
    "source_unit",
    "source_token",
    "row_count",
]

POLICY_FIELDS = [
    "harmonized_token",
    "token_role",
    "emit_as_model_token",
    "non_drug_drugitem_class",
    "target_vocabulary",
    "target_concept_id",
    "target_code",
    "target_label",
    "mapping_source",
    "match_strength",
    "mapping_confidence",
]

COMPACT_COLUMNS = IDENTITY_COLUMNS + POLICY_FIELDS
