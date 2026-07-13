"""Tests for high-frequency numeric inventory transform and CLI."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import polars as pl

from metaicu.transforms.hf_inventory import HFInventoryBuilder, HFInventoryConfig


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

    def test_default_rare_dense_gate_is_aggressive_enough_for_rare_crrt_like_streams(self) -> None:
        cfg = HFInventoryConfig(
            input_path=self.numeric_dir,
            vocab_path=self.vocab_path,
            output_csv_path=self.metadata / "hf_numeric_inventory.csv",
            output_json_path=self.metadata / "hf_numeric_highres_items.json",
            summary_path=self.metadata / "hf_numeric_inventory_summary.json",
        )
        self.assertEqual(cfg.rare_dense_min_groups, 2)

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

    def test_inventory_flags_rare_but_dense_high_row_count_items(self) -> None:
        extra_rows: list[dict[str, object]] = []
        for adm_idx in [1, 2]:
            for minute in [0, 10, 20]:
                extra_rows.append(
                    {
                        "patientid": adm_idx,
                        "admissionid": adm_idx * 10,
                        "itemid": 4,
                        "admission_relative_ms": minute * 60_000,
                    }
                )
        existing = pl.read_parquet(self.numeric_dir / "part-00000.parquet")
        pl.concat([existing, pl.DataFrame(extra_rows)], how="vertical_relaxed").write_parquet(
            self.numeric_dir / "part-00000.parquet"
        )
        vocab = pd.read_csv(self.vocab_path)
        vocab = pd.concat(
            [
                vocab,
                pd.DataFrame(
                    [
                        {
                            "source_table": "numericitems",
                            "source_itemid": 4,
                            "row_count": 1_000_000,
                            "source_token": "MEASUREMENT_BEDSIDE//4//mmHg",
                            "harmonized_token": "Rare dense setting",
                            "source_label": "Rare dense setting",
                            "source_unit": "mmHg",
                            "emit_as_model_token": "True",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        vocab.to_csv(self.vocab_path, index=False)

        cfg = HFInventoryConfig(
            input_path=self.numeric_dir,
            vocab_path=self.vocab_path,
            output_csv_path=self.metadata / "hf_numeric_inventory.csv",
            output_json_path=self.metadata / "hf_numeric_highres_items.json",
            summary_path=self.metadata / "hf_numeric_inventory_summary.json",
            min_groups=4,
            rare_dense_min_groups=2,
            rare_dense_min_row_count=500_000,
            patient_batch_size=4,
            highres_threshold_minutes=45.0,
            confidence_level=0.99,
        )
        HFInventoryBuilder(cfg).run()
        out = pl.read_csv(cfg.output_csv_path).filter(pl.col("itemid") == 4).row(0, named=True)
        self.assertTrue(out["is_high_resolution"])
        self.assertEqual(out["status"], "high_resolution_rare_but_dense")

if __name__ == "__main__":
    unittest.main(verbosity=2)
