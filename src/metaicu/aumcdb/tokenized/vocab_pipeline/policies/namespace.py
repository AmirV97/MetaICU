"""Canonical OMOP concept namespace formatting -- a deterministic rule over resolved concepts.

Rewrites the legacy ``OMOP//OMOP_CONCEPT//{id}`` namespace to the canonical
``OMOP_CONCEPT//{vocabulary_id}//{id}`` form the supplied-vocabulary contract requires. The real
``vocabulary_id`` comes from a live CONCEPT.csv lookup (``omop_validation.py``), so this rule
responds to the configured OMOP/Athena export rather than a frozen mapping. A concept_id absent
from the local export is left in the legacy namespace untouched (never emitted -- enforced by
validation.py).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metaicu.aumcdb.tokenized.vocab_pipeline.omop_validation import lookup_concept_vocabulary

LEGACY_NAMESPACE_PREFIX = "OMOP//OMOP_CONCEPT//"


def apply_namespace_canonicalization(vocab: pd.DataFrame, omop_vocab_dir: Path) -> pd.DataFrame:
    fixed = vocab.copy()
    is_legacy = fixed["harmonized_token"].astype(str).str.startswith(LEGACY_NAMESPACE_PREFIX)
    legacy_concept_ids = (
        fixed.loc[is_legacy, "target_concept_id"]
        .dropna()
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )
    legacy_concept_ids = legacy_concept_ids[legacy_concept_ids.str.match(r"^\d+$")].astype(int).unique().tolist()
    concept_vocab_by_id = lookup_concept_vocabulary(legacy_concept_ids, omop_vocab_dir)

    for idx in fixed.index[is_legacy]:
        raw_id = str(fixed.loc[idx, "target_concept_id"])
        if not raw_id or not raw_id.replace(".0", "").isdigit():
            continue
        concept_id = int(float(raw_id))
        real_vocab = concept_vocab_by_id.get(concept_id)
        if real_vocab is None:
            continue
        fixed.loc[idx, "harmonized_token"] = f"OMOP_CONCEPT//{real_vocab}//{concept_id}"
        fixed.loc[idx, "target_vocabulary"] = real_vocab
    return fixed
