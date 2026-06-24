# AUMC Pipeline User Runbook

This runbook describes the current user-facing pipeline pieces. Runtime MEDS conversion and tokenization are not implemented yet; the current package supports supplied-vocabulary consumption, source-vocabulary extraction, external-resource inventory, evidence normalization, and candidate-map construction.

## Required Inputs

A fresh run should provide these directories explicitly through Hydra overrides:

```text
/path/to/AUMC_pipeline/          package checkout
/path/to/amsterdam_external/     AMSTEL, AmsterdamUMCdb, BlendedICU, YAIB/ricu resources
/path/to/omop_vocab/             local OMOP/Athena vocabulary export
/path/to/AmsterdamUMCdb/         raw AmsterdamUMCdb CSV directory
/path/to/audits/                 output audit directory
```

The active supplied vocabulary ships with the package at:

```text
AUMC_pipeline/mappings/aumc_supplied_vocab.csv
```

## Install Or Run From Checkout

Preferred, when `pip` is available in the target environment:

```bash
cd /path/to/AUMC_pipeline
python -m pip install -e .
```

Then use:

```bash
build-amsterdam-vocab step=external_inventory ...
```

On systems where the Python environment does not provide `pip`, run from checkout with `PYTHONPATH`:

```bash
cd /path/to/AUMC_pipeline
PYTHONPATH=/path/to/AUMC_pipeline/src \
  python scripts/build_amsterdam_vocab.py step=external_inventory ...
```

## Smoke Test In A Fresh Folder

Create a fresh workspace. Large inputs can be symlinks.

```bash
mkdir -p /tmp/aumc_pipeline_fresh_test
# copy AUMC_pipeline into /tmp/aumc_pipeline_fresh_test/AUMC_pipeline
# set up standard folders and retrieve GitHub externals:
python /path/to/AUMC_pipeline/scripts/retrieve_externals.py \
  --parent-dir /tmp/aumc_pipeline_fresh_test
# then place or symlink raw Amsterdam CSVs into AUMC_raw/
# and extract Athena/OMOP CSVs into externals/omop_vocab/
```

Run tests from the fresh checkout:

```bash
cd /tmp/aumc_pipeline_fresh_test/AUMC_pipeline
PYTHONPATH=/tmp/aumc_pipeline_fresh_test/AUMC_pipeline/src \
  python -m unittest discover -s tests -v
```

Expected current result:

```text
20 tests passed
```

## One-Command Vocabulary Build

Run the public workflow once the folders above are in place:

```bash
PYTHONPATH=/tmp/aumc_pipeline_fresh_test/AUMC_pipeline/src \
python scripts/build_amsterdam_vocab.py \
  step=build_vocab \
  paths.parent_dir=/tmp/aumc_pipeline_fresh_test
```

Main output:

```text
/tmp/aumc_pipeline_fresh_test/outputs/aumc_supplied_vocab.csv
```

The command expects `AUMC_raw/`, `externals/`, and `externals/omop_vocab/` under the parent folder. It writes source-vocab, evidence-normalization, and candidate-map audits under `outputs/audits/` by default. The lower-level CLI steps are available for debugging, but users should not need to run them manually.

## Outputs To Check

After a build run, inspect:

```text
audits/vocab_pipeline_external_resources_summary.json
audits/vocab_pipeline_source_vocab_summary.json
audits/vocab_pipeline_mapping_evidence_summary.json
audits/vocab_pipeline_candidates_summary.json
```

In the current verified fresh-folder smoke test, the expected high-level results were:

```text
external resources: 93 found, 0 missing required
source-vocab raw smoke: 60,000 rows scanned, 1,391 source tokens, 0 duplicate/empty tokens
normalized evidence: 72,897 rows
candidate map smoke: 1,391 / 1,391 source tokens with candidate evidence
```

## What Is Not Implemented Yet

The runtime path is the next task. It will consume `mappings/aumc_supplied_vocab.csv` and implement MEDS conversion, high-frequency numeric binning, numeric quantile tokenization, score derivation, D/APACHE diagnosis handling, medication ATC-depth selection, and tokenization QA.
