"""Generic replay of a versioned policy manifest: absolute per-source_token field overwrites.

A manifest row is a full assignment of every ``POLICY_FIELDS`` value for one source_token, not a
relative patch -- this makes replay robust to small differences in whatever state feeds into it,
since each manifest layer fully re-specifies the fields it owns rather than diffing against an
assumed prior value. Manifests never touch source-identity columns or ``row_count``.

Each manifest here is a versioned reference to a historical, one-off clinical-curation decision
(see docs/aumc_vocab_rebuild_handoff.md, "Policy Manifest Contract": "Reviewed exceptions should
remain data") that was captured by diffing the real historical artifact lineage rather than
re-derived from raw evidence. See docs/aumc_vocab_rebuild_handoff.md for how these were produced
and verified.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metaicu.aumcdb.tokenized.vocab_pipeline.schema import POLICY_FIELDS


def load_manifest(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def apply_manifest(state: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    """Overwrite POLICY_FIELDS for every source_token present in both the manifest and state.

    A manifest source_token absent from ``state`` (e.g. a smaller/bounded raw dataset, or a test
    fixture) is simply not applicable this run -- not an error; the manifest is a reference for
    the current full AmsterdamUMCdb release, not a required-coverage contract for every subset.
    """

    indexed_manifest = manifest.set_index("source_token")[POLICY_FIELDS]
    result = state.set_index("source_token")
    applicable = indexed_manifest.index.intersection(result.index)
    result.loc[applicable, POLICY_FIELDS] = indexed_manifest.loc[applicable]
    return result.reset_index()


def apply_manifest_layers(state: pd.DataFrame, manifest_dir: Path, layer_names: list[str]) -> pd.DataFrame:
    for layer_name in layer_names:
        manifest = load_manifest(manifest_dir / f"{layer_name}.csv")
        state = apply_manifest(state, manifest)
    return state
