# MetaICU

A multi-database ICU data-processing library (AmsterdamUMCdb now; MIMIC/eICU/SICdb/HiRID planned). Each database gets its own submodule under `src/metaicu/<db>/`, currently `aumcdb/`, which supports vocabulary construction, split-aware pre-MEDS, MEDS-like outputs, ETHOS-style tokenized timelines (`aumcdb/tokenized/`), and an iCareFM-style hourly grid feature manifest (`aumcdb/grid/`).

## Quick Start

```bash
git clone https://github.com/AmirV97/MetaICU.git
cd MetaICU
python -m pip install -e .
```

For the full step-by-step workflow (external retrieval, vocabulary build, pre-MEDS, MEDS, tokenization, all CLI commands and flags), see **[docs/user_runbook.md](docs/user_runbook.md)**.

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
