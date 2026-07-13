"""Tests for split-aware MEDS orchestration."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "MetaICU"
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.meds.build_workflow import SplitMEDSConfig, write_split_meds_outputs


def admission_row(patientid: int, admissionid: int) -> dict[str, object]:
    return {
        "patientid": patientid,
        "subject_id": patientid,
        "hadm_id": admissionid,
        "stay_id": admissionid,
        "admissionid": admissionid,
        "admissioncount": 1,
        "admittedat": 0,
        "dischargedat": 24 * 60 * 60_000,
        "admittedattime": datetime(2010, 1, 1),
        "dischargedattime": datetime(2010, 1, 2),
        "dateofdeathtime": None,
        "gender": "Man",
        "agegroup": "60-69",
        "weightgroup": "70-79",
        "heightgroup": "170-179",
    }


def numeric_row(value: float, patientid: int, admissionid: int) -> dict[str, object]:
    return {
        "patientid": patientid,
        "subject_id": patientid,
        "hadm_id": admissionid,
        "stay_id": admissionid,
        "admissionid": admissionid,
        "itemid": 1,
        "item": "Heart rate",
        "value": value,
        "unitid": 15,
        "unit": "/min",
        "comment": "",
        "admittedat": 0,
        "dischargedat": 24 * 60 * 60_000,
        "admittedattime": datetime(2010, 1, 1),
        "dischargedattime": datetime(2010, 1, 2),
        "measuredat": 60 * 60_000,
        "admission_relative_ms": 60 * 60_000,
        "measuredattime": datetime(2010, 1, 1, 1),
    }


def write_split(pre_meds_dir: Path, split: str, values: list[float], patientid: int, admissionid: int) -> None:
    split_dir = pre_meds_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame([admission_row(patientid, admissionid)]).write_parquet(split_dir / "admissions.parquet")
    (split_dir / "numericitems_binned").mkdir(parents=True, exist_ok=True)
    pl.DataFrame([numeric_row(v, patientid, admissionid) for v in values]).write_parquet(
        split_dir / "numericitems_binned/part-00000.parquet"
    )


def write_vocab(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {
            "dataset": "AmsterdamUMCdb",
            "source_table": "numericitems",
            "source_itemid": 1,
            "source_valueid": "",
            "source_unitid": 15,
            "source_ordercategoryid": "",
            "source_label": "Heart rate",
            "source_value": "",
            "source_unit": "/min",
            "source_token": "MEASUREMENT_BEDSIDE//1///min",
            "row_count": 12,
            "harmonized_token": "VITAL//HEART_RATE",
            "token_role": "dynamic_event",
            "emit_as_model_token": True,
            "non_drug_drugitem_class": "",
            "target_vocabulary": "",
            "target_concept_id": "",
            "target_code": "",
            "target_label": "",
            "mapping_source": "fixture",
            "match_strength": "fixture",
            "mapping_confidence": "fixture",
        }
    ]).to_csv(path, index=False)


class SplitMEDSTests(unittest.TestCase):
    def test_split_meds_writes_outputs_and_global_audits_with_train_quantiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pre_meds = root / "data/pre-MEDS"
            write_split(pre_meds, "train", [float(v) for v in range(1, 11)], 1, 10)
            write_split(pre_meds, "val", [1000.0], 2, 20)
            write_split(pre_meds, "test", [5.0], 3, 30)
            vocab_path = root / "vocab/aumc_supplied_vocab.csv"
            write_vocab(vocab_path)

            outputs = write_split_meds_outputs(
                SplitMEDSConfig(
                    pre_meds_dir=pre_meds,
                    vocab_path=vocab_path,
                    output_dir=root / "data/MEDS",
                    audit_dir=root / "audits",
                    metadata_dir=root / "data/metadata",
                    overwrite=True,
                )
            )

            self.assertTrue(outputs["quantile_boundaries"].exists())
            for split in ["train", "val", "test"]:
                self.assertTrue((root / f"data/MEDS/{split}/data/0.parquet").exists())
                self.assertTrue((root / f"data/MEDS/{split}/debug/0.parquet").exists())
            self.assertTrue((root / "audits/meds/meds_split_summary.json").exists())
            self.assertTrue((root / "audits/meds/meds_split_event_counts.csv").exists())
            self.assertTrue((root / "audits/meds/meds_split_quantile_assignment_counts.csv").exists())

            val_debug = pl.read_parquet(root / "data/MEDS/val/debug/0.parquet")
            val_numeric = val_debug.filter(pl.col("source_table") == "numericitems")
            self.assertEqual(val_numeric["quantile_bin"].to_list(), [10])
            self.assertEqual(val_numeric["binning_method"].to_list(), ["raw"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
