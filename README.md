# AUMC Pipeline

Build AmsterdamUMCdb supplied vocabulary, pre-MEDS parquet, and bounded MEDS-like event outputs.

Main output:

```text
<workspace>/outputs/aumc_supplied_vocab.csv
```

## 1. Make A Workspace

Create an empty folder for one run:

```bash
mkdir -p /path/to/aumc_workspace
```

## 2. Get The Code

Clone this repository, or use an existing checkout:

```bash
git clone https://github.com/AmirV97/AUMCdb_pipeline.git /path/to/AUMC_pipeline
cd /path/to/AUMC_pipeline
```

Optional editable install:

```bash
python -m pip install -e .
```

If you do not install the package, run scripts by absolute path as shown below.

## 3. Retrieve GitHub Externals

This creates the expected workspace folders and clones the GitHub-hosted references:

```bash
python /path/to/AUMC_pipeline/scripts/retrieve_externals.py \
  --parent-dir /path/to/aumc_workspace
```

The command also writes `externals/external_versions.json` with the branch and commit for each retrieved Git repository.

The workspace layout after this step is:

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

## 4. Add OMOP/Athena CSVs

The OMOP/Athena vocabulary export must be downloaded manually from:

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

Extract the Athena download into:

```text
/path/to/aumc_workspace/externals/omop_vocab/
```

That folder must contain at least:

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

## 5. Build The Vocabulary

Run:

```bash
python /path/to/AUMC_pipeline/scripts/build_amsterdam_vocab.py \
  step=build_vocab \
  paths.parent_dir=/path/to/aumc_workspace
```

The vocabulary is written to:

```text
/path/to/aumc_workspace/outputs/aumc_supplied_vocab.csv
```

If that file already exists, the command stops by default. To intentionally replace it, add:

```bash
run.overwrite=true
```

Audit files are written under:

```text
/path/to/aumc_workspace/outputs/audits/
```

Important audit files include:

```text
run_config.json
build_vocab_summary.json
vocab_pipeline_source_vocab.csv
vocab_pipeline_mapping_evidence.csv
vocab_pipeline_candidates.csv
```

## 6. Build Pre-MEDS

Convert raw AmsterdamUMCdb CSVs to source-preserving pre-MEDS parquet:

```bash
build-aumc-premeds \
  paths.parent_dir=/path/to/aumc_workspace
```

For a bounded QC run:

```bash
build-aumc-premeds \
  paths.parent_dir=/path/to/aumc_workspace \
  run.num_patients=1000
```

Output:

```text
/path/to/aumc_workspace/outputs/pre_meds/
```

## 7. Build Bounded MEDS

Convert pre-MEDS to MEDS-like event parquet using the supplied vocabulary:

```bash
build-aumc-meds \
  paths.parent_dir=/path/to/aumc_workspace
```

For a bounded QC run from an already bounded pre-MEDS directory:

```bash
build-aumc-meds \
  paths.pre_meds_dir=/path/to/aumc_workspace/outputs/pre_meds_1000 \
  paths.vocab_path=/path/to/aumc_workspace/outputs/aumc_supplied_vocab.csv \
  paths.output_dir=/path/to/aumc_workspace/outputs/meds_1000 \
  paths.audit_dir=/path/to/aumc_workspace/outputs/audits
```

## Notes

- Implemented: vocabulary build, pre-MEDS extraction, bounded MEDS-like conversion.
- Not yet implemented: subject splits, train-frozen numeric quantile boundaries, high-frequency numeric binning, and tokenization.
- Detailed resource notes are in `docs/amsterdam_vocab_documentation.md`.
- Vocabulary schema and modeling decisions are in `docs/policy_decisions.md`.
