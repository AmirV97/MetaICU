"""Regression test: run the real joint AUMCdb+MIMIC-IV grid pipeline (metaicu.grid.cli.
grid_build_joint_dataset's own orchestration, called directly rather than through Hydra) against
real, bounded samples of both cohorts and sanity-check the two real-data properties the design
plan calls out explicitly: cohort weights reflect the real 1/sqrt(n_train) ratio, and a tag real
only on one side (here "pt", real on MIMIC-IV, structural_zero on AUMCdb) ends up pooled as a
scaler that is visibly, verifiably that cohort's own solo fit -- not diluted, not silently
mis-transformed.

Requires local raw data (see tests/real_data/mimiciv/grid/test_grid_build_regression.py for the
MIMIC-IV-only counterpart of this env-var pattern):

    METAICU_AUMCDB_REGRESSION_RAW_DIR         AmsterdamUMCdb raw CSV directory (admissions.csv, ...)
    METAICU_MIMICIV_REGRESSION_RAW_DIR        MIMIC-IV pre_MEDS export root (icu/, hosp/ subdirs)
    METAICU_AUMCDB_REGRESSION_RAW_SHARDS_DIR  optional: an already-built AUMCdb raw-parquet shard cache
    METAICU_MIMICIV_REGRESSION_RAW_SHARDS_DIR optional: an already-built MIMIC-IV raw-parquet shard cache

Run on an HPC batch job (touches the real raw tables for both cohorts):

    METAICU_AUMCDB_REGRESSION_RAW_DIR=/path/to/AmsterdamUMCdb \
    METAICU_MIMICIV_REGRESSION_RAW_DIR=/path/to/pre_MEDS \
    python -m unittest tests.real_data.grid.test_joint_grid_build_regression -v
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import polars as pl

from metaicu.aumcdb.grid.build.build_workflow import GridDatasetConfig as AumcConfig
from metaicu.aumcdb.grid.build.build_workflow import build_pre_scale_grid as build_aumcdb_pre_scale_grid
from metaicu.aumcdb.grid.build.build_workflow import finish_grid_dataset as finish_aumcdb
from metaicu.aumcdb.grid.build.impute import (
    capture_presence_mask as aumcdb_capture_presence_mask,
    materialize_structural_zero_columns as aumcdb_materialize_structural_zero,
)
from metaicu.aumcdb.grid.build.manifest_parser import DEFAULT_REVIEWED_MANIFEST as AUMCDB_DEFAULT_MANIFEST
from metaicu.mimiciv.grid.build.build_workflow import GridDatasetConfig as MimicConfig
from metaicu.mimiciv.grid.build.build_workflow import build_pre_scale_grid as build_mimiciv_pre_scale_grid
from metaicu.mimiciv.grid.build.build_workflow import finish_grid_dataset as finish_mimiciv
from metaicu.mimiciv.grid.build.impute import (
    capture_presence_mask as mimiciv_capture_presence_mask,
    materialize_structural_zero_columns as mimiciv_materialize_structural_zero,
)
from metaicu.mimiciv.grid.build.manifest_parser import DEFAULT_REVIEWED_MANIFEST as MIMICIV_DEFAULT_MANIFEST
from metaicu.grid.cli.grid_build_joint_dataset import _compute_pooled_scalers, _pad_pre_scale_grid
from metaicu.grid.joint_assemble import write_joint_outputs
from metaicu.grid.pool_scale import compute_cohort_weights
from metaicu.grid.schema_union import compute_union_matches

AUMCDB_RAW_DIR_ENV = "METAICU_AUMCDB_REGRESSION_RAW_DIR"
AUMCDB_RAW_SHARDS_DIR_ENV = "METAICU_AUMCDB_REGRESSION_RAW_SHARDS_DIR"
MIMICIV_RAW_DIR_ENV = "METAICU_MIMICIV_REGRESSION_RAW_DIR"
MIMICIV_RAW_SHARDS_DIR_ENV = "METAICU_MIMICIV_REGRESSION_RAW_SHARDS_DIR"

SAMPLE_SIZE = 500


def _env_dir(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    path = Path(value)
    return path if path.is_dir() else None


def _missing_env_reason() -> str | None:
    missing = [name for name in (AUMCDB_RAW_DIR_ENV, MIMICIV_RAW_DIR_ENV) if _env_dir(name) is None]
    if missing:
        return f"Set {', '.join(missing)} to real raw data directories to run this regression test"
    return None


@unittest.skipIf(_missing_env_reason(), _missing_env_reason() or "")
class JointGridBuildRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        workspace = Path(cls.tmp.name)

        aumc_config = AumcConfig(
            raw_data_dir=_env_dir(AUMCDB_RAW_DIR_ENV),
            output_dir=workspace / "aumcdb",
            audit_dir=workspace / "aumcdb" / "audit",
            manifest_path=AUMCDB_DEFAULT_MANIFEST,
            raw_shards_dir=_env_dir(AUMCDB_RAW_SHARDS_DIR_ENV) or (workspace / "aumcdb_raw_shards"),
            build_raw_shards=True,
            sample_size=SAMPLE_SIZE,
            patients_per_file=200,
            random_seed=42,
            scale=True,
            impute=True,
            one_hot=True,
        )
        mimic_config = MimicConfig(
            raw_data_dir=_env_dir(MIMICIV_RAW_DIR_ENV),
            output_dir=workspace / "mimic_iv",
            audit_dir=workspace / "mimic_iv" / "audit",
            manifest_path=MIMICIV_DEFAULT_MANIFEST,
            raw_shards_dir=_env_dir(MIMICIV_RAW_SHARDS_DIR_ENV) or (workspace / "mimic_iv_raw_shards"),
            build_raw_shards=True,
            sample_size=SAMPLE_SIZE,
            patients_per_file=200,
            random_seed=42,
            scale=True,
            impute=True,
            one_hot=True,
        )
        cls.configs = {"aumcdb": aumc_config, "mimic_iv": mimic_config}

        pre_scale_by_cohort = {
            "aumcdb": build_aumcdb_pre_scale_grid(aumc_config),
            "mimic_iv": build_mimiciv_pre_scale_grid(mimic_config),
        }

        union_registry = compute_union_matches({name: p.matches for name, p in pre_scale_by_cohort.items()})
        _pad_pre_scale_grid("aumcdb", pre_scale_by_cohort["aumcdb"], union_registry,
                             aumcdb_materialize_structural_zero, aumcdb_capture_presence_mask)
        _pad_pre_scale_grid("mimic_iv", pre_scale_by_cohort["mimic_iv"], union_registry,
                             mimiciv_materialize_structural_zero, mimiciv_capture_presence_mask)

        cls.n_train = {name: len(p.train_admission_ids) for name, p in pre_scale_by_cohort.items()}
        cls.weights = compute_cohort_weights(cls.n_train)
        cls.pooled_scalers = _compute_pooled_scalers(pre_scale_by_cohort, cls.weights)
        cls.pre_scale_by_cohort = pre_scale_by_cohort

        finish_aumcdb(aumc_config, pre_scale_by_cohort["aumcdb"], external_scalers=cls.pooled_scalers)
        finish_mimiciv(mimic_config, pre_scale_by_cohort["mimic_iv"], external_scalers=cls.pooled_scalers)

        cls.joint_output_dir = workspace / "joint" / "data"
        cls.joint_audit_dir = workspace / "joint" / "audit"
        cls.outputs = write_joint_outputs(
            cohort_output_dirs={"aumcdb": aumc_config.output_dir, "mimic_iv": mimic_config.output_dir},
            joint_output_dir=cls.joint_output_dir,
            joint_audit_dir=cls.joint_audit_dir,
            patients_per_file=200,
            weights=cls.weights,
            n_train_admissions_by_cohort=cls.n_train,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_cohort_weight_ratio_matches_sqrt_of_real_train_counts(self) -> None:
        expected_ratio = math.sqrt(self.n_train["mimic_iv"]) / math.sqrt(self.n_train["aumcdb"])
        actual_ratio = self.weights["aumcdb"] / self.weights["mimic_iv"]
        self.assertAlmostEqual(actual_ratio, expected_ratio, places=6)

    def test_pt_pooled_scaler_is_visibly_mimic_derived(self) -> None:
        self.assertTrue(self.pre_scale_by_cohort["aumcdb"].matches_with_derived["pt"]["structural_zero"])
        self.assertIn("pt", self.pooled_scalers)
        pt_scaler = self.pooled_scalers["pt"]
        self.assertEqual(pt_scaler["log"], "log1p")

        mimic_grid = self.pre_scale_by_cohort["mimic_iv"].grid
        mimic_train_ids = self.pre_scale_by_cohort["mimic_iv"].train_admission_ids
        mimic_pt = (
            mimic_grid.filter(pl.col("admissionid").is_in(list(mimic_train_ids)))["pt"]
            .drop_nulls()
            .to_numpy()
        )
        mimic_pt_log1p = np.log1p(mimic_pt)
        self.assertAlmostEqual(pt_scaler["mean"], float(mimic_pt_log1p.mean()), places=6)
        self.assertAlmostEqual(pt_scaler["std"], float(mimic_pt_log1p.std()), places=6)

    def test_joint_output_is_well_formed(self) -> None:
        integrity = json.loads(self.outputs["integrity"].read_text())
        self.assertTrue(integrity["passed"])
        metadata = pl.read_csv(self.outputs["metadata"])
        self.assertEqual(metadata["admissionid"].n_unique(), metadata.height)
        summary = json.loads(self.outputs["summary"].read_text())
        self.assertEqual(summary["cross_cohort_id_collisions_pre_namespacing"]["admissionid"], 0)

    def test_report_real_cohort_counts_and_weights(self) -> None:
        # Not an assertion -- prints the real numbers the plan's verification step 5 asked to be
        # reported back (replacing HANDOFF.md's placeholder 33.8%/66.2% estimate), visible with -v.
        print(f"\nReal (sample_size={SAMPLE_SIZE}) train admission counts: {self.n_train}")
        print(f"Cohort weights (1/sqrt(n_train), normalized): {self.weights}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
