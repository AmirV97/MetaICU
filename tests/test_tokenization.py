"""Tests for AUMC MEDS -> tokenized safetensor conversion."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
from safetensors.torch import load_file

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "MetaICU"
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.tokenization.build_workflow import TokenizationConfig, write_tokenized_outputs


def event(
    subject_id: int,
    hadm_id: int,
    minutes: int,
    code: str,
    icustay_id: int | None = None,
) -> dict[str, object]:
    return {
        "subject_id": subject_id,
        "time": datetime(2010, 1, 1) + timedelta(minutes=minutes),
        "code": code,
        "numeric_value": None,
        "text_value": None,
        "hadm_id": hadm_id,
        "icustay_id": icustay_id if icustay_id is not None else hadm_id,
    }


def write_meds_split(root: Path, split: str, rows: list[dict[str, object]]) -> None:
    data_dir = root / f"data/MEDS/{split}/data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(data_dir / "0.parquet")


class TokenizationTests(unittest.TestCase):
    def test_train_vocab_is_frozen_and_timelines_are_admission_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_meds_split(root, "train", [
                event(1, 10, 0, "ICU_ADMISSION"),
                event(1, 10, 120, "MEDICATION//C07//A//B02"),
                event(1, 10, 180, "ICU_DISCHARGE"),
                event(1, 11, 0, "ICU_ADMISSION"),
                event(1, 11, 60, "VITAL//HEART_RATE//Q5"),
            ])
            write_meds_split(root, "val", [
                event(2, 20, 0, "ICU_ADMISSION"),
                event(2, 20, 60, "VAL_ONLY_CODE"),
                event(2, 20, 120, "VITAL//HEART_RATE//Q5"),
            ])
            write_meds_split(root, "test", [
                event(3, 30, 0, "ICU_ADMISSION"),
                event(3, 30, 60, "VITAL//HEART_RATE//Q5"),
            ])

            outputs = write_tokenized_outputs(
                TokenizationConfig(
                    meds_dir=root / "data/MEDS",
                    output_dir=root / "data/tokenized",
                    audit_dir=root / "audits/tokenization",
                    metadata_dir=root / "data/tokenized/metadata",
                    max_timelines_per_shard=1,
                    medication_atc_depth="2",
                    overwrite=True,
                )
            )

            self.assertTrue(outputs["summary"].exists())
            self.assertTrue(outputs["vocab"].exists())
            self.assertTrue(outputs["timeline_index"].exists())

            vocab_codes = outputs["vocab"].read_text().splitlines()
            self.assertIn("MEDICATION//C07//A", vocab_codes)
            self.assertNotIn("MEDICATION//C07//A//B02", vocab_codes)
            self.assertNotIn("VAL_ONLY_CODE", vocab_codes)
            self.assertIn("UNK", vocab_codes)
            self.assertIn("TIMELINE_END", vocab_codes)
            self.assertIn("2h-3h", vocab_codes)

            timeline_index = pl.read_parquet(outputs["timeline_index"])
            train_idx = timeline_index.filter(pl.col("split") == "train")
            self.assertEqual(train_idx.height, 2)
            self.assertEqual(train_idx["subject_id"].to_list(), [1, 1])
            self.assertEqual(train_idx["hadm_id"].to_list(), [10, 11])

            shard = load_file(str(root / "data/tokenized/train/0.safetensors"))
            self.assertEqual(set(shard), {"tokens", "times", "patient_ids", "patient_offsets", "hadm_id", "icustay_id"})
            self.assertEqual(shard["patient_ids"].tolist(), [1])
            self.assertEqual(shard["patient_offsets"].tolist(), [0])
            self.assertEqual(len(shard["tokens"]), len(shard["times"]))
            self.assertEqual(len(shard["tokens"]), len(shard["hadm_id"]))

            unknown = pl.read_csv(root / "audits/tokenization/tokenization_unknown_codes.csv")
            self.assertEqual(unknown.filter(pl.col("code") == "VAL_ONLY_CODE")["mapped_rows"].to_list(), [1])

            val_counts = pl.read_csv(root / "data/tokenized/val/code_counts.csv")
            self.assertEqual(val_counts.filter(pl.col("code") == "UNK")["count"].to_list(), [1])

            summary = json.loads(outputs["summary"].read_text())
            val_summary = next(row for row in summary["split_summaries"] if row["split"] == "val")
            self.assertEqual(val_summary["unknown_mapped_rows"], 1)
            self.assertEqual(val_summary["unknown_dropped_rows"], 0)

    def test_subject_analysis_unit_concatenates_admissions_but_keeps_token_hadm_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_meds_split(root, "train", [
                event(1, 10, 0, "ICU_ADMISSION"),
                event(1, 10, 30, "VITAL//HEART_RATE//Q5"),
                event(1, 10, 60, "ICU_DISCHARGE"),
                event(1, 11, 120, "ICU_ADMISSION"),
                event(1, 11, 150, "VITAL//HEART_RATE//Q6"),
                event(1, 11, 180, "ICU_DISCHARGE"),
            ])
            write_meds_split(root, "val", [event(2, 20, 0, "ICU_ADMISSION")])
            write_meds_split(root, "test", [event(3, 30, 0, "ICU_ADMISSION")])

            outputs = write_tokenized_outputs(
                TokenizationConfig(
                    meds_dir=root / "data/MEDS",
                    output_dir=root / "data/tokenized",
                    audit_dir=root / "audits/tokenization",
                    metadata_dir=root / "data/tokenized/metadata",
                    analysis_unit="subject",
                    max_timelines_per_shard=10,
                    overwrite=True,
                )
            )

            timeline_index = pl.read_parquet(outputs["timeline_index"])
            train_idx = timeline_index.filter(pl.col("split") == "train")
            self.assertEqual(train_idx.height, 1)
            self.assertEqual(train_idx["analysis_unit"].to_list(), ["subject"])
            self.assertEqual(train_idx["subject_id"].to_list(), [1])
            self.assertEqual(train_idx["hadm_id"].to_list(), [-1])
            self.assertEqual(train_idx["n_admissions"].to_list(), [2])
            self.assertEqual(train_idx["hadm_ids"].to_list(), [[10, 11]])

            shard = load_file(str(root / "data/tokenized/train/0.safetensors"))
            self.assertEqual(shard["patient_ids"].tolist(), [1])
            self.assertEqual(set(shard["hadm_id"].tolist()), {10, 11})

            summary = json.loads(outputs["summary"].read_text())
            self.assertEqual(summary["analysis_unit"], "subject")
            train_summary = next(row for row in summary["split_summaries"] if row["split"] == "train")
            self.assertEqual(train_summary["timelines"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
