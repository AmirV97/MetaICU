# AUMC Pipeline

Build the AmsterdamUMCdb supplied vocabulary from raw Amsterdam CSVs plus external reference resources.

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

Audit files are written under:

```text
/path/to/aumc_workspace/outputs/audits/
```

## Notes

- The current package builds the supplied vocabulary only.
- MEDS conversion and tokenizer-facing processing are separate next-stage work.
- Detailed resource notes are in `docs/amsterdam_vocab_documentation.md`.
- Vocabulary schema and modeling decisions are in `docs/policy_decisions.md`.
