#!/bin/bash
#SBATCH --job-name=aumc_meds_ws
#SBATCH --output=/msc/home/avahda55/dataset_EDA/MetaICU/slurm/logs/meds_workspace_%j.out
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=180G

set -euo pipefail

PIPELINE_ROOT="${PIPELINE_ROOT:-/msc/home/avahda55/dataset_EDA/MetaICU}"
PYTHON="${PYTHON:-/msc/home/avahda55/.venvs/ethos/.venv/bin/python}"
WORKSPACE="${WORKSPACE:?Set WORKSPACE to an AUMC workspace containing data/pre-MEDS and vocab/aumc_supplied_vocab.csv}"

mkdir -p "${PIPELINE_ROOT}/slurm/logs"
export PYTHONPATH="${PIPELINE_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

echo "[meds] workspace=${WORKSPACE}"
"${PYTHON}" -m metaicu.cli.build_amsterdam_meds \
  paths.parent_dir="${WORKSPACE}" \
  run.overwrite=true

echo "[validate] checking split MEDS outputs"
"${PYTHON}" - <<'PYVALIDATE'
from pathlib import Path
import json
import os
import polars as pl

workspace = Path(os.environ["WORKSPACE"])
rows = {}
for split in ["train", "val", "test"]:
    data_path = workspace / "data/MEDS" / split / "data/0.parquet"
    debug_path = workspace / "data/MEDS" / split / "debug/0.parquet"
    summary_path = workspace / "audits/MEDS/meds" / split / "meds_summary.json"
    if not data_path.exists():
        raise SystemExit(f"Missing MEDS data file: {data_path}")
    if not debug_path.exists():
        raise SystemExit(f"Missing MEDS debug file: {debug_path}")
    if not summary_path.exists():
        raise SystemExit(f"Missing MEDS summary file: {summary_path}")
    rows[split] = pl.scan_parquet(data_path).select(pl.len()).collect().item()
    if rows[split] <= 0:
        raise SystemExit(f"Empty MEDS output for split {split}")

boundary_path = workspace / "data/metadata/numeric_quantile_boundaries.parquet"
split_summary = workspace / "audits/MEDS/meds/meds_split_summary.json"
if not boundary_path.exists():
    raise SystemExit(f"Missing numeric quantile boundaries: {boundary_path}")
if not split_summary.exists():
    raise SystemExit(f"Missing MEDS split summary: {split_summary}")

payload = {
    "workspace": str(workspace),
    "meds_rows": rows,
    "quantile_boundaries": str(boundary_path),
    "split_summary": str(split_summary),
}
print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
PYVALIDATE

echo "[done] MEDS workspace smoke passed"
