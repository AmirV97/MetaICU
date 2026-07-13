"""Tests for external-resource inventory and evidence normalization."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "MetaICU/src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.vocab_pipeline.evidence_normalization import (
    EVIDENCE_COLUMNS,
    EvidenceConfig,
    normalize_mapping_evidence,
    summarize_evidence,
    write_mapping_evidence,
)
from metaicu.vocab_pipeline.resources import inventory_resources, summarize_inventory, write_resource_inventory


PIPELINE_ROOT = REPO_ROOT / "MetaICU"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_csv(path: Path, rows: list[dict[str, object]], sep: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, sep=sep)


class EvidenceNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.external_root = self.root / "external"
        self.omop_vocab = self.root / "omop_vocab"
        self.audit_dir = self.root / "audits"
        self._write_fixture_resources()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_raw_amsterdam_tables(self, raw_dir: Path) -> None:
        write_csv(
            raw_dir / "numericitems.csv",
            [
                {"admissionid": 1, "itemid": 1, "item": "Heart rate", "tag": "", "value": 80, "unitid": 15, "unit": "/min", "comment": "", "measuredat": 1, "registeredat": 1, "registeredby": "", "updatedat": 1, "updatedby": "", "islabresult": 0, "fluidout": 0},
            ],
        )
        write_csv(
            raw_dir / "listitems.csv",
            [
                {"admissionid": 1, "itemid": 10, "item": "Rhythm", "valueid": 2, "value": "Sinus Tac", "measuredat": 1, "registeredat": 1, "registeredby": "", "updatedat": 1, "updatedby": "", "islabresult": 0},
            ],
        )
        write_csv(raw_dir / "drugitems.csv", [{"admissionid": 1, "orderid": 1, "ordercategoryid": 5, "ordercategory": "Infusion", "itemid": 20, "item": "Drug A"}])
        write_csv(raw_dir / "freetextitems.csv", [{"admissionid": 1, "itemid": 30, "item": "Free label", "value": "A", "comment": "", "measuredat": 1, "registeredat": 1, "registeredby": "", "updatedat": 1, "updatedby": "", "islabresult": 1}])
        write_csv(raw_dir / "processitems.csv", [{"admissionid": 1, "itemid": 40, "item": "Arterial line", "start": 1, "stop": 2, "duration": 1}])
        write_csv(raw_dir / "procedureorderitems.csv", [{"admissionid": 1, "orderid": 1, "ordercategoryid": 7, "ordercategoryname": "Imaging", "itemid": 50, "item": "X-ray", "registeredat": 1, "registeredby": ""}])

    def _write_fixture_resources(self) -> None:
        mappings = self.external_root / "AMSTEL/data/mappings"
        source_concepts = self.external_root / "AMSTEL/data/source_concepts"
        write_csv(
            mappings / "drugitems_item.usagi.csv",
            [
                {
                    "sourceCode": "20-5",
                    "sourceName": "Drug A",
                    "matchScore": "0.9",
                    "mappingStatus": "APPROVED",
                    "equivalence": "EQUAL",
                    "conceptId": "123",
                    "conceptName": "Drug A ingredient",
                    "comment": "fixture",
                }
            ],
        )
        write_csv(
            mappings / "source_to_concept_map.csv",
            [
                {
                    "source_code": "10-2",
                    "source_concept_id": "0",
                    "source_vocabulary_id": "AUMC List",
                    "source_code_description": "Rhythm sinus tachycardia",
                    "target_concept_id": "456",
                    "target_vocabulary_id": "SNOMED",
                    "valid_start_date": "2020-01-01",
                    "valid_end_date": "2099-12-31",
                    "invalid_reason": "",
                }
            ],
        )
        write_csv(
            mappings / "source_to_value_map.csv",
            [
                {
                    "SOURCE_CODE": "10-2",
                    "SOURCE_CONCEPT_ID": "0",
                    "SOURCE_VOCABULARY_ID": "AUMC List",
                    "SOURCE_CODE_DESCRIPTION": "Rhythm",
                    "VALUE": "Sinus Tac",
                    "ROW": "1",
                }
            ],
        )
        write_text(mappings / "local_vocabularies.yaml", "AUMC List: fixture\n")
        write_csv(
            source_concepts / "listitems_value.csv",
            [
                {
                    "source_concept_id": "10-2",
                    "source_concept": "Rhythm: Sinus Tac",
                    "itemid": "10",
                    "item": "Rhythm",
                    "valueid": "2",
                    "value": "Sinus Tac",
                    "table": "listitems",
                    "concept_id": "456",
                    "concept_name": "Sinus tachycardia",
                    "vocabulary_id": "SNOMED",
                    "vocabulary_concept_code": "11092001",
                    "vocabulary_concept_name": "Sinus tachycardia",
                }
            ],
        )
        dict_dir = self.external_root / "AmsterdamUMCdb/amsterdamumcdb/dictionary"
        write_csv(
            dict_dir / "dictionary.csv",
            [
                {
                    "concept_id": "456",
                    "concept_name": "Sinus tachycardia",
                    "domain_id": "Condition",
                    "concept_class_id": "Clinical Finding",
                    "vocabulary_id": "SNOMED",
                    "concept_code": "11092001",
                    "source_vocabulary_id": "AUMC List",
                    "source_code": "10-2",
                    "source_code_description": "Rhythm: Sinus Tac",
                    "value_of_concept_id": "",
                    "value_of_source_code": "Sinus Tac",
                    "source_frequency": "3",
                    "source_frequency_validated": "3",
                    "mapping_status": "APPROVED",
                    "equivalence": "EQUAL",
                }
            ],
        )
        write_csv(
            dict_dir / "legacy/dictionary.csv",
            [
                {
                    "itemid": "10",
                    "item": "Rhythm",
                    "item_en": "Rhythm",
                    "vocabulary_id": "SNOMED",
                    "vocabulary_concept_code": "11092001",
                    "vocabulary_concept_name": "Sinus tachycardia",
                    "abbreviation": "",
                    "categoryid": "1",
                    "category": "Cardiac",
                    "category_en": "Cardiac",
                    "ordercategoryid": "",
                    "ordercategory": "",
                    "islabresult": "0",
                    "valueid": "2",
                    "value": "Sinus Tac",
                    "unitid": "",
                    "unit": "",
                    "ucum_code": "",
                    "low_normal_value": "",
                    "high_normal_value": "",
                    "expected_min_value": "",
                    "expected_max_value": "",
                    "table": "listitems",
                    "count": "3",
                    "count_validated": "3",
                }
            ],
        )
        sql_dir = self.external_root / "AmsterdamUMCdb/amsterdamumcdb/sql/flowsheets/legacy"
        for name in ["respiration", "circulation", "nephrology", "neurology"]:
            write_text(
                sql_dir / f"get_{name}_flowsheet_itemids.sql",
                """
DROP TABLE IF EXISTS fs;
CREATE TEMP TABLE fs (itemid int, item varchar(50), item_english varchar(50), itemcategory varchar(100), itemcategoryid int, label varchar(50), item_type varchar(30));
INSERT INTO fs VALUES (10, 'Rhythm', 'Rhythm', 'cardiac grouping', 1, 'rhythm', 'list');
""".strip(),
            )
        user_dir = self.external_root / "BlendedICU/auxillary_files/user_input"
        write_csv(
            user_dir / "timeseries_variables.csv",
            [
                {
                    "concept_id": "999",
                    "blended": "heart_rate",
                    "eicu": "Heart Rate",
                    "mimic4": "Heart Rate",
                    "mimic3": "Heart Rate",
                    "amsterdam": "Hartfrequentie",
                    "hirid": "Heart rate",
                    "categories": "Vitals",
                    "user_min": "0",
                    "user_max": "",
                    "is_numeric": "1",
                    "agg_method": "mean",
                    "unit_concept_id": "8541",
                }
            ],
            sep=";",
        )
        write_csv(user_dir / "medication_ingredients.csv", [{"ingredient": "procainamide"}])
        write_text(user_dir / "manual_icu_meds.csv", "procainamide;metoprolol\nPronestyl;Selokeen\n")
        write_text(user_dir / "unit_type_v2.json", json.dumps({"Medical": ["ICU"]}))
        med_dir = self.external_root / "BlendedICU/auxillary_files/medication_mapping_files"
        write_csv(med_dir / "amsterdam_medications.csv", [{"drugname": "Drug A", "count": "1"}], sep=";")
        pl.DataFrame([{"drugname": "Drug A", "count": 1.0, "dataset": "amsterdam"}]).write_parquet(med_dir / "drugnames.parquet")
        pl.DataFrame([{"concept_id": "123"}]).write_parquet(med_dir / "med_concept_ids.parquet")
        write_csv(med_dir / "ohdsi_icu_medications.csv", [{"ingredient": "procainamide"}], sep=";")
        write_text(med_dir / "medications_v10.json", "{}")
        for fname in ["eicu_medications.csv", "hirid_medications.csv", "mimic3_medications.csv", "mimic4_medications.csv"]:
            write_csv(med_dir / fname, [{"drugname": "Drug A"}], sep=";")
        write_csv(
            self.omop_vocab / "VOCABULARY.csv",
            [
                {
                    "vocabulary_id": "SNOMED",
                    "vocabulary_name": "SNOMED CT",
                    "vocabulary_reference": "fixture",
                    "vocabulary_version": "2026 fixture",
                    "vocabulary_concept_id": "1",
                }
            ],
            sep="\t",
        )
        for fname in [
            "CONCEPT.csv",
            "CONCEPT_RELATIONSHIP.csv",
            "CONCEPT_ANCESTOR.csv",
            "DOMAIN.csv",
            "RELATIONSHIP.csv",
            "CONCEPT_CLASS.csv",
            "CONCEPT_SYNONYM.csv",
            "DRUG_STRENGTH.csv",
        ]:
            write_text(self.omop_vocab / fname, "dummy\n")

    def test_build_vocab_parent_dir_uses_default_subfolders(self) -> None:
        parent_dir = self.root / "parent_workspace"
        raw_dir = parent_dir / "data/raw"
        externals = parent_dir / "externals"
        omop = externals / "omop_vocab"
        self._write_raw_amsterdam_tables(raw_dir)

        import shutil
        shutil.copytree(self.external_root, externals, dirs_exist_ok=True)
        shutil.copytree(self.omop_vocab, omop, dirs_exist_ok=True)

        cmd = [
            sys.executable,
            str(PIPELINE_ROOT / "scripts/build_amsterdam_vocab.py"),
            "step=build_vocab",
            f"paths.parent_dir={parent_dir}",
        ]
        subprocess.run(cmd, cwd=self.root, check=True)

        self.assertTrue((parent_dir / "vocab/aumc_supplied_vocab.csv").exists())
        self.assertTrue((parent_dir / "audits/vocab/build_vocab_summary.json").exists())
        self.assertTrue((parent_dir / "audits/vocab/run_config.json").exists())

    def test_build_vocab_from_outside_checkout_uses_packaged_supplied_vocab(self) -> None:
        raw_dir = self.root / "raw_amsterdam_outside"
        self._write_raw_amsterdam_tables(raw_dir)
        output_vocab = self.root / "outside_vocab/aumc_supplied_vocab.csv"

        cmd = [
            sys.executable,
            str(PIPELINE_ROOT / "scripts/build_amsterdam_vocab.py"),
            "step=build_vocab",
            f"paths.raw_data_dir={raw_dir}",
            f"paths.external_root={self.external_root}",
            f"paths.omop_vocab_dir={self.omop_vocab}",
            f"paths.output_vocab={output_vocab}",
        ]
        subprocess.run(cmd, cwd=self.root, check=True)

        self.assertTrue(output_vocab.exists())
        self.assertTrue((output_vocab.parent / "audits/build_vocab_summary.json").exists())
        self.assertTrue((output_vocab.parent / "audits/run_config.json").exists())

    def test_build_vocab_one_command_writes_vocab_and_audits(self) -> None:
        raw_dir = self.root / "raw_amsterdam"
        self._write_raw_amsterdam_tables(raw_dir)
        supplied_vocab = self.root / "supplied_vocab.csv"
        write_csv(supplied_vocab, [{"source_token": "DRUG//START//5//20", "harmonized_token": "MEDICATION//A", "emit_as_model_token": True}])
        output_vocab = self.root / "vocab/aumc_supplied_vocab.csv"
        cli_audit = self.root / "build_audits"

        cmd = [
            sys.executable,
            str(PIPELINE_ROOT / "scripts/build_amsterdam_vocab.py"),
            "step=build_vocab",
            f"paths.raw_data_dir={raw_dir}",
            f"paths.external_root={self.external_root}",
            f"paths.omop_vocab_dir={self.omop_vocab}",
            f"paths.audit_dir={cli_audit}",
            f"paths.supplied_vocab={supplied_vocab}",
            f"paths.output_vocab={output_vocab}",
        ]
        subprocess.run(cmd, cwd=PIPELINE_ROOT, check=True)

        self.assertTrue(output_vocab.exists())
        self.assertTrue((cli_audit / "build_vocab_summary.json").exists())
        self.assertTrue((cli_audit / "run_config.json").exists())
        run_config = json.loads((cli_audit / "run_config.json").read_text())
        self.assertFalse(run_config["overwrite"])
        self.assertTrue((cli_audit / "vocab_pipeline_source_vocab.csv").exists())
        self.assertTrue((cli_audit / "vocab_pipeline_mapping_evidence.csv").exists())
        self.assertTrue((cli_audit / "vocab_pipeline_candidates.csv").exists())
        copied = pd.read_csv(output_vocab)
        self.assertEqual(copied.iloc[0]["source_token"], "DRUG//START//5//20")


    def test_build_vocab_refuses_to_overwrite_existing_output_by_default(self) -> None:
        raw_dir = self.root / "raw_amsterdam_no_overwrite"
        self._write_raw_amsterdam_tables(raw_dir)
        supplied_vocab = self.root / "supplied_vocab_no_overwrite.csv"
        write_csv(supplied_vocab, [{"source_token": "DRUG//START//5//20", "harmonized_token": "MEDICATION//A", "emit_as_model_token": True}])
        output_vocab = self.root / "outputs_no_overwrite/aumc_supplied_vocab.csv"
        output_vocab.parent.mkdir(parents=True, exist_ok=True)
        output_vocab.write_text("already here\n")

        cmd = [
            sys.executable,
            str(PIPELINE_ROOT / "scripts/build_amsterdam_vocab.py"),
            "step=build_vocab",
            f"paths.raw_data_dir={raw_dir}",
            f"paths.external_root={self.external_root}",
            f"paths.omop_vocab_dir={self.omop_vocab}",
            f"paths.supplied_vocab={supplied_vocab}",
            f"paths.output_vocab={output_vocab}",
        ]
        failed = subprocess.run(cmd, cwd=PIPELINE_ROOT, capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("run.overwrite=true", failed.stderr + failed.stdout)

        overwrite_cmd = [*cmd, "run.overwrite=true"]
        subprocess.run(overwrite_cmd, cwd=PIPELINE_ROOT, check=True)
        self.assertIn("DRUG//START//5//20", output_vocab.read_text())

    def test_inventory_detects_missing_required_resources(self) -> None:
        empty_external = self.root / "empty_external"
        empty_omop = self.root / "empty_omop"
        empty_external.mkdir()
        empty_omop.mkdir()
        inventory = inventory_resources(empty_external, empty_omop)
        summary = summarize_inventory(inventory)
        self.assertGreater(summary["missing_required_resources"], 0)

    def test_inventory_records_present_resources_and_headers(self) -> None:
        inventory = inventory_resources(self.external_root, self.omop_vocab)
        summary = summarize_inventory(inventory)
        self.assertEqual(summary["missing_required_resources"], 0)
        self.assertIn("AMSTEL mappings", summary["families"])
        vocab_row = inventory[inventory["path"].str.endswith("VOCABULARY.csv")].iloc[0]
        self.assertIn("vocabulary_id", vocab_row["header_columns"])

    def test_evidence_normalization_uses_fixed_schema_and_provenance(self) -> None:
        evidence = normalize_mapping_evidence(
            EvidenceConfig(external_root=self.external_root, omop_vocab_dir=self.omop_vocab, audit_dir=self.audit_dir)
        )
        self.assertEqual(list(evidence.columns), EVIDENCE_COLUMNS)
        self.assertGreater(len(evidence), 0)
        self.assertFalse(evidence["evidence_family"].eq("").any())
        self.assertFalse(evidence["evidence_file"].eq("").any())
        self.assertIn("AMSTEL mappings", set(evidence["evidence_family"]))
        self.assertIn("AmsterdamUMCdb flowsheets", set(evidence["evidence_family"]))
        self.assertIn("BlendedICU user input", set(evidence["evidence_family"]))
        self.assertIn("OMOP Athena", set(evidence["evidence_family"]))
        self.assertTrue((evidence["evidence_role"] == "clinical_grouping").any())
        self.assertTrue((evidence["target_concept_id"] == "456").any())
        summary = summarize_evidence(evidence)
        self.assertEqual(summary["rows_missing_provenance"], 0)
        self.assertEqual(summary["non_integer_target_concept_ids"], 0)

    def test_writers_and_cli_create_expected_outputs(self) -> None:
        inv_outputs = write_resource_inventory(self.external_root, self.omop_vocab, self.audit_dir)
        ev_outputs = write_mapping_evidence(
            EvidenceConfig(external_root=self.external_root, omop_vocab_dir=self.omop_vocab, audit_dir=self.audit_dir)
        )
        for path in list(inv_outputs.values()) + list(ev_outputs.values()):
            self.assertTrue(path.exists())

        cli_audit = self.root / "cli_audits"
        cmd = [
            sys.executable,
            str(PIPELINE_ROOT / "scripts/build_amsterdam_vocab.py"),
            "step=normalize_evidence",
            f"paths.external_root={self.external_root}",
            f"paths.omop_vocab_dir={self.omop_vocab}",
            f"paths.audit_dir={cli_audit}",
        ]
        subprocess.run(cmd, cwd=PIPELINE_ROOT, check=True)
        self.assertTrue((cli_audit / "vocab_pipeline_external_resources.csv").exists())
        self.assertTrue((cli_audit / "vocab_pipeline_mapping_evidence.csv").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
