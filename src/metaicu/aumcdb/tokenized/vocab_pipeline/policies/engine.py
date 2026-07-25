"""Fixed-order policy engine: baseline resolution -> curated manifests -> deterministic rules.

Order matters -- later, more specific layers intentionally override earlier, more general ones
(see docs/aumc_vocab_rebuild_handoff.md, "Policy Layer Order"). This exact sequence was verified
to reproduce the historical v16 vocabulary with zero row-level differences before being ported
here as real code.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metaicu.aumcdb.tokenized.vocab_pipeline.policies.gcs_components import apply_gcs_component_policy
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.lab_role import apply_lab_role_assignment
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.manifest_replay import apply_manifest_layers
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.namespace import apply_namespace_canonicalization
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.zero_sentinel import apply_zero_sentinel_normalization

# Curated, one-off clinical decisions frozen as versioned manifests (see manifest_replay.py).
CURATED_MANIFEST_LAYERS_PRE_LAB = [
    "v4_curated_unmapped",
    "v5_keep_drop_review",
    "v6_semantic_contamination",
    "v7_targeted_refinement",
    "v8_device_outcome_refinement",
    "v9_admission_respiratory_cleanup",
    "v10_medication_atc",
    "v11_listitem_values",
]
LAB_CONSOLIDATION_MANIFEST_LAYER = "v13_lab_consolidation"

DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "data" / "policy_manifests"


def apply_policy_layers(baseline: pd.DataFrame, omop_vocab_dir: Path, manifest_dir: Path = DEFAULT_MANIFEST_DIR) -> pd.DataFrame:
    """Apply the full, fixed policy-layer order to a baseline-resolved compact vocabulary."""

    state = apply_manifest_layers(baseline, manifest_dir, CURATED_MANIFEST_LAYERS_PRE_LAB)
    state = apply_zero_sentinel_normalization(state)
    state = apply_manifest_layers(state, manifest_dir, [LAB_CONSOLIDATION_MANIFEST_LAYER])
    state = apply_namespace_canonicalization(state, omop_vocab_dir)
    state = apply_lab_role_assignment(state)
    state = apply_gcs_component_policy(state)
    return state
