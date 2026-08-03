"""Small UTF-8 MIMIC-IV raw tables shared by mimiciv grid tests. Mirrors
tests/fixtures/aumc_bounded.py's role; differs where MIMIC's own pre_MEDS export differs --
gzip-compressed .csv.gz (not plain .csv), icu/hosp subdirectories, ISO timestamp strings (not
integer milliseconds), no sentinel (-1899) convention, patients.parquet carries year_of_birth
(a pre_MEDS-derived column, not raw MIMIC-IV's anchor_age)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _write_csv_gz(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, compression="gzip")


def write_bounded_mimic_raw(raw_dir: Path) -> None:
    """Write two ICU stays and representative rows from all five cached large tables, plus the
    small icustays/admissions/patients tables load_admissions() reads directly."""

    _write_csv_gz(
        raw_dir / "icu/icustays.csv.gz",
        [
            {
                "subject_id": subject_id, "hadm_id": hadm_id, "stay_id": stay_id,
                "first_careunit": "Medical ICU", "last_careunit": "Medical ICU",
                "intime": "2180-01-01 00:00:00", "outtime": "2180-01-01 02:00:00", "los": 2.0 / 24.0,
            }
            for subject_id, hadm_id, stay_id in [(1, 100, 10), (2, 200, 20)]
        ],
    )
    _write_csv_gz(
        raw_dir / "hosp/admissions.csv.gz",
        [
            {
                "subject_id": subject_id, "hadm_id": hadm_id,
                "admittime": "2180-01-01 00:00:00", "dischtime": "2180-01-01 02:00:00",
                "admission_type": "EW EMER." if subject_id == 1 else "ELECTIVE",
                "admission_location": "EMERGENCY ROOM" if subject_id == 1 else "PHYSICIAN REFERRAL",
                "discharge_location": "HOME", "insurance": "Other", "language": "English",
                "marital_status": "SINGLE", "race": "WHITE", "edregtime": "", "edouttime": "",
                "hospital_expire_flag": 0,
            }
            for subject_id, hadm_id in [(1, 100), (2, 200)]
        ],
    )
    pd.DataFrame([
        {"subject_id": 1, "gender": "M", "year_of_birth": 2120},
        {"subject_id": 2, "gender": "F", "year_of_birth": 2115},
    ]).to_parquet(raw_dir / "hosp/patients.parquet", index=False)

    _write_csv_gz(
        raw_dir / "icu/chartevents.csv.gz",
        [
            {
                "subject_id": 1, "hadm_id": 100, "stay_id": 10, "caregiver_id": 1,
                "charttime": charttime, "storetime": charttime, "itemid": 1,
                "value": str(value), "valuenum": value, "valueuom": "bpm", "warning": 0,
            }
            for charttime, value in [
                ("2180-01-01 00:10:00", 80.0),
                ("2180-01-01 00:40:00", 82.0),
                ("2179-12-31 23:00:00", 999.0),  # before intime -- must be filtered (negative admission_relative_ms)
            ]
        ]
        + [
            {
                "subject_id": 2, "hadm_id": 200, "stay_id": 20, "caregiver_id": 1,
                "charttime": "2180-01-01 01:05:00", "storetime": "2180-01-01 01:05:00", "itemid": 1,
                "value": "90.0", "valuenum": 90.0, "valueuom": "bpm", "warning": 0,
            },
            {
                # a real clinical value that happens to collide with pandas' default na_values
                # vocabulary -- regression fixture for the read_gzip_csv_batches keep_default_na
                # fix (see raw_shards.py's docstring): must round-trip as the literal string
                # "None", not become an actual null.
                "subject_id": 1, "hadm_id": 100, "stay_id": 10, "caregiver_id": 1,
                "charttime": "2180-01-01 00:20:00", "storetime": "2180-01-01 00:20:00", "itemid": 2,
                "value": "None", "valuenum": None, "valueuom": "", "warning": 0,
            },
        ],
    )
    _write_csv_gz(
        raw_dir / "hosp/labevents.csv.gz",
        [
            {
                "labevent_id": 1, "subject_id": 1, "hadm_id": 100, "specimen_id": 1, "itemid": 51301,
                "order_provider_id": "", "charttime": "2180-01-01 00:30:00", "storetime": "2180-01-01 00:30:00",
                "value": "7.5", "valuenum": 7.5, "valueuom": "K/uL", "ref_range_lower": 4.0,
                "ref_range_upper": 11.0, "flag": "", "priority": "ROUTINE", "comments": "café",
            },
        ],
    )
    _write_csv_gz(
        raw_dir / "icu/inputevents.csv.gz",
        [
            {
                "subject_id": 1, "hadm_id": 100, "stay_id": 10, "caregiver_id": 1,
                "starttime": "2180-01-01 00:10:00", "endtime": "2180-01-01 00:40:00",
                "storetime": "2180-01-01 00:10:00", "itemid": 3, "amount": 2.5, "amountuom": "mg",
                "rate": 1.5, "rateuom": "mcg/kg/min", "orderid": 1, "linkorderid": 1,
                "ordercategoryname": "01-Drips", "secondaryordercategoryname": "",
                "ordercomponenttypedescription": "Main order parameter",
                "ordercategorydescription": "Continuous Med", "patientweight": 70.0,
                "totalamount": 250.0, "totalamountuom": "ml", "isopenbag": 0, "continueinnextdept": 0,
                "statusdescription": "FinishedRunning", "originalamount": 250.0, "originalrate": 1.5,
            },
        ],
    )
    _write_csv_gz(
        raw_dir / "icu/outputevents.csv.gz",
        [
            {
                "subject_id": 1, "hadm_id": 100, "stay_id": 10, "caregiver_id": 1,
                "charttime": "2180-01-01 00:50:00", "storetime": "2180-01-01 00:50:00",
                "itemid": 226559, "value": 100.0, "valueuom": "ml",
            },
        ],
    )
    _write_csv_gz(
        raw_dir / "icu/procedureevents.csv.gz",
        [
            {
                "subject_id": 1, "hadm_id": 100, "stay_id": 10, "caregiver_id": 1,
                "starttime": "2180-01-01 00:00:00", "endtime": "2180-01-01 01:00:00",
                "storetime": "2180-01-01 00:00:00", "itemid": 225792, "value": 60.0, "valueuom": "min",
                "location": "", "locationcategory": "", "orderid": 1, "linkorderid": 1,
                "ordercategoryname": "Ventilation", "ordercategorydescription": "Task",
                "patientweight": 70.0, "isopenbag": 0, "continueinnextdept": 0,
                "statusdescription": "FinishedRunning", "originalamount": 0.0, "originalrate": 0.0,
            },
        ],
    )
