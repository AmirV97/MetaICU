"""Tests for the Amsterdam source-vocabulary extraction step."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "AUMC_pipeline/src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aumc_pipeline.vocab_pipeline.source_vocab import (
    SOURCE_VOCAB_COLUMNS,
    SourceVocabConfig,
    compare_to_reference,
    extract_source_vocab,
    validate_source_vocab,
)


PIPELINE_ROOT = Path(__file__).resolve().parents[1]


def write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(path)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


class SourceVocabExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pre_meds = self.root / "pre_meds"
        self.raw_data = self.root / "raw_amsterdam"
        self.audit_dir = self.root / "audits"
        self._write_fixture_tables()
        self._write_raw_fixture_tables()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_fixture_tables(self) -> None:
        write_parquet(
            self.pre_meds / "numericitems.parquet",
            [
                {"itemid": 1, "item": "Heart rate", "unitid": 15, "unit": "/min", "code_prefix": "MEASUREMENT_BEDSIDE"},
                {"itemid": 1, "item": "Heart rate", "unitid": 15, "unit": "/min", "code_prefix": "MEASUREMENT_BEDSIDE"},
                {"itemid": 2, "item": "Saturation", "unitid": 0, "unit": None, "code_prefix": "MEASUREMENT_BEDSIDE"},
                {"itemid": 3, "item": "Urine", "unitid": 10, "unit": "ml", "code_prefix": "SUBJECT_FLUID_OUTPUT"},
            ],
        )
        list_dir = self.pre_meds / "listitems"
        write_parquet(
            list_dir / "part-0.parquet",
            [
                {"itemid": 10, "item": "Rhythm", "valueid": 1, "value": "NSR"},
                {"itemid": 10, "item": "Rhythm", "valueid": 1, "value": "NSR"},
            ],
        )
        write_parquet(
            list_dir / "part-1.parquet",
            [{"itemid": 10, "item": "Rhythm", "valueid": 2, "value": "Sinus Tac"}],
        )
        write_parquet(
            self.pre_meds / "drugitems.parquet",
            [
                {"itemid": 20, "item": "Drug A", "ordercategoryid": 5, "ordercategory": "Infusion"},
                {"itemid": 20, "item": "Drug A", "ordercategoryid": 5, "ordercategory": "Infusion"},
                {"itemid": 21, "item": "Food A", "ordercategoryid": 9, "ordercategory": "Nutrition"},
            ],
        )
        write_parquet(
            self.pre_meds / "freetextitems.parquet",
            [
                {"itemid": 30, "item": "Free label", "value": "A"},
                {"itemid": 30, "item": "Free label", "value": "B"},
            ],
        )
        write_parquet(
            self.pre_meds / "processitems.parquet",
            [
                {"itemid": 40, "item": "Arterial line"},
                {"itemid": 40, "item": "Arterial line"},
            ],
        )
        write_parquet(
            self.pre_meds / "procedureorderitems.parquet",
            [
                {"itemid": 50, "item": "X-ray", "ordercategoryid": 7, "ordercategoryname": "Imaging"},
                {"itemid": 51, "item": "Lab", "ordercategoryid": 8, "ordercategoryname": "Lab order"},
            ],
        )


    def _write_raw_fixture_tables(self) -> None:
        write_csv(
            self.raw_data / "numericitems.csv",
            [
                {"admissionid": 1, "itemid": 1, "item": "Heart rate", "tag": "", "value": 80, "unitid": 15, "unit": "/min", "comment": "", "measuredat": 1, "registeredat": 1, "registeredby": "", "updatedat": 1, "updatedby": "", "islabresult": 0, "fluidout": 0},
                {"admissionid": 1, "itemid": 1, "item": "Heart rate", "tag": "", "value": 81, "unitid": 15, "unit": "/min", "comment": "", "measuredat": 2, "registeredat": 2, "registeredby": "", "updatedat": 2, "updatedby": "", "islabresult": 0, "fluidout": 0},
                {"admissionid": 1, "itemid": 2, "item": "Cortisol", "tag": "", "value": 100, "unitid": 97, "unit": "nmol/l", "comment": "", "measuredat": 3, "registeredat": 3, "registeredby": "", "updatedat": 3, "updatedby": "", "islabresult": 1, "fluidout": 0},
                {"admissionid": 1, "itemid": 3, "item": "Urine", "tag": "", "value": 20, "unitid": 10, "unit": "ml", "comment": "", "measuredat": 4, "registeredat": 4, "registeredby": "", "updatedat": 4, "updatedby": "", "islabresult": 0, "fluidout": 1},
            ],
        )
        write_csv(
            self.raw_data / "listitems.csv",
            [
                {"admissionid": 1, "itemid": 10, "item": "Rhythm", "valueid": 1, "value": "NSR", "measuredat": 1, "registeredat": 1, "registeredby": "", "updatedat": 1, "updatedby": "", "islabresult": 0},
                {"admissionid": 1, "itemid": 10, "item": "Rhythm", "valueid": 2, "value": "Sinus Tac", "measuredat": 2, "registeredat": 2, "registeredby": "", "updatedat": 2, "updatedby": "", "islabresult": 0},
            ],
        )
        write_csv(
            self.raw_data / "drugitems.csv",
            [
                {"admissionid": 1, "orderid": 1, "ordercategoryid": 5, "ordercategory": "Infusion", "itemid": 20, "item": "Drug A"},
                {"admissionid": 1, "orderid": 2, "ordercategoryid": 5, "ordercategory": "Infusion", "itemid": 20, "item": "Drug A"},
            ],
        )
        write_csv(
            self.raw_data / "freetextitems.csv",
            [
                {"admissionid": 1, "itemid": 30, "item": "Free label", "value": "A", "comment": "", "measuredat": 1, "registeredat": 1, "registeredby": "", "updatedat": 1, "updatedby": "", "islabresult": 1},
                {"admissionid": 1, "itemid": 30, "item": "Free label", "value": "B", "comment": "", "measuredat": 2, "registeredat": 2, "registeredby": "", "updatedat": 2, "updatedby": "", "islabresult": 1},
            ],
        )
        write_csv(
            self.raw_data / "processitems.csv",
            [
                {"admissionid": 1, "itemid": 40, "item": "Arterial line", "start": 1, "stop": 2, "duration": 1},
                {"admissionid": 1, "itemid": 40, "item": "Arterial line", "start": 3, "stop": 4, "duration": 1},
            ],
        )
        write_csv(
            self.raw_data / "procedureorderitems.csv",
            [
                {"admissionid": 1, "orderid": 1, "ordercategoryid": 7, "ordercategoryname": "Imaging", "itemid": 50, "item": "X-ray", "registeredat": 1, "registeredby": ""},
                {"admissionid": 1, "orderid": 2, "ordercategoryid": 8, "ordercategoryname": "Lab order", "itemid": 51, "item": "Lab", "registeredat": 2, "registeredby": ""},
            ],
        )

    def test_extracts_expected_source_tokens_and_counts(self) -> None:
        config = SourceVocabConfig(pre_meds_dir=self.pre_meds, input_format="pre_meds", audit_dir=self.audit_dir)
        vocab = extract_source_vocab(config)
        self.assertEqual(list(vocab.columns), SOURCE_VOCAB_COLUMNS)
        by_token = vocab.set_index("source_token")

        self.assertEqual(by_token.loc["MEASUREMENT_BEDSIDE//1///min", "row_count"], 2)
        self.assertEqual(by_token.loc["MEASUREMENT_BEDSIDE//2//UNKNOWN", "row_count"], 1)
        self.assertEqual(by_token.loc["SUBJECT_FLUID_OUTPUT//3//ml", "row_count"], 1)
        self.assertEqual(by_token.loc["MEASUREMENT_CATEGORICAL//10//1", "row_count"], 2)
        self.assertEqual(by_token.loc["MEASUREMENT_CATEGORICAL//10//2", "row_count"], 1)
        self.assertEqual(by_token.loc["DRUG//START//5//20", "row_count"], 2)
        self.assertEqual(by_token.loc["DRUG//START//9//21", "row_count"], 1)
        self.assertEqual(by_token.loc["FREETEXT//30//1", "row_count"], 2)
        self.assertEqual(by_token.loc["PROCESS_INTERVAL//40", "row_count"], 2)
        self.assertEqual(by_token.loc["ORDER_INTENT//7//50", "row_count"], 1)


    def test_extracts_source_tokens_from_raw_amsterdam_csvs(self) -> None:
        config = SourceVocabConfig(
            pre_meds_dir=None,
            raw_data_dir=self.raw_data,
            input_format="raw",
            audit_dir=self.audit_dir,
        )
        vocab = extract_source_vocab(config)
        by_token = vocab.set_index("source_token")

        self.assertEqual(by_token.loc["MEASUREMENT_BEDSIDE//1///min", "row_count"], 2)
        self.assertEqual(by_token.loc["LAB//2//nmol/l", "row_count"], 1)
        self.assertEqual(by_token.loc["SUBJECT_FLUID_OUTPUT//3//ml", "row_count"], 1)
        self.assertEqual(by_token.loc["MEASUREMENT_CATEGORICAL//10//1", "row_count"], 1)
        self.assertEqual(by_token.loc["DRUG//START//5//20", "row_count"], 2)
        self.assertEqual(by_token.loc["FREETEXT//30//1", "row_count"], 2)
        self.assertEqual(by_token.loc["PROCESS_INTERVAL//40", "row_count"], 2)
        self.assertEqual(by_token.loc["ORDER_INTENT//7//50", "row_count"], 1)

        summary = validate_source_vocab(vocab, config)
        self.assertEqual(summary["row_count_sum"], 14)
        for table_summary in summary["tables"].values():
            self.assertTrue(table_summary["row_count_matches_input_rows"])
            self.assertEqual(table_summary["unexpected_prefixes"], [])

    def test_validation_accounts_for_every_input_row(self) -> None:
        config = SourceVocabConfig(pre_meds_dir=self.pre_meds, input_format="pre_meds", audit_dir=self.audit_dir)
        vocab = extract_source_vocab(config)
        summary = validate_source_vocab(vocab, config)
        self.assertEqual(summary["empty_source_tokens"], 0)
        self.assertEqual(summary["duplicate_source_tokens"], 0)
        self.assertEqual(summary["nonpositive_row_counts"], 0)
        for table_summary in summary["tables"].values():
            self.assertTrue(table_summary["row_count_matches_input_rows"])
            self.assertEqual(table_summary["unexpected_prefixes"], [])

    def test_reference_comparison_reports_exact_diffs(self) -> None:
        config = SourceVocabConfig(pre_meds_dir=self.pre_meds, input_format="pre_meds", audit_dir=self.audit_dir)
        vocab = extract_source_vocab(config)
        self.assertTrue(compare_to_reference(vocab, vocab.copy()).empty)

        reference = vocab.copy()
        reference.loc[reference["source_token"].eq("DRUG//START//5//20"), "row_count"] = 99
        reference = reference[~reference["source_token"].eq("FREETEXT//30//1")].copy()
        extra = reference.iloc[[0]].copy()
        extra["source_token"] = "EXTRA//TOKEN"
        reference = pd.concat([reference, extra], ignore_index=True)

        diffs = compare_to_reference(vocab, reference)
        diff_types = set(diffs["diff_type"])
        self.assertIn("field_mismatch", diff_types)
        self.assertIn("extra_in_extracted", diff_types)
        self.assertIn("missing_in_extracted", diff_types)

    def test_slurm_wrapper_shell_syntax(self) -> None:
        wrapper = PIPELINE_ROOT / "scripts/run_build_amsterdam_vocab_source_vocab.sh"
        subprocess.run(["bash", "-n", str(wrapper)], check=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
