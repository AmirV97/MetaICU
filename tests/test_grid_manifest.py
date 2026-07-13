"""Tests for the iCareFM-style grid feature manifest."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "MetaICU"
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.grid.manifest import GridManifestConfig, build_feature_manifest, load_feature_seed, write_grid_manifest_outputs


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class GridManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.audit_dir = self.workspace / "audits/grid_manifest"
        self.output_manifest = self.workspace / "grid/aumc_grid_feature_manifest.csv"
        self.feature_list = self.root / "features.csv"
        self.source_vocab = self.workspace / "audits/vocab_pipeline_source_vocab.csv"
        self.supplied_vocab = self.workspace / "vocab/aumc_supplied_vocab.csv"
        self.openicu_root = self.workspace / "externals/OpenICU"
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
        write_csv(
            self.source_vocab,
            [
                {
                    "dataset": "amsterdamumcdb",
                    "source_table": "numericitems",
                    "source_itemid": "6640",
                    "source_valueid": "",
                    "source_unitid": "17",
                    "source_ordercategoryid": "",
                    "source_label": "Hartfrequentie",
                    "source_value": "",
                    "source_unit": "/min",
                    "source_token": "MEASUREMENT_BEDSIDE//6640///min",
                    "row_count": 100,
                },
                {
                    "dataset": "amsterdamumcdb",
                    "source_table": "listitems",
                    "source_itemid": "1001",
                    "source_valueid": "1",
                    "source_unitid": "",
                    "source_ordercategoryid": "",
                    "source_label": "EMV score",
                    "source_value": "15",
                    "source_unit": "",
                    "source_token": "MEASUREMENT_CATEGORICAL//1001//1",
                    "row_count": 10,
                },
                {
                    "dataset": "amsterdamumcdb",
                    "source_table": "drugitems",
                    "source_itemid": "7179",
                    "source_valueid": "",
                    "source_unitid": "",
                    "source_ordercategoryid": "65",
                    "source_label": "Dobutamine",
                    "source_value": "",
                    "source_unit": "",
                    "source_token": "DRUG//START//65//7179",
                    "row_count": 30,
                },
            ],
        )
        write_csv(
            self.supplied_vocab,
            [
                {
                    "dataset": "amsterdamumcdb",
                    "source_table": "numericitems",
                    "source_itemid": "6640",
                    "source_valueid": "",
                    "source_unitid": "17",
                    "source_ordercategoryid": "",
                    "source_label": "Hartfrequentie",
                    "source_value": "",
                    "source_unit": "/min",
                    "source_token": "MEASUREMENT_BEDSIDE//6640///min",
                    "row_count": 100,
                    "harmonized_token": "OMOP_CONCEPT//LOINC//3027018",
                    "token_role": "dynamic_event",
                    "emit_as_model_token": False,
                    "target_concept_id": "3027018",
                    "target_code": "8867-4",
                    "target_label": "Heart rate",
                },
                {
                    "dataset": "amsterdamumcdb",
                    "source_table": "drugitems",
                    "source_itemid": "7179",
                    "source_valueid": "",
                    "source_unitid": "",
                    "source_ordercategoryid": "65",
                    "source_label": "Dobutamine",
                    "source_value": "",
                    "source_unit": "",
                    "source_token": "DRUG//START//65//7179",
                    "row_count": 30,
                    "harmonized_token": "MEDICATION//C01//C//A07",
                    "token_role": "dynamic_event",
                    "emit_as_model_token": True,
                    "target_concept_id": "",
                    "target_code": "C01CA07",
                    "target_label": "Dobutamine",
                },
            ],
        )
        write_text(
            self.openicu_root / "config/datasets/aumc/1.5.0/mappings/heart_rate.yml",
            "codes:\n  - 3027018\n",
        )

    def _config(self, feature_list: Path | None = None) -> GridManifestConfig:
        return GridManifestConfig(
            output_manifest=self.output_manifest,
            audit_dir=self.audit_dir,
            feature_list=feature_list or self.feature_list,
            source_vocab=self.source_vocab,
            supplied_vocab=self.supplied_vocab,
            openicu_root=self.openicu_root,
        )

    def test_packaged_seed_loads_129_extractable_rows(self) -> None:
        features = load_feature_seed(None)
        self.assertEqual(len(features), 129)
        self.assertFalse(features["tag"].duplicated().any())
        self.assertEqual(set(["tag", "name", "type", "organ_system", "target_unit"]), set(features.columns))

    def test_manifest_classifies_special_features_and_keeps_non_emitted_candidates(self) -> None:
        manifest, candidates, summary = build_feature_manifest(self._config())
        by_tag = manifest.set_index("tag")

        self.assertEqual(by_tag.loc["ethnic", "reconstruction_type"], "unavailable")
        self.assertEqual(by_tag.loc["ethnic", "mapping_status"], "unavailable")
        self.assertEqual(by_tag.loc["tgcs", "reconstruction_type"], "derived_score")
        self.assertEqual(by_tag.loc["samp", "mapping_status"], "needs_policy")
        self.assertEqual(by_tag.loc["dobu", "reconstruction_type"], "treatment_rate")
        self.assertEqual(by_tag.loc["dobu_ind", "reconstruction_type"], "treatment_indicator")

        self.assertIn("heart_rate.yml", by_tag.loc["hr", "openicu_mapping_file"])
        self.assertEqual(by_tag.loc["hr", "openicu_omop_concept_ids"], "3027018")
        self.assertIn("MEASUREMENT_BEDSIDE//6640///min", candidates.loc[candidates["tag"].eq("hr"), "source_token"].tolist())
        self.assertIn("DRUG//START//65//7179", candidates.loc[candidates["tag"].eq("dobu"), "source_token"].tolist())
        self.assertEqual(summary["total_features"], 6)

    def test_writer_creates_manifest_and_audits(self) -> None:
        outputs = write_grid_manifest_outputs(self._config())
        for path in outputs.values():
            self.assertTrue(path.exists(), path)

        manifest = pd.read_csv(outputs["feature_manifest"])
        self.assertEqual(len(manifest), 6)
        self.assertFalse(manifest["tag"].duplicated().any())
        self.assertIn("source_itemid_candidates", manifest.columns)

        summary = json.loads(outputs["manifest_summary"].read_text())
        self.assertEqual(summary["paper_claimed_total_features"], 130)
        self.assertEqual(summary["extractable_table_s3_features"], 6)

    def test_cli_uses_packaged_seed_and_does_not_need_raw_csvs(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        cmd = [
            sys.executable,
            "-m",
            "metaicu.cli.grid_build_manifest",
            f"paths.parent_dir={self.workspace}",
            f"paths.source_vocab={self.source_vocab}",
            f"paths.supplied_vocab={self.supplied_vocab}",
            f"paths.openicu_root={self.openicu_root}",
        ]
        result = subprocess.run(cmd, cwd=PIPELINE_ROOT, env=env, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        manifest = pd.read_csv(payload["feature_manifest"])
        self.assertEqual(len(manifest), 129)
        self.assertFalse((self.workspace / "data/raw").exists())
        self.assertTrue((self.workspace / "audits/grid_manifest/grid_manifest_summary.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
