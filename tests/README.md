# Test Suite

GitHub Actions runs the unit and integration suites below on every push and
pull request. The `real_data` suite is deliberately excluded because hosted CI
does not have access to AmsterdamUMCdb or MIMIC-IV.

Run the CI lint check locally:

```bash
uv run ruff check src tests scripts
```

Tests are separated by execution scope and then by pipeline subsystem.

```text
tests/
├── unit/          in-memory tests of individual transforms and policy functions
├── integration/   fixture pipelines, CLI behavior, package assets, and contracts
├── real_data/     opt-in regressions requiring local ICU datasets and externals
└── fixtures/      shared bounded synthetic inputs
```

Run the fast unit suite while developing:

```bash
python -m unittest discover -s tests/unit -t . -v
```

Run fixture-based integration tests:

```bash
python -m unittest discover -s tests/integration -t . -v
```

Run everything. Real-data tests skip unless their documented environment variables are set:

```bash
python -m unittest discover -s tests -t . -v
```

Run the Amsterdam full-data vocabulary regression explicitly:

```bash
python -m unittest tests.real_data.tokenized.vocab.test_vocab_build_regression -v
```

Run the MIMIC-IV transformed-grid determinism regression explicitly:

```bash
METAICU_MIMICIV_REGRESSION_RAW_DIR=/path/to/pre_MEDS \
METAICU_MIMICIV_REGRESSION_RAW_SHARDS_DIR=/path/to/raw_shards \
python -m unittest tests.real_data.mimiciv.grid.test_grid_build_regression -v
```
