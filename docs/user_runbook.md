# AUMC Pipeline User Runbook

This runbook expands the short README workflow. The current package builds the AmsterdamUMCdb supplied vocabulary. MEDS conversion and tokenization are not implemented in this repository version.

## Required Inputs

Use one workspace folder per run:

```text
/path/to/aumc_workspace/
├── AUMC_raw/              raw AmsterdamUMCdb CSV files
├── externals/             GitHub external resources
│   └── omop_vocab/        manually downloaded Athena/OMOP CSV export
└── outputs/               generated vocabulary and audits
```

The active supplied vocabulary also ships with the package at:

```text
mappings/aumc_supplied_vocab.csv
```

## Setup

Clone the code:

```bash
git clone https://github.com/AmirV97/AUMCdb_pipeline.git /path/to/AUMC_pipeline
cd /path/to/AUMC_pipeline
```

Optional editable install:

```bash
python -m pip install -e .
```

If the package is installed, the command-line entry points are:

```bash
retrieve-aumc-externals --parent-dir /path/to/aumc_workspace
build-amsterdam-vocab step=build_vocab paths.parent_dir=/path/to/aumc_workspace
```

If the package is not installed, use the checkout wrappers:

```bash
python /path/to/AUMC_pipeline/scripts/retrieve_externals.py \
  --parent-dir /path/to/aumc_workspace

python /path/to/AUMC_pipeline/scripts/build_amsterdam_vocab.py \
  step=build_vocab \
  paths.parent_dir=/path/to/aumc_workspace
```

## External Resources

`retrieve_externals.py` creates the workspace layout and clones GitHub-hosted resources into:

```text
/path/to/aumc_workspace/externals/
```

The script does not download the Athena/OMOP export. Download it manually from:

```text
https://athena.ohdsi.org/vocabulary/list
```

Select the vocabularies listed in `README.md`, then extract the resulting CSV files into:

```text
/path/to/aumc_workspace/externals/omop_vocab/
```

## Raw AmsterdamUMCdb Data

Place or symlink the raw AmsterdamUMCdb CSV files into:

```text
/path/to/aumc_workspace/AUMC_raw/
```

The vocabulary build expects the raw table CSVs used by AmsterdamUMCdb, including large tables such as `numericitems.csv`, `listitems.csv`, and `drugitems.csv`.

## Build Output

Run:

```bash
python /path/to/AUMC_pipeline/scripts/build_amsterdam_vocab.py \
  step=build_vocab \
  paths.parent_dir=/path/to/aumc_workspace
```

Main output:

```text
/path/to/aumc_workspace/outputs/aumc_supplied_vocab.csv
```

Audit/debug outputs:

```text
/path/to/aumc_workspace/outputs/audits/
```

The build prints progress for the four substeps: source vocabulary extraction, evidence normalization, candidate map construction, and supplied-vocabulary writing.

## Tests

From a checkout:

```bash
cd /path/to/AUMC_pipeline
python -m unittest discover -s tests -v
```

Current expected result:

```text
25 tests passed
```

## Not Implemented Yet

The runtime path is next-stage work. It will consume `aumc_supplied_vocab.csv` and implement MEDS conversion, high-frequency numeric binning, numeric quantile tokenization, score derivation, D/APACHE diagnosis handling, medication ATC-depth selection, and tokenization QA.
