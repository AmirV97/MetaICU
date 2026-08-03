"""Regression test: categorical mode-tie-break determinism in extract_numeric_categorical's
group_by(...).agg(pl.col("label").mode()...) step.

pl.Series.mode() returns every value tied for most-frequent, in an order that depends on
evaluation/scan order (confirmed nondeterministic under engine="streaming": re-running the same
extraction twice flipped 0.01-0.09% of hours per categorical tag on the MIMIC-IV side,
2026-08-03). .mode().first() alone is therefore nondeterministic on ties; .mode().sort().first()
breaks ties alphabetically instead, independent of row order.
"""

from __future__ import annotations

import unittest

import polars as pl


class ModeTieBreakTests(unittest.TestCase):
    def test_tied_labels_resolve_alphabetically_regardless_of_row_order(self) -> None:
        # (admissionid=1, hour=0): "b" and "a" each appear twice -- a genuine tie.
        forward = pl.DataFrame({
            "tag": ["x"] * 4, "admissionid": [1] * 4, "hour": [0] * 4,
            "label": ["b", "a", "b", "a"],
        })
        reversed_rows = forward.reverse()

        agg_forward = forward.group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("label").mode().sort().first().alias("agg_label")
        )
        agg_reversed = reversed_rows.group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("label").mode().sort().first().alias("agg_label")
        )

        self.assertEqual(agg_forward["agg_label"].to_list(), ["a"])
        self.assertEqual(agg_reversed["agg_label"].to_list(), ["a"])

    def test_non_tied_mode_is_unaffected(self) -> None:
        df = pl.DataFrame({
            "tag": ["x"] * 3, "admissionid": [1] * 3, "hour": [0] * 3,
            "label": ["a", "a", "b"],
        })
        agg = df.group_by(["tag", "admissionid", "hour"]).agg(
            pl.col("label").mode().sort().first().alias("agg_label")
        )
        self.assertEqual(agg["agg_label"].to_list(), ["a"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
