"""Unit tests for metaicu.grid.joint_assemble's pure helpers -- ID namespacing, cross-cohort
collision counting, uniqueness assertion, and TTE-target-list merging for a joint multi-dataset
grid build. write_joint_outputs itself (disk I/O against real per-cohort outputs) is covered by
tests/integration/grid/test_joint_assemble_integration.py instead."""

from __future__ import annotations

import unittest

import polars as pl

from metaicu.grid.joint_assemble import (
    assert_globally_unique,
    count_cross_cohort_id_collisions,
    merge_tte_targets,
    namespace_ids,
)


class NamespaceIdsTests(unittest.TestCase):
    def test_prefixes_and_casts_present_id_columns(self) -> None:
        df = pl.DataFrame({"admissionid": [1, 2], "subject_id": [10, 20], "hour": [0, 1]})
        namespaced = namespace_ids(df, "aumcdb")
        self.assertEqual(namespaced["admissionid"].to_list(), ["aumcdb_1", "aumcdb_2"])
        self.assertEqual(namespaced["subject_id"].to_list(), ["aumcdb_10", "aumcdb_20"])
        self.assertEqual(namespaced["hour"].to_list(), [0, 1])
        self.assertEqual(namespaced.schema["admissionid"], pl.Utf8)

    def test_only_namespaces_columns_that_are_present(self) -> None:
        df = pl.DataFrame({"admissionid": [1, 2], "hour": [0, 1]})
        namespaced = namespace_ids(df, "mimic_iv")
        self.assertEqual(set(namespaced.columns), {"admissionid", "hour"})
        self.assertEqual(namespaced["admissionid"].to_list(), ["mimic_iv_1", "mimic_iv_2"])

    def test_does_not_mutate_input(self) -> None:
        df = pl.DataFrame({"admissionid": [1]})
        namespace_ids(df, "aumcdb")
        self.assertEqual(df["admissionid"].to_list(), [1])
        self.assertEqual(df.schema["admissionid"], pl.Int64)


class CountCrossCohortIdCollisionsTests(unittest.TestCase):
    def test_no_overlap_is_zero(self) -> None:
        self.assertEqual(count_cross_cohort_id_collisions({"a": {1, 2}, "b": {3, 4}}), 0)

    def test_counts_shared_values(self) -> None:
        self.assertEqual(count_cross_cohort_id_collisions({"a": {1, 2, 3}, "b": {2, 3, 4}}), 2)

    def test_single_cohort_is_zero(self) -> None:
        self.assertEqual(count_cross_cohort_id_collisions({"a": {1, 2, 3}}), 0)


class AssertGloballyUniqueTests(unittest.TestCase):
    def test_no_duplicates_does_not_raise(self) -> None:
        df = pl.DataFrame({"admissionid": ["aumcdb_1", "mimic_iv_1"]})
        assert_globally_unique(df, "admissionid")  # should not raise

    def test_duplicate_raises(self) -> None:
        df = pl.DataFrame({"admissionid": ["aumcdb_1", "aumcdb_1", "mimic_iv_1"]})
        with self.assertRaises(ValueError):
            assert_globally_unique(df, "admissionid")


class MergeTteTargetsTests(unittest.TestCase):
    def test_union_targets_intersect_missing_merge_derived(self) -> None:
        # Mirrors the real AUMC (K34) vs MIMIC (K34 + bili_dir) asymmetry -- bili_dir must survive
        # into the joint target list even though only one cohort has it.
        aumc = {
            "targets": ["lact", "map"],
            "missing": ["tri"],
            "derived": {"pf_ratio": ["po2", "fio2"]},
        }
        mimic = {
            "targets": ["lact", "map", "bili_dir"],
            "missing": [],
            "derived": {"pf_ratio": ["po2", "fio2"], "urine_rate_per_weight": ["urine_rate", "weight"]},
        }
        merged = merge_tte_targets({"aumcdb": aumc, "mimic_iv": mimic})
        self.assertEqual(merged["targets"], ["bili_dir", "lact", "map"])
        # "tri" is missing for aumcdb but not declared missing for mimic_iv -- only genuinely
        # globally-missing tags (missing in EVERY cohort) belong in the joint "missing" list.
        self.assertEqual(merged["missing"], [])
        self.assertEqual(merged["derived"], {
            "pf_ratio": ["po2", "fio2"],
            "urine_rate_per_weight": ["urine_rate", "weight"],
        })

    def test_tag_missing_in_every_cohort_stays_missing(self) -> None:
        aumc = {"targets": [], "missing": ["tri"], "derived": {}}
        mimic = {"targets": [], "missing": ["tri"], "derived": {}}
        merged = merge_tte_targets({"aumcdb": aumc, "mimic_iv": mimic})
        self.assertEqual(merged["missing"], ["tri"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
