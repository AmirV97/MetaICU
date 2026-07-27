# Test Suite

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

Future datasets, including MIMIC-IV, should mirror the same subsystem layout instead of
adding flat `test_*.py` files at the root.
