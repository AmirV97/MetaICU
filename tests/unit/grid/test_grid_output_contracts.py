"""Unit tests for shared grid ordering, rerun safety, and post-write integrity."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

from metaicu.aumcdb.grid.build.assemble import canonical_column_order as aumc_order
from metaicu.grid.integrity import audit_grid_dataset
from metaicu.mimiciv.grid.build.assemble import canonical_column_order as mimic_order
from metaicu.mimiciv.grid.build.build_workflow import _prepare_output_dir


class GridOutputContractTests(unittest.TestCase):
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
