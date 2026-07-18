"""Unit tests for grid.build.derive_targets: pf_ratio / urine_rate_per_weight computation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import polars as pl

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.grid.build.derive_targets import add_derived_tte_targets


class DeriveTargetsTests(unittest.TestCase):
    def setUp(self) -> None:
        # admission 1, 4 hours: real po2/fio2 at hour 0; po2 missing at hour 1 (must null out);
        # fio2 exactly 0 at hour 2 (degenerate denominator, must null out even though both
        # constituents are technically "present"); real values again at hour 3.
        self.grid = pl.DataFrame({
            "admissionid": [1, 1, 1, 1],
            "hour": [0, 1, 2, 3],
            "po2": [90.0, None, 80.0, 100.0],
            "fio2": [30.0, 40.0, 0.0, 50.0],
            "urine_rate": [40.0, None, 20.0, 60.0],
        })
        self.admissions = pl.DataFrame({"admissionid": [1], "weight": [80.0]})

    def test_pf_ratio_null_propagation_and_zero_denominator_guard(self) -> None:
        grid, new_matches = add_derived_tte_targets(self.grid, self.admissions)
        self.assertIn("pf_ratio", new_matches)
        pf = grid.sort("hour")["pf_ratio"].to_list()
        self.assertAlmostEqual(pf[0], 90.0 / (30.0 / 100.0))   # fio2 %->fraction: 90/0.30 = 300
        self.assertIsNone(pf[1])  # po2 missing
        self.assertIsNone(pf[2])  # fio2 == 0, degenerate denominator
        self.assertAlmostEqual(pf[3], 100.0 / (50.0 / 100.0))  # 100/0.50 = 200

    def test_urine_rate_per_weight_uses_raw_unscaled_weight(self) -> None:
        grid, new_matches = add_derived_tte_targets(self.grid, self.admissions)
        self.assertIn("urine_rate_per_weight", new_matches)
        urpw = grid.sort("hour")["urine_rate_per_weight"].to_list()
        self.assertAlmostEqual(urpw[0], 40.0 / 80.0)
        self.assertIsNone(urpw[1])  # urine_rate missing
        self.assertAlmostEqual(urpw[2], 20.0 / 80.0)
        self.assertAlmostEqual(urpw[3], 60.0 / 80.0)
        # the raw `weight` helper column must not leak into the returned grid
        self.assertNotIn("weight", grid.columns)

    def test_missing_source_columns_skip_gracefully(self) -> None:
        bare_grid = pl.DataFrame({"admissionid": [1], "hour": [0]})
        grid, new_matches = add_derived_tte_targets(bare_grid, self.admissions)
        self.assertEqual(new_matches, {})
        self.assertNotIn("pf_ratio", grid.columns)
        self.assertNotIn("urine_rate_per_weight", grid.columns)


if __name__ == "__main__":
    unittest.main(verbosity=2)
