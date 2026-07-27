"""Tests for baseline target resolution, the Tier-1 policy rules, manifest replay, and the
supplied-vocabulary validation contract (see docs/aumc_vocab_rebuild_handoff.md).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd


from metaicu.aumcdb.tokenized.vocab_pipeline.policies.gcs_components import apply_gcs_component_policy
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.lab_role import apply_lab_role_assignment
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.manifest_replay import apply_manifest
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.namespace import apply_namespace_canonicalization
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.zero_sentinel import apply_zero_sentinel_normalization
from metaicu.aumcdb.tokenized.vocab_pipeline.schema import COMPACT_COLUMNS, IDENTITY_COLUMNS, POLICY_FIELDS
from metaicu.aumcdb.tokenized.vocab_pipeline.target_resolution import resolve_baseline_targets
from metaicu.aumcdb.tokenized.vocab_pipeline.validation import validate_supplied_vocab


def write_csv(path: Path, rows: list[dict[str, object]], sep: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, sep=sep)


def _row(**overrides: object) -> dict[str, object]:
    base = {col: "" for col in COMPACT_COLUMNS}
    base.update(
        {
            "dataset": "AmsterdamUMCdb",
            "row_count": "10",
            "emit_as_model_token": "False",
            "token_role": "metadata_only",
            "mapping_confidence": "unmapped",
        }
    )
    base.update(overrides)
    return base


class ZeroSentinelTests(unittest.TestCase):
    def test_zero_sentinel_is_demoted_to_unmapped_metadata(self) -> None:
        vocab = pd.DataFrame(
            [
                _row(source_token="A", target_concept_id="0", harmonized_token="OMOP_CONCEPT//LOINC//0", emit_as_model_token="True", token_role="dynamic_event"),
                _row(source_token="B", target_concept_id="123", harmonized_token="OMOP_CONCEPT//LOINC//123", emit_as_model_token="True", token_role="dynamic_event/lab"),
            ]
        )
        fixed = apply_zero_sentinel_normalization(vocab)
        a = fixed.set_index("source_token").loc["A"]
        b = fixed.set_index("source_token").loc["B"]
        self.assertEqual(a["harmonized_token"], "")
        self.assertEqual(a["emit_as_model_token"], "False")
        self.assertEqual(a["token_role"], "metadata_only")
        self.assertEqual(a["mapping_confidence"], "unmapped")
        # untouched row is not affected
        self.assertEqual(b["harmonized_token"], "OMOP_CONCEPT//LOINC//123")
        self.assertEqual(b["emit_as_model_token"], "True")


class LabRoleTests(unittest.TestCase):
    def test_emitted_lab_row_gets_lab_role(self) -> None:
        vocab = pd.DataFrame(
            [_row(source_token="LAB//123//mmol/l", emit_as_model_token="True", token_role="dynamic_event")]
        )
        fixed = apply_lab_role_assignment(vocab)
        self.assertEqual(fixed.iloc[0]["token_role"], "dynamic_event/lab")

    def test_non_lab_row_mapped_to_loinc_keeps_its_role(self) -> None:
        vocab = pd.DataFrame(
            [_row(source_token="SUBJECT_FLUID_OUTPUT//9//UNKNOWN", emit_as_model_token="True", token_role="dynamic_event", target_vocabulary="LOINC")]
        )
        fixed = apply_lab_role_assignment(vocab)
        self.assertEqual(fixed.iloc[0]["token_role"], "dynamic_event")

    def test_non_emitted_lab_row_is_left_alone(self) -> None:
        vocab = pd.DataFrame(
            [_row(source_token="LAB//123//mmol/l", emit_as_model_token="False", token_role="metadata_only")]
        )
        fixed = apply_lab_role_assignment(vocab)
        self.assertEqual(fixed.iloc[0]["token_role"], "metadata_only")


class GcsComponentTests(unittest.TestCase):
    def test_accepted_component_is_emitted_as_score_component(self) -> None:
        vocab = pd.DataFrame(
            [
                _row(
                    source_token="MEASUREMENT_CATEGORICAL//6732//1",
                    source_table="listitems",
                    source_itemid="6732",
                    target_concept_id="3016335",
                    emit_as_model_token="False",
                    token_role="metadata_only",
                )
            ]
        )
        fixed = apply_gcs_component_policy(vocab)
        self.assertEqual(fixed.iloc[0]["emit_as_model_token"], "True")
        self.assertEqual(fixed.iloc[0]["token_role"], "dynamic_event/score_component")

    def test_ra_verbal_is_corrected_from_motor_to_verbal_concept(self) -> None:
        vocab = pd.DataFrame(
            [
                _row(
                    source_token="MEASUREMENT_CATEGORICAL//14482//1",
                    source_table="listitems",
                    source_itemid="14482",
                    target_concept_id="3026549",
                    harmonized_token="OMOP_CONCEPT//LOINC//3026549",
                )
            ]
        )
        fixed = apply_gcs_component_policy(vocab)
        self.assertEqual(fixed.iloc[0]["target_concept_id"], "3013144.0")
        self.assertEqual(fixed.iloc[0]["harmonized_token"], "OMOP_CONCEPT//LOINC//3013144")

    def test_non_gcs_listitem_is_untouched(self) -> None:
        vocab = pd.DataFrame(
            [_row(source_token="MEASUREMENT_CATEGORICAL//1//1", source_table="listitems", target_concept_id="999999")]
        )
        fixed = apply_gcs_component_policy(vocab)
        self.assertEqual(fixed.iloc[0]["emit_as_model_token"], "False")


class NamespaceCanonicalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.omop_vocab_dir = Path(self.tmp.name)
        write_csv(
            self.omop_vocab_dir / "CONCEPT.csv",
            [{"concept_id": "123", "vocabulary_id": "LOINC", "concept_name": "Sodium"}],
            sep="\t",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_legacy_namespace_is_rewritten_to_canonical_form(self) -> None:
        vocab = pd.DataFrame(
            [_row(source_token="A", target_concept_id="123", harmonized_token="OMOP//OMOP_CONCEPT//123", target_vocabulary="OMOP_CONCEPT")]
        )
        fixed = apply_namespace_canonicalization(vocab, self.omop_vocab_dir)
        self.assertEqual(fixed.iloc[0]["harmonized_token"], "OMOP_CONCEPT//LOINC//123")
        self.assertEqual(fixed.iloc[0]["target_vocabulary"], "LOINC")

    def test_concept_id_absent_from_export_is_left_untouched(self) -> None:
        vocab = pd.DataFrame(
            [_row(source_token="A", target_concept_id="999", harmonized_token="OMOP//OMOP_CONCEPT//999", target_vocabulary="OMOP_CONCEPT")]
        )
        fixed = apply_namespace_canonicalization(vocab, self.omop_vocab_dir)
        self.assertEqual(fixed.iloc[0]["harmonized_token"], "OMOP//OMOP_CONCEPT//999")


class ManifestReplayTests(unittest.TestCase):
    def test_manifest_overwrites_only_listed_source_tokens(self) -> None:
        state = pd.DataFrame(
            [_row(source_token="A", harmonized_token="OLD"), _row(source_token="B", harmonized_token="UNTOUCHED")]
        )
        manifest_row = {"source_token": "A", "policy_layer": "test"}
        manifest_row.update({field: ("NEW" if field == "harmonized_token" else "") for field in POLICY_FIELDS})
        manifest = pd.DataFrame([manifest_row])
        replayed = apply_manifest(state, manifest).set_index("source_token")
        self.assertEqual(replayed.loc["A", "harmonized_token"], "NEW")
        self.assertEqual(replayed.loc["B", "harmonized_token"], "UNTOUCHED")


class BaselineResolutionTests(unittest.TestCase):
    def test_covered_source_tokens_get_baseline_fields(self) -> None:
        source_vocab = pd.DataFrame([_row(source_token="A")])[IDENTITY_COLUMNS]
        baseline_row = {"source_token": "A"}
        baseline_row.update({field: ("X" if field == "harmonized_token" else "") for field in POLICY_FIELDS})
        baseline = pd.DataFrame([baseline_row])
        resolved = resolve_baseline_targets(source_vocab, baseline)
        self.assertEqual(resolved.set_index("source_token").loc["A", "harmonized_token"], "X")

    def test_uncovered_source_token_raises_by_default(self) -> None:
        source_vocab = pd.DataFrame([_row(source_token="NEW_TOKEN")])[IDENTITY_COLUMNS]
        baseline = pd.DataFrame(columns=["source_token"] + POLICY_FIELDS)
        with self.assertRaises(ValueError):
            resolve_baseline_targets(source_vocab, baseline)

    def test_uncovered_source_token_allowed_with_explicit_flag(self) -> None:
        source_vocab = pd.DataFrame([_row(source_token="NEW_TOKEN")])[IDENTITY_COLUMNS]
        baseline = pd.DataFrame(columns=["source_token"] + POLICY_FIELDS)
        resolved = resolve_baseline_targets(source_vocab, baseline, allow_unresolved_source_tokens=True)
        row = resolved.set_index("source_token").loc["NEW_TOKEN"]
        self.assertEqual(row["emit_as_model_token"], "False")
        self.assertEqual(row["mapping_confidence"], "unmapped")


class ValidationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.omop_vocab_dir = Path(self.tmp.name)
        write_csv(
            self.omop_vocab_dir / "CONCEPT.csv",
            [{"concept_id": "123", "vocabulary_id": "LOINC", "concept_name": "Sodium"}],
            sep="\t",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _valid_vocab(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                _row(
                    source_token="LAB//1//mmol/l",
                    emit_as_model_token="True",
                    token_role="dynamic_event/lab",
                    harmonized_token="OMOP_CONCEPT//LOINC//123",
                    target_concept_id="123",
                    target_vocabulary="LOINC",
                ),
                _row(source_token="Metoprolol_dose", source_label="Metoprolol", emit_as_model_token="True", token_role="dynamic_event", harmonized_token="MED//X"),
            ]
        )

    def test_valid_vocab_passes(self) -> None:
        vocab = self._valid_vocab()
        source_vocab = vocab[IDENTITY_COLUMNS]
        report = validate_supplied_vocab(source_vocab, vocab, self.omop_vocab_dir)
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["emitted_source_tokens"], 2)

    def test_missing_metoprolol_row_fails_strict_but_passes_non_strict(self) -> None:
        vocab = self._valid_vocab()
        vocab = vocab[vocab["source_label"] != "Metoprolol"].reset_index(drop=True)
        source_vocab = vocab[IDENTITY_COLUMNS]
        with self.assertRaises(AssertionError):
            validate_supplied_vocab(source_vocab, vocab, self.omop_vocab_dir, strict=True)
        report = validate_supplied_vocab(source_vocab, vocab, self.omop_vocab_dir, strict=False)
        self.assertEqual(report["violations"], [])

    def test_emitted_zero_sentinel_is_rejected(self) -> None:
        vocab = self._valid_vocab()
        vocab.loc[vocab["source_token"] == "LAB//1//mmol/l", "target_concept_id"] = "0"
        source_vocab = vocab[IDENTITY_COLUMNS]
        with self.assertRaises(AssertionError):
            validate_supplied_vocab(source_vocab, vocab, self.omop_vocab_dir)

    def test_emitted_legacy_namespace_is_rejected(self) -> None:
        vocab = self._valid_vocab()
        vocab.loc[vocab["source_token"] == "LAB//1//mmol/l", "harmonized_token"] = "OMOP//OMOP_CONCEPT//123"
        source_vocab = vocab[IDENTITY_COLUMNS]
        with self.assertRaises(AssertionError):
            validate_supplied_vocab(source_vocab, vocab, self.omop_vocab_dir)

    def test_row_count_change_is_rejected(self) -> None:
        vocab = self._valid_vocab()
        source_vocab = vocab[IDENTITY_COLUMNS].copy()
        vocab.loc[vocab.index[0], "row_count"] = "999999"
        with self.assertRaises(AssertionError):
            validate_supplied_vocab(source_vocab, vocab, self.omop_vocab_dir)


if __name__ == "__main__":
    unittest.main(verbosity=2)
