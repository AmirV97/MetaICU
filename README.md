# MetaICU

Clean AmsterdamUMCdb ICU pipeline for vocabulary construction, split-aware pre-MEDS, MEDS-like outputs, and ETHOS-style tokenized timelines.

Current main artifact:

```text
<workspace>/vocab/aumc_supplied_vocab.csv
```

## Pipeline

1. Create a workspace.
2. Retrieve GitHub externals.
3. Manually add Athena/OMOP CSVs.
4. Build the supplied vocabulary.
5. Optionally build the iCareFM-style grid feature manifest.
6. Build pre-MEDS, including deterministic subject splits, train-derived high-frequency numeric inventory, and causal mean-binned numeric outputs.
7. Build MEDS-like outputs.
8. Build tokenized safetensors.

## 1. Workspace And Code

```bash
mkdir -p /path/to/aumc_workspace
git clone https://github.com/AmirV97/MetaICU.git /path/to/MetaICU
cd /path/to/MetaICU
python -m pip install -e .
```

## 2. Retrieve Externals

```bash
retrieve-aumc-externals --parent-dir /path/to/aumc_workspace
```

This creates:

```text
/path/to/aumc_workspace/
├── data/
│   ├── raw/
│   ├── raw_shards/
│   ├── pre-MEDS/
│   ├── MEDS/
│   ├── tokenized/
│   └── metadata/
├── externals/
│   └── omop_vocab/
├── vocab/
└── audits/
```

Put the raw AmsterdamUMCdb CSV files in:

```text
/path/to/aumc_workspace/data/raw/
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
/path/to/aumc_workspace/vocab/aumc_supplied_vocab.csv
```

Use `run.overwrite=true` only when intentionally replacing an existing output.

## 5. Optional Grid Feature Manifest

```bash
grid_build_manifest paths.parent_dir=/path/to/aumc_workspace
```

Output:

```text
/path/to/aumc_workspace/grid/aumc_grid_feature_manifest.csv
/path/to/aumc_workspace/audits/grid_manifest/
```

This is stage 1 of the iCareFM-style hourly-grid fork. It uses the packaged 129-row Table S3 feature seed, the source/supplied vocabulary artifacts, and OpenICU mappings when available. It does not scan raw AUMC rows or build the hourly grid dataset.

## 6. Build Pre-MEDS

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace
```

This creates or reuses the deterministic 80/10/10 subject split at:

```text
/path/to/aumc_workspace/data/metadata/subject_splits.parquet
```

It also creates or reuses schema-cast parquet caches for large raw tables under:

```text
/path/to/aumc_workspace/data/raw_shards/
```

These raw shards are an internal pre-MEDS cache. They preserve source rows and make later bounded/split pre-MEDS runs avoid rescanning the large raw CSVs.

Override split fractions if needed:

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace \
  split.train_frac=0.8 split.val_frac=0.1 split.test_frac=0.1
```

Outputs:

```text
/path/to/aumc_workspace/data/pre-MEDS/
/path/to/aumc_workspace/data/pre-MEDS/{train,val,test}/
/path/to/aumc_workspace/data/pre-MEDS/{train,val,test}/numericitems_binned/
/path/to/aumc_workspace/data/metadata/hf_numeric_inventory.csv
/path/to/aumc_workspace/data/metadata/hf_numeric_binning_summary.json
```

Useful bounded QC run:

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace \
  run.num_patients=1000 run.max_rows=1000000
```

The high-frequency inventory is built from the train split. Causal mean-binning writes `numericitems_binned` and does not modify raw `numericitems`. Rare-but-dense numeric streams, such as CRRT settings that appear in few stays but are dense when present, are also binned when supported by the train-derived inventory.

## 7. Build MEDS-Like Outputs

```bash
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace
```

If `data/pre-MEDS/train`, `val`, and `test` exist, this writes split outputs under `data/MEDS/{train,val,test}/`. Numeric quantile boundaries are fit on train only and saved to `data/metadata/numeric_quantile_boundaries.parquet`, then reused for all splits.

For one-cohort QC instead:

```bash
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace run.split_outputs=false
```

MEDS numeric conversion prefers `numericitems_binned` when present, otherwise falls back to raw `numericitems`.

## 8. Build Tokenized Outputs

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace
```

The token vocabulary is built from `data/MEDS/train` only, then applied unchanged to `train`, `val`, and `test`.
Codes seen only in `val` or `test` are mapped to the frozen `UNK` token and audited.

Outputs:

```text
/path/to/aumc_workspace/data/tokenized/{train,val,test}/
/path/to/aumc_workspace/data/tokenized/metadata/timeline_index.parquet
```

Each tokenized timeline is one ICU admission/stay. Patient and admission identity remain recoverable through `patient_ids`, `hadm_id`, `icustay_id`, and `timeline_index.parquet`.

The unit of analysis is configurable:

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace run.analysis_unit=stay
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace run.analysis_unit=subject
```

`stay` is the default. `subject` concatenates a patient's admissions chronologically while preserving per-token `hadm_id` and `icustay_id`.

## Current Status

Implemented:

- external retrieval/setup helper
- supplied vocabulary build/install
- iCareFM-style grid feature manifest
- deterministic subject splits as a pre-MEDS substage
- source-preserving pre-MEDS extraction
- train-derived high-frequency numeric inventory
- rare-but-dense numeric binning for sparse CRRT-like dense streams
- causal mean-binned numeric pre-MEDS outputs
- bounded/full MEDS-like conversion for a supplied pre-MEDS directory
- split-aware MEDS conversion for train/val/test
- train-frozen numeric quantile boundaries across train/val/test
- train-frozen token vocabulary and tokenized safetensor outputs

## Tests

```bash
python -m unittest discover -s tests -v
```

More detail:

- `docs/user_runbook.md`
- `docs/policy_decisions.md`
- `docs/amsterdam_vocab_documentation.md`
