"""Integration tests for the tokenized-output integrity audit."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from metaicu.aumcdb.tokenized.tokenization.audit import (
    FullTokenizedAudit,
    TokenizedAuditConfig,
)
from metaicu.aumcdb.tokenized.tokenization.build_workflow import (
    TokenizationConfig,
    write_tokenized_outputs,
)


def _event(subject: int, admission: int, minute: int, code: str) -> dict:
    return {
        "subject_id": subject,
        "time": datetime(2020, 1, 1) + timedelta(minutes=minute),
        "code": code,
        "numeric_value": None,
        "text_value": None,
        "hadm_id": admission,
        "icustay_id": admission,
    }


def _write_split(root: Path, split: str, rows: list[dict]) -> None:
    output = root / "data/MEDS" / split / "data"
    output.mkdir(parents=True)
    pl.DataFrame(rows).write_parquet(output / "0.parquet")


class TokenizedAuditTests(unittest.TestCase):
    def test_full_audit_reconciles_fixture_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_split(
                root,
                "train",
                [
                    _event(1, 10, 0, "ICU_ADMISSION"),
                    *[
                        _event(1, 10, 10 + index, f"LAB//A//Q{index}")
                        for index in range(1, 11)
                    ],
                    _event(1, 10, 120, "ICU_DISCHARGE"),
                ],
            )
            _write_split(root, "val", [_event(2, 20, 0, "ICU_ADMISSION")])
            _write_split(root, "test", [_event(3, 30, 0, "ICU_ADMISSION")])
            write_tokenized_outputs(
                TokenizationConfig(
                    meds_dir=root / "data/MEDS",
                    output_dir=root / "data/tokenized",
                    audit_dir=root / "audits/tokenization",
                    metadata_dir=root / "data/tokenized/metadata",
                    max_timelines_per_shard=10,
                    overwrite=True,
                )
            )

            result = FullTokenizedAudit(
                TokenizedAuditConfig(
                    parent_dir=root,
                    samples_per_split=1,
                )
            ).run()

            self.assertTrue(result["passed"])
            self.assertEqual(result["samples_checked"], 3)
            output = root / "audits/tokenization/full_integrity"
            self.assertTrue((output / "full_integrity_summary.json").is_file())
            self.assertTrue((output / "full_integrity_checks.csv").is_file())
            self.assertTrue((output / "full_integrity_failures.csv").is_file())
            self.assertTrue((output / "sequence_length_histogram.png").is_file())
            self.assertTrue((output / "timeline_duration_histogram.png").is_file())
            self.assertTrue((output / "sampled_meds_token_tracebacks.csv").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
