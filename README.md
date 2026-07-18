# MetaICU

A multi-database ICU data-processing library. AmsterdamUMCdb currently has two sibling pipelines under `src/metaicu/aumcdb/`:

- `tokenized/`: supplied vocabulary, pre-MEDS, MEDS-like events, and ETHOS-style tokenization.
- `grid/`: iCareFM-style raw CSV to split-aware hourly grid construction.

## Quick Start

```bash
git clone https://github.com/AmirV97/MetaICU.git
cd MetaICU
uv pip install --python /path/to/python -e .
```

For the full step-by-step workflow (external retrieval, vocabulary build, pre-MEDS, MEDS, tokenization, all CLI commands and flags), see **[docs/user_runbook.md](docs/user_runbook.md)**.

## Current Status

Implemented:

- external retrieval/setup helper
- supplied vocabulary build/install
- iCareFM-style grid feature manifest and reviewed-manifest parser
- shared Latin-1-preserving raw parquet cache for the grid and tokenized pipelines
- raw CSV to hourly grid extraction with unit harmonization, broad physiological outlier removal, train-fitted scaling, imputation, and categorical encoding
- grid per-feature presence masks (`{tag}__observed`), derived TTE targets (P/F ratio, urine-rate-per-weight), static-demographic prepend onto every hourly row, always subject-level splits, and an emitted K=34 TTE-target manifest (`tte_targets.json`)
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
