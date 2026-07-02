"""Tests for high-frequency numeric inventory transform and CLI."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import polars as pl

from aumc_pipeline.transforms.hf_inventory import HFInventoryBuilder, HFInventoryConfig


def write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(path)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


class HFInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.numeric_dir = self.root / "data/pre-MEDS/train/numericitems"
        self.vocab_path = self.root / "vocab/aumc_supplied_vocab.csv"
        self.metadata = self.root / "data/metadata"
        self._write_fixture()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_fixture(self) -> None:
        rows: list[dict[str, object]] = []
        for adm_idx in range(1, 5):
            patientid = adm_idx
            admissionid = adm_idx * 10
            for minute in [0, 10, 20]:
                rows.append(
                    {
                        "patientid": patientid,
                        "admissionid": admissionid,
                        "itemid": 1,
                        "admission_relative_ms": minute * 60_000,
                    }
                )
            for minute in [0, 60, 120]:
                rows.append(
                    {
                        "patientid": patientid,
                        "admissionid": admissionid,
                        "itemid": 2,
                        "admission_relative_ms": minute * 60_000,
                    }
                )
        write_parquet(self.numeric_dir / "part-00000.parquet", rows)
        write_csv(
            self.vocab_path,
            [
                {
                    "source_table": "numericitems",
                    "source_itemid": 1,
                    "row_count": 12,
                    "source_token": "MEASUREMENT_BEDSIDE//1///min",
                    "harmonized_token": "HR//Q",
                    "source_label": "Fast monitor",
                    "source_unit": "/min",
                    "emit_as_model_token": "True",
                },
                {
                    "source_table": "numericitems",
                    "source_itemid": 2,
                    "row_count": 12,
                    "source_token": "MEASUREMENT_BEDSIDE//2///min",
                    "harmonized_token": "Slow monitor",
                    "source_label": "Slow monitor",
                    "source_unit": "/min",
                    "emit_as_model_token": "True",
                },
                {
                    "source_table": "numericitems",
                    "source_itemid": 3,
                    "row_count": 10,
                    "source_token": "MEASUREMENT_BEDSIDE//3///min",
                    "harmonized_token": "Dropped",
                    "source_label": "Dropped",
                    "source_unit": "/min",
                    "emit_as_model_token": "False",
                },
            ],
        )

    def test_inventory_classifies_high_and_low_frequency_items(self) -> None:
        cfg = HFInventoryConfig(
            input_path=self.numeric_dir,
            vocab_path=self.vocab_path,
            output_csv_path=self.metadata / "hf_numeric_inventory.csv",
            output_json_path=self.metadata / "hf_numeric_highres_items.json",
            summary_path=self.metadata / "hf_numeric_inventory_summary.json",
            min_groups=2,
            patient_batch_size=2,
            highres_threshold_minutes=45.0,
            confidence_level=0.99,
        )
        summary = HFInventoryBuilder(cfg).run()
        out = pl.read_csv(cfg.output_csv_path).sort("itemid")
        statuses = dict(zip(out["itemid"].to_list(), out["is_high_resolution"].to_list()))
        self.assertEqual(statuses, {1: True, 2: False})
        self.assertEqual(summary["high_resolution_signals"], 1)
        self.assertTrue(cfg.output_json_path.exists())

if __name__ == "__main__":
    unittest.main(verbosity=2)
