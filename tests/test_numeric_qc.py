"""Tests for tokenized.meds.numeric_qc: itemid-level corrections ported from the grid pipeline."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import polars as pl

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.tokenized.meds.numeric_qc import (
    EXCLUDED_ITEMIDS,
    apply_itemid_corrections,
    build_itemid_corrections,
)


class BuildItemidCorrectionsTests(unittest.TestCase):
    def test_pt_itemid_is_excluded(self) -> None:
        corrections = build_itemid_corrections()
        self.assertIn(6789, EXCLUDED_ITEMIDS)
        self.assertEqual(corrections[6789], {"excluded": True})

    def test_po2_kpa_itemid_gets_the_mmhg_factor(self) -> None:
        corrections = build_itemid_corrections()
        self.assertAlmostEqual(corrections[21214]["factor"], 7.50062)
        self.assertIsNone(corrections[21214]["affine"])

    def test_hba1c_itemid_gets_an_affine_not_a_factor(self) -> None:
        corrections = build_itemid_corrections()
        self.assertEqual(corrections[16166]["affine"], (0.09148, 2.152))

    def test_po2_bound_matches_plausibility_bounds(self) -> None:
        corrections = build_itemid_corrections()
        self.assertEqual((corrections[21214]["lo"], corrections[21214]["hi"]), (0.0, 700.0))


class ApplyItemidCorrectionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.df = pl.DataFrame({
            "itemid": [1, 1, 2, 2, 3, 4, 5],
            "value": [90.0, -1.0, 0.8, 40.0, 1903.0, 999.0, 50.0],
        })

    def test_factor_applied(self) -> None:
        corrections = {1: {"excluded": False, "sentinel": frozenset(), "cond_percent_threshold": None,
                            "affine": None, "factor": 10.0, "lo": None, "hi": None}}
        out = apply_itemid_corrections(self.df, corrections)
        self.assertEqual(out.filter(pl.col("itemid") == 1)["value"].to_list(), [900.0, -10.0])

    def test_affine_takes_precedence_over_factor(self) -> None:
        corrections = {1: {"excluded": False, "sentinel": frozenset(), "cond_percent_threshold": None,
                            "affine": (2.0, 3.0), "factor": 999.0, "lo": None, "hi": None}}
        out = apply_itemid_corrections(self.df, corrections)
        self.assertEqual(out.filter(pl.col("itemid") == 1)["value"].to_list(), [183.0, 1.0])

    def test_sentinel_value_dropped(self) -> None:
        corrections = {1: {"excluded": False, "sentinel": frozenset({-1.0}), "cond_percent_threshold": None,
                            "affine": None, "factor": 1.0, "lo": None, "hi": None}}
        out = apply_itemid_corrections(self.df, corrections)
        self.assertEqual(out.filter(pl.col("itemid") == 1)["value"].to_list(), [90.0])

    def test_conditional_percent_fixes_fraction_scale_only(self) -> None:
        corrections = {2: {"excluded": False, "sentinel": frozenset(), "cond_percent_threshold": 1.5,
                            "affine": None, "factor": 1.0, "lo": None, "hi": None}}
        out = apply_itemid_corrections(self.df, corrections)
        self.assertEqual(out.filter(pl.col("itemid") == 2)["value"].to_list(), [80.0, 40.0])

    def test_plausibility_bound_drops_out_of_range(self) -> None:
        corrections = {3: {"excluded": False, "sentinel": frozenset(), "cond_percent_threshold": None,
                            "affine": None, "factor": 1.0, "lo": 0.0, "hi": 20.0}}
        out = apply_itemid_corrections(self.df, corrections)
        self.assertEqual(out.filter(pl.col("itemid") == 3).height, 0)

    def test_excluded_itemid_dropped_entirely(self) -> None:
        corrections = {4: {"excluded": True}}
        out = apply_itemid_corrections(self.df, corrections)
        self.assertEqual(out.filter(pl.col("itemid") == 4).height, 0)

    def test_itemid_absent_from_corrections_passes_through(self) -> None:
        out = apply_itemid_corrections(self.df, {1: {"excluded": False, "sentinel": frozenset(),
                                                       "cond_percent_threshold": None, "affine": None,
                                                       "factor": 1.0, "lo": None, "hi": None}})
        self.assertEqual(out.filter(pl.col("itemid") == 5)["value"].to_list(), [50.0])

    def test_empty_corrections_is_noop(self) -> None:
        out = apply_itemid_corrections(self.df, {})
        self.assertEqual(out["value"].to_list(), self.df["value"].to_list())


if __name__ == "__main__":
    unittest.main(verbosity=2)
