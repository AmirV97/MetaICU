# AUMC Pipeline

Clean AmsterdamUMCdb ICU pipeline for vocabulary construction, split-aware pre-MEDS, and MEDS-like QC outputs.

Current main artifact:

```text
<workspace>/outputs/aumc_supplied_vocab.csv
```

## Pipeline

1. Create a workspace.
2. Retrieve GitHub externals.
3. Manually add Athena/OMOP CSVs.
4. Build the supplied vocabulary.
5. Build deterministic subject splits.
6. Build pre-MEDS, including train-derived high-frequency numeric inventory and causal mean-binned numeric outputs.
7. Build MEDS-like QC outputs.

## 1. Workspace And Code

```bash
mkdir -p /path/to/aumc_workspace
git clone https://github.com/AmirV97/AUMCdb_pipeline.git /path/to/AUMC_pipeline
cd /path/to/AUMC_pipeline
python -m pip install -e .
```

## 2. Retrieve Externals

```bash
retrieve-aumc-externals --parent-dir /path/to/aumc_workspace
```

This creates:

```text
/path/to/aumc_workspace/
├── AUMC_raw/
├── externals/
│   └── omop_vocab/
└── outputs/
```

Put the raw AmsterdamUMCdb CSV files in:

```text
/path/to/aumc_workspace/AUMC_raw/
```

## 3. Add Athena/OMOP CSVs

Download manually from:

```text
https://athena.ohdsi.org/vocabulary/list
```

Select:

```text
SNOMED
LOINC
RxNorm
RxNorm Extension
ATC
UCUM
OMOP Extension
```

Extract the Athena CSVs into:

```text
/path/to/aumc_workspace/externals/omop_vocab/
```

Required files:

```text
CONCEPT.csv
CONCEPT_RELATIONSHIP.csv
CONCEPT_ANCESTOR.csv
VOCABULARY.csv
DOMAIN.csv
RELATIONSHIP.csv
CONCEPT_CLASS.csv
CONCEPT_SYNONYM.csv
DRUG_STRENGTH.csv
```

## 4. Build Vocabulary

```bash
build-amsterdam-vocab step=build_vocab paths.parent_dir=/path/to/aumc_workspace
```

Output:

```text
/path/to/aumc_workspace/outputs/aumc_supplied_vocab.csv
```

Use `run.overwrite=true` only when intentionally replacing an existing output.

## 5. Build Subject Splits

```bash
build-aumc-split paths.parent_dir=/path/to/aumc_workspace
```

Default split is 80/10/10. Override if needed:

```bash
build-aumc-split paths.parent_dir=/path/to/aumc_workspace \
  run.train_frac=0.8 run.val_frac=0.1 run.test_frac=0.1
```

Output:

```text
/path/to/aumc_workspace/outputs/metadata/subject_splits.parquet
```

## 6. Build Pre-MEDS

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace
```

Outputs:

```text
/path/to/aumc_workspace/outputs/pre_meds/
/path/to/aumc_workspace/outputs/pre_meds/{train,val,test}/
/path/to/aumc_workspace/outputs/pre_meds/{train,val,test}/numericitems_binned/
/path/to/aumc_workspace/outputs/metadata/hf_numeric_inventory.csv
/path/to/aumc_workspace/outputs/metadata/hf_numeric_binning_summary.json
```

Useful bounded QC run:

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace \
  run.num_patients=1000 run.max_rows=1000000
```

The high-frequency inventory is built from the train split. Causal mean-binning writes `numericitems_binned` and does not modify raw `numericitems`.

## 7. Build MEDS-Like QC Outputs

For a combined pre-MEDS QC run:

```bash
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace
```

For split-specific QC using the binned numeric table:

```bash
build-aumc-meds \
  paths.pre_meds_dir=/path/to/aumc_workspace/outputs/pre_meds/train \
  paths.vocab_path=/path/to/aumc_workspace/outputs/aumc_supplied_vocab.csv \
  paths.output_dir=/path/to/aumc_workspace/outputs/meds/train \
  paths.audit_dir=/path/to/aumc_workspace/outputs/audits/meds_train
```

MEDS numeric conversion prefers `numericitems_binned` when present, otherwise falls back to raw `numericitems`.

## Current Status

Implemented:

- external retrieval/setup helper
- supplied vocabulary build/install
- deterministic subject splits
- source-preserving pre-MEDS extraction
- train-derived high-frequency numeric inventory
- causal mean-binned numeric pre-MEDS outputs
- bounded/full MEDS-like QC conversion for a supplied pre-MEDS directory

Not final yet:

- train-frozen numeric quantile boundaries across train/val/test
- one-command split-aware MEDS orchestration
- final tokenization

## Tests

```bash
python -m unittest discover -s tests -v
```

More detail:

- `docs/user_runbook.md`
- `docs/policy_decisions.md`
- `docs/amsterdam_vocab_documentation.md`
