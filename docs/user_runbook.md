# AUMC Pipeline User Runbook

This runbook expands the README command sequence. The package currently supports:

- external resource setup
- supplied vocabulary build/install
- subject-level train/val/test split creation
- source-preserving pre-MEDS extraction
- train-derived high-frequency numeric inventory
- causal mean-binned `numericitems_binned` outputs
- MEDS-like QC conversion for a supplied pre-MEDS directory

Tokenization is not implemented yet.

## Workspace Layout

Use one workspace per run:

```text
/path/to/aumc_workspace/
├── AUMC_raw/              raw AmsterdamUMCdb CSV files
├── externals/             GitHub external resources
│   └── omop_vocab/        manually downloaded Athena/OMOP CSV export
└── outputs/               generated vocab, metadata, pre-MEDS, MEDS, audits
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
build-aumc-split paths.parent_dir=/path/to/aumc_workspace
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
/path/to/aumc_workspace/AUMC_raw/
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
/path/to/aumc_workspace/outputs/aumc_supplied_vocab.csv
```

Audit outputs are under:

```text
/path/to/aumc_workspace/outputs/audits/
```

## Splits

```bash
build-aumc-split paths.parent_dir=/path/to/aumc_workspace
```

Output:

```text
/path/to/aumc_workspace/outputs/metadata/subject_splits.parquet
```

The split is subject-level and deterministic. Defaults are 80/10/10.

## Pre-MEDS

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace
```

Pre-MEDS writes:

```text
outputs/pre_meds/                         combined source-preserving pre-MEDS
outputs/pre_meds/train|val|test/          split-specific pre-MEDS
outputs/pre_meds/train|val|test/numericitems_binned/
outputs/metadata/hf_numeric_inventory.csv
outputs/metadata/hf_numeric_binning_summary.json
outputs/audits/premeds_summary.json
```

The high-frequency inventory is fitted on train only. Causal mean-binning is then applied to each split using that frozen inventory. Empty bins are not emitted.

Useful QC run:

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace \
  run.num_patients=1000 run.max_rows=1000000
```

## MEDS-Like QC Conversion

Combined pre-MEDS QC:

```bash
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace
```

Split-specific QC:

```bash
build-aumc-meds \
  paths.pre_meds_dir=/path/to/aumc_workspace/outputs/pre_meds/train \
  paths.vocab_path=/path/to/aumc_workspace/outputs/aumc_supplied_vocab.csv \
  paths.output_dir=/path/to/aumc_workspace/outputs/meds/train \
  paths.audit_dir=/path/to/aumc_workspace/outputs/audits/meds_train
```

Numeric MEDS conversion uses `numericitems_binned` when present, otherwise raw `numericitems`.

Current MEDS quantile boundaries are fitted on the supplied cohort. Final train-frozen fit/apply boundaries are still pending before tokenization.

## Tests

```bash
cd /path/to/AUMC_pipeline
python -m unittest discover -s tests -v
```
