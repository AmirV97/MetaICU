"""Unit tests for grid.build.impute: presence-mask capture and the fill policies it precedes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import polars as pl

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.grid.build.impute import capture_presence_mask, impute_grid


MATCHES = {
    "hr": {"reconstruction_type": "direct_numeric"},
    "urine_rate": {"reconstruction_type": "derived_output_rate"},
    "mgcs": {"reconstruction_type": "categorical"},
    "norepi_ind": {"reconstruction_type": "treatment_indicator"},
}


class PresenceMaskTests(unittest.TestCase):
    def setUp(self) -> None:
        # admission 1, hours 0-3: hr observed at 0 and 2 (repeats its own prior value at hour 2
        # to prove the mask isn't a value-diff heuristic), never observed at hour 3 until then
        # forward-filled; mgcs/norepi_ind included to confirm they get no mask column at all.
        self.grid = pl.DataFrame({
            "admissionid": [1, 1, 1, 1],
            "hour": [0, 1, 2, 3],
            "hr": [80.0, None, 80.0, None],
            "urine_rate": [None, None, None, 50.0],
            "mgcs": ["M6_Obeys_commands", None, None, None],
            "norepi_ind": [None, None, 1, None],
        })

    def test_mask_only_added_for_continuous_reconstruction_types(self) -> None:
        grid, mask_cols = capture_presence_mask(self.grid, MATCHES)
        self.assertEqual(set(mask_cols), {"hr__observed", "urine_rate__observed"})
        self.assertNotIn("mgcs__observed", grid.columns)
        self.assertNotIn("norepi_ind__observed", grid.columns)

    def test_mask_reflects_true_nulls_not_a_value_diff_heuristic(self) -> None:
        grid, _ = capture_presence_mask(self.grid, MATCHES)
        hr_observed = grid.sort("hour")["hr__observed"].to_list()
        # hour 2 repeats hour 0's value (80.0) but was a genuine reading -- observed=1, not 0.
        self.assertEqual(hr_observed, [1, 0, 1, 0])
        urine_observed = grid.sort("hour")["urine_rate__observed"].to_list()
        self.assertEqual(urine_observed, [0, 0, 0, 1])

    def test_mask_captured_before_impute_still_shows_0_where_value_gets_filled(self) -> None:
        grid, mask_cols = capture_presence_mask(self.grid, MATCHES)
        grid = impute_grid(grid, MATCHES, scaled=True)
        grid = grid.sort("hour")
        # hour 1: forward-filled from hour 0's real 80.0 -- value present, but observed=0.
        self.assertEqual(grid["hr"].to_list(), [80.0, 80.0, 80.0, 80.0])
        self.assertEqual(grid["hr__observed"].to_list(), [1, 0, 1, 0])
        # urine_rate: 0-filled for hours 0-2 (pre-first-observation), real reading at hour 3.
        self.assertEqual(grid["urine_rate"].to_list(), [0.0, 0.0, 0.0, 50.0])
        self.assertEqual(grid["urine_rate__observed"].to_list(), [0, 0, 0, 1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
