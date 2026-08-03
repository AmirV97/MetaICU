"""Fast structural tests for the installable MIMIC-IV hourly-grid pipeline. Mirrors
tests/integration/grid/test_grid_dataset_structure.py, adapted for two real differences: no
unit_of_analysis (M4_grid's split is unconditionally by subject_id, its shard/metadata output
unconditionally admission-grain -- see GridDatasetConfig's own docstring), and a dedicated
regression test for the Stage 0 split-by-subject fix (grid.build.split.assign_splits used to
accept a `unit` parameter that could split by admission instead, a real cross-split leakage
risk for multi-admission patients -- never triggered in practice, but removed entirely rather
than left as a footgun)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl
from omegaconf import OmegaConf


from metaicu.mimiciv.grid.build.build_workflow import GridDatasetConfig
from metaicu.mimiciv.grid.build.split import assign_splits
from metaicu.mimiciv.grid.cli.grid_build_dataset import _build_config
from metaicu.mimiciv.grid.build.manifest_parser import DEFAULT_REVIEWED_MANIFEST, parse_manifest


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
                "split": {"train_frac": 0.8, "val_frac": 0.1, "test_frac": 0.1, "seed": 7},
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
        self.assertEqual(config.features, ("map", "lact"))

    def test_grid_config_is_package_local_and_path_explicit(self) -> None:
        config = GridDatasetConfig(
            raw_data_dir=Path("/data/raw"),
            output_dir=Path("/data/grid"),
            audit_dir=Path("/data/audits"),
            manifest_path=Path("/data/manifest.md"),
        )
        self.assertEqual(config.patients_per_file, 1_000)
        self.assertTrue(config.apply_inclusion_criteria)
        self.assertTrue(config.build_raw_shards)
        self.assertEqual(config.raw_shard_rows, 5_000_000)

    def test_split_always_groups_by_subject_id_even_when_leakage_would_otherwise_occur(self) -> None:
        # subject 100 has two admissions; if splitting ever fell back to admission-level (the
        # Stage 0 bug this guards against), a 50/50-ish train/test split could easily place
        # admission 1 in train and admission 2 in test for the SAME patient -- real leakage.
        # Run many seeds: every one must keep both of subject 100's admissions in the same split.
        admissions = pl.DataFrame({
            "admissionid": [1, 2, 3, 4, 5, 6],
            "subject_id": [100, 100, 200, 300, 400, 500],
        })
        for seed in range(20):
            assignments = assign_splits(admissions, train_frac=0.5, val_frac=0.25, test_frac=0.25, seed=seed)
            by_admission = dict(zip(assignments["admissionid"].to_list(), assignments["split"].to_list()))
            self.assertEqual(
                by_admission[1], by_admission[2],
                f"seed={seed}: subject 100's two admissions landed in different splits "
                f"({by_admission[1]!r} vs {by_admission[2]!r}) -- cross-split patient leakage",
            )

    def test_split_has_no_admission_level_fallback_parameter(self) -> None:
        # assign_splits must not accept a unit-of-analysis-style parameter at all -- the Stage 0
        # fix removed it entirely rather than defaulting it to "subject", so there is no
        # remaining code path that could ever select admission-level splitting.
        import inspect
        params = list(inspect.signature(assign_splits).parameters)
        self.assertEqual(params, ["admissions", "train_frac", "val_frac", "test_frac", "seed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
