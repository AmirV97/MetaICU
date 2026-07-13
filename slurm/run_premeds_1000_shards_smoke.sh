#!/bin/bash
#SBATCH --job-name=aumc_premeds_1000
#SBATCH --output=/msc/home/avahda55/dataset_EDA/MetaICU/slurm/logs/premeds_1000_shards_%j.out
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=250G

set -euo pipefail

PIPELINE_ROOT="${PIPELINE_ROOT:-/msc/home/avahda55/dataset_EDA/MetaICU}"
PYTHON="${PYTHON:-/msc/home/avahda55/.venvs/ethos/.venv/bin/python}"
RAW_DATA_DIR="${RAW_DATA_DIR:-/msc/home/avahda55/Datasets/AmsterdamUMCdb}"
VOCAB_PATH="${VOCAB_PATH:-${PIPELINE_ROOT}/mappings/aumc_supplied_vocab.csv}"
WORKSPACE="${WORKSPACE:-/msc/home/avahda55/audits/aumc_premeds_1000_shards_${SLURM_JOB_ID}}"
KEEP_WORKSPACE="${KEEP_WORKSPACE:-1}"
N_PATIENTS="${N_PATIENTS:-1000}"
TRAIN_N="${TRAIN_N:-800}"
VAL_N="${VAL_N:-100}"
TEST_N="${TEST_N:-100}"

mkdir -p "${PIPELINE_ROOT}/slurm/logs"
export PIPELINE_ROOT PYTHON RAW_DATA_DIR VOCAB_PATH WORKSPACE KEEP_WORKSPACE N_PATIENTS TRAIN_N VAL_N TEST_N
export PYTHONPATH="${PIPELINE_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

cleanup() {
  if [[ "${KEEP_WORKSPACE}" != "1" && -n "${WORKSPACE}" && -d "${WORKSPACE}" ]]; then
    echo "[cleanup] removing ${WORKSPACE}"
    rm -rf "${WORKSPACE}"
  else
    echo "[cleanup] keeping ${WORKSPACE}"
  fi
}
trap cleanup EXIT

echo "[setup] workspace=${WORKSPACE}"
echo "[setup] raw=${RAW_DATA_DIR}"
echo "[setup] vocab=${VOCAB_PATH}"
rm -rf "${WORKSPACE}"
mkdir -p \
  "${WORKSPACE}/data/raw" \
  "${WORKSPACE}/data/raw_shards" \
  "${WORKSPACE}/data/metadata" \
  "${WORKSPACE}/data/pre-MEDS" \
  "${WORKSPACE}/vocab" \
  "${WORKSPACE}/audits"

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

echo "[premeds] starting bounded pre-MEDS with internal raw shard cache"
"${PYTHON}" -m metaicu.cli.build_amsterdam_premeds \
  paths.parent_dir="${WORKSPACE}" \
  run.num_patients="${N_PATIENTS}" \
  run.overwrite=true

echo "[validate] checking pre-MEDS split counts, raw shard cache, and input modes"
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
summary_path = workspace / "audits/pre-MEDS/premeds_summary.json"
summary = json.loads(summary_path.read_text())

for table in ["numericitems", "listitems", "drugitems"]:
    shard_dir = workspace / "data/raw_shards" / table
    if not list(shard_dir.glob("*.parquet")):
        raise SystemExit(f"Missing raw shard parquet files for {table}: {shard_dir}")
    mode = summary["large_tables"][table]["input_mode"]
    if mode != "raw_parquet_shards":
        raise SystemExit(f"Expected raw_parquet_shards for {table}, observed {mode}")

observed = {}
for split, n in expected.items():
    patient_path = workspace / "data/pre-MEDS" / split / "patient.parquet"
    if not patient_path.exists():
        raise SystemExit(f"Missing split patient file for {split}: {patient_path}")
    patients = pl.read_parquet(patient_path)
    observed[split] = patients.select(pl.col("subject_id").n_unique()).item()

if observed != expected:
    raise SystemExit(f"Split patient counts mismatch: expected={expected}, observed={observed}")

payload = {
    "workspace": str(workspace),
    "summary": str(summary_path),
    "expected_patient_counts": expected,
    "observed_patient_counts": observed,
    "raw_shards": summary["raw_shards"],
    "large_table_input_modes": {
        table: summary["large_tables"][table]["input_mode"]
        for table in ["numericitems", "listitems", "drugitems"]
    },
    "large_table_rows_emitted": {
        table: summary["large_tables"][table]["row_counts"]["rows_emitted"]
        for table in ["numericitems", "listitems", "drugitems"]
    },
}
print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
PYVALIDATE

echo "[done] bounded pre-MEDS raw-shard smoke passed"
