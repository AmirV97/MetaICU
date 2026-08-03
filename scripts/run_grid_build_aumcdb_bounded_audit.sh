#!/usr/bin/env bash
#SBATCH --job-name=metaicu_aumc_qc
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=00:10:00
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
  paths.output_dir=/msc/home/avahda55/MetaICU_outputs/audits/aumcdb_bounded_output \
  paths.audit_dir=/msc/home/avahda55/MetaICU_outputs/audits/aumcdb_bounded \
  run.build_raw_shards=false \
  run.sample_size=500 \
  run.overwrite=true
