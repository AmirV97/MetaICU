"""Packaging contract for data required by installed MetaICU commands."""

from __future__ import annotations

import tomllib
import unittest
from importlib.resources import files

from tests._paths import PROJECT_ROOT

EXPECTED_POLICY_FILES = {
    "generation_summary.json",
    "tier0_baseline_resolution.csv",
    "v4_curated_unmapped.csv",
    "v5_keep_drop_review.csv",
    "v6_semantic_contamination.csv",
    "v7_targeted_refinement.csv",
    "v8_device_outcome_refinement.csv",
    "v9_admission_respiratory_cleanup.csv",
    "v10_medication_atc.csv",
    "v11_listitem_values.csv",
    "v13_lab_consolidation.csv",
}


class PackageAssetTests(unittest.TestCase):
    def test_policy_manifests_are_declared_as_package_data(self) -> None:
        config = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
        package_data = config["tool"]["setuptools"]["package-data"]
        patterns = package_data["metaicu.aumcdb.tokenized.vocab_pipeline"]
        self.assertIn("data/policy_manifests/*.csv", patterns)
        self.assertIn("data/policy_manifests/*.json", patterns)

    def test_every_required_policy_manifest_is_present(self) -> None:
        root = files("metaicu.aumcdb.tokenized.vocab_pipeline").joinpath(
            "data/policy_manifests"
        )
        present = {entry.name for entry in root.iterdir() if entry.is_file()}
        self.assertEqual(present, EXPECTED_POLICY_FILES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
