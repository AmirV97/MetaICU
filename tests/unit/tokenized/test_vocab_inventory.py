"""Tests for memory-safe full-cohort token vocabulary inventory."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import polars as pl

from metaicu.aumcdb.tokenized.tokenization.vocab_inventory import (
    VocabInventoryConfig,
    write_scoped_vocabularies,
)


class VocabInventoryTests(unittest.TestCase):
    def test_train_only_is_subset_of_full_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pre_meds = root / "pre_meds"
            pre_meds.mkdir()
            admissions = pl.DataFrame({
                "admissionid": [10, 20],
                "hadm_id": [10, 20],
                "subject_id": [1, 2],
                "admittedattime": [datetime(2010, 1, 1), datetime(2010, 1, 1)],
                "dischargedattime": [datetime(2010, 1, 2), datetime(2010, 1, 2)],
                "dateofdeathtime": [None, datetime(2010, 1, 2)],
                "gender": ["Man", "Vrouw"],
                "agegroup": ["60-69", "70-79"],
                "weightgroup": ["70-79", "80-89"],
                "heightgroup": ["170-179", "160-169"],
            })
            admissions.write_parquet(pre_meds / "admissions.parquet")
            pl.DataFrame({
                "admissionid": [10, 20, 10],
                "itemid": [1, 2, 6789],
                "unitid": [1, 1, 1],
                "event_temporal_phase": ["admission", "admission", "admission"],
            }).write_parquet(pre_meds / "numericitems.parquet")
            pl.DataFrame({
                "admissionid": [10, 20],
                "itemid": [3, 4],
                "valueid": [1, 1],
                "event_temporal_phase": ["admission", "admission"],
            }).write_parquet(pre_meds / "listitems.parquet")
            for table in ("drugitems", "processitems"):
                pl.DataFrame(schema={
                    "admissionid": pl.Int64,
                    "itemid": pl.Int64,
                    "ordercategoryid": pl.Int64,
                    "start_temporal_phase": pl.String,
                    "stop_temporal_phase": pl.String,
                    "start_admission_relative_ms": pl.Int64,
                    "stop_admission_relative_ms": pl.Int64,
                    "stoptime": pl.Datetime,
                }).write_parquet(pre_meds / f"{table}.parquet")

            split_path = root / "subject_splits.parquet"
            pl.DataFrame({
                "subject_id": [1, 2],
                "split": ["train", "val"],
            }).write_parquet(split_path)

            vocab_path = root / "vocab.csv"
            pl.DataFrame([
                self._vocab_row("numericitems", 1, "LAB//TRAIN", unitid=1),
                self._vocab_row("numericitems", 2, "LAB//VAL", unitid=1),
                self._vocab_row("numericitems", 6789, "LAB//EXCLUDED_PT", unitid=1),
                self._vocab_row("listitems", 3, "STATE//TRAIN", valueid=1),
                self._vocab_row("listitems", 4, "STATE//VAL", valueid=1),
            ]).write_csv(vocab_path)

            outputs = write_scoped_vocabularies(VocabInventoryConfig(
                pre_meds_dir=pre_meds,
                supplied_vocab=vocab_path,
                split_manifest=split_path,
                output_dir=root / "mappings",
            ))
            train = set(outputs["train_only"].read_text().splitlines())
            full = set(outputs["full_data"].read_text().splitlines())

            self.assertLess(train, full)
            self.assertIn("STATE//VAL", full - train)
            self.assertNotIn("LAB//VAL", full)
            self.assertNotIn("LAB//EXCLUDED_PT", train | full)
            self.assertEqual({f"Q{i}" for i in range(1, 11)}, {x for x in train if x.startswith("Q")})

    @staticmethod
    def _vocab_row(
        table: str,
        itemid: int,
        token: str,
        *,
        unitid: int | None = None,
        valueid: int | None = None,
    ) -> dict[str, object]:
        return {
            "source_table": table,
            "source_itemid": itemid,
            "source_valueid": valueid,
            "source_unitid": unitid,
            "source_ordercategoryid": None,
            "source_token": f"SOURCE//{table}//{itemid}",
            "harmonized_token": token,
            "token_role": "dynamic_event",
            "emit_as_model_token": True,
            "source_label": f"item {itemid}",
            "source_value": None,
            "source_unit": None,
        }


if __name__ == "__main__":
    unittest.main()
