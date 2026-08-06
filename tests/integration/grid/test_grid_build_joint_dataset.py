"""Integration test for metaicu.grid.cli.grid_build_joint_dataset's own orchestration logic
(_pad_pre_scale_grid, _compute_pooled_scalers) plus the real finish_grid_dataset/write_joint_outputs
chain -- exercised directly against two hand-built PreScaleGrid objects (bypassing raw extraction,
which Phase 2's own tests already cover) so the NEW Phase 5 glue code runs for real, not mocked.

Deliberately gives the two cohorts a tag-parity GAP ("crp" real only in mimic_iv) to exercise
cross-cohort schema padding, and >= MIN_TRAIN_VALUES real per-tag values so pooled_mean_std/
pooled_fit_treatment actually fit (not skip) -- verified against hand-computed expectations.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import polars as pl

from metaicu.aumcdb.grid.build.build_workflow import GridDatasetConfig as AumcConfig
from metaicu.aumcdb.grid.build.build_workflow import finish_grid_dataset as finish_aumcdb
from metaicu.aumcdb.grid.build.impute import (
    capture_presence_mask as aumcdb_capture_presence_mask,
    materialize_structural_zero_columns as aumcdb_materialize_structural_zero,
)
from metaicu.mimiciv.grid.build.build_workflow import GridDatasetConfig as MimicConfig
from metaicu.mimiciv.grid.build.build_workflow import finish_grid_dataset as finish_mimiciv
from metaicu.mimiciv.grid.build.impute import (
    capture_presence_mask as mimiciv_capture_presence_mask,
    materialize_structural_zero_columns as mimiciv_materialize_structural_zero,
)
from metaicu.grid.cli.grid_build_joint_dataset import _compute_pooled_scalers, _pad_pre_scale_grid
from metaicu.grid.joint_assemble import write_joint_outputs
from metaicu.grid.pool_scale import compute_cohort_weights, pooled_mean_std
from metaicu.grid.pre_scale import PreScaleGrid
from metaicu.grid.schema_union import compute_union_matches

HOURS = list(range(10))  # >= MIN_TRAIN_VALUES(10) real values per pooled tag


def _grid_frame(admission_rows):
    """admission_rows: {admissionid: {"hr": [...], "crp": [...] | None, "nor": [...] | None}}."""
    rows = []
    for admission_id, tags in admission_rows.items():
        n_hours = len(tags["hr"])
        for hour in range(n_hours):
            row = {"admissionid": admission_id, "hour": hour, "hr": tags["hr"][hour]}
            if tags.get("crp") is not None:
                row["crp"] = tags["crp"][hour]
            if tags.get("nor") is not None:
                row["nor"] = tags["nor"][hour]
            rows.append(row)
    return pl.DataFrame(rows)


def _admissions_frame(rows, subject_col):
    return pl.DataFrame(rows).rename({"subject": subject_col})


class GridBuildJointDatasetOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)

        # --- AUMCdb: has hr + nor, does NOT have crp at all (native tag-parity gap). ---
        aumc_matches = {
            "hr": {"reconstruction_type": "direct_numeric", "target_unit": "bpm", "keep_matches": [], "n_keep": 1},
            "nor": {"reconstruction_type": "treatment_rate", "target_unit": "mcg/kg/min", "keep_matches": [], "n_keep": 1},
        }
        aumc_grid = _grid_frame({
            10: {"hr": [70.0 + h for h in HOURS], "nor": [1.0 + 0.1 * h for h in HOURS]},  # train
            20: {"hr": [90.0], "nor": [0.0]},  # val
        })
        aumc_admissions = _admissions_frame([
            {"admissionid": 10, "subject": 1, "split": "train", "admittedat": 0, "true_los_hours": 10.0,
             "dateofdeath": None, "age": 60.0, "weight": 80.0, "height": 175.0, "sex": "M", "adm": "medical", "ethnic": "unknown"},
            {"admissionid": 20, "subject": 2, "split": "val", "admittedat": 0, "true_los_hours": 5.0,
             "dateofdeath": None, "age": 55.0, "weight": 70.0, "height": 165.0, "sex": "F", "adm": "surgical", "ethnic": "unknown"},
        ], subject_col="patientid")
        aumc_pre_scale = PreScaleGrid(
            grid=aumc_grid, matches=aumc_matches, matches_with_derived=dict(aumc_matches),
            derived_target_matches={}, admissions=aumc_admissions, train_admission_ids=[10],
            demo_source=aumc_admissions.select(["admissionid", "sex", "adm", "ethnic"]),
            static_categorical_encoding=[], next_categorical_pos=0, presence_mask_cols=[],
            manifest_report={}, raw_shard_summary={}, admissions_before_inclusion=2,
        )
        cls.aumc_config = AumcConfig(
            raw_data_dir=Path("/unused"), output_dir=root / "aumcdb_staging" / "data",
            audit_dir=root / "aumcdb_staging" / "audit", manifest_path=Path("/unused"),
            unit_of_analysis="admission", scale=True, impute=True, one_hot=False, overwrite=True,
        )

        # --- MIMIC-IV: has hr + crp + nor (crp is the tag AUMCdb structurally lacks). ---
        mimic_matches = {
            "hr": {"reconstruction_type": "direct_numeric", "target_unit": "bpm", "keep_matches": [], "n_keep": 1},
            "crp": {"reconstruction_type": "direct_numeric", "target_unit": "mg/L", "keep_matches": [], "n_keep": 1},
            "nor": {"reconstruction_type": "treatment_rate", "target_unit": "mcg/kg/min", "keep_matches": [], "n_keep": 1},
        }
        mimic_grid = _grid_frame({
            100: {"hr": [74.0 + h for h in HOURS], "crp": [5.0 + 0.5 * h for h in HOURS], "nor": [2.0 + 0.1 * h for h in HOURS]},  # train
            200: {"hr": [95.0], "crp": [10.0], "nor": [0.0]},  # val
        })
        mimic_admissions = _admissions_frame([
            {"admissionid": 100, "subject": 1, "split": "train", "true_los_hours": 10.0,
             "hospital_expire_flag": 0, "age": 65.0, "weight": 85.0, "height": 180.0, "sex": "M", "adm": "medical", "ethnic": "white"},
            {"admissionid": 200, "subject": 3, "split": "val", "true_los_hours": 6.0,
             "hospital_expire_flag": 0, "age": 50.0, "weight": 75.0, "height": 170.0, "sex": "F", "adm": "surgical", "ethnic": "black"},
        ], subject_col="subject_id")
        mimic_pre_scale = PreScaleGrid(
            grid=mimic_grid, matches=mimic_matches, matches_with_derived=dict(mimic_matches),
            derived_target_matches={}, admissions=mimic_admissions, train_admission_ids=[100],
            demo_source=mimic_admissions.select(["admissionid", "sex", "adm", "ethnic"]),
            static_categorical_encoding=[], next_categorical_pos=0, presence_mask_cols=[],
            manifest_report={}, raw_shard_summary={}, admissions_before_inclusion=2,
        )
        cls.mimic_config = MimicConfig(
            raw_data_dir=Path("/unused"), output_dir=root / "mimic_iv_staging" / "data",
            audit_dir=root / "mimic_iv_staging" / "audit", manifest_path=Path("/unused"),
            scale=True, impute=True, one_hot=False, overwrite=True,
        )

        pre_scale_by_cohort = {"aumcdb": aumc_pre_scale, "mimic_iv": mimic_pre_scale}

        # --- Phase 1: cross-cohort schema padding (real dispatcher helper). ---
        union_registry = compute_union_matches({name: p.matches for name, p in pre_scale_by_cohort.items()})
        cls.union_registry = union_registry
        _pad_pre_scale_grid("aumcdb", aumc_pre_scale, union_registry,
                             aumcdb_materialize_structural_zero, aumcdb_capture_presence_mask)
        _pad_pre_scale_grid("mimic_iv", mimic_pre_scale, union_registry,
                             mimiciv_materialize_structural_zero, mimiciv_capture_presence_mask)

        # --- Phase 3: pooled statistics (real dispatcher helper). ---
        cls.n_train = {"aumcdb": 1, "mimic_iv": 1}
        cls.weights = compute_cohort_weights(cls.n_train)
        cls.pooled_scalers = _compute_pooled_scalers(pre_scale_by_cohort, cls.weights)

        # --- Phase 2: finish each cohort's own staging build with the shared pooled scalers. ---
        finish_aumcdb(cls.aumc_config, aumc_pre_scale, external_scalers=cls.pooled_scalers)
        finish_mimiciv(cls.mimic_config, mimic_pre_scale, external_scalers=cls.pooled_scalers)

        # --- Phase 4: joint assembly. ---
        cls.joint_output_dir = root / "joint" / "data"
        cls.joint_audit_dir = root / "joint" / "audit"
        cls.outputs = write_joint_outputs(
            cohort_output_dirs={"aumcdb": cls.aumc_config.output_dir, "mimic_iv": cls.mimic_config.output_dir},
            joint_output_dir=cls.joint_output_dir,
            joint_audit_dir=cls.joint_audit_dir,
            patients_per_file=1000,
            weights=cls.weights,
            n_train_admissions_by_cohort=cls.n_train,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_padding_gives_aumcdb_a_structural_zero_crp_column(self) -> None:
        self.assertEqual(set(self.union_registry), {"hr", "crp", "nor"})
        crp_path = self.aumc_config.output_dir / "train"
        shard = pl.concat([pl.read_parquet(p) for p in sorted(crp_path.glob("*.parquet"))])
        self.assertIn("crp", shard.columns)
        self.assertIn("crp__observed", shard.columns)
        self.assertEqual(shard["crp__observed"].to_list(), [0] * shard.height)

    def test_hr_pooled_mean_std_matches_hand_computation(self) -> None:
        aumc_hr = np.array([70.0 + h for h in HOURS])
        mimic_hr = np.array([74.0 + h for h in HOURS])
        expected_mean, expected_std = pooled_mean_std(
            {
                "aumcdb": {"mean": float(aumc_hr.mean()), "std": float(aumc_hr.std()), "n": len(aumc_hr)},
                "mimic_iv": {"mean": float(mimic_hr.mean()), "std": float(mimic_hr.std()), "n": len(mimic_hr)},
            },
            self.weights,
        )
        hr_scaler = self.pooled_scalers["hr"]
        self.assertEqual(hr_scaler["type"], "observation")
        self.assertIsNone(hr_scaler["log"])
        self.assertAlmostEqual(hr_scaler["mean"], expected_mean)
        self.assertAlmostEqual(hr_scaler["std"], expected_std)

    def test_crp_pooled_scaler_is_100_percent_mimic_derived(self) -> None:
        # aumcdb has no real crp at all (padded structural_zero) -- the pooled fit must reproduce
        # mimic_iv's own solo mean/std exactly, not be diluted toward 0 by the padded column. crp
        # is one of scale.py's LOG_TRANSFORM_TAGS ("log1p"), so "mean"/"std" are in log1p space,
        # not raw units -- comparing against the raw mean/std here (as an earlier version of this
        # test did) fails even though pooling is correct, since it's comparing the wrong space.
        mimic_crp_log1p = np.log1p(np.array([5.0 + 0.5 * h for h in HOURS]))
        crp_scaler = self.pooled_scalers["crp"]
        self.assertEqual(crp_scaler["log"], "log1p")
        self.assertAlmostEqual(crp_scaler["mean"], float(mimic_crp_log1p.mean()))
        self.assertAlmostEqual(crp_scaler["std"], float(mimic_crp_log1p.std()))

    def test_nor_treatment_rate_is_pooled_not_skipped(self) -> None:
        self.assertIn("nor", self.pooled_scalers)
        self.assertEqual(self.pooled_scalers["nor"]["type"], "treatment")
        self.assertIsNotNone(self.pooled_scalers["nor"]["transformer"])

    def test_both_cohorts_apply_the_identical_pooled_scaler_object(self) -> None:
        # Both finish_* calls were given the SAME external_scalers dict -- the actual scaled hr
        # values for a known raw input should therefore match between cohorts' own scalers.pkl.
        import pickle
        aumc_scalers = pickle.loads((self.aumc_config.output_dir / "scalers.pkl").read_bytes())
        mimic_scalers = pickle.loads((self.mimic_config.output_dir / "scalers.pkl").read_bytes())
        self.assertEqual(aumc_scalers["hr"]["mean"], mimic_scalers["hr"]["mean"])
        self.assertEqual(aumc_scalers["hr"]["std"], mimic_scalers["hr"]["std"])

    def test_joint_output_namespaces_and_records_source(self) -> None:
        metadata = pl.read_csv(self.outputs["metadata"])
        self.assertEqual(
            sorted(metadata["admissionid"].to_list()),
            ["aumcdb_10", "aumcdb_20", "mimic_iv_100", "mimic_iv_200"],
        )
        source_by_admission = dict(zip(metadata["admissionid"].to_list(), metadata["source"].to_list()))
        self.assertEqual(source_by_admission["aumcdb_10"], "aumcdb")
        self.assertEqual(source_by_admission["mimic_iv_100"], "mimic_iv")

    def test_native_ids_trace_back_to_the_original_per_cohort_values(self) -> None:
        metadata = pl.read_csv(self.outputs["metadata"])
        native_by_admission = dict(zip(metadata["admissionid"].to_list(), metadata["native_admissionid"].to_list()))
        self.assertEqual(native_by_admission["aumcdb_10"], 10)
        self.assertEqual(native_by_admission["mimic_iv_100"], 100)
        native_subject_by_admission = dict(
            zip(metadata["admissionid"].to_list(), metadata["native_subject_id"].to_list())
        )
        self.assertEqual(native_subject_by_admission["aumcdb_10"], 1)
        self.assertEqual(native_subject_by_admission["mimic_iv_100"], 1)

    def test_joint_output_includes_copied_scalers_pkl(self) -> None:
        import pickle
        self.assertIsNotNone(self.outputs["scalers"])
        self.assertTrue(self.outputs["scalers"].exists())
        joint_scalers = pickle.loads(self.outputs["scalers"].read_bytes())
        aumc_scalers = pickle.loads((self.aumc_config.output_dir / "scalers.pkl").read_bytes())
        self.assertEqual(joint_scalers["hr"]["mean"], aumc_scalers["hr"]["mean"])
        self.assertEqual(joint_scalers["hr"]["std"], aumc_scalers["hr"]["std"])
        self.assertTrue((self.joint_output_dir / "scalers.summary.json").exists())

    def test_joint_feature_schema_has_all_three_tags(self) -> None:
        schema = json.loads(self.outputs["feature_schema"].read_text())
        self.assertEqual({"hr", "crp", "nor"} & set(schema), {"hr", "crp", "nor"})

    def test_joint_integrity_audit_passes(self) -> None:
        integrity = json.loads(self.outputs["integrity"].read_text())
        self.assertTrue(integrity["passed"])
        self.assertEqual(integrity["admissions"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
