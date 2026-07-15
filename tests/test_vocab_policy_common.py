"""Tests for shared vocabulary-policy helper functions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.tokenized.vocab_pipeline.policy_common import norm_key, norm_label_key


class PolicyCommonTests(unittest.TestCase):
    def test_norm_key_handles_null_literals_and_numeric_artifacts(self) -> None:
        for value in [None, float("nan"), pd.NA, "nan", "None", " null ", ""]:
            self.assertEqual(norm_key(value), "")

        self.assertEqual(norm_key(" 12.0 "), "12")
        self.assertEqual(norm_key(12.0), "12")
        self.assertEqual(norm_key("abc.0"), "abc.0")
        self.assertEqual(norm_key("  A label  "), "A label")

    def test_norm_label_key_is_casefolded_single_space_text(self) -> None:
        self.assertEqual(norm_label_key("  Hartritme   Sinus Tac "), "hartritme sinus tac")
        self.assertEqual(norm_label_key("None"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
