"""Patient and admissions anchor table transform for Amsterdam pre-MEDS."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


ADMISSIONS_SOURCE_COLUMNS = [
    "patientid",
    "admissionid",
    "admissioncount",
    "location",
    "urgency",
    "origin",
    "admittedat",
    "admissionyeargroup",
    "dischargedat",
    "lengthofstay",
    "destination",
    "gender",
    "agegroup",
    "dateofdeath",
    "weightgroup",
    "weightsource",
    "heightgroup",
    "heightsource",
    "specialty",
]


def load_epoch_map(epoch_map_cfg: dict[str, str]) -> dict[str, pd.Timestamp]:
    """Convert Hydra config epoch strings to Timestamps keyed by yeargroup string."""
    return {str(key): pd.Timestamp(value) for key, value in epoch_map_cfg.items()}


def read_admissions(raw_data_dir: Path) -> pd.DataFrame:
    admissions_path = raw_data_dir / "admissions.csv"
    if not admissions_path.is_file():
        raise FileNotFoundError(f"Missing Amsterdam admissions file: {admissions_path}")
    df = pd.read_csv(admissions_path, encoding="latin1", low_memory=False)
    missing_cols = sorted(set(ADMISSIONS_SOURCE_COLUMNS) - set(df.columns))
    if missing_cols:
        raise ValueError(f"admissions.csv is missing expected columns: {missing_cols}")
    return df


def add_synthetic_time(
    df: pd.DataFrame,
    source_col: str,
    epoch_map: dict[str, pd.Timestamp],
) -> pd.Series:
    """Convert a millisecond-offset column to a synthetic wall-clock datetime."""
    base = pd.to_datetime(df["admissionyeargroup"].map(epoch_map))
    offsets = pd.to_numeric(df[source_col], errors="coerce")
    return base + pd.to_timedelta(offsets, unit="ms")


def estimate_age_years(agegroup: object) -> float | None:
    if pd.isna(agegroup):
        return None
    text = str(agegroup).strip()
    m = re.fullmatch(r"(\d+)-(\d+)", text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (lo + hi) / 2
    m = re.fullmatch(r"(\d+)\+", text)
    if m:
        return float(m.group(1))
    if re.fullmatch(r"\d+", text):
        return float(text)
    return None


def build_admissions_table(
    raw: pd.DataFrame,
    epoch_map: dict[str, pd.Timestamp],
) -> pd.DataFrame:
    unknown = sorted(
        set(raw["admissionyeargroup"].dropna().astype(str)) - set(epoch_map)
    )
    if unknown:
        raise ValueError(
            f"admissionyeargroup values missing from epoch map: {unknown}"
        )
    adm = raw.copy()
    adm["subject_id"] = adm["patientid"]
    adm["hadm_id"] = adm["admissionid"]
    adm["stay_id"] = adm["admissionid"]
    adm["source_dataset"] = "AmsterdamUMCdb"
    adm["admittedattime"] = add_synthetic_time(adm, "admittedat", epoch_map)
    adm["dischargedattime"] = add_synthetic_time(adm, "dischargedat", epoch_map)
    adm["dateofdeathtime"] = add_synthetic_time(adm, "dateofdeath", epoch_map)
    adm["true_los_hours"] = (adm["dischargedat"] - adm["admittedat"]) / 3_600_000
    return adm


def build_patient_table(admissions: pd.DataFrame) -> pd.DataFrame:
    """One row per patient selected from their first (lowest admissioncount) admission."""
    first = (
        admissions
        .sort_values(["patientid", "admissioncount", "admittedat", "admissionid"])
        .drop_duplicates("patientid", keep="first")
        .copy()
    )
    # Use the earliest recorded dateofdeath across all admissions for this patient.
    death_offsets = admissions.groupby("patientid", dropna=False)["dateofdeath"].min()
    first["dateofdeath"] = first["patientid"].map(death_offsets)
    first["dateofdeathtime"] = first["admittedattime"] + pd.to_timedelta(
        pd.to_numeric(first["dateofdeath"], errors="coerce"), unit="ms"
    )
    first["age_years_approx"] = first["agegroup"].map(estimate_age_years)
    first["dateofbirth"] = first["admittedattime"] - pd.to_timedelta(
        pd.to_numeric(first["age_years_approx"], errors="coerce") * 365.25, unit="D"
    )
    first["dateofbirth_is_approx"] = first["age_years_approx"].notna()
    columns = [
        "subject_id",
        "patientid",
        "gender",
        "agegroup",
        "age_years_approx",
        "dateofbirth",
        "dateofbirth_is_approx",
        "dateofdeath",
        "dateofdeathtime",
        "admissionid",
        "admissioncount",
        "admissionyeargroup",
        "admittedattime",
        "source_dataset",
    ]
    if "split" in first.columns:
        columns.append("split")
    return first[columns].rename(
        columns={
            "admissionid": "first_admissionid",
            "admissioncount": "first_admissioncount",
            "admissionyeargroup": "first_admissionyeargroup",
            "admittedattime": "firstadmittedattime",
        }
    ).assign(source_table="admissions")


def sample_patients(admissions: pd.DataFrame, num_patients: int) -> pd.DataFrame:
    """Deterministically keep the first num_patients patientids (sorted by patientid)."""
    pids = sorted(admissions["patientid"].unique())[:num_patients]
    return admissions[admissions["patientid"].isin(set(pids))].copy()


def attach_split_manifest(
    admissions: pd.DataFrame,
    split_manifest: pd.DataFrame,
) -> pd.DataFrame:
    """Attach subject-level split labels to admissions by patientid."""
    manifest = split_manifest[["subject_id", "split"]].drop_duplicates("subject_id")
    if manifest["subject_id"].duplicated().any():
        raise ValueError("split manifest has duplicate subject_id rows")
    manifest = manifest.rename(columns={"subject_id": "patientid"})
    manifest["patientid"] = pd.to_numeric(manifest["patientid"], errors="coerce").astype("Int64")

    out = admissions.copy()
    out["patientid"] = pd.to_numeric(out["patientid"], errors="coerce").astype("Int64")
    out = out.merge(manifest, on="patientid", how="left", validate="many_to_one")
    missing = out[out["split"].isna()]["patientid"].drop_duplicates().tolist()
    if missing:
        preview = missing[:10]
        raise ValueError(
            f"split manifest is missing {len(missing)} selected patientids; "
            f"first examples: {preview}"
        )
    out["split"] = out["split"].astype(str)
    return out


def write_admissions_outputs(
    raw_data_dir: Path,
    pre_meds_dir: Path,
    epoch_map: dict[str, pd.Timestamp],
    num_patients: int | None = None,
    split_manifest: pd.DataFrame | None = None,
    split_outputs: bool = False,
) -> tuple[dict[str, Path], dict[str, int]]:
    """Build patient/admission parquet outputs; return paths and row counts."""
    raw = read_admissions(raw_data_dir)
    admissions = build_admissions_table(raw, epoch_map)

    if num_patients is not None:
        admissions = sample_patients(admissions, num_patients)

    if split_manifest is not None:
        admissions = attach_split_manifest(admissions, split_manifest)

    patient = build_patient_table(admissions)

    pre_meds_dir.mkdir(parents=True, exist_ok=True)
    admissions_path = pre_meds_dir / "admissions.parquet"
    patient_path = pre_meds_dir / "patient.parquet"
    admissions.to_parquet(admissions_path, index=False)
    patient.to_parquet(patient_path, index=False)

    paths = {"admissions": admissions_path, "patient": patient_path}
    split_counts: dict[str, dict[str, int]] = {}
    if split_outputs:
        if "split" not in admissions.columns:
            raise ValueError("split_outputs=true requires a split manifest")
        for split in sorted(admissions["split"].dropna().unique()):
            split_dir = pre_meds_dir / str(split)
            split_dir.mkdir(parents=True, exist_ok=True)
            adm_split = admissions[admissions["split"] == split]
            patient_split = patient[patient["split"] == split]
            adm_path = split_dir / "admissions.parquet"
            pat_path = split_dir / "patient.parquet"
            adm_split.to_parquet(adm_path, index=False)
            patient_split.to_parquet(pat_path, index=False)
            paths[f"{split}_admissions"] = adm_path
            paths[f"{split}_patient"] = pat_path
            split_counts[str(split)] = {
                "admissions_rows_emitted": int(len(adm_split)),
                "patient_rows_emitted": int(len(patient_split)),
                "unique_patients": int(adm_split["patientid"].nunique()),
                "unique_admissions": int(adm_split["admissionid"].nunique()),
            }

    counts = {
        "raw_admissions_rows": int(len(raw)),
        "admissions_rows_emitted": int(len(admissions)),
        "patient_rows_emitted": int(len(patient)),
        "unique_patients": int(admissions["patientid"].nunique()),
        "unique_admissions": int(admissions["admissionid"].nunique()),
        "split_counts": split_counts,
    }
    return paths, counts
