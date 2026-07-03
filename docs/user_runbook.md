# AUMC Pipeline User Runbook

This runbook expands the README command sequence. The package currently supports:

- external resource setup
- supplied vocabulary build/install
- subject-level train/val/test split creation
- source-preserving pre-MEDS extraction
- train-derived high-frequency numeric inventory
- causal mean-binned `numericitems_binned` outputs
- MEDS-like QC conversion for a supplied pre-MEDS directory
- ETHOS-style tokenized safetensor outputs

## Workspace Layout

Use one workspace per run:

```text
/path/to/aumc_workspace/
├── data/
│   ├── raw/              raw AmsterdamUMCdb CSV files
│   ├── raw_shards/       internal schema-cast parquet cache for large raw tables
│   ├── pre-MEDS/         pre-MEDS parquet outputs
│   ├── MEDS/             MEDS-like parquet outputs
│   ├── tokenized/        tokenized safetensor outputs
│   └── metadata/         splits, high-frequency inventory, quantile boundaries
├── externals/            GitHub external resources
│   └── omop_vocab/       manually downloaded Athena/OMOP CSV export
├── vocab/                supplied vocabulary artifact
└── audits/               audit JSON/CSV outputs
```

## Install

```bash
git clone https://github.com/AmirV97/AUMCdb_pipeline.git /path/to/AUMC_pipeline
cd /path/to/AUMC_pipeline
python -m pip install -e .
```

Main CLI entry points:

```bash
retrieve-aumc-externals --parent-dir /path/to/aumc_workspace
build-amsterdam-vocab step=build_vocab paths.parent_dir=/path/to/aumc_workspace
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace
```

## Inputs

Run external retrieval first:

```bash
retrieve-aumc-externals --parent-dir /path/to/aumc_workspace
```

Then place or symlink raw AmsterdamUMCdb CSVs into:

```text
/path/to/aumc_workspace/data/raw/
```

Download Athena/OMOP manually from:

```text
https://athena.ohdsi.org/vocabulary/list
```

Select SNOMED, LOINC, RxNorm, RxNorm Extension, ATC, UCUM, and OMOP Extension. Extract the CSVs into:

```text
/path/to/aumc_workspace/externals/omop_vocab/
```

## Vocabulary

```bash
build-amsterdam-vocab step=build_vocab paths.parent_dir=/path/to/aumc_workspace
```

Output:

```text
/path/to/aumc_workspace/vocab/aumc_supplied_vocab.csv
```

Audit outputs are under:

```text
/path/to/aumc_workspace/audits/
```

## Pre-MEDS

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace
```

Pre-MEDS creates or reuses `data/metadata/subject_splits.parquet` using the default 80/10/10 subject split, then writes:

```text
data/metadata/subject_splits.parquet   deterministic subject split
data/raw_shards/                       reusable raw parquet cache for large tables
data/pre-MEDS/                         combined source-preserving pre-MEDS
data/pre-MEDS/train|val|test/          split-specific pre-MEDS
data/pre-MEDS/train|val|test/numericitems_binned/
data/metadata/hf_numeric_inventory.csv
data/metadata/hf_numeric_binning_summary.json
audits/pre-MEDS/premeds_summary.json
```

The raw shard cache is source-preserving and internal to pre-MEDS: no patient filtering, vocab decisions, sentinel drops, or time transforms are applied there. The high-frequency inventory is fitted on train only. Causal mean-binning is then applied to each split using that frozen inventory. Rare-but-dense numeric variables, such as CRRT settings that appear in few stays but are very dense when present, are also flagged for binning; the default rare-dense gate requires 2 sampled admission/item groups plus a high row burden and a high-frequency CI above the threshold. Empty bins are not emitted.

Selected repeated categorical state streams are state-change deduplicated in pre-MEDS. Defaults include ventilation mode, CRRT modality, rhythm, oxygen/admin route, NIV program status, sputum state, pupil state, selected score components/final scores, ectopy, chest-drain state, and EVD state. The policy keeps the first value and later value changes per admission/item.

Useful QC run:

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace \
  run.num_patients=1000 run.max_rows=1000000
```

## MEDS-Like QC Conversion

Split-aware MEDS conversion:

```bash
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace
```

When split pre-MEDS folders exist, this writes `data/MEDS/{train,val,test}/`. Numeric quantile boundaries are fit on train only, saved to `data/metadata/numeric_quantile_boundaries.parquet`, and reused for all splits.

One-cohort QC is still available:

```bash
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace run.split_outputs=false
```

Numeric MEDS conversion uses `numericitems_binned` when present, otherwise raw `numericitems`.

## Tokenization

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace
```

This builds the token vocabulary from `data/MEDS/train` only and reuses that frozen vocabulary for `val` and `test`.
Codes seen only in `val` or `test` are mapped to the frozen `UNK` token and recorded in the tokenization unknown-code audit.

Outputs:

```text
data/tokenized/train|val|test/*.safetensors
data/tokenized/train/vocab_t*.csv
data/tokenized/train/vocab_decoded.csv
data/tokenized/train/code_counts.csv
data/tokenized/train/interval_estimates.json
data/tokenized/metadata/codes.parquet
data/tokenized/metadata/timeline_index.parquet
audits/tokenization/tokenization_summary.json
```

Each tokenized timeline is one ICU admission/stay, keyed by `(subject_id, hadm_id)`. Multi-admission patients therefore produce multiple timelines, but patient/admission identity is preserved through `patient_ids`, `hadm_id`, `icustay_id`, and `timeline_index.parquet`.

The tokenized unit of analysis is configurable:

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace run.analysis_unit=stay
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace run.analysis_unit=subject
```

`stay` is the default and writes one timeline per ICU admission/stay. `subject` writes one timeline per patient, concatenating that patient's admissions chronologically. Per-token `hadm_id` and `icustay_id` are still stored, so admission identity remains recoverable.

Medication ATC detail can be coarsened at tokenization time:

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace run.medication_atc_depth=2
```

## Tests

```bash
cd /path/to/AUMC_pipeline
python -m unittest discover -s tests -v
```

## Next Development Tasks

- Re-run bounded pre-MEDS -> MEDS -> tokenization QC after the aggressive rare-dense binning default. Confirm whether CRRT dilution/flow streams are now binned rather than raw-passthrough.
- Decide the policy for any remaining super-long ICU stays before full tokenization runs. Some stays are genuinely long, e.g. 37-95 ICU days, so hourly data alone can still produce long sequences.
