"""Baseline target resolution: join the extracted source vocabulary to a resolved mapping.

Known scope limit (see docs/aumc_vocab_rebuild_handoff.md, "Stage 4: Baseline Target
Resolution"): the historical OMOP-validated candidate ranking that produces this baseline
(concept existence/validity checks, standard/non-standard "Maps to" resolution, safe-replacement
downgrades -- historically scripts 08/09/11/12/14/16) is its own large sub-pipeline that was not
re-implemented from scratch here. Its already-verified *output*, for the current AmsterdamUMCdb
source-token universe, is packaged as a versioned reference (``data/policy_manifests/
tier0_baseline_resolution.csv``) and joined onto the freshly-extracted source vocabulary below.
Row counts, source-token identity, and everything downstream (the policy layers in ``policies/``)
are still computed fresh from raw data every run -- only this one baseline-ranking layer is a
frozen reference rather than freshly re-derived. Reproducing that ranking sub-pipeline as
genuinely dynamic code is tracked as follow-on work in the handoff doc.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metaicu.aumcdb.tokenized.vocab_pipeline.schema import IDENTITY_COLUMNS, POLICY_FIELDS

DEFAULT_BASELINE_RESOLUTION = (
    Path(__file__).resolve().parent / "data" / "policy_manifests" / "tier0_baseline_resolution.csv"
)


def load_baseline_resolution(path: Path = DEFAULT_BASELINE_RESOLUTION) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)[["source_token"] + POLICY_FIELDS]


def resolve_baseline_targets(
    source_vocab: pd.DataFrame,
    baseline_resolution: pd.DataFrame,
    allow_unresolved_source_tokens: bool = False,
) -> pd.DataFrame:
    """Join baseline policy fields onto every extracted source token.

    Every source token in ``source_vocab`` must have a baseline entry unless
    ``allow_unresolved_source_tokens`` is set -- a new source token with no rule and no reviewed
    decision must fail the build loudly by default (per the handoff doc's "Changed Dataset
    Releases" policy), not silently emit as an untyped/unmapped token.
    """

    missing = set(source_vocab["source_token"]) - set(baseline_resolution["source_token"])
    if missing and not allow_unresolved_source_tokens:
        sample = sorted(missing)[:20]
        raise ValueError(
            f"{len(missing)} source tokens have no baseline resolution or policy coverage "
            f"(sample: {sample}). Set run.allow_unresolved_source_tokens=true for an "
            "audit-only/incomplete build, or add coverage before releasing."
        )

    merged = source_vocab.merge(baseline_resolution, on="source_token", how="left")
    for field in POLICY_FIELDS:
        merged[field] = merged[field].fillna("")
    unresolved = merged["harmonized_token"].eq("") & merged["target_concept_id"].eq("")
    merged.loc[unresolved, "token_role"] = merged.loc[unresolved, "token_role"].replace("", "metadata_only")
    merged.loc[unresolved, "emit_as_model_token"] = merged.loc[unresolved, "emit_as_model_token"].replace("", "False")
    merged.loc[unresolved, "mapping_confidence"] = merged.loc[unresolved, "mapping_confidence"].replace("", "unmapped")
    return merged[IDENTITY_COLUMNS + POLICY_FIELDS]
