"""Proves the "data-content invariant schema" contract (metaicu.grid.schema_union) against the
real, packaged AUMCdb/MIMIC-IV manifests -- not a synthetic fixture. feature_schema.json is a
pure function of a cohort's own `matches` (+ derived targets and presence-mask flags, both
themselves derived from `matches`) plus categorical vocab; if `matches`/vocab are already union-
stable for both cohorts, every solo run's feature_schema.json is *guaranteed* identical to the
padded joint run's, without needing three separate full-pipeline builds to check file bytes.

Operationalizes the Phase 1 design note: "today's 120/120 tag parity ... write the schema-
identity test to prove it, not assume it."
"""

from __future__ import annotations

import unittest

from metaicu.aumcdb.grid.build.encode import get_categorical_vocab as aumcdb_categorical_vocab
from metaicu.aumcdb.grid.build.manifest_parser import parse_manifest as parse_aumcdb_manifest
from metaicu.aumcdb.grid.build.scale import LOG_TRANSFORM_TAGS as AUMCDB_LOG_TRANSFORM_TAGS
from metaicu.mimiciv.grid.build.encode import get_categorical_vocab as mimiciv_categorical_vocab
from metaicu.mimiciv.grid.build.manifest_parser import parse_manifest as parse_mimiciv_manifest
from metaicu.mimiciv.grid.build.scale import LOG_TRANSFORM_TAGS as MIMICIV_LOG_TRANSFORM_TAGS
from metaicu.grid.schema_union import (
    compute_union_categorical_vocab,
    compute_union_matches,
    pad_matches_for_cohort,
)


class RealManifestSchemaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aumc_matches, _ = parse_aumcdb_manifest()
        cls.mimic_matches, _ = parse_mimiciv_manifest()
        cls.union = compute_union_matches({"aumcdb": cls.aumc_matches, "mimic_iv": cls.mimic_matches})

    def test_union_matches_without_conflict(self) -> None:
        # compute_union_matches hard-raises on any reconstruction_type/target_unit disagreement --
        # setUpClass already ran it; this just documents the union covers every real tag.
        self.assertEqual(set(self.union), set(self.aumc_matches) | set(self.mimic_matches))

    def test_padding_is_a_no_op_for_both_cohorts(self) -> None:
        self.assertEqual(pad_matches_for_cohort(self.aumc_matches, self.union), self.aumc_matches)
        self.assertEqual(pad_matches_for_cohort(self.mimic_matches, self.union), self.mimic_matches)

    def test_categorical_vocab_union_is_a_no_op_for_both_cohorts(self) -> None:
        aumc_vocab = aumcdb_categorical_vocab(self.aumc_matches)
        mimic_vocab = mimiciv_categorical_vocab(self.mimic_matches)
        union_vocab = compute_union_categorical_vocab({"aumcdb": aumc_vocab, "mimic_iv": mimic_vocab})
        for tag, categories in aumc_vocab.items():
            self.assertEqual(categories, union_vocab[tag], f"{tag}: AUMCdb vocab differs from union")
        for tag, categories in mimic_vocab.items():
            self.assertEqual(categories, union_vocab[tag], f"{tag}: MIMIC-IV vocab differs from union")

    def test_log_transform_choice_agrees_wherever_both_pipelines_declare_a_tag(self) -> None:
        # metaicu.grid.cli.grid_build_joint_dataset._compute_pooled_scalers imports
        # LOG_TRANSFORM_TAGS from ONE pipeline only (aumcdb) and uses it for every pooled tag --
        # a tag declared with a different log_kind (or undeclared, i.e. raw) on the other side
        # would silently pool that tag in the wrong space. This caught exactly that for "pt"
        # (real/log1p on MIMIC, structural_zero/absent from AUMC's dict) before this test existed.
        shared = set(AUMCDB_LOG_TRANSFORM_TAGS) & set(MIMICIV_LOG_TRANSFORM_TAGS)
        self.assertGreater(len(shared), 0)
        for tag in shared:
            self.assertEqual(
                AUMCDB_LOG_TRANSFORM_TAGS[tag], MIMICIV_LOG_TRANSFORM_TAGS[tag],
                f"{tag}: log_kind disagrees between aumcdb ({AUMCDB_LOG_TRANSFORM_TAGS[tag]!r}) "
                f"and mimic_iv ({MIMICIV_LOG_TRANSFORM_TAGS[tag]!r})",
            )
        for tag in set(self.union) & (set(AUMCDB_LOG_TRANSFORM_TAGS) | set(MIMICIV_LOG_TRANSFORM_TAGS)):
            if self.union[tag]["reconstruction_type"] not in ("direct_numeric", "derived_output_rate", "treatment_rate"):
                continue
            self.assertEqual(
                AUMCDB_LOG_TRANSFORM_TAGS.get(tag), MIMICIV_LOG_TRANSFORM_TAGS.get(tag),
                f"{tag}: poolable tag must declare the same log_kind on both sides (or neither) "
                f"since the joint dispatcher's pooled-scaler code only ever consults aumcdb's dict",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
