"""Integration test for metaicu.grid.joint_assemble.write_joint_outputs against two hand-built
per-cohort output directories, shaped exactly like a real write_grid_dataset_outputs() run
(metadata.csv/feature_schema.json/tte_targets.json/train-val-test parquet shards) -- deliberately
reusing admissionid/subject_id 10 and 1 in BOTH cohorts (a real collision scenario, not contrived
padding) to exercise the namespacing + uniqueness-assertion path end to end, then runs the shared
audit_grid_dataset check against the actual joint output."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

from metaicu.grid.joint_assemble import write_joint_outputs

_SCHEMA = {
    "hr": {
        "reconstruction_type": "direct_numeric",
        "target_unit": "bpm",
        "presence_mask_column": "hr__observed",
        "physical_columns": ["hr"],
    }
}


def _write_cohort_output(output_dir: Path, admissions: list[dict], grid_rows: list[dict], tte_targets: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_split: dict[str, list[int]] = {}
    for row in admissions:
        by_split.setdefault(row["split"], []).append(row["admissionid"])

    grid = pl.DataFrame(grid_rows, schema={"admissionid": pl.Int64, "hour": pl.Int64,
                                           "hr": pl.Float64, "hr__observed": pl.Int8})
    for split, admission_ids in by_split.items():
        split_dir = output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        shard = grid.filter(pl.col("admissionid").is_in(admission_ids)).sort(["admissionid", "hour"])
        shard.write_parquet(split_dir / "0.parquet")

    metadata = pl.DataFrame([
        {
            "admissionid": row["admissionid"],
            "subject_id": row["subject_id"],
            "split": row["split"],
            "shard_file": f"{row['split']}/0.parquet",
            "n_rows": sum(1 for r in grid_rows if r["admissionid"] == row["admissionid"]),
            "los_hours": 2.0,
            "outcome": "alive",
        }
        for row in admissions
    ])
    metadata.write_csv(output_dir / "metadata.csv")
    (output_dir / "feature_schema.json").write_text(json.dumps(_SCHEMA, indent=2, sort_keys=True))
    (output_dir / "tte_targets.json").write_text(json.dumps(tte_targets, indent=2))


class WriteJointOutputsIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)

        # Deliberate raw-ID collisions: admissionid=10 and subject_id=1 both appear in AUMCdb AND
        # MIMIC-IV's own native ID spaces (the two cohorts number admissions/patients
        # independently -- a shared raw value is coincidence, not a real merge).
        aumc_dir = root / "aumcdb_output"
        _write_cohort_output(
            aumc_dir,
            admissions=[
                {"admissionid": 10, "subject_id": 1, "split": "train"},
                {"admissionid": 20, "subject_id": 2, "split": "val"},
            ],
            grid_rows=[
                {"admissionid": 10, "hour": 0, "hr": 80.0, "hr__observed": 1},
                {"admissionid": 10, "hour": 1, "hr": 82.0, "hr__observed": 1},
                {"admissionid": 20, "hour": 0, "hr": 90.0, "hr__observed": 1},
            ],
            tte_targets={"targets": [], "missing": ["hr"], "derived": {}},
        )

        mimic_dir = root / "mimic_iv_output"
        _write_cohort_output(
            mimic_dir,
            admissions=[
                {"admissionid": 10, "subject_id": 1, "split": "train"},
                {"admissionid": 30, "subject_id": 3, "split": "test"},
            ],
            grid_rows=[
                {"admissionid": 10, "hour": 0, "hr": 75.0, "hr__observed": 1},
                {"admissionid": 30, "hour": 0, "hr": 95.0, "hr__observed": 1},
                {"admissionid": 30, "hour": 1, "hr": 96.0, "hr__observed": 1},
            ],
            tte_targets={"targets": ["hr"], "missing": [], "derived": {}},
        )

        self.joint_output_dir = root / "joint" / "output"
        self.joint_audit_dir = root / "joint" / "audit"
        self.outputs = write_joint_outputs(
            cohort_output_dirs={"aumcdb": aumc_dir, "mimic_iv": mimic_dir},
            joint_output_dir=self.joint_output_dir,
            joint_audit_dir=self.joint_audit_dir,
            patients_per_file=1000,
            weights={"aumcdb": 0.4, "mimic_iv": 0.6},
            n_train_admissions_by_cohort={"aumcdb": 1, "mimic_iv": 1},
        )

    def test_namespaced_ids_are_globally_unique_despite_raw_collisions(self) -> None:
        metadata = pl.read_csv(self.outputs["metadata"])
        self.assertEqual(
            sorted(metadata["admissionid"].to_list()),
            ["aumcdb_10", "aumcdb_20", "mimic_iv_10", "mimic_iv_30"],
        )
        self.assertEqual(metadata["admissionid"].n_unique(), metadata.height)
        self.assertEqual(metadata["subject_id"].n_unique(), metadata.height)

    def test_source_column_records_origin_cohort(self) -> None:
        metadata = pl.read_csv(self.outputs["metadata"])
        source_by_admission = dict(zip(metadata["admissionid"].to_list(), metadata["source"].to_list()))
        self.assertEqual(source_by_admission["aumcdb_10"], "aumcdb")
        self.assertEqual(source_by_admission["mimic_iv_30"], "mimic_iv")

    def test_splits_concatenate_across_cohorts(self) -> None:
        metadata = pl.read_csv(self.outputs["metadata"])
        by_split = metadata.group_by("split").len().sort("split")
        counts = dict(zip(by_split["split"].to_list(), by_split["len"].to_list()))
        self.assertEqual(counts, {"test": 1, "train": 2, "val": 1})
        self.assertTrue((self.joint_output_dir / "train" / "0.parquet").exists())

    def test_summary_reports_pre_namespacing_collisions(self) -> None:
        summary = json.loads(self.outputs["summary"].read_text())
        self.assertEqual(summary["cross_cohort_id_collisions_pre_namespacing"], {"admissionid": 1, "subject_id": 1})
        self.assertEqual(summary["cohort_weights"], {"aumcdb": 0.4, "mimic_iv": 0.6})

    def test_tte_targets_merged_across_cohorts(self) -> None:
        tte = json.loads(self.outputs["tte_targets"].read_text())
        self.assertEqual(tte["targets"], ["hr"])
        self.assertEqual(tte["missing"], [])

    def test_integrity_audit_passes(self) -> None:
        # write_joint_outputs already calls audit_grid_dataset internally and would have raised
        # on failure -- re-reading its own summary just confirms it reported success.
        integrity = json.loads(self.outputs["integrity"].read_text())
        self.assertTrue(integrity["passed"])
        self.assertEqual(integrity["admissions"], 4)


class WriteJointOutputsMultiAdmissionPatientTests(unittest.TestCase):
    """A real patient with >1 admission legitimately repeats their own (namespaced) subject_id
    across metadata rows -- admission-grain metadata is not one-row-per-subject. This is not a
    collision and must not raise; caught by a real 500-admission sample during Phase 6 real-data
    verification (2 patients each had 2 admissions), where an earlier version of
    write_joint_outputs incorrectly required subject_id to be globally unique the same way
    admissionid is."""

    def test_repeated_subject_id_within_one_cohort_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aumc_dir = root / "aumcdb_output"
            _write_cohort_output(
                aumc_dir,
                admissions=[
                    {"admissionid": 10, "subject_id": 1, "split": "train"},
                    {"admissionid": 11, "subject_id": 1, "split": "train"},
                ],
                grid_rows=[
                    {"admissionid": 10, "hour": 0, "hr": 80.0, "hr__observed": 1},
                    {"admissionid": 11, "hour": 0, "hr": 85.0, "hr__observed": 1},
                ],
                tte_targets={"targets": [], "missing": ["hr"], "derived": {}},
            )
            outputs = write_joint_outputs(
                cohort_output_dirs={"aumcdb": aumc_dir},
                joint_output_dir=root / "joint" / "output",
                joint_audit_dir=root / "joint" / "audit",
                patients_per_file=1000,
                weights={"aumcdb": 1.0},
                n_train_admissions_by_cohort={"aumcdb": 2},
            )
            metadata = pl.read_csv(outputs["metadata"])
        self.assertEqual(sorted(metadata["admissionid"].to_list()), ["aumcdb_10", "aumcdb_11"])
        self.assertEqual(metadata["subject_id"].to_list(), ["aumcdb_1", "aumcdb_1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
