"""Tests for one-admission death assignment and metadata."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import polars as pl

from metaicu.aumcdb.tokenized.meds.anchors import anchor_and_context_events
from metaicu.aumcdb.tokenized.meds.outcomes import (
    assign_death_outcomes,
    build_admissions_metadata,
    build_subjects_metadata,
    write_cohort_metadata,
)


def admission(
    subject_id: int,
    hadm_id: int,
    admitted: datetime,
    discharged: datetime,
    death: datetime | None,
    admission_count: int = 1,
) -> dict[str, object]:
    return {
        "patientid": subject_id,
        "subject_id": subject_id,
        "admissionid": hadm_id,
        "hadm_id": hadm_id,
        "stay_id": hadm_id,
        "admissioncount": admission_count,
        "admittedattime": admitted,
        "dischargedattime": discharged,
        "dateofdeathtime": death,
        "true_los_hours": (discharged - admitted).total_seconds() / 3600,
        "split": "train",
        "gender": "Man",
        "agegroup": "60-69",
        "weightgroup": "70-79",
        "heightgroup": "170-179",
    }


class DeathOutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admissions = pl.DataFrame(
            [
                admission(
                    1,
                    10,
                    datetime(2010, 1, 1, 8),
                    datetime(2010, 1, 2, 8),
                    datetime(2010, 1, 5),
                    1,
                ),
                admission(
                    1,
                    11,
                    datetime(2010, 1, 4, 8),
                    datetime(2010, 1, 5, 15),
                    datetime(2010, 1, 5),
                    2,
                ),
                admission(
                    2,
                    20,
                    datetime(2010, 2, 1),
                    datetime(2010, 2, 2),
                    datetime(2010, 2, 2, 12),
                ),
                admission(
                    3,
                    30,
                    datetime(2010, 3, 1),
                    datetime(2010, 3, 2),
                    datetime(2010, 3, 4),
                ),
                admission(
                    4,
                    40,
                    datetime(2010, 4, 1),
                    datetime(2010, 4, 2),
                    None,
                ),
                admission(
                    5,
                    50,
                    datetime(2010, 5, 2),
                    datetime(2010, 5, 3),
                    datetime(2010, 5, 1, 16),
                ),
            ]
        )

    def test_assigns_at_most_one_death_admission_per_subject(self) -> None:
        assigned = assign_death_outcomes(self.admissions)
        emitted = assigned.filter(pl.col("death_token_emitted"))

        self.assertEqual(emitted.height, 3)
        self.assertEqual(
            emitted.select(["subject_id", "hadm_id"]).rows(),
            [(1, 11), (2, 20), (5, 50)],
        )
        during = emitted.filter(pl.col("subject_id") == 1).row(0, named=True)
        self.assertEqual(during["death_relation"], "during_icu")
        self.assertEqual(during["death_token_time"], datetime(2010, 1, 5, 15))

        within_24h = emitted.filter(pl.col("subject_id") == 2).row(0, named=True)
        self.assertEqual(within_24h["death_relation"], "within_24h_after_discharge")
        self.assertEqual(within_24h["death_token_time"], datetime(2010, 2, 2, 12))

        late = assigned.filter(pl.col("subject_id") == 3).row(0, named=True)
        self.assertEqual(late["death_relation"], "more_than_24h_after_discharge")
        self.assertFalse(late["death_token_emitted"])
        self.assertIsNone(late["death_token_time"])

    def test_anchor_events_emit_only_eligible_assigned_deaths(self) -> None:
        anchors = anchor_and_context_events(self.admissions)
        deaths = anchors.filter(pl.col("code") == "MEDS_DEATH")

        self.assertEqual(deaths.height, 3)
        self.assertEqual(
            deaths.select(["subject_id", "hadm_id", "time"]).rows(),
            [
                (1, 11, datetime(2010, 1, 5, 15)),
                (2, 20, datetime(2010, 2, 2, 12)),
                (5, 50, datetime(2010, 5, 3)),
            ],
        )

    def test_metadata_retains_late_death_without_emitting_token(self) -> None:
        admissions_meta = build_admissions_metadata(self.admissions)
        subjects_meta = build_subjects_metadata(self.admissions)

        late_admission = admissions_meta.filter(pl.col("subject_id") == 3).row(
            0, named=True
        )
        self.assertEqual(late_admission["death_time"], datetime(2010, 3, 4))
        self.assertEqual(
            late_admission["death_relation"], "more_than_24h_after_discharge"
        )
        self.assertFalse(late_admission["death_token_emitted"])

        late_subject = subjects_meta.filter(pl.col("subject_id") == 3).row(
            0, named=True
        )
        self.assertEqual(late_subject["dateofdeath"], datetime(2010, 3, 4))
        self.assertEqual(late_subject["n_admissions"], 1)

    def test_writes_canonical_parquet_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outputs = write_cohort_metadata(self.admissions, Path(tmp))
            self.assertTrue(outputs["subjects_metadata"].is_file())
            self.assertTrue(outputs["admissions_metadata"].is_file())
            self.assertEqual(
                pl.read_parquet(outputs["subjects_metadata"]).height,
                5,
            )
            self.assertEqual(
                pl.read_parquet(outputs["admissions_metadata"]).height,
                6,
            )


if __name__ == "__main__":
    unittest.main()
