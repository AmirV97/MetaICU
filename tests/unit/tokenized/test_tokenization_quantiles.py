"""Unit tests for compositional numeric quantile token expansion."""

from __future__ import annotations

import unittest

from metaicu.aumcdb.tokenized.tokenization.build_workflow import (
    _expand_fused_quantile_code,
)


class QuantileTokenExpansionTests(unittest.TestCase):
    def test_valid_fused_quantile_code_becomes_identity_value_pair(self) -> None:
        self.assertEqual(
            _expand_fused_quantile_code("OMOP_CONCEPT//LOINC//1234//Q10"),
            ("OMOP_CONCEPT//LOINC//1234", "Q10"),
        )

    def test_non_quantile_suffixes_are_not_split(self) -> None:
        for code in ("OMOP_CONCEPT//LOINC//1234//Q0", "CODE//Q11", "ICD//CM//Q_FEVER", "Q3"):
            with self.subTest(code=code):
                self.assertEqual(_expand_fused_quantile_code(code), (code,))


if __name__ == "__main__":
    unittest.main()
