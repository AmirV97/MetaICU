"""Tests for subject splits and split-aware pre-MEDS output."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path

import pandas as pd
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "MetaICU"
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.pre_meds.build_workflow import PreMedsConfig, write_premeds_outputs
from metaicu.utils.parquet_datasets import parquet_exists
from metaicu.splits.build_splits import (
    SplitConfig,
    assign_subject_splits,
    write_subject_splits,
)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


class SplitAndPreMedsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw = self.root / "data/raw"
        self.raw_shards = self.root / "data/raw_shards"
        self.metadata = self.root / "data/metadata"
        self.pre_meds = self.root / "data/pre-MEDS"
        self.audits = self.root / "audits"
        self.vocab_path = self.root / "vocab/aumc_supplied_vocab.csv"
        self._write_raw_tables()
        self._write_vocab()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_raw_tables(self) -> None:
        admissions = []
        for patientid, admissionid in [(1, 10), (2, 20), (3, 30), (4, 40)]:
            admissions.append(
                {
                    "patientid": patientid,
                    "admissionid": admissionid,
                    "admissioncount": 1,
                    "location": "ICU",
                    "urgency": "",
                    "origin": "",
                    "admittedat": 0,
                    "admissionyeargroup": "2003-2009",
                    "dischargedat": 86400000,
                    "lengthofstay": 1.0,
                    "destination": "",
                    "gender": "Man",
                    "agegroup": "60-69",
                    "dateofdeath": "",
                    "weightgroup": "70-79",
                    "weightsource": "",
                    "heightgroup": "170-179",
                    "heightsource": "",
                    "specialty": "",
                }
            )
        write_csv(self.raw / "admissions.csv", admissions)

        write_csv(
            self.raw / "numericitems.csv",
            [
                {
                    "admissionid": 10,
                    "itemid": 1,
                    "item": "Heart rate",
                    "tag": "",
                    "value": 80.0,
                    "unitid": 15,
                    "unit": "/min",
                    "comment": "",
                    "measuredat": 1000,
                    "registeredat": 1000,
                    "registeredby": "",
                    "updatedat": 1000,
                    "updatedby": "",
                    "islabresult": 0,
                    "fluidout": 0,
                },
                {
                    "admissionid": 30,
                    "itemid": 1,
                    "item": "Heart rate",
                    "tag": "",
                    "value": 90.0,
                    "unitid": 15,
                    "unit": "/min",
                    "comment": "",
                    "measuredat": 2000,
                    "registeredat": 2000,
                    "registeredby": "",
                    "updatedat": 2000,
                    "updatedby": "",
                    "islabresult": 0,
                    "fluidout": 0,
                },
            ],
        )
        write_csv(
            self.raw / "listitems.csv",
            [
                {
                    "admissionid": 10,
                    "itemid": 2,
                    "item": "Rhythm",
                    "valueid": 1,
                    "value": "NSR",
                    "measuredat": 1000,
                    "registeredat": 1000,
                    "registeredby": "",
                    "updatedat": 1000,
                    "updatedby": "",
                    "islabresult": 0,
                },
                {
                    "admissionid": 30,
                    "itemid": 2,
                    "item": "Rhythm",
                    "valueid": 2,
                    "value": "AF",
                    "measuredat": 2000,
                    "registeredat": 2000,
                    "registeredby": "",
                    "updatedat": 2000,
                    "updatedby": "",
                    "islabresult": 0,
                },
            ],
        )
        write_csv(
            self.raw / "drugitems.csv",
            [
                {
                    "admissionid": 10,
                    "orderid": 1,
                    "ordercategoryid": 24,
                    "ordercategory": "Injecties",
                    "itemid": 3,
                    "item": "Drug A",
                    "isadditive": 0,
                    "isconditional": 0,
                    "rate": 1.0,
                    "rateunit": "ml/h",
                    "rateunitid": 1,
                    "ratetimeunitid": 1,
                    "doserateperkg": 0,
                    "dose": 1.0,
                    "doseunit": "mg",
                    "doserateunit": "",
                    "doseunitid": 1,
                    "doserateunitid": 0,
                    "administered": 1.0,
                    "administeredunit": "mg",
                    "administeredunitid": 1,
                    "action": "start",
                    "start": 1000,
                    "stop": 2000,
                    "duration": 1000,
                    "solutionitemid": 0,
                    "solutionitem": "",
                    "solutionadministered": 0.0,
                    "solutionadministeredunit": "",
                    "fluidin": 0.0,
                    "iscontinuous": 0,
                },
                {
                    "admissionid": 30,
                    "orderid": 2,
                    "ordercategoryid": 24,
                    "ordercategory": "Injecties",
                    "itemid": 3,
                    "item": "Drug A",
                    "isadditive": 0,
                    "isconditional": 0,
                    "rate": 1.0,
                    "rateunit": "ml/h",
                    "rateunitid": 1,
                    "ratetimeunitid": 1,
                    "doserateperkg": 0,
                    "dose": 1.0,
                    "doseunit": "mg",
                    "doserateunit": "",
                    "doseunitid": 1,
                    "doserateunitid": 0,
                    "administered": 1.0,
                    "administeredunit": "mg",
                    "administeredunitid": 1,
                    "action": "start",
                    "start": 1000,
                    "stop": 2000,
                    "duration": 1000,
                    "solutionitemid": 0,
                    "solutionitem": "",
                    "solutionadministered": 0.0,
                    "solutionadministeredunit": "",
                    "fluidin": 0.0,
                    "iscontinuous": 0,
                },
            ],
        )
        write_csv(
            self.raw / "freetextitems.csv",
            [
                {
                    "admissionid": 10,
                    "itemid": 4,
                    "item": "Note",
                    "value": "abc",
                    "measuredat": 1000,
                    "registeredat": 1000,
                    "updatedat": 1000,
                }
            ],
        )
        write_csv(
            self.raw / "processitems.csv",
            [
                {
                    "admissionid": 10,
                    "itemid": 5,
                    "item": "Line",
                    "start": 1000,
                    "stop": 2000,
                },
                {
                    "admissionid": 30,
                    "itemid": 5,
                    "item": "Line",
                    "start": 1000,
                    "stop": 2000,
                },
            ],
        )
        write_csv(
            self.raw / "procedureorderitems.csv",
            [
                {
                    "admissionid": 10,
                    "itemid": 6,
                    "item": "X-ray",
                    "ordercategoryid": 7,
                    "ordercategoryname": "Imaging",
                    "registeredat": 1000,
                }
            ],
        )

    def _write_vocab(self) -> None:
        write_csv(
            self.vocab_path,
            [
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
                    "row_count": 2,
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
            ],
        )

    def test_assign_subject_splits_is_deterministic_and_subject_exclusive(self) -> None:
        subjects = list(range(1, 11))
        first = assign_subject_splits(subjects, 0.8, 0.1, 0.1, seed=7)
        second = assign_subject_splits(subjects, 0.8, 0.1, 0.1, seed=7)
        self.assertTrue(first.equals(second))
        self.assertEqual(first["subject_id"].nunique(), 10)
        self.assertEqual(first["split"].value_counts().to_dict(), {"train": 8, "val": 1, "test": 1})

    def test_split_cli_writes_expected_schema(self) -> None:
        cmd = [
            sys.executable,
            str(PIPELINE_ROOT / "scripts/build_amsterdam_split.py"),
            f"paths.parent_dir={self.root}",
            "run.train_frac=0.5",
            "run.val_frac=0.25",
            "run.test_frac=0.25",
        ]
        subprocess.run(cmd, cwd=PIPELINE_ROOT, check=True, capture_output=True, text=True)
        split_path = self.metadata / "subject_splits.parquet"
        self.assertTrue(split_path.exists())
        out = pl.read_parquet(split_path)
        self.assertEqual(out.columns, ["subject_id", "split"])
        self.assertEqual(out.height, 4)
        self.assertEqual(out.select("subject_id").n_unique(), 4)

    def test_premeds_creates_split_manifest_when_missing(self) -> None:
        split_path = self.metadata / "subject_splits.parquet"
        self.assertFalse(split_path.exists())

        outputs = write_premeds_outputs(
            PreMedsConfig(
                raw_data_dir=self.raw,
                raw_shards_dir=self.raw_shards,
                pre_meds_dir=self.pre_meds,
                audit_dir=self.audits,
                epoch_map={"2003-2009": "2003-01-01 00:00:00"},
                partition_rows=1,
                split_path=split_path,
                split_outputs=True,
                split_train_frac=0.5,
                split_val_frac=0.25,
                split_test_frac=0.25,
                split_seed=11,
                vocab_path=self.vocab_path,
                build_hf_inventory=False,
                build_binned_numericitems=False,
                overwrite=False,
            )
        )

        self.assertTrue(split_path.exists())
        self.assertEqual(outputs["subject_splits"], split_path)
        split_df = pl.read_parquet(split_path)
        self.assertEqual(split_df.height, 4)
        self.assertEqual(set(split_df["split"].to_list()), {"train", "val", "test"})
        self.assertTrue((self.pre_meds / "train/admissions.parquet").exists())
        self.assertTrue((self.pre_meds / "val/admissions.parquet").exists())
        self.assertTrue((self.pre_meds / "test/admissions.parquet").exists())

    def test_premeds_writes_combined_and_split_outputs(self) -> None:
        split_df = pd.DataFrame(
            [
                {"subject_id": 1, "split": "train"},
                {"subject_id": 2, "split": "val"},
                {"subject_id": 3, "split": "test"},
                {"subject_id": 4, "split": "test"},
            ]
        )
        split_path = self.metadata / "subject_splits.parquet"
        split_path.parent.mkdir(parents=True, exist_ok=True)
        split_df.to_parquet(split_path, index=False)

        outputs = write_premeds_outputs(
            PreMedsConfig(
                raw_data_dir=self.raw,
                raw_shards_dir=self.raw_shards,
                pre_meds_dir=self.pre_meds,
                audit_dir=self.audits,
                epoch_map={"2003-2009": "2003-01-01 00:00:00"},
                partition_rows=1,
                split_path=split_path,
                split_outputs=True,
                vocab_path=self.vocab_path,
                build_hf_inventory=True,
                hf_inventory_metadata_dir=self.metadata,
                hf_min_groups=1,
                hf_patient_batch_size=1,
                binning_window_minutes=60,
                overwrite=True,
            )
        )
        self.assertTrue(outputs["admissions"].exists())
        self.assertTrue((self.raw_shards / "numericitems/part-00000.parquet").exists())
        self.assertTrue(outputs["hf_numeric_inventory"].exists())
        self.assertTrue((self.metadata / "hf_numeric_inventory_summary.json").exists())
        self.assertTrue(outputs["hf_numeric_binning_summary"].exists())
        self.assertTrue((self.pre_meds / "train/admissions.parquet").exists())
        self.assertTrue((self.pre_meds / "test/admissions.parquet").exists())
        self.assertTrue((self.pre_meds / "train/numericitems/part-00000.parquet").exists())
        self.assertTrue((self.pre_meds / "test/numericitems/part-00000.parquet").exists())
        self.assertTrue((self.pre_meds / "train/numericitems_binned/part-00000.parquet").exists())
        self.assertTrue((self.pre_meds / "test/numericitems_binned/part-00000.parquet").exists())
        self.assertTrue((self.pre_meds / "val/numericitems_binned").is_dir())
        self.assertTrue((self.pre_meds / "val/numericitems").is_dir())
        self.assertFalse(parquet_exists(self.pre_meds / "val/numericitems"))

        train_adm = pl.read_parquet(self.pre_meds / "train/admissions.parquet")
        test_adm = pl.read_parquet(self.pre_meds / "test/admissions.parquet")
        self.assertEqual(set(train_adm["patientid"].to_list()), {1})
        self.assertEqual(set(test_adm["patientid"].to_list()), {3, 4})

        train_num = pl.scan_parquet(str(self.pre_meds / "train/numericitems/*.parquet")).collect()
        test_num = pl.scan_parquet(str(self.pre_meds / "test/numericitems/*.parquet")).collect()
        self.assertEqual(set(train_num["patientid"].to_list()), {1})
        self.assertEqual(set(test_num["patientid"].to_list()), {3})
        self.assertIn("split", train_num.columns)

        summary = json.loads((self.audits / "premeds_summary.json").read_text())
        self.assertEqual(summary["raw_shards"]["numericitems"]["action"], "built")
        self.assertEqual(summary["large_tables"]["numericitems"]["input_mode"], "raw_parquet_shards")

    def test_premeds_can_fallback_to_csv_chunks_when_raw_shards_disabled(self) -> None:
        split_path = self.metadata / "subject_splits.parquet"
        split_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {"subject_id": 1, "split": "train"},
                {"subject_id": 2, "split": "val"},
                {"subject_id": 3, "split": "test"},
                {"subject_id": 4, "split": "test"},
            ]
        ).to_parquet(split_path, index=False)

        write_premeds_outputs(
            PreMedsConfig(
                raw_data_dir=self.raw,
                pre_meds_dir=self.pre_meds,
                audit_dir=self.audits,
                epoch_map={"2003-2009": "2003-01-01 00:00:00"},
                partition_rows=1,
                split_path=split_path,
                split_outputs=True,
                vocab_path=self.vocab_path,
                build_raw_shards=False,
                build_hf_inventory=False,
                build_binned_numericitems=False,
                overwrite=True,
            )
        )

        self.assertFalse((self.raw_shards / "numericitems").exists())
        summary = json.loads((self.audits / "premeds_summary.json").read_text())
        self.assertEqual(summary["raw_shards"]["skipped"], "run.build_raw_shards=false")
        self.assertEqual(summary["large_tables"]["numericitems"]["input_mode"], "raw_csv_chunks")

    def test_premeds_state_change_deduplicates_configured_listitems(self) -> None:
        write_csv(
            self.raw / "listitems.csv",
            [
                {
                    "admissionid": 10,
                    "itemid": 9,
                    "item": "Ventilatie Mode (Set)",
                    "valueid": valueid,
                    "value": value,
                    "measuredat": measuredat,
                    "registeredat": measuredat,
                    "registeredby": "",
                    "updatedat": measuredat,
                    "updatedby": "",
                    "islabresult": 0,
                }
                for measuredat, valueid, value in [
                    (1000, 1, "PS/CPAP"),
                    (2000, 1, "PS/CPAP"),
                    (3000, 2, "PC"),
                    (4000, 2, "PC"),
                    (5000, 1, "PS/CPAP"),
                ]
            ],
        )
        split_path = self.metadata / "subject_splits.parquet"
        split_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {"subject_id": 1, "split": "train"},
                {"subject_id": 2, "split": "val"},
                {"subject_id": 3, "split": "test"},
                {"subject_id": 4, "split": "test"},
            ]
        ).to_parquet(split_path, index=False)

        write_premeds_outputs(
            PreMedsConfig(
                raw_data_dir=self.raw,
                raw_shards_dir=self.raw_shards,
                pre_meds_dir=self.pre_meds,
                audit_dir=self.audits,
                epoch_map={"2003-2009": "2003-01-01 00:00:00"},
                partition_rows=2,
                split_path=split_path,
                split_outputs=True,
                vocab_path=self.vocab_path,
                build_hf_inventory=False,
                build_binned_numericitems=False,
                overwrite=True,
            )
        )

        train_list = pl.scan_parquet(str(self.pre_meds / "train/listitems/*.parquet")).collect()
        vent = train_list.filter(pl.col("item") == "Ventilatie Mode (Set)").sort("measuredat")
        self.assertEqual(vent["valueid"].to_list(), [1, 2, 1])

        summary = json.loads((self.audits / "premeds_summary.json").read_text())
        dedup = summary["large_tables"]["listitems"]["state_change_dedup"]["combined"]
        self.assertEqual(dedup["rows_before"], 5)
        self.assertEqual(dedup["rows_after"], 3)
        self.assertEqual(dedup["rows_removed"], 2)

    def test_premeds_reuses_existing_raw_shards_by_default(self) -> None:
        split_path = self.metadata / "subject_splits.parquet"
        split_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {"subject_id": 1, "split": "train"},
                {"subject_id": 2, "split": "val"},
                {"subject_id": 3, "split": "test"},
                {"subject_id": 4, "split": "test"},
            ]
        ).to_parquet(split_path, index=False)

        base_kwargs = dict(
            raw_data_dir=self.raw,
            raw_shards_dir=self.raw_shards,
            pre_meds_dir=self.pre_meds,
            audit_dir=self.audits,
            epoch_map={"2003-2009": "2003-01-01 00:00:00"},
            partition_rows=1,
            split_path=split_path,
            split_outputs=True,
            vocab_path=self.vocab_path,
            build_hf_inventory=False,
            build_binned_numericitems=False,
            overwrite=True,
        )
        write_premeds_outputs(PreMedsConfig(**base_kwargs))
        write_premeds_outputs(
            PreMedsConfig(
                **{
                    **base_kwargs,
                    "pre_meds_dir": self.root / "data/pre-MEDS-second",
                    "audit_dir": self.root / "audits-second",
                }
            )
        )

        summary = json.loads((self.root / "audits-second/premeds_summary.json").read_text())
        self.assertEqual(summary["raw_shards"]["numericitems"]["action"], "reused")
        self.assertEqual(summary["large_tables"]["numericitems"]["input_mode"], "raw_parquet_shards")


if __name__ == "__main__":
    unittest.main(verbosity=2)
