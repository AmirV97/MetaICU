#!/usr/bin/env bash
#SBATCH --job-name=metaicu_grid_mimic
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=00:08:00
#SBATCH --output=/msc/home/avahda55/MetaICU_outputs/logs/%x_%j.out
#SBATCH --error=/msc/home/avahda55/MetaICU_outputs/logs/%x_%j.err

set -euo pipefail

REPO=/msc/home/avahda55/MetaICU
PYTHON=/msc/home/avahda55/.venvs/ethos/.venv/bin/python

cd "$REPO"
export PYTHONPATH="$REPO/src"
export POLARS_MAX_THREADS="${SLURM_CPUS_PER_TASK:-4}"

"$PYTHON" -m metaicu.mimiciv.grid.cli.grid_build_dataset \
  paths.raw_data_dir=/msc/home/avahda55/mimic_run_f/pre_MEDS \
  paths.raw_shards_dir=/msc/home/avahda55/dataset_EDA/M4_grid/mimiciv_raw_shards \
  paths.output_dir=/msc/home/avahda55/MetaICU_outputs/mimic_iv \
  paths.audit_dir=/msc/home/avahda55/MetaICU_outputs/audits/mimic_iv \
  run.build_raw_shards=false \
  run.overwrite=true
