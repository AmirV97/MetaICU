"""Tests for Step 4 candidate-map construction."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.tokenized.vocab_pipeline.candidate_map import (
    CANDIDATE_COLUMNS,
    CandidateMapConfig,
    construct_candidate_map,
    load_mapping_evidence,
    load_source_vocab,
    summarize_candidates,
    unmatched_source_tokens,
    write_candidate_map_outputs,
)
from metaicu.aumcdb.tokenized.vocab_pipeline.evidence_normalization import EVIDENCE_COLUMNS
from metaicu.aumcdb.tokenized.vocab_pipeline.source_vocab import SOURCE_VOCAB_COLUMNS


PIPELINE_ROOT = Path(__file__).resolve().parents[1]


def source_row(
    table: str,
    token: str,
    itemid: str,
    label: str,
    row_count: int = 1,
    valueid: str = "",
    value: str = "",
    unitid: str = "",
    unit: str = "",
    ordercategoryid: str = "",
) -> dict[str, object]:
    return {
        "dataset": "AmsterdamUMCdb",
        "source_table": table,
        "source_itemid": itemid,
        "source_valueid": valueid,
        "source_unitid": unitid,
        "source_ordercategoryid": ordercategoryid,
        "source_label": label,
        "source_value": value,
        "source_unit": unit,
        "source_token": token,
        "row_count": row_count,
    }


def evidence_row(
    evidence_id: str,
    family: str,
    role: str,
    table: str = "",
    itemid: str = "",
    valueid: str = "",
    unitid: str = "",
    ordercategoryid: str = "",
    label: str = "",
    target_id: str = "",
) -> dict[str, str]:
    row = {col: "" for col in EVIDENCE_COLUMNS}
    row.update(
        {
            "evidence_id": evidence_id,
            "evidence_family": family,
            "evidence_source": "fixture",
            "evidence_file": "fixture.csv",
            "evidence_role": role,
            "source_table": table,
            "source_itemid": itemid,
            "source_valueid": valueid,
            "source_unitid": unitid,
            "source_ordercategoryid": ordercategoryid,
            "source_code": f"{itemid}-{valueid or unitid or ordercategoryid}".strip("-"),
            "source_vocabulary": "AUMC Fixture",
            "source_label": label,
            "target_vocabulary": "SNOMED" if target_id else "",
            "target_concept_id": target_id,
            "target_code": f"CODE-{target_id}" if target_id else "",
            "target_label": f"Target {target_id}" if target_id else "",
            "mapping_status": "APPROVED" if target_id else "UNMATCHED",
            "equivalence": "EQUAL" if target_id else "UNMATCHED",
            "match_type": "fixture",
            "evidence_text": "fixture evidence",
            "join_key_status": "explicit_columns" if table else "label_only",
        }
    )
    return row


class CandidateMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source_path = self.root / "source.csv"
        self.evidence_path = self.root / "evidence.csv"
        self.audit_dir = self.root / "audits"
        self._write_fixtures()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_fixtures(self) -> None:
        source_rows = [
            source_row("numericitems", "MEASUREMENT_BEDSIDE//1///min", "1", "Heart rate", 2, unitid="15", unit="/min"),
            source_row("listitems", "MEASUREMENT_CATEGORICAL//10//2", "10", "Rhythm", 3, valueid="2", value="Sinus Tac"),
            source_row("drugitems", "DRUG//START//5//20", "20", "Drug A", 4, value="Infusion", ordercategoryid="5"),
            source_row("drugitems", "DRUG//START//9//21", "21", "Nutrition A", 5, value="Nutrition", ordercategoryid="9"),
            source_row("freetextitems", "FREETEXT//30//1", "30", "Free label", 6),
            source_row("processitems", "PROCESS_INTERVAL//40", "40", "Arterial line", 7),
            source_row("procedureorderitems", "ORDER_INTENT//7//50", "50", "X-ray", 8, value="Imaging", ordercategoryid="7"),
            source_row("procedureorderitems", "ORDER_INTENT//8//51", "51", "Lab order", 9, value="Lab", ordercategoryid="8"),
            source_row("numericitems", "MEASUREMENT_BEDSIDE//99//kg", "99", "No evidence", 10, unitid="1", unit="kg"),
            source_row("numericitems", "MEASUREMENT_BEDSIDE//77//kg", "77", "Blended Label", 11, unitid="1", unit="kg"),
        ]
        evidence_rows = [
            evidence_row("E_NUM_UNIT", "AMSTEL mappings", "standard_mapping", "numericitems", "1", unitid="15", label="Heart rate", target_id="100"),
            evidence_row("E_NUM_ITEM", "AMSTEL source concepts", "source_metadata", "numericitems", "1", label="Heart rate", target_id="101"),
            evidence_row("E_LIST_VALUE", "AMSTEL mappings", "standard_mapping", "listitems", "10", valueid="2", label="Rhythm", target_id="200"),
            evidence_row("E_LIST_ITEM", "AmsterdamUMCdb legacy dictionary", "source_metadata", "listitems", "10", label="Rhythm", target_id="201"),
            evidence_row("E_DRUG_ORDER", "AMSTEL mappings", "standard_mapping", "drugitems", "20", ordercategoryid="5", label="Drug A", target_id="300"),
            evidence_row("E_DRUG_ITEM", "AMSTEL source concepts", "source_metadata", "drugitems", "20", label="Drug A", target_id="301"),
            evidence_row("E_DRUG_CAT", "AMSTEL source concepts", "source_metadata", "drugitems", ordercategoryid="9", label="Nutrition", target_id="0"),
            evidence_row("E_FREE", "AMSTEL mappings", "standard_mapping", "freetextitems", "30", label="Free label", target_id="400"),
            evidence_row("E_PROC", "AMSTEL mappings", "standard_mapping", "processitems", "40", label="Arterial line", target_id="500"),
            evidence_row("E_PROCEDURE_ORDER", "AMSTEL mappings", "standard_mapping", "procedureorderitems", "50", ordercategoryid="7", label="X-ray", target_id="600"),
            evidence_row("E_PROCEDURE_ITEM", "AMSTEL source concepts", "source_metadata", "procedureorderitems", "50", label="X-ray", target_id="601"),
            evidence_row("E_PROCEDURE_CAT", "AMSTEL source concepts", "source_metadata", "procedureorderitems", ordercategoryid="8", label="Lab", target_id="0"),
            evidence_row("E_LABEL", "BlendedICU user input", "clinical_context", label="Blended Label", target_id="700"),
            evidence_row("E_OMOP_ONLY", "OMOP Athena", "omop_vocab_metadata", target_id="800"),
            evidence_row("E_DUP", "AMSTEL mappings", "standard_mapping", "processitems", "40", label="Arterial line", target_id="501"),
            evidence_row("E_DUP", "BlendedICU user input", "clinical_context", label="Arterial line", target_id="501"),
        ]
        pd.DataFrame(source_rows, columns=SOURCE_VOCAB_COLUMNS).to_csv(self.source_path, index=False)
        pd.DataFrame(evidence_rows, columns=EVIDENCE_COLUMNS).to_csv(self.evidence_path, index=False)

    def test_constructs_exact_typed_and_label_context_candidates(self) -> None:
        source = load_source_vocab(self.source_path)
        evidence = load_mapping_evidence(self.evidence_path)
        candidates = construct_candidate_map(source, evidence)
        self.assertEqual(list(candidates.columns), CANDIDATE_COLUMNS)

        by_evidence = candidates.set_index("evidence_id")
        self.assertEqual(by_evidence.loc["E_NUM_UNIT", "candidate_match_method"], "numeric_item_unit")
        self.assertEqual(by_evidence.loc["E_LIST_VALUE", "candidate_match_method"], "list_item_value")
        self.assertEqual(by_evidence.loc["E_DRUG_ORDER", "candidate_match_method"], "drug_item_ordercategory")
        self.assertEqual(by_evidence.loc["E_DRUG_CAT", "candidate_match_method"], "drug_ordercategory")
        self.assertEqual(by_evidence.loc["E_FREE", "candidate_match_method"], "freetext_item")
        self.assertEqual(by_evidence.loc["E_PROC", "candidate_match_method"], "process_item")
        self.assertEqual(by_evidence.loc["E_PROCEDURE_ORDER", "candidate_match_method"], "procedure_item_ordercategory")
        self.assertEqual(by_evidence.loc["E_PROCEDURE_CAT", "candidate_match_method"], "procedure_ordercategory")
        self.assertEqual(by_evidence.loc["E_LABEL", "candidate_match_method"], "label_exact_context")
        self.assertNotIn("E_OMOP_ONLY", set(candidates["evidence_id"]))

    def test_deduplicates_to_more_specific_candidate(self) -> None:
        source = load_source_vocab(self.source_path)
        evidence = load_mapping_evidence(self.evidence_path)
        candidates = construct_candidate_map(source, evidence)
        dup = candidates[candidates["evidence_id"].eq("E_DUP")]
        self.assertEqual(len(dup), 1)
        self.assertEqual(dup.iloc[0]["source_token"], "PROCESS_INTERVAL//40")
        self.assertEqual(dup.iloc[0]["candidate_match_method"], "process_item")

    def test_summary_and_unmatched_outputs_are_consistent(self) -> None:
        source = load_source_vocab(self.source_path)
        candidates = construct_candidate_map(source, load_mapping_evidence(self.evidence_path))
        unmatched = unmatched_source_tokens(source, candidates)
        summary = summarize_candidates(source, candidates)
        self.assertIn("MEASUREMENT_BEDSIDE//99//kg", set(unmatched["source_token"]))
        self.assertEqual(summary["source_tokens_without_candidates"], len(unmatched))
        self.assertGreater(summary["candidate_rows_with_target_concept_zero"], 0)
        self.assertGreater(summary["source_tokens_with_nonzero_target_concepts"], 0)

    def test_writer_and_hydra_cli_create_expected_outputs(self) -> None:
        outputs = write_candidate_map_outputs(
            CandidateMapConfig(source_vocab=self.source_path, mapping_evidence=self.evidence_path, audit_dir=self.audit_dir)
        )
        for path in outputs.values():
            self.assertTrue(path.exists())
        written = pd.read_csv(outputs["candidates"], dtype=str, keep_default_na=False)
        self.assertIn("candidate_id", written.columns)
        self.assertTrue(written["candidate_id"].str.startswith("CANDIDATE:").all())

        cli_audit = self.root / "cli_audits"
        cmd = [
            sys.executable,
            str(PIPELINE_ROOT / "scripts/build_amsterdam_vocab.py"),
            "step=candidate_map",
            f"paths.source_vocab={self.source_path}",
            f"paths.mapping_evidence={self.evidence_path}",
            f"paths.audit_dir={cli_audit}",
        ]
        subprocess.run(cmd, cwd=PIPELINE_ROOT, check=True)
        self.assertTrue((cli_audit / "vocab_pipeline_candidates.csv").exists())
        self.assertTrue((cli_audit / "vocab_pipeline_candidate_unmatched_source_tokens.csv").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
