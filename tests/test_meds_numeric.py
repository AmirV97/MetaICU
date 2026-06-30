"""Tests for numeric MEDS conversion input selection."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "AUMC_pipeline"
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aumc_pipeline.meds.numeric import numeric_events
from aumc_pipeline.meds.vocab import load_vocab


def numeric_row(value: float, method: str | None = None, raw_rows: int | None = None) -> dict[str, object]:
    row = {
        "patientid": 1,
        "subject_id": 1,
        "hadm_id": 10,
        "stay_id": 10,
        "admissionid": 10,
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
    if method is not None:
        row["binning_method"] = method
    if raw_rows is not None:
        row["raw_rows_in_bin"] = raw_rows
    return row


class NumericMEDSTests(unittest.TestCase):
    def test_numeric_events_prefers_binned_numericitems_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pre_meds = root / "pre_meds"
            audit_dir = root / "audits"
            (pre_meds / "numericitems").mkdir(parents=True)
            (pre_meds / "numericitems_binned").mkdir(parents=True)
            pl.DataFrame([numeric_row(1.0)]).write_parquet(pre_meds / "numericitems/part-00000.parquet")
            pl.DataFrame([numeric_row(10.0, "causal_mean", 2)]).write_parquet(
                pre_meds / "numericitems_binned/part-00000.parquet"
            )

            vocab_path = root / "vocab.csv"
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
                    "row_count": 1,
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
            ]).to_csv(vocab_path, index=False)

            vocab = load_vocab(vocab_path)
            events, exclusions = numeric_events(
                [10],
                pre_meds,
                vocab,
                include_phases=("admission",),
                bins=10,
                audit_dir=audit_dir,
            )

            self.assertTrue(any(r["exclusion_reason"] == "matched_emitted_before_phase_filter" for r in exclusions))
            self.assertEqual(events.height, 1)
            row = events.row(0, named=True)
            self.assertEqual(row["raw_numeric_value"], 10.0)
            self.assertEqual(row["binning_method"], "causal_mean")
            self.assertEqual(row["raw_rows_in_bin"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
