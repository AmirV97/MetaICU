#!/usr/bin/env bash
#SBATCH --job-name=aumc_samp_audit
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=REDACTED_PATH/MetaICU/slurm/logs/aumc_samp_audit_%j.out
#SBATCH --error=REDACTED_PATH/MetaICU/slurm/logs/aumc_samp_audit_%j.err

set -euo pipefail

PYTHON="${PYTHON:-REDACTED_PATH/.venvs/ethos/.venv/bin/python}"
PROJECT_DIR="${PROJECT_DIR:-REDACTED_PATH/MetaICU}"
RAW_DIR="${RAW_DIR:-REDACTED_PATH/Datasets/AmsterdamUMCdb}"
VOCAB="${VOCAB:-REDACTED_PATH/MetaICU/mappings/aumc_supplied_vocab.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-REDACTED_PATH/audits/aumc_samp_policy_audit}"
CHUNKSIZE="${CHUNKSIZE:-1000000}"

mkdir -p "${PROJECT_DIR}/slurm/logs" "${OUTPUT_DIR}"

cd "${PROJECT_DIR}"

echo "[aumc_samp_audit] started: $(date)"
echo "[aumc_samp_audit] raw dir: ${RAW_DIR}"
echo "[aumc_samp_audit] vocab: ${VOCAB}"
echo "[aumc_samp_audit] output dir: ${OUTPUT_DIR}"

"${PYTHON}" "${PROJECT_DIR}/scripts/audit_samp_policies.py" \
  --raw-dir "${RAW_DIR}" \
  --vocab "${VOCAB}" \
  --output-dir "${OUTPUT_DIR}" \
  --chunksize "${CHUNKSIZE}"

echo "[aumc_samp_audit] finished: $(date)"
