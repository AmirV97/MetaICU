#!/usr/bin/env bash
#SBATCH --job-name=metaicu_grid_aumc
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=72G
#SBATCH --time=00:15:00
#SBATCH --output=/msc/home/avahda55/MetaICU_outputs/logs/%x_%j.out
#SBATCH --error=/msc/home/avahda55/MetaICU_outputs/logs/%x_%j.err

set -euo pipefail

REPO=/msc/home/avahda55/MetaICU
PYTHON=/msc/home/avahda55/.venvs/ethos/.venv/bin/python

cd "$REPO"
export PYTHONPATH="$REPO/src"
export POLARS_MAX_THREADS="${SLURM_CPUS_PER_TASK:-4}"

"$PYTHON" -m metaicu.grid.cli.grid_build_dataset \
  dataset=aumcdb \
  paths.raw_data_dir=/msc/home/avahda55/Datasets/AmsterdamUMCdb \
  paths.raw_shards_dir=/msc/home/avahda55/Datasets/AUMCdb_tokenized_temp/data/raw_shards \
  paths.output_dir=/msc/home/avahda55/MetaICU_outputs/aumcdb \
  paths.audit_dir=/msc/home/avahda55/MetaICU_outputs/audits/aumcdb \
  run.build_raw_shards=false \
  run.overwrite=false
