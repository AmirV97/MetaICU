#!/bin/bash
#SBATCH --job-name=aumc_pm_meds_1000
#SBATCH --output=/msc/home/avahda55/dataset_EDA/AUMC_pipeline/slurm/logs/premeds_meds_1000_%j.out
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=250G

set -euo pipefail

PIPELINE_ROOT="${PIPELINE_ROOT:-/msc/home/avahda55/dataset_EDA/AUMC_pipeline}"
PYTHON="${PYTHON:-/msc/home/avahda55/.venvs/ethos/.venv/bin/python}"
RAW_DATA_DIR="${RAW_DATA_DIR:-/msc/home/avahda55/Datasets/AmsterdamUMCdb}"
VOCAB_PATH="${VOCAB_PATH:-${PIPELINE_ROOT}/mappings/aumc_supplied_vocab.csv}"
WORKSPACE="${WORKSPACE:-/msc/home/avahda55/audits/aumc_premeds_meds_1000_${SLURM_JOB_ID}}"
KEEP_WORKSPACE="${KEEP_WORKSPACE:-0}"
N_PATIENTS="${N_PATIENTS:-1000}"
TRAIN_N="${TRAIN_N:-800}"
VAL_N="${VAL_N:-100}"
TEST_N="${TEST_N:-100}"

mkdir -p "${PIPELINE_ROOT}/slurm/logs"
export PIPELINE_ROOT PYTHON RAW_DATA_DIR VOCAB_PATH WORKSPACE KEEP_WORKSPACE N_PATIENTS TRAIN_N VAL_N TEST_N

cleanup() {
  if [[ "${KEEP_WORKSPACE}" != "1" && -n "${WORKSPACE}" && -d "${WORKSPACE}" ]]; then
    echo "[cleanup] removing ${WORKSPACE}"
    rm -rf "${WORKSPACE}"
  else
    echo "[cleanup] keeping ${WORKSPACE}"
  fi
}
trap cleanup EXIT

export PYTHONPATH="${PIPELINE_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

echo "[setup] workspace=${WORKSPACE}"
echo "[setup] raw=${RAW_DATA_DIR}"
echo "[setup] vocab=${VOCAB_PATH}"
rm -rf "${WORKSPACE}"
mkdir -p "${WORKSPACE}/data/raw" "${WORKSPACE}/data/metadata" "${WORKSPACE}/data/pre-MEDS" "${WORKSPACE}/data/MEDS" "${WORKSPACE}/vocab" "${WORKSPACE}/audits"

"${PYTHON}" - <<'PYSETUP'
from pathlib import Path
import os
import pandas as pd

workspace = Path(os.environ["WORKSPACE"])
raw = Path(os.environ["RAW_DATA_DIR"])
vocab = Path(os.environ["VOCAB_PATH"])
for csv in raw.glob("*.csv"):
    target = workspace / "data/raw" / csv.name
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(csv)

vocab_target = workspace / "vocab/aumc_supplied_vocab.csv"
if vocab_target.exists() or vocab_target.is_symlink():
    vocab_target.unlink()
vocab_target.symlink_to(vocab)

n_patients = int(os.environ["N_PATIENTS"])
train_n = int(os.environ["TRAIN_N"])
val_n = int(os.environ["VAL_N"])
test_n = int(os.environ["TEST_N"])
adm = pd.read_csv(raw / "admissions.csv", encoding="latin1", usecols=["patientid"])
subjects = sorted(pd.to_numeric(adm["patientid"], errors="coerce").dropna().astype("int64").drop_duplicates().tolist())[:n_patients]
if len(subjects) != n_patients:
    raise SystemExit(f"Expected {n_patients} subjects, found {len(subjects)}")
splits = ["train"] * train_n + ["val"] * val_n + ["test"] * test_n
if len(splits) != len(subjects):
    raise SystemExit(f"Split sizes {len(splits)} do not match subjects {len(subjects)}")
split = pd.DataFrame({"subject_id": subjects, "split": splits})
split.to_parquet(workspace / "data/metadata/subject_splits.parquet", index=False)
split.to_csv(workspace / "data/metadata/subject_splits.csv", index=False)
print("[setup] split counts:", split["split"].value_counts().sort_index().to_dict(), flush=True)
PYSETUP

echo "[premeds] starting bounded pre-MEDS"
"${PYTHON}" -m aumc_pipeline.cli.build_amsterdam_premeds \
  paths.parent_dir="${WORKSPACE}" \
  run.num_patients="${N_PATIENTS}" \
  run.overwrite=true

echo "[meds] starting split-aware MEDS"
"${PYTHON}" -m aumc_pipeline.cli.build_amsterdam_meds \
  paths.parent_dir="${WORKSPACE}" \
  run.overwrite=true

echo "[validate] checking split counts and outputs"
"${PYTHON}" - <<'PYVALIDATE'
from pathlib import Path
import json
import os
import polars as pl

workspace = Path(os.environ["WORKSPACE"])
expected = {
    "train": int(os.environ["TRAIN_N"]),
    "val": int(os.environ["VAL_N"]),
    "test": int(os.environ["TEST_N"]),
}
observed = {}
meds_rows = {}
for split, n in expected.items():
    patient_path = workspace / "data/pre-MEDS" / split / "patient.parquet"
    meds_path = workspace / "data/MEDS" / split / "data/0.parquet"
    debug_path = workspace / "data/MEDS" / split / "debug/0.parquet"
    if not patient_path.exists():
        raise SystemExit(f"Missing pre-MEDS patient file for {split}: {patient_path}")
    if not meds_path.exists():
        raise SystemExit(f"Missing MEDS data file for {split}: {meds_path}")
    if not debug_path.exists():
        raise SystemExit(f"Missing MEDS debug file for {split}: {debug_path}")
    patients = pl.read_parquet(patient_path)
    observed[split] = patients.select(pl.col("subject_id").n_unique()).item()
    meds_rows[split] = pl.read_parquet(meds_path).height

if observed != expected:
    raise SystemExit(f"Split patient counts mismatch: expected={expected}, observed={observed}")
if any(v <= 0 for v in meds_rows.values()):
    raise SystemExit(f"MEDS split produced empty output: {meds_rows}")

summary = {
    "workspace": str(workspace),
    "expected_patient_counts": expected,
    "observed_patient_counts": observed,
    "meds_rows": meds_rows,
    "premeds_dirs": {split: str(workspace / "data/pre-MEDS" / split) for split in expected},
    "meds_dirs": {split: str(workspace / "data/MEDS" / split) for split in expected},
}
print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
PYVALIDATE

echo "[done] bounded pre-MEDS -> MEDS smoke passed"
