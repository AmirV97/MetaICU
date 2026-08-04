"""Unit tests for shared grid ordering, rerun safety, and post-write integrity."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

from metaicu.aumcdb.grid.build.assemble import canonical_column_order as aumc_order
from metaicu.aumcdb.grid.build.impute import (
    capture_presence_mask as aumc_capture,
    materialize_structural_zero_columns as aumc_materialize,
)
from metaicu.aumcdb.grid.build.manifest_parser import parse_manifest as parse_aumc_manifest
from metaicu.grid.integrity import audit_grid_dataset
from metaicu.mimiciv.grid.build.assemble import canonical_column_order as mimic_order
from metaicu.mimiciv.grid.build.build_workflow import _prepare_output_dir
from metaicu.mimiciv.grid.build.impute import (
    capture_presence_mask as mimic_capture,
    materialize_structural_zero_columns as mimic_materialize,
)
from metaicu.mimiciv.grid.build.manifest_parser import parse_manifest as parse_mimic_manifest


class GridOutputContractTests(unittest.TestCase):
    def test_resolved_manifests_have_the_same_feature_set_and_order(self) -> None:
        aumc, _ = parse_aumc_manifest()
        mimic, _ = parse_mimic_manifest()
        self.assertEqual(len(aumc), 120)
        self.assertEqual(list(aumc), list(mimic))

    def test_structural_zero_semantics_match_in_both_builds(self) -> None:
        matches = {
            "tri": {"reconstruction_type": "direct_numeric", "structural_zero": True},
            "hba1c": {"reconstruction_type": "direct_numeric"},
            "adh": {"reconstruction_type": "treatment_rate", "structural_zero": True},
            "adh_ind": {"reconstruction_type": "treatment_indicator", "structural_zero": True},
        }
        source = pl.DataFrame({"admissionid": [1, 1], "hour": [0, 1]})
        for materialize, capture in (
            (aumc_materialize, aumc_capture),
            (mimic_materialize, mimic_capture),
        ):
            grid = materialize(source, matches)
            grid, masks = capture(grid, matches)
            self.assertEqual(masks, ["tri__observed", "hba1c__observed"])
            self.assertEqual(grid["tri"].to_list(), [0.0, 0.0])
            self.assertEqual(grid["tri__observed"].to_list(), [0, 0])
            self.assertEqual(grid["hba1c"].to_list(), [None, None])
            self.assertEqual(grid["hba1c__observed"].to_list(), [0, 0])
            self.assertEqual(grid["adh"].to_list(), [0.0, 0.0])
            self.assertEqual(grid["adh_ind"].to_list(), [0, 0])
            self.assertNotIn("adh__observed", grid.columns)
            self.assertNotIn("adh_ind__observed", grid.columns)
            self.assertEqual(grid.schema["tri"], pl.Float64)
            self.assertEqual(grid.schema["adh"], pl.Float64)
            self.assertEqual(grid.schema["adh_ind"], pl.Int32)

    def test_both_datasets_use_the_same_manifest_order(self) -> None:
        columns = ["b", "hour", "a__observed", "admissionid", "a"]
        matches = {"a": {"reconstruction_type": "direct_numeric"}, "b": {"reconstruction_type": "direct_numeric"}}
        expected = ["admissionid", "hour", "a", "b", "a__observed"]
        for order in (aumc_order, mimic_order):
            physical, mapping = order(columns, matches, [], ["a__observed"], [])
            self.assertEqual(physical, expected)
            self.assertEqual(mapping, {"a": ["a"], "b": ["b"]})

    def test_overwrite_refuses_stale_outputs_and_preserves_unrelated_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "train").mkdir()
            (root / "train" / "0.parquet").write_bytes(b"stale")
            (root / "note.txt").write_text("keep")
            with self.assertRaises(FileExistsError):
                _prepare_output_dir(root, overwrite=False)
            _prepare_output_dir(root, overwrite=True)
            self.assertFalse((root / "train").exists())
            self.assertEqual((root / "note.txt").read_text(), "keep")

    def test_integrity_audit_accepts_a_consistent_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "grid"
            audit = Path(tmp) / "audit"
            (root / "train").mkdir(parents=True)
            frame = pl.DataFrame({
                "admissionid": [1, 1], "hour": [0, 1], "x": [0.0, 1.0], "x__observed": [0, 1]
            })
            frame.write_parquet(root / "train" / "0.parquet")
            pl.DataFrame({
                "admissionid": [1], "subject_id": [10], "split": ["train"],
                "shard_file": ["train/0.parquet"], "n_rows": [2],
            }).write_csv(root / "metadata.csv")
            (root / "feature_schema.json").write_text(json.dumps({
                "x": {"physical_columns": ["x"], "presence_mask_column": "x__observed"}
            }))
            (root / "tte_targets.json").write_text(json.dumps({"targets": ["x"], "missing": []}))
            result = audit_grid_dataset(root, audit, frame.columns, "subject_id")
            self.assertTrue(json.loads(result.read_text())["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
