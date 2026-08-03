"""Tests for the iCareFM-style MIMIC-IV grid feature manifest. Mirrors
tests/integration/grid/test_grid_manifest.py, adapted for a real architectural difference:
metaicu.mimiciv.grid.manifest searches MIMIC's own raw item catalogs (icu/d_items.csv.gz,
hosp/d_labitems.csv.gz) directly by label keyword, not aumcdb's vocab-chaining
(source_vocab/supplied_vocab/openicu_root) -- see that module's docstring for why."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import polars as pl

from tests._paths import PROJECT_ROOT as PIPELINE_ROOT, SRC_ROOT

from metaicu.mimiciv.grid.manifest import GridManifestConfig, build_feature_manifest, load_feature_seed, write_grid_manifest_outputs


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def write_csv_gz(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, compression="gzip")


def _row(manifest: pl.DataFrame, tag: str) -> dict:
    return manifest.filter(pl.col("tag") == tag).row(0, named=True)


class GridManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.audit_dir = self.workspace / "audits/grid_manifest"
        self.output_manifest = self.workspace / "grid/mimic_grid_feature_manifest.csv"
        self.feature_list = self.root / "features.csv"
        self.raw_data_dir = self.root / "raw"
        self._write_fixture_inputs()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_fixture_inputs(self) -> None:
        write_csv(
            self.feature_list,
            [
                {"tag": "hr", "name": "Heart Rate", "type": "observation", "organ_system": "circulatory", "target_unit": "/min"},
                {"tag": "ethnic", "name": "Ethnicity", "type": "demographic", "organ_system": "", "target_unit": "categorical"},
                {"tag": "tgcs", "name": "Total GCS", "type": "observation", "organ_system": "neuro", "target_unit": "score"},
                {"tag": "dobu", "name": "Dobutamine", "type": "treatment", "organ_system": "circulatory", "target_unit": "mcg/kg/min"},
                {"tag": "dobu_ind", "name": "Dobutamine Indicator", "type": "treatment", "organ_system": "circulatory", "target_unit": "indicator"},
                {"tag": "samp", "name": "Microbiology Sampling", "type": "observation", "organ_system": "infection", "target_unit": "indicator"},
            ],
        )
        write_csv_gz(
            self.raw_data_dir / "icu/d_items.csv.gz",
            [
                {"itemid": 220045, "label": "Heart Rate", "linksto": "chartevents", "unitname": "bpm"},
                {"itemid": 221653, "label": "Dobutamine", "linksto": "inputevents", "unitname": "mcg/kg/min"},
                {"itemid": 225792, "label": "Blood Culture", "linksto": "chartevents", "unitname": ""},
                {"itemid": 220048, "label": "Heart Rhythm", "linksto": "chartevents", "unitname": ""},
            ],
        )
        write_csv_gz(
            self.raw_data_dir / "hosp/d_labitems.csv.gz",
            [
                {"itemid": 51301, "label": "White Blood Cells", "fluid": "Blood"},
            ],
        )

    def _config(self, feature_list: Path | None = None) -> GridManifestConfig:
        return GridManifestConfig(
            output_manifest=self.output_manifest,
            audit_dir=self.audit_dir,
            raw_data_dir=self.raw_data_dir,
            feature_list=feature_list or self.feature_list,
        )

    def test_packaged_seed_loads_129_extractable_rows(self) -> None:
        features = load_feature_seed(None)
        self.assertEqual(features.height, 129)
        self.assertFalse(features["tag"].is_duplicated().any())
        self.assertEqual({"tag", "name", "type", "organ_system", "target_unit"}, set(features.columns))

    def test_manifest_classifies_special_features_and_finds_candidates(self) -> None:
        manifest, candidates, summary = build_feature_manifest(self._config())

        self.assertEqual(_row(manifest, "ethnic")["reconstruction_type"], "unavailable")
        # unlike AUMC (no reliable ethnicity field at all), MIMIC-IV's admissions.race IS
        # resolvable -- mapping_status reflects that even though reconstruction_type stays
        # "unavailable" (ethnic bypasses the 5 mechanically-extractable types either way).
        self.assertEqual(_row(manifest, "ethnic")["mapping_status"], "source_candidates_found")
        self.assertEqual(_row(manifest, "tgcs")["reconstruction_type"], "derived_score")
        # samp is treatment_indicator directly (no bespoke microbiology/needs_policy class) --
        # matches the already-reviewed manifest's own reclassification, see manifest.py's
        # _reconstruction_type docstring.
        self.assertEqual(_row(manifest, "samp")["mapping_status"], "no_source_candidates")
        self.assertEqual(_row(manifest, "samp")["reconstruction_type"], "treatment_indicator")
        self.assertEqual(_row(manifest, "dobu")["reconstruction_type"], "treatment_rate")
        self.assertEqual(_row(manifest, "dobu_ind")["reconstruction_type"], "treatment_indicator")

        self.assertIn(220045, candidates.filter(pl.col("tag") == "hr")["source_itemid"].to_list())
        self.assertIn(221653, candidates.filter(pl.col("tag") == "dobu")["source_itemid"].to_list())
        self.assertEqual(summary["total_features"], 6)

    def test_writer_creates_manifest_and_audits(self) -> None:
        outputs = write_grid_manifest_outputs(self._config())
        for path in outputs.values():
            self.assertTrue(path.exists(), path)

        manifest = pl.read_csv(outputs["feature_manifest"])
        self.assertEqual(manifest.height, 6)
        self.assertFalse(manifest["tag"].is_duplicated().any())
        self.assertIn("source_itemid_candidates", manifest.columns)

        summary = json.loads(outputs["manifest_summary"].read_text())
        self.assertEqual(summary["paper_claimed_total_features"], 130)
        self.assertEqual(summary["extractable_table_s3_features"], 6)

    def test_cli_uses_packaged_seed_by_default(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        cmd = [
            sys.executable,
            "-m",
            "metaicu.mimiciv.grid.cli.grid_build_manifest",
            f"paths.parent_dir={self.workspace}",
            f"paths.raw_data_dir={self.raw_data_dir}",
        ]
        result = subprocess.run(cmd, cwd=PIPELINE_ROOT, env=env, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        manifest = pl.read_csv(payload["feature_manifest"])
        self.assertEqual(manifest.height, 129)
        self.assertTrue((self.workspace / "audits/grid_manifest/grid_manifest_summary.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
