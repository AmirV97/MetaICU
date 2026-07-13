#!/bin/bash
#SBATCH --job-name=aumc_meds_1000
#SBATCH --output=/msc/home/avahda55/dataset_EDA/MetaICU/slurm/logs/meds_1000_%j.out
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=128G

mkdir -p /msc/home/avahda55/dataset_EDA/MetaICU/slurm/logs

source /msc/home/avahda55/.venvs/ethos/.venv/bin/activate

build-aumc-meds \
    paths.pre_meds_dir=/msc/home/avahda55/dataset_EDA/MetaICU/outputs/pre_meds_1000 \
    paths.vocab_path=/msc/home/avahda55/dataset_EDA/MetaICU/mappings/aumc_supplied_vocab.csv \
    paths.output_dir=/msc/home/avahda55/dataset_EDA/MetaICU/outputs/meds_1000 \
    paths.audit_dir=/msc/home/avahda55/dataset_EDA/MetaICU/outputs/audits \
    run.mode=full \
    run.overwrite=true
