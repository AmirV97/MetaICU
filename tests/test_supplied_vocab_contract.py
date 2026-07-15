"""Contract tests for the supplied AmsterdamUMCdb vocabulary artifact."""

from __future__ import annotations

import sys
import unittest
from importlib.resources import files
from pathlib import Path

import pandas as pd

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

SUPPLIED_VOCAB = Path(
    str(files("metaicu.aumcdb.tokenized").joinpath("data/aumc_supplied_vocab.csv"))
)
REQUIRED_COLUMNS = [
    "dataset",
    "source_table",
    "source_itemid",
    "source_valueid",
    "source_unitid",
    "source_ordercategoryid",
    "source_label",
    "source_value",
    "source_unit",
    "source_token",
    "row_count",
    "harmonized_token",
    "token_role",
    "emit_as_model_token",
    "non_drug_drugitem_class",
    "target_vocabulary",
    "target_concept_id",
    "target_code",
    "target_label",
    "mapping_source",
    "match_strength",
    "mapping_confidence",
]


def _is_true(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.lower().isin(["true", "1", "yes"])


class SuppliedVocabContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocab = pd.read_csv(SUPPLIED_VOCAB, dtype=str, keep_default_na=False, low_memory=False)
        cls.vocab["row_count_num"] = pd.to_numeric(cls.vocab["row_count"], errors="coerce").fillna(0).astype("int64")
        cls.emit = _is_true(cls.vocab["emit_as_model_token"])

    def test_supplied_vocab_exists_with_compact_schema(self) -> None:
        self.assertTrue(SUPPLIED_VOCAB.exists())
        self.assertEqual(list(self.vocab.columns.drop("row_count_num")), REQUIRED_COLUMNS)

    def test_source_tokens_are_complete_and_unique(self) -> None:
        self.assertEqual(len(self.vocab), 9014)
        self.assertEqual(self.vocab["source_token"].nunique(), 9014)
        self.assertTrue((self.vocab["row_count_num"] > 0).all())

    def test_emitted_rows_have_model_tokens_and_roles(self) -> None:
        emitted = self.vocab[self.emit]
        self.assertEqual(len(emitted), 4836)
        self.assertTrue(emitted["harmonized_token"].ne("").all())
        self.assertTrue(emitted["token_role"].ne("").all())

    def test_emitted_rows_use_canonical_omop_concept_namespace(self) -> None:
        emitted = self.vocab[self.emit]
        legacy = emitted[emitted["harmonized_token"].str.startswith("OMOP//OMOP_CONCEPT//")]
        self.assertTrue(legacy.empty)

        unresolved = self.vocab[self.vocab["harmonized_token"].str.startswith("OMOP//OMOP_CONCEPT//")]
        if not unresolved.empty:
            self.assertFalse(_is_true(unresolved["emit_as_model_token"]).any())

    def test_lab_numericitems_have_lab_role_only_by_source_prefix(self) -> None:
        lab = self.vocab[
            self.vocab["source_table"].eq("numericitems")
            & self.vocab["source_token"].str.startswith("LAB//")
            & self.emit
        ]
        self.assertEqual(len(lab), 515)
        self.assertEqual(int(lab["row_count_num"].sum()), 14301315)
        self.assertTrue(lab["token_role"].eq("dynamic_event/lab").all())

        non_lab_lab_role = self.vocab[
            ~self.vocab["source_token"].str.startswith("LAB//")
            & self.vocab["token_role"].eq("dynamic_event/lab")
        ]
        self.assertTrue(non_lab_lab_role.empty)

    def test_wondlekkage_remains_non_lab_despite_loinc_target(self) -> None:
        rows = self.vocab[self.vocab["source_label"].eq("Wondlekkage")]
        self.assertFalse(rows.empty)
        self.assertTrue(rows["target_vocabulary"].eq("LOINC").any())
        self.assertFalse(rows["token_role"].eq("dynamic_event/lab").any())

    def test_gcs_components_are_emitted_openicu_style(self) -> None:
        component_ids = {"3016335", "3026019", "3008223", "3026549", "3009094", "3013144"}
        target = self.vocab["target_concept_id"].str.replace(r"\.0$", "", regex=True)
        rows = self.vocab[self.vocab["source_table"].eq("listitems") & target.isin(component_ids)]
        self.assertEqual(len(rows), 88)
        self.assertEqual(int(rows["row_count_num"].sum()), 877730)
        self.assertTrue(_is_true(rows["emit_as_model_token"]).all())
        self.assertTrue(rows["token_role"].eq("dynamic_event/score_component").all())

        ra_verbal = rows[rows["source_label"].eq("RA_Verbal")]
        self.assertEqual(len(ra_verbal), 3)
        self.assertTrue(ra_verbal["harmonized_token"].eq("OMOP_CONCEPT//LOINC//3013144").all())

    def test_gos_outcome_rows_remain_non_emitted(self) -> None:
        gos = self.vocab[self.vocab["source_label"].eq("GOS (Glasgow Outcome Score)")]
        self.assertEqual(len(gos), 5)
        self.assertFalse(_is_true(gos["emit_as_model_token"]).any())
        self.assertTrue(gos["token_role"].eq("metadata_only").all())

    def test_freetext_and_procedure_orders_are_not_emitted(self) -> None:
        excluded = self.vocab[self.vocab["source_table"].isin(["freetextitems", "procedureorderitems"])]
        self.assertFalse(_is_true(excluded["emit_as_model_token"]).any())

    def test_known_metoprolol_conflict_is_absent(self) -> None:
        rows = self.vocab[self.vocab["source_label"].str.contains("Metoprolol|Selokeen", case=False, na=False)]
        emitted = rows[_is_true(rows["emit_as_model_token"])]
        self.assertFalse(emitted.empty)
        joined = "|".join(emitted["harmonized_token"].tolist() + emitted["target_label"].tolist())
        self.assertNotIn("pantoprazole", joined.lower())


if __name__ == "__main__":
    unittest.main()
