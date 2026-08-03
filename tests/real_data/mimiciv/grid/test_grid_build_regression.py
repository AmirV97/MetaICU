"""Regression test: run the MIMIC-IV grid pipeline against a real MIMIC-IV pre_MEDS export and
confirm two independent extractions of the same bounded sample are byte-identical.

Unlike aumcdb's real_data vocab regression (tests/real_data/tokenized/vocab/
test_vocab_build_regression.py), there is no long-lived reference artifact committed to this
repo to diff against yet -- the validated baseline from the M4_grid port (test_10k_output_v8_stage3,
~779k rows) lives outside the repository in dataset_EDA/M4_grid/, not as a packaged fixture.
Committing a frozen reference dataset here is a follow-up decision, not made unilaterally by
this test. In the meantime, this test guards the specific property Stage 0 fixed and Stage 3
almost silently broke: given the same seed, two runs must produce EXACTLY the same output --
any nondeterminism (a categorical mode-tie-break regression, a raw-ingestion race, an unstable
sort) would show up as a spurious diff here before it ever reached a real training run.

Requires local MIMIC-IV pre_MEDS data:

    METAICU_MIMICIV_REGRESSION_RAW_DIR         MIMIC-IV pre_MEDS export root (icu/, hosp/ subdirs)
    METAICU_MIMICIV_REGRESSION_RAW_SHARDS_DIR  optional: an already-built raw-parquet shard cache
                                                (see metaicu.mimiciv.common.raw_shards) -- building
                                                one from scratch is a ~20-minute one-time cost
                                                (the full chartevents/labevents tables), so point
                                                this at an existing cache to skip that on repeat
                                                runs. Unset: builds a fresh cache in a temp dir.

Run on an HPC batch job (a full run touches the multi-GB chartevents/labevents tables), e.g.:

    METAICU_MIMICIV_REGRESSION_RAW_DIR=/path/to/pre_MEDS \
    METAICU_MIMICIV_REGRESSION_RAW_SHARDS_DIR=/path/to/raw_shards \
    python -m unittest tests.real_data.mimiciv.grid.test_grid_build_regression -v
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import polars as pl
from polars.testing import assert_frame_equal


from metaicu.mimiciv.grid.build.build_workflow import GridDatasetConfig, write_grid_dataset_outputs
from metaicu.mimiciv.grid.build.manifest_parser import DEFAULT_REVIEWED_MANIFEST

RAW_DIR_ENV = "METAICU_MIMICIV_REGRESSION_RAW_DIR"
RAW_SHARDS_DIR_ENV = "METAICU_MIMICIV_REGRESSION_RAW_SHARDS_DIR"


def _env_dir(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    path = Path(value)
    return path if path.is_dir() else None


def _missing_env_reason() -> str | None:
    if _env_dir(RAW_DIR_ENV) is None:
        return f"Set {RAW_DIR_ENV} to a real MIMIC-IV pre_MEDS export to run this regression test"
    return None


def _load_grid(output_dir: Path) -> pl.DataFrame:
    parts = [
        pl.read_parquet(shard)
        for split in ("train", "val", "test")
        for shard in sorted((output_dir / split).glob("*.parquet"))
    ]
    return pl.concat(parts, how="vertical_relaxed").sort(["admissionid", "hour"])


@unittest.skipIf(_missing_env_reason(), _missing_env_reason() or "")
class GridBuildRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        workspace = Path(cls.tmp.name)
        raw_data_dir = _env_dir(RAW_DIR_ENV)
        raw_shards_dir = _env_dir(RAW_SHARDS_DIR_ENV) or (workspace / "raw_shards")

        def _config(name: str) -> GridDatasetConfig:
            return GridDatasetConfig(
                raw_data_dir=raw_data_dir,
                output_dir=workspace / name,
                audit_dir=workspace / name / "audit",
                manifest_path=DEFAULT_REVIEWED_MANIFEST,
                raw_shards_dir=raw_shards_dir,
                build_raw_shards=True,
                sample_size=500,
                patients_per_file=200,
                seed=42,
                split_seed=42,
                scale=True,
                impute=True,
                one_hot=True,
            )

        cls.outputs_a = write_grid_dataset_outputs(_config("run_a"))
        cls.outputs_b = write_grid_dataset_outputs(_config("run_b"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_two_runs_of_the_same_sample_are_byte_identical(self) -> None:
        grid_a = _load_grid(self.outputs_a["output_dir"])
        grid_b = _load_grid(self.outputs_b["output_dir"])
        assert_frame_equal(grid_a, grid_b, check_column_order=True)

    def test_run_produced_a_nonempty_grid_with_expected_shard_layout(self) -> None:
        grid = _load_grid(self.outputs_a["output_dir"])
        self.assertGreater(grid.height, 0)
        self.assertIn("admissionid", grid.columns)
        self.assertIn("hour", grid.columns)
        metadata = pl.read_csv(self.outputs_a["metadata"])
        self.assertGreater(metadata.height, 0)
        self.assertLessEqual(metadata.height, 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
