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


EXPECTED_MIMICIV_GRID_DATA_FILES = {
    "mimic_grid_feature_manifest_review.md",
    "icarefm_table_s3_features.csv",
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

    def test_mimiciv_grid_data_is_declared_as_package_data(self) -> None:
        config = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
        package_data = config["tool"]["setuptools"]["package-data"]
        patterns = package_data["metaicu.mimiciv.grid"]
        self.assertIn("data/*.md", patterns)
        self.assertIn("data/*.csv", patterns)
        self.assertIn("configs/*.yaml", patterns)

    def test_every_required_mimiciv_grid_data_file_is_present(self) -> None:
        root = files("metaicu.mimiciv.grid").joinpath("data")
        present = {entry.name for entry in root.iterdir() if entry.is_file()}
        self.assertEqual(present, EXPECTED_MIMICIV_GRID_DATA_FILES)

    def test_dispatcher_dataset_configs_are_declared_as_package_data(self) -> None:
        config = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
        package_data = config["tool"]["setuptools"]["package-data"]
        patterns = package_data["metaicu.grid"]
        self.assertIn("configs/dataset/*.yaml", patterns)

    def test_dispatcher_has_a_dataset_config_for_every_registered_dataset(self) -> None:
        from metaicu.grid.cli.grid_build_dataset import _DATASETS

        root = files("metaicu.grid").joinpath("configs/dataset")
        present = {entry.name for entry in root.iterdir() if entry.is_file()}
        expected = {f"{name}.yaml" for name in _DATASETS}
        self.assertEqual(present, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
