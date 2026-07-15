"""Fast structural tests for the installable AUMC hourly-grid pipeline."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from omegaconf import OmegaConf


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.grid.build_workflow import GridDatasetConfig
from metaicu.aumcdb.grid.cli.grid_build_dataset import _build_config
from metaicu.aumcdb.grid.manifest_parser import DEFAULT_REVIEWED_MANIFEST, parse_manifest


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
        self.assertTrue(config.apply_inclusion_criteria)


if __name__ == "__main__":
    unittest.main(verbosity=2)
