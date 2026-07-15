"""Tests for causal mean-binning transform used by pre-MEDS."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import polars as pl

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.tokenized.transforms.binning import CausalMeanBinningConfig, CausalMeanBinningTransform


def fixture_numericitems() -> pl.DataFrame:
    rows = [
        (1, 10, 100, 10, 10, 1, "Dense HR", 10.0, 0),
        (1, 10, 100, 10, 10, 1, "Dense HR", 20.0, 30 * 60_000),
        (1, 10, 100, 10, 10, 1, "Dense HR", 30.0, 60 * 60_000),
        (1, 10, 100, 10, 10, 1, "Dense HR", 50.0, 90 * 60_000),
        (2, 20, 200, 20, 20, 1, "Dense HR", 100.0, 0),
        (2, 20, 200, 20, 20, 1, "Dense HR", 200.0, 30 * 60_000),
        (1, 10, 100, 10, 10, 2, "Sparse lab", 4.0, 0),
        (1, 10, 100, 10, 10, 2, "Sparse lab", 5.0, 120 * 60_000),
    ]
    return pl.DataFrame(
        rows,
        schema=[
            "patientid",
            "subject_id",
            "hadm_id",
            "stay_id",
            "admissionid",
            "itemid",
            "item",
            "value",
            "admission_relative_ms",
        ],
        orient="row",
    ).with_columns(
        [
            pl.lit(0).alias("admittedat"),
            pl.lit(24 * 60 * 60_000).alias("dischargedat"),
            pl.lit(datetime(2010, 1, 1)).alias("admittedattime"),
            pl.lit(datetime(2010, 1, 2)).alias("dischargedattime"),
            pl.col("admission_relative_ms").alias("measuredat"),
            (pl.lit(datetime(2010, 1, 1)) + pl.duration(milliseconds=pl.col("admission_relative_ms"))).alias(
                "measuredattime"
            ),
            pl.lit("AmsterdamUMCdb").alias("source_dataset"),
            pl.lit("numericitems").alias("source_table"),
        ]
    )


class CausalMeanBinningTests(unittest.TestCase):
    def test_transform_bins_dense_rows_passes_sparse_rows_and_does_not_impute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "numericitems.parquet"
            output_path = root / "numericitems_binned"
            inventory_path = root / "hf_numeric_inventory.csv"
            summary_path = root / "hf_numeric_binning_train_summary.json"
            fixture_numericitems().write_parquet(input_path)
            pl.DataFrame(
                [
                    {"itemid": 1, "row_count": 6, "is_high_resolution": True},
                    {"itemid": 2, "row_count": 2, "is_high_resolution": False},
                ]
            ).write_csv(inventory_path)

            result = CausalMeanBinningTransform(
                CausalMeanBinningConfig(
                    input_path=input_path,
                    output_path=output_path,
                    inventory_path=inventory_path,
                    summary_path=summary_path,
                    split_name="train",
                    window_minutes=60,
                    overwrite=True,
                )
            ).run()

            self.assertTrue(input_path.exists())
            self.assertTrue((output_path / "part-00000.parquet").is_file())
            self.assertTrue(result.summary_path.is_file())

            out = pl.read_parquet(output_path / "part-00000.parquet")
            dense = out.filter((pl.col("itemid") == 1) & (pl.col("admissionid") == 10)).sort(
                "admission_relative_ms"
            )
            self.assertEqual(dense["admission_relative_ms"].to_list(), [60 * 60_000, 120 * 60_000])
            self.assertEqual(dense["value"].to_list(), [15.0, 40.0])
            self.assertEqual(dense["raw_rows_in_bin"].to_list(), [2, 2])
            self.assertEqual(dense["binning_method"].unique().to_list(), ["causal_mean"])

            second_stay = out.filter((pl.col("itemid") == 1) & (pl.col("admissionid") == 20))
            self.assertEqual(second_stay["value"].to_list(), [150.0])

            sparse = out.filter(pl.col("itemid") == 2).sort("admission_relative_ms")
            self.assertEqual(sparse["value"].to_list(), [4.0, 5.0])
            self.assertEqual(sparse["binning_method"].unique().to_list(), ["raw_passthrough"])

            summary = json.loads(summary_path.read_text())
            self.assertEqual(summary["high_resolution_signal_count"], 1)
            self.assertEqual(summary["high_resolution_raw_rows"], 6)
            self.assertEqual(summary["high_resolution_binned_rows"], 3)

    def test_transform_does_not_emit_empty_bins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "numericitems.parquet"
            output_path = root / "numericitems_binned"
            inventory_path = root / "hf_numeric_inventory.csv"
            summary_path = root / "summary.json"
            fixture_numericitems().filter(pl.col("itemid") == 1).filter(pl.col("admissionid") == 10).filter(
                pl.col("admission_relative_ms").is_in([0, 30 * 60_000, 90 * 60_000])
            ).write_parquet(input_path)
            pl.DataFrame([{"itemid": 1, "row_count": 3, "is_high_resolution": True}]).write_csv(inventory_path)

            CausalMeanBinningTransform(
                CausalMeanBinningConfig(
                    input_path=input_path,
                    output_path=output_path,
                    inventory_path=inventory_path,
                    summary_path=summary_path,
                    window_minutes=60,
                    overwrite=True,
                )
            ).run()
            out = pl.read_parquet(output_path / "part-00000.parquet").sort("admission_relative_ms")
            self.assertEqual(out["admission_relative_ms"].to_list(), [60 * 60_000, 120 * 60_000])


if __name__ == "__main__":
    unittest.main(verbosity=2)
