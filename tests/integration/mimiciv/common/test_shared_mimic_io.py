"""Bounded regressions for shared raw ingestion used by the MIMIC-IV grid pipeline. Mirrors
tests/integration/common/test_shared_aumc_io.py's role; adapted for real differences -- UTF-8
gzip source (not Latin-1 plain CSV), ISO timestamp strings parsed to Datetime once at
shard-build time (not AUMC's already-integer-millisecond timestamps), no sentinel convention.

Includes a dedicated regression test for a real bug found while building this layer: pandas'
default na_values list treats literal strings like "None"/"NA"/"NULL" as missing, silently
nulling real MIMIC-IV clinical values (e.g. chartevents' "None" meaning "no O2 delivery
device") -- fixed via keep_default_na=False + na_values=[""] in raw_shards.read_gzip_csv_batches.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl
from polars.testing import assert_frame_equal


from metaicu.mimiciv.common.raw_shards import build_raw_shards_for_tables, raw_shards_exist
from metaicu.mimiciv.common.raw_tables import load_admissions, raw_table_input_mode
from metaicu.mimiciv.grid.build.extract_numeric import extract_numeric_categorical
from tests.fixtures.mimic_bounded import write_bounded_mimic_raw


TABLE_FILES = {
    "chartevents": "icu/chartevents.csv.gz",
    "labevents": "hosp/labevents.csv.gz",
    "inputevents": "icu/inputevents.csv.gz",
}


class SharedMimicIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw_dir = self.root / "raw"
        self.raw_shards_dir = self.root / "raw_shards"
        write_bounded_mimic_raw(self.raw_dir)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _build_shards(self) -> dict[str, dict[str, object]]:
        return build_raw_shards_for_tables(
            tables=TABLE_FILES,
            raw_data_dir=self.raw_dir,
            raw_shards_dir=self.raw_shards_dir,
            partition_rows=2,
            max_rows=None,
            rebuild=False,
        )

    def test_raw_table_input_mode_reports_correctly(self) -> None:
        self.assertEqual(raw_table_input_mode("chartevents", None), "raw_csv_scan")
        self.assertEqual(raw_table_input_mode("chartevents", self.raw_shards_dir), "raw_csv_scan")
        self._build_shards()
        self.assertTrue(raw_shards_exist(self.raw_shards_dir, "chartevents"))
        self.assertEqual(raw_table_input_mode("chartevents", self.raw_shards_dir), "raw_parquet_shards")

    def test_shared_shards_preserve_utf8_rows_and_parse_timestamps_at_build_time(self) -> None:
        summary = self._build_shards()
        self.assertEqual(summary["chartevents"]["action"], "built")

        labevents = pl.scan_parquet(str(self.raw_shards_dir / "labevents/*.parquet")).collect()
        self.assertIn("café", labevents["comments"].to_list())
        self.assertEqual(labevents.schema["valuenum"], pl.Float64)
        # timestamps are parsed to Datetime ONCE at shard-build time, not left as raw ISO strings
        chartevents = pl.scan_parquet(str(self.raw_shards_dir / "chartevents/*.parquet")).collect()
        self.assertEqual(chartevents.schema["charttime"], pl.Datetime)

        reused = self._build_shards()
        self.assertEqual(reused["chartevents"]["action"], "reused")

    def test_literal_none_and_na_strings_are_not_corrupted_to_null(self) -> None:
        # regression test for the read_gzip_csv_batches na_values bug -- see module docstring.
        self._build_shards()
        chartevents = pl.scan_parquet(str(self.raw_shards_dir / "chartevents/*.parquet")).collect()
        none_row = chartevents.filter(pl.col("itemid") == 2)
        self.assertEqual(none_row.height, 1)
        self.assertEqual(none_row["value"].to_list(), ["None"])
        self.assertFalse(none_row["value"].is_null().any())
        # a genuinely empty numeric field (valuenum for this same row) must still be a real null.
        self.assertTrue(none_row["valuenum"].is_null().all())

    def test_grid_hourly_extraction_matches_csv_scan_and_shared_shards(self) -> None:
        self._build_shards()
        admissions = load_admissions(self.raw_dir)
        matches = {
            "hr": {
                "reconstruction_type": "direct_numeric",
                "target_unit": "bpm",
                "keep_matches": [{"table": "chartevents", "itemid": "1"}],
            }
        }

        csv_numeric, _ = extract_numeric_categorical(
            matches, self.raw_dir, admissions, admission_ids={10, 20}, raw_shards_dir=None,
        )
        shard_numeric, _ = extract_numeric_categorical(
            matches, self.raw_dir, admissions, admission_ids={10, 20}, raw_shards_dir=self.raw_shards_dir,
        )
        columns = ["admissionid", "tag", "hour", "agg_value"]
        assert_frame_equal(
            csv_numeric.select(columns).sort(columns[:-1]),
            shard_numeric.select(columns).sort(columns[:-1]),
        )
        # admission 10's pre-intime row (itemid 1, value 999.0) must be filtered out of both
        # paths (negative admission_relative_ms) -- only the two real readings survive.
        self.assertEqual(shard_numeric["agg_value"].sort().to_list(), [81.0, 90.0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
