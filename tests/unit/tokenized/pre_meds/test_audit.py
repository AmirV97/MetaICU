"""Tests for pre-MEDS integrity-audit output formatting."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from metaicu.aumcdb.tokenized.pre_meds.audit import _checks_frame


class AuditOutputTests(unittest.TestCase):
    def test_checks_frame_serializes_mixed_values_for_csv(self):
        checks = [
            {
                "category": "row_accounting",
                "check": "row_count",
                "passed": True,
                "observed": 10,
                "expected": 10,
                "detail": "",
            },
            {
                "category": "split_manifest",
                "check": "split_names",
                "passed": True,
                "observed": ["test", "train", "val"],
                "expected": {"splits": 3},
                "detail": "mixed values",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "checks.csv"
            frame = _checks_frame(checks)
            frame.write_csv(output)

            self.assertEqual(
                frame["observed"].to_list(),
                ["10", '["test", "train", "val"]'],
            )
            self.assertEqual(json.loads(frame["expected"][1]), {"splits": 3})
            self.assertTrue(
                output.read_text().startswith(
                    "category,check,passed,observed,expected,detail\n"
                )
            )

    def test_checks_frame_writes_empty_failure_table_with_headers(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "failures.csv"
            _checks_frame([]).write_csv(output)

            self.assertEqual(
                output.read_text(),
                "category,check,passed,observed,expected,detail\n",
            )
