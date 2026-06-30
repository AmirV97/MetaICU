#!/bin/bash
#SBATCH --job-name=aumc_meds_1000
#SBATCH --output=REDACTED_PATH/AUMC_pipeline/slurm/logs/meds_1000_%j.out
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=128G

mkdir -p REDACTED_PATH/AUMC_pipeline/slurm/logs

source REDACTED_PATH/.venvs/ethos/.venv/bin/activate

build-aumc-meds \
    paths.pre_meds_dir=REDACTED_PATH/AUMC_pipeline/outputs/pre_meds_1000 \
    paths.vocab_path=REDACTED_PATH/AUMC_pipeline/mappings/aumc_supplied_vocab.csv \
    paths.output_dir=REDACTED_PATH/AUMC_pipeline/outputs/meds_1000 \
    paths.audit_dir=REDACTED_PATH/AUMC_pipeline/outputs/audits \
    run.mode=full \
    run.overwrite=true
