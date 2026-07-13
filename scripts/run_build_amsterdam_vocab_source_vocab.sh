#!/usr/bin/env bash
# Run source-vocabulary extraction over raw AmsterdamUMCdb CSV tables.
# Submit from the MetaICU project root, or override paths below.

#SBATCH --job-name=aumc_vocab_source
#SBATCH --output=aumc_vocab_source_%j.log
#SBATCH --error=aumc_vocab_source_%j.err

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

PYTHON="${PYTHON:-python}"
INPUT_FORMAT="${INPUT_FORMAT:-raw}"
RAW_DATA_DIR="${RAW_DATA_DIR:-/msc/home/avahda55/Datasets/AmsterdamUMCdb}"
PRE_MEDS_DIR="${PRE_MEDS_DIR:-}"
AUDIT_DIR="${AUDIT_DIR:-audits}"
REFERENCE_VOCAB="${REFERENCE_VOCAB:-}"
MAX_ROWS_PER_TABLE="${MAX_ROWS_PER_TABLE:-}"

cd "${PIPELINE_ROOT}"
mkdir -p "${AUDIT_DIR}"

args=(
  scripts/build_amsterdam_vocab.py
  step=source_vocab
  source_vocab.input_format="${INPUT_FORMAT}"
  paths.audit_dir="${AUDIT_DIR}"
)

if [[ "${INPUT_FORMAT}" == "raw" ]]; then
  args+=(paths.raw_data_dir="${RAW_DATA_DIR}")
elif [[ "${INPUT_FORMAT}" == "pre_meds" ]]; then
  if [[ -z "${PRE_MEDS_DIR}" ]]; then
    echo "PRE_MEDS_DIR is required when INPUT_FORMAT=pre_meds" >&2
    exit 2
  fi
  args+=(paths.pre_meds_dir="${PRE_MEDS_DIR}")
else
  echo "Unsupported INPUT_FORMAT=${INPUT_FORMAT}; expected raw or pre_meds" >&2
  exit 2
fi

if [[ -n "${REFERENCE_VOCAB}" ]]; then
  args+=(paths.reference_vocab="${REFERENCE_VOCAB}")
fi

if [[ -n "${MAX_ROWS_PER_TABLE}" ]]; then
  args+=(source_vocab.max_rows_per_table="${MAX_ROWS_PER_TABLE}")
fi

"${PYTHON}" "${args[@]}"
