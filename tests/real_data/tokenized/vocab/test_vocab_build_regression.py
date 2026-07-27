"""Regression test: run build-amsterdam-vocab against a real AmsterdamUMCdb release and diff the
result against the packaged reference vocabulary.

Unlike the other vocab_pipeline tests, this one exercises the real raw data rather than tiny
synthetic fixtures -- it is what actually validates the resolver + policy engine against
production data, not just wiring. Raw AmsterdamUMCdb data is large (tens of GB) and not part of
this repository, so the test is skipped unless the environment points at a real release:

    METAICU_AUMC_REGRESSION_RAW_DIR       raw AmsterdamUMCdb CSV directory
    METAICU_AUMC_REGRESSION_EXTERNAL_ROOT external evidence root (AMSTEL/AmsterdamUMCdb/BlendedICU)
    METAICU_AUMC_REGRESSION_OMOP_VOCAB_DIR local Athena/OMOP vocabulary export

Run on an HPC batch job (source-vocabulary extraction scans the full raw tables), e.g.:

    METAICU_AUMC_REGRESSION_RAW_DIR=/path/to/raw \
    METAICU_AUMC_REGRESSION_EXTERNAL_ROOT=/path/to/externals \
    METAICU_AUMC_REGRESSION_OMOP_VOCAB_DIR=/path/to/omop_vocab \
    python -m unittest tests.real_data.tokenized.vocab.test_vocab_build_regression -v

`run.allow_unresolved_source_tokens=true` is used because the current release has a known,
documented residual gap against the packaged reference -- see docs/aumc_vocab_rebuild_handoff.md,
"Open issue". The bounds below are that gap's baseline, not an exact-match requirement: they
should only need updating if the gap is deliberately fixed (should shrink) or the raw release
changes in a way that needs review (should not silently grow).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tests._paths import PROJECT_ROOT as PIPELINE_ROOT


from metaicu.aumcdb.tokenized.vocab_pipeline.build_workflow import BuildVocabConfig, write_build_vocab_outputs
from metaicu.aumcdb.tokenized.vocab_pipeline.schema import POLICY_FIELDS

REFERENCE_VOCAB = PIPELINE_ROOT / "mappings/aumc_supplied_vocab.csv"

RAW_DIR_ENV = "METAICU_AUMC_REGRESSION_RAW_DIR"
EXTERNAL_ROOT_ENV = "METAICU_AUMC_REGRESSION_EXTERNAL_ROOT"
OMOP_VOCAB_DIR_ENV = "METAICU_AUMC_REGRESSION_OMOP_VOCAB_DIR"

# Baseline for the documented, known residual gap (see module docstring). Upper bounds, not
# exact counts: a real fix should shrink these; an unexplained increase indicates a regression.
MAX_EXTRA_IN_BUILD = 350
MAX_MISSING_IN_BUILD = 300


def _env_dir(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    path = Path(value)
    return path if path.is_dir() else None


def _missing_env_reason() -> str | None:
    missing = [name for name in (RAW_DIR_ENV, EXTERNAL_ROOT_ENV, OMOP_VOCAB_DIR_ENV) if _env_dir(name) is None]
    if missing:
        return f"Set {', '.join(missing)} to real AmsterdamUMCdb paths to run this regression test"
    return None


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.set_index("source_token")[POLICY_FIELDS].copy()
    frame["target_concept_id"] = frame["target_concept_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    frame["emit_as_model_token"] = frame["emit_as_model_token"].astype(str)
    return frame


@unittest.skipIf(_missing_env_reason(), _missing_env_reason() or "")
class VocabBuildRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        workspace = Path(cls.tmp.name)
        config = BuildVocabConfig(
            raw_data_dir=_env_dir(RAW_DIR_ENV),
            external_root=_env_dir(EXTERNAL_ROOT_ENV),
            omop_vocab_dir=_env_dir(OMOP_VOCAB_DIR_ENV),
            audit_dir=workspace / "audits",
            supplied_vocab=REFERENCE_VOCAB,
            output_vocab=workspace / "vocab/aumc_supplied_vocab.csv",
            mode="rebuild",
            allow_unresolved_source_tokens=True,
        )
        cls.outputs = write_build_vocab_outputs(config)
        cls.built = pd.read_csv(cls.outputs["output_vocab"], dtype=str, keep_default_na=False)
        cls.reference = pd.read_csv(REFERENCE_VOCAB, dtype=str, keep_default_na=False)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_build_passes_its_own_validation_contract(self) -> None:
        import json

        report = json.loads(self.outputs["final_vocab_validation"].read_text())
        self.assertEqual(report["violations"], [])

    def test_common_source_tokens_match_reference_exactly(self) -> None:
        built = _normalize(self.built)
        reference = _normalize(self.reference)
        common = built.index.intersection(reference.index)
        self.assertGreater(len(common), 0)

        mismatched = (built.loc[common] != reference.loc[common]).any(axis=1)
        if mismatched.any():
            sample = built.index[mismatched][:10].tolist()
            self.fail(f"{int(mismatched.sum())} source tokens differ from the reference vocab, e.g. {sample}")

    def test_residual_gap_against_reference_has_not_grown(self) -> None:
        built = _normalize(self.built)
        reference = _normalize(self.reference)
        extra_in_build = built.index.difference(reference.index)
        missing_in_build = reference.index.difference(built.index)

        self.assertLessEqual(
            len(extra_in_build), MAX_EXTRA_IN_BUILD,
            f"{len(extra_in_build)} source tokens in the fresh build are absent from the reference "
            f"(baseline: {MAX_EXTRA_IN_BUILD}) -- see docs/aumc_vocab_rebuild_handoff.md 'Open issue'",
        )
        self.assertLessEqual(
            len(missing_in_build), MAX_MISSING_IN_BUILD,
            f"{len(missing_in_build)} reference source tokens are absent from the fresh build "
            f"(baseline: {MAX_MISSING_IN_BUILD}) -- see docs/aumc_vocab_rebuild_handoff.md 'Open issue'",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
