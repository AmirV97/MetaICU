"""Bounded regressions for shared raw ingestion used by both AUMC branches."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
from polars.testing import assert_frame_equal


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from metaicu.aumcdb.common.raw_shards import (
    build_raw_shards_for_tables,
    raw_shards_exist,
)
from metaicu.aumcdb.common.raw_tables import load_admissions
from metaicu.aumcdb.grid.build.extract_numeric import extract_numeric_categorical
from metaicu.aumcdb.tokenized.pre_meds.large_tables import transform_table
from tests.fixtures.aumc_bounded import write_bounded_aumc_raw


class SharedAumcIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw_dir = self.root / "raw"
        self.raw_shards_dir = self.root / "raw_shards"
        write_bounded_aumc_raw(self.raw_dir)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _build_shards(self) -> dict[str, dict[str, object]]:
        return build_raw_shards_for_tables(
            tables=["numericitems", "listitems", "drugitems"],
            raw_dir=self.raw_dir,
            raw_shards_dir=self.raw_shards_dir,
            partition_rows=2,
            max_rows=None,
            rebuild=False,
        )

    def test_shared_shards_preserve_latin1_rows_and_canonical_dtypes(self) -> None:
        summary = self._build_shards()
        self.assertEqual(summary["numericitems"]["action"], "built")
        self.assertTrue(raw_shards_exist(self.raw_shards_dir, "numericitems"))

        numeric = pl.scan_parquet(str(self.raw_shards_dir / "numericitems/*.parquet")).collect()
        drug = pl.scan_parquet(str(self.raw_shards_dir / "drugitems/*.parquet")).collect()
        self.assertIn("Hartfrequentie patiënt", numeric["item"].to_list())
        self.assertIn("café", numeric["comment"].to_list())
        self.assertEqual(numeric.schema["value"], pl.Float64)
        self.assertEqual(drug.schema["doserateperkg"], pl.Int64)

        reused = self._build_shards()
        self.assertEqual(reused["numericitems"]["action"], "reused")

    def test_grid_hourly_extraction_matches_csv_and_shared_shards(self) -> None:
        self._build_shards()
        admissions = load_admissions(self.raw_dir)
        matches = {
            "hr": {
                "reconstruction_type": "direct_numeric",
                "target_unit": "/min",
                "keep_matches": [{"table": "numericitems", "itemid": "1"}],
            }
        }

        csv_numeric, _ = extract_numeric_categorical(
            matches,
            self.raw_dir,
            admissions,
            admission_ids={10, 20},
            raw_shards_dir=None,
        )
        shard_numeric, _ = extract_numeric_categorical(
            matches,
            self.raw_dir,
            admissions,
            admission_ids={10, 20},
            raw_shards_dir=self.raw_shards_dir,
        )
        columns = ["admissionid", "tag", "hour", "agg_value"]
        assert_frame_equal(
            csv_numeric.select(columns).sort(columns[:-1]),
            shard_numeric.select(columns).sort(columns[:-1]),
        )
        self.assertEqual(shard_numeric["agg_value"].sort().to_list(), [81.0, 90.0])

    def test_tokenized_premeds_rows_match_csv_and_shared_shards(self) -> None:
        self._build_shards()
        start = datetime(2003, 1, 1)
        anchors = pl.DataFrame(
            {
                "admissionid": [10, 20],
                "patientid": [1, 2],
                "subject_id": [1, 2],
                "hadm_id": [10, 20],
                "stay_id": [10, 20],
                "admittedat": [0, 0],
                "dischargedat": [7_200_000, 7_200_000],
                "admittedattime": [start, start],
                "dischargedattime": [start + timedelta(hours=2), start + timedelta(hours=2)],
            }
        )
        csv_output = self.root / "pre_meds_csv"
        shard_output = self.root / "pre_meds_shards"
        csv_acc = transform_table(
            table="numericitems",
            raw_dir=self.raw_dir,
            output_dir=csv_output,
            anchors=anchors,
            partition_rows=2,
            max_rows=None,
            overwrite=False,
            admission_ids={10},
            raw_shards_dir=None,
        )
        shard_acc = transform_table(
            table="numericitems",
            raw_dir=self.raw_dir,
            output_dir=shard_output,
            anchors=anchors,
            partition_rows=2,
            max_rows=None,
            overwrite=False,
            admission_ids={10},
            raw_shards_dir=self.raw_shards_dir,
        )

        csv_rows = pl.scan_parquet(str(csv_output / "numericitems/*.parquet")).collect()
        shard_rows = pl.scan_parquet(str(shard_output / "numericitems/*.parquet")).collect()
        sort_columns = ["admissionid", "itemid", "measuredat", "value"]
        assert_frame_equal(csv_rows.sort(sort_columns), shard_rows.sort(sort_columns))
        self.assertEqual(csv_acc.input_mode, "raw_csv_chunks")
        self.assertEqual(shard_acc.input_mode, "raw_parquet_shards")
        self.assertEqual(shard_rows.height, 2)
        self.assertEqual(shard_rows["item"].unique().to_list(), ["Hartfrequentie patiënt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
