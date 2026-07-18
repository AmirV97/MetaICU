"""Fast structural tests for the installable AUMC hourly-grid pipeline."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import polars as pl
from omegaconf import OmegaConf


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.grid.build.build_workflow import (
    GridDatasetConfig,
    _write_metadata_by_subject,
    _write_shards,
)
from metaicu.aumcdb.grid.cli.grid_build_dataset import _build_config
from metaicu.aumcdb.grid.build.manifest_parser import DEFAULT_REVIEWED_MANIFEST, parse_manifest


class GridDatasetStructureTests(unittest.TestCase):
    def test_packaged_reviewed_manifest_parses_without_workspace_paths(self) -> None:
        self.assertTrue(DEFAULT_REVIEWED_MANIFEST.exists())
        matches, report = parse_manifest()
        self.assertGreater(len(matches), 0)
        self.assertIn("map", matches)
        self.assertGreater(report["n_total_blocks"], len(matches))

    def test_hydra_config_resolves_parent_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent_dir = Path(tmp) / "workspace"
            config = _build_config(OmegaConf.create({
                "paths": {
                    "parent_dir": str(parent_dir),
                    "raw_data_dir": None,
                    "raw_shards_dir": None,
                    "output_dir": None,
                    "audit_dir": None,
                    "manifest_path": None,
                    "admission_ids_file": None,
                },
                "split": {"unit_of_analysis": "subject", "train_frac": 0.8, "val_frac": 0.1, "test_frac": 0.1, "seed": 7},
                "run": {
                    "build_raw_shards": True,
                    "rebuild_raw_shards": False,
                    "raw_shard_rows": 1000,
                    "sample_size": 20,
                    "patients_per_file": 10,
                    "seed": 3,
                    "features": ["map", "lact"],
                    "reconstruction_types": ["direct_numeric"],
                    "apply_inclusion_criteria": True,
                    "scale": True,
                    "impute": True,
                    "one_hot": True,
                },
            }))
        self.assertEqual(config.raw_data_dir, parent_dir / "data/raw")
        self.assertEqual(config.raw_shards_dir, parent_dir / "data/raw_shards")
        self.assertEqual(config.output_dir, parent_dir / "data/grid")
        self.assertEqual(config.audit_dir, parent_dir / "audits/grid_dataset")
        self.assertEqual(config.manifest_path, DEFAULT_REVIEWED_MANIFEST)
        self.assertEqual(config.unit_of_analysis, "subject")
        self.assertEqual(config.features, ("map", "lact"))

    def test_grid_config_is_package_local_and_path_explicit(self) -> None:
        config = GridDatasetConfig(
            raw_data_dir=Path("/data/raw"),
            output_dir=Path("/data/grid"),
            audit_dir=Path("/data/audits"),
        )
        self.assertEqual(config.patients_per_file, 1_000)
        self.assertEqual(config.unit_of_analysis, "admission")
        self.assertTrue(config.apply_inclusion_criteria)

    def test_subject_level_shards_concatenate_admissions_in_chronological_order(self) -> None:
        # Patient 100 has two admissions (out of chronological order in the input),
        # patient 200 has one. Demographics differ between patient 100's two admissions.
        admissions = pl.DataFrame({
            "admissionid": [2, 1, 3],
            "patientid": [100, 100, 200],
            "admittedat": [100, 0, 0],
            "true_los_hours": [3.0, 5.0, 10.0],
            "dateofdeath": [12345.0, None, None],
            "age": [55.5, 44.5, 64.5],
            "weight": [70.0, 60.0, 80.0],
            "height": [170.0, 160.0, 180.0],
            "sex": ["Man", "Vrouw", "Man"],
            "adm": ["emergency", "elective", "elective"],
            "split": ["train", "train", "val"],
        })
        grid = pl.DataFrame({
            "admissionid": [1, 1, 2, 3],
            "hour": [0, 1, 0, 0],
            "val": [10.0, 11.0, 20.0, 30.0],
        })

        with tempfile.TemporaryDirectory() as tmp:
            split_dir = Path(tmp)
            shard_info = _write_shards(
                grid, admissions, [1, 2, 3], split_dir, units_per_file=10, unit_of_analysis="subject"
            )
            shard = pl.read_parquet(split_dir / "0.parquet")
            metadata_path = split_dir / "metadata.csv"
            _write_metadata_by_subject(admissions, shard_info, metadata_path)
            metadata = pl.read_csv(metadata_path)

        # both patients land in one shard (units_per_file=10); admission 1 (earlier)
        # precedes admission 2 (later) for patient 100.
        patient_100_rows = shard.filter(pl.col("admissionid").is_in([1, 2]))
        self.assertEqual(patient_100_rows["admissionid"].to_list(), [1, 1, 2])

        row_100 = metadata.filter(pl.col("patientid") == 100).row(0, named=True)
        self.assertEqual(row_100["admission_ids"], "1,2")
        self.assertEqual(row_100["n_admissions"], 2)
        self.assertEqual(row_100["outcome"], "died")  # from admission 2, the later one
        self.assertEqual(row_100["age"], 44.5)  # from admission 1, the earlier one
        self.assertEqual(row_100["weight"], 60.0)
        self.assertAlmostEqual(row_100["los_hours"], 8.0)
        self.assertEqual(row_100["n_rows"], 3)

        row_200 = metadata.filter(pl.col("patientid") == 200).row(0, named=True)
        self.assertEqual(row_200["admission_ids"], "3")
        self.assertEqual(row_200["n_admissions"], 1)
        self.assertEqual(row_200["outcome"], "alive")


if __name__ == "__main__":
    unittest.main(verbosity=2)
