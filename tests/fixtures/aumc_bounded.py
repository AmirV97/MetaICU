"""Small Latin-1 Amsterdam raw tables shared by grid and tokenized tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="latin1")


def write_bounded_aumc_raw(raw_dir: Path) -> None:
    """Write two admissions and representative rows from all large tables."""
    _write_csv(
        raw_dir / "admissions.csv",
        [
            {
                "patientid": patient_id,
                "admissionid": admission_id,
                "admittedat": 0,
                "dischargedat": 7_200_000,
                "dateofdeath": "",
                "gender": "Man" if patient_id == 1 else "Vrouw",
                "agegroup": "60-69",
                "weightgroup": "70-79",
                "heightgroup": "170-179",
                "urgency": 1,
                "origin": "Eerste Hulp afdeling zelfde ziekenhuis",
            }
            for patient_id, admission_id in [(1, 10), (2, 20)]
        ],
    )
    _write_csv(
        raw_dir / "numericitems.csv",
        [
            {
                "admissionid": 10,
                "itemid": 1,
                "item": "Hartfrequentie patiënt",
                "tag": "",
                "value": value,
                "unitid": 15,
                "unit": "/min",
                "comment": "café",
                "measuredat": measured_at,
                "registeredat": measured_at,
                "registeredby": "",
                "updatedat": measured_at,
                "updatedby": "",
                "islabresult": 0,
                "fluidout": 0,
            }
            for measured_at, value in [(600_000, 80.0), (1_200_000, 82.0), (-1899, 999.0)]
        ]
        + [
            {
                "admissionid": 20,
                "itemid": 1,
                "item": "Hartfrequentie patiënt",
                "tag": "",
                "value": 90.0,
                "unitid": 15,
                "unit": "/min",
                "comment": "",
                "measuredat": 3_900_000,
                "registeredat": 3_900_000,
                "registeredby": "",
                "updatedat": 3_900_000,
                "updatedby": "",
                "islabresult": 0,
                "fluidout": 0,
            }
        ],
    )
    _write_csv(
        raw_dir / "listitems.csv",
        [
            {
                "admissionid": admission_id,
                "itemid": 2,
                "item": "Hartritme",
                "valueid": value_id,
                "value": value,
                "measuredat": 600_000,
                "registeredat": 600_000,
                "registeredby": "",
                "updatedat": 600_000,
                "updatedby": "",
                "islabresult": 0,
            }
            for admission_id, value_id, value in [(10, 1, "Sinusritme"), (20, 2, "Atriumfibrilleren")]
        ],
    )
    _write_csv(
        raw_dir / "drugitems.csv",
        [
            {
                "admissionid": 10,
                "orderid": 1,
                "ordercategoryid": 24,
                "ordercategory": "Injecties",
                "itemid": 3,
                "item": "Dobutamine",
                "isadditive": 0,
                "isconditional": 0,
                "rate": 1.5,
                "rateunit": "ml/h",
                "rateunitid": 1,
                "ratetimeunitid": 1,
                "doserateperkg": 0,
                "dose": 2.5,
                "doseunit": "mg",
                "doserateunit": "",
                "doseunitid": 1,
                "doserateunitid": 0,
                "administered": 2.5,
                "administeredunit": "mg",
                "administeredunitid": 1,
                "action": "start",
                "start": 600_000,
                "stop": 1_800_000,
                "duration": 1_200,
                "solutionitemid": 0,
                "solutionitem": "",
                "solutionadministered": 0.0,
                "solutionadministeredunit": "",
                "fluidin": 0.0,
                "iscontinuous": 1,
            }
        ],
    )

