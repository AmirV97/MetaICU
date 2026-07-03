#!/usr/bin/env bash
#SBATCH --job-name=aumc_bounded_pipeline
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=08:00:00
#SBATCH --output=/msc/home/avahda55/dataset_EDA/audits/aumc_bounded_pipeline_%j.log

set -euo pipefail

PYTHON="/msc/home/avahda55/.venvs/ethos/.venv/bin/python"
PARENT_DIR="/msc/home/avahda55/dataset_EDA/audits/aumc_bounded_pipeline_${SLURM_JOB_ID}"
RAW_DIR="/msc/home/avahda55/Datasets/AmsterdamUMCdb"
EXTERNAL_ROOT="/msc/home/avahda55/dataset_EDA/amsterdam_external"
OMOP_VOCAB_DIR="/msc/home/avahda55/dataset_EDA/omop_vocab"

mkdir -p "${PARENT_DIR}/data" "${PARENT_DIR}/externals" "${PARENT_DIR}/vocab"
ln -sfn "${RAW_DIR}" "${PARENT_DIR}/data/raw"
ln -sfn "${EXTERNAL_ROOT}" "${PARENT_DIR}/externals/amsterdam_external"
ln -sfn "${OMOP_VOCAB_DIR}" "${PARENT_DIR}/externals/omop_vocab"
cp -f mappings/aumc_supplied_vocab.csv "${PARENT_DIR}/vocab/aumc_supplied_vocab.csv"

echo "[1/3] pre-MEDS bounded run"
"${PYTHON}" -m aumc_pipeline.cli.build_amsterdam_premeds \
  paths.parent_dir="${PARENT_DIR}" \
  run.num_patients=1000 \
  run.overwrite=true

echo "[2/3] MEDS split-aware run"
"${PYTHON}" -m aumc_pipeline.cli.build_amsterdam_meds \
  paths.parent_dir="${PARENT_DIR}" \
  run.mode=bounded \
  run.split_outputs=true \
  run.overwrite=true

echo "[3/3] tokenization run"
"${PYTHON}" -m aumc_pipeline.cli.build_amsterdam_tokenized \
  paths.parent_dir="${PARENT_DIR}" \
  run.analysis_unit=stay \
  run.overwrite=true

echo "DONE"
echo "Workspace: ${PARENT_DIR}"
