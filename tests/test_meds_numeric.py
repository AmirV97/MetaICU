"""Tests for numeric MEDS conversion input selection and frozen quantiles."""

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

from metaicu.aumcdb.tokenized.meds.numeric import fit_numeric_quantile_boundaries, numeric_events
from metaicu.aumcdb.tokenized.meds.vocab import load_vocab


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


def numeric_row(
    value: float,
    itemid: int = 1,
    unitid: int = 15,
    unit: str | None = "/min",
    patientid: int = 1,
    admissionid: int = 10,
    method: str | None = None,
    raw_rows: int | None = None,
) -> dict[str, object]:
    row = {
        "patientid": patientid,
        "subject_id": patientid,
        "hadm_id": admissionid,
        "stay_id": admissionid,
        "admissionid": admissionid,
        "itemid": itemid,
        "item": "Heart rate" if itemid == 1 else "Resp rate",
        "value": value,
        "unitid": unitid,
        "unit": unit,
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


def vocab_row(itemid: int = 1, unitid: int = 15, unit: str | None = "/min") -> dict[str, object]:
    label = "Heart rate" if itemid == 1 else "Resp rate"
    token = "VITAL//HEART_RATE" if itemid == 1 else "VITAL//RESP_RATE"
    return {
        "dataset": "AmsterdamUMCdb",
        "source_table": "numericitems",
        "source_itemid": itemid,
        "source_valueid": "",
        "source_unitid": unitid,
        "source_ordercategoryid": "",
        "source_label": label,
        "source_value": "",
        "source_unit": unit,
        "source_token": f"MEASUREMENT_BEDSIDE//{itemid}//{unit or 'UNKNOWN'}",
        "row_count": 1,
        "harmonized_token": token,
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


def write_vocab(path: Path, rows: list[dict[str, object]]) -> pl.DataFrame:
    pd.DataFrame(rows).to_csv(path, index=False)
    return load_vocab(path)


def write_split_numeric(pre_meds: Path, rows: list[dict[str, object]], admissions: list[dict[str, object]] | None = None) -> None:
    pre_meds.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(admissions or [admission_row(1, 10)]).write_parquet(pre_meds / "admissions.parquet")
    (pre_meds / "numericitems").mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(pre_meds / "numericitems/part-00000.parquet")


class NumericMEDSTests(unittest.TestCase):
    def test_numeric_events_prefers_binned_numericitems_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pre_meds = root / "pre_meds"
            audit_dir = root / "audits"
            (pre_meds / "numericitems").mkdir(parents=True)
            (pre_meds / "numericitems_binned").mkdir(parents=True)
            pl.DataFrame([numeric_row(1.0)]).write_parquet(pre_meds / "numericitems/part-00000.parquet")
            pl.DataFrame([numeric_row(10.0, method="causal_mean", raw_rows=2)]).write_parquet(
                pre_meds / "numericitems_binned/part-00000.parquet"
            )

            vocab = write_vocab(root / "vocab.csv", [vocab_row()])
            events, exclusions = numeric_events(
                [10], pre_meds, vocab, include_phases=("admission",), bins=10, audit_dir=audit_dir
            )

            self.assertTrue(any(r["exclusion_reason"] == "matched_emitted_before_phase_filter" for r in exclusions))
            self.assertEqual(events.height, 1)
            row = events.row(0, named=True)
            self.assertEqual(row["raw_numeric_value"], 10.0)
            self.assertEqual(row["binning_method"], "causal_mean")
            self.assertEqual(row["raw_rows_in_bin"], 2)

    def test_val_uses_train_boundaries_not_val_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train = root / "pre_meds/train"
            val = root / "pre_meds/val"
            audit_dir = root / "audits"
            write_split_numeric(train, [numeric_row(float(v)) for v in range(1, 11)])
            write_split_numeric(val, [numeric_row(1000.0)])
            vocab = write_vocab(root / "vocab.csv", [vocab_row()])

            boundaries, _ = fit_numeric_quantile_boundaries(train, vocab, ("admission",), bins=10)
            events, _ = numeric_events(
                [10], val, vocab, ("admission",), bins=10, audit_dir=audit_dir, quantile_boundaries=boundaries
            )

            self.assertEqual(events.height, 1)
            self.assertEqual(events["quantile_bin"].to_list(), [10])
            self.assertEqual(events["code"].to_list(), ["VITAL//HEART_RATE//Q10"])

    def test_missing_train_boundary_drops_numeric_row_with_audit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train = root / "pre_meds/train"
            val = root / "pre_meds/val"
            audit_dir = root / "audits"
            write_split_numeric(train, [numeric_row(float(v)) for v in range(1, 11)])
            write_split_numeric(val, [numeric_row(22.0, itemid=2)])
            vocab = write_vocab(root / "vocab.csv", [vocab_row(), vocab_row(itemid=2)])

            boundaries, _ = fit_numeric_quantile_boundaries(train, vocab, ("admission",), bins=10)
            events, exclusions = numeric_events(
                [10], val, vocab, ("admission",), bins=10, audit_dir=audit_dir, quantile_boundaries=boundaries
            )

            self.assertEqual(events.height, 0)
            self.assertTrue(any(r["exclusion_reason"] == "numeric_missing_train_quantile_boundary" for r in exclusions))

    def test_null_unit_boundaries_join_with_frozen_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train = root / "pre_meds/train"
            val = root / "pre_meds/val"
            audit_dir = root / "audits"
            write_split_numeric(train, [numeric_row(float(v), unitid=0, unit=None) for v in range(1, 11)])
            write_split_numeric(val, [numeric_row(1000.0, unitid=0, unit=None)])
            vocab = write_vocab(root / "vocab.csv", [vocab_row(unitid=0, unit=None)])

            boundaries, _ = fit_numeric_quantile_boundaries(train, vocab, ("admission",), bins=10)
            self.assertEqual(boundaries["source_unit_key"].to_list(), ["<NULL>"])
            events, exclusions = numeric_events(
                [10], val, vocab, ("admission",), bins=10, audit_dir=audit_dir, quantile_boundaries=boundaries
            )

            self.assertFalse(any(r["exclusion_reason"] == "numeric_missing_train_quantile_boundary" for r in exclusions))
            self.assertEqual(events.height, 1)
            self.assertEqual(events["quantile_bin"].to_list(), [10])


if __name__ == "__main__":
    unittest.main(verbosity=2)
