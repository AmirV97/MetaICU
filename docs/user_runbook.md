# MetaICU User Runbook

This runbook expands the README command sequence. The package currently supports:

- external resource setup
- reviewed supplied-vocabulary installation and optional raw-data rebuild
- iCareFM-style grid feature manifest
- iCareFM-style hourly grid dataset build
- subject-level train/val/test split creation
- source-preserving pre-MEDS extraction
- train-derived high-frequency numeric inventory
- causal mean-binned `numericitems_binned` outputs
- MEDS-like QC conversion for a supplied pre-MEDS directory
- ETHOS-style tokenized safetensor outputs

## Workspace Layout

Use one workspace per run:

```text
/path/to/aumc_workspace/
├── data/
│   ├── raw/              raw AmsterdamUMCdb CSV files
│   ├── raw_shards/       internal schema-cast parquet cache for large raw tables
│   ├── pre-MEDS/         pre-MEDS parquet outputs
│   ├── MEDS/             MEDS-like parquet outputs
│   ├── tokenized/        tokenized safetensor outputs
│   └── metadata/         splits, high-frequency inventory, quantile boundaries
├── externals/            GitHub external resources
│   └── omop_vocab/       manually downloaded Athena/OMOP CSV export
├── vocab/                supplied vocabulary artifact
└── audits/               audit JSON/CSV outputs
```

## Install

```bash
git clone https://github.com/AmirV97/MetaICU.git /path/to/MetaICU
cd /path/to/MetaICU
python -m pip install -e .
```

Main CLI entry points:

```bash
retrieve-aumc-externals --parent-dir /path/to/aumc_workspace
build-amsterdam-vocab paths.parent_dir=/path/to/aumc_workspace
grid_build_manifest paths.parent_dir=/path/to/aumc_workspace
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace
```

## Inputs

The reviewed Amsterdam vocabulary is bundled with MetaICU. Install it into a
workspace without raw data or external resources:

```bash
build-amsterdam-vocab paths.parent_dir=/path/to/aumc_workspace
```

Output:

```text
/path/to/aumc_workspace/vocab/aumc_supplied_vocab.csv
```

To install a different reviewed vocabulary file instead of the bundled artifact:

```bash
build-amsterdam-vocab \
  paths.parent_dir=/path/to/aumc_workspace \
  paths.supplied_vocab=/path/to/reviewed_vocab.csv
```

To rebuild and audit the vocabulary against local raw data, first retrieve the
external repositories:

```bash
retrieve-aumc-externals --parent-dir /path/to/aumc_workspace
```

Place or symlink the raw AmsterdamUMCdb CSVs into:

```text
/path/to/aumc_workspace/data/raw/
```

Download Athena/OMOP from `https://athena.ohdsi.org/vocabulary/list`. Select
SNOMED, LOINC, RxNorm, RxNorm Extension, ATC, UCUM, and OMOP Extension, then
extract the CSVs into:

```text
/path/to/aumc_workspace/externals/omop_vocab/
```

Run the optional rebuild:

```bash
build-amsterdam-vocab \
  paths.parent_dir=/path/to/aumc_workspace \
  run.mode=rebuild \
  run.overwrite=true
```

The rebuild extracts Latin-1 source tokens, generates evidence/candidate audits,
replays the reviewed mapping and policy manifests, and validates the result.
Candidate evidence is retained for audit; the reviewed baseline manifest owns
target selection. New uncovered source tokens fail by default. Use
`run.allow_unresolved_source_tokens=true` only for bounded or audit-only runs.

## Grid Feature Manifest

```bash
grid_build_manifest paths.parent_dir=/path/to/aumc_workspace
```

This writes:

```text
grid/aumc_grid_feature_manifest.csv
audits/grid_manifest/grid_manifest_summary.json
audits/grid_manifest/grid_manifest_unmatched_features.csv
audits/grid_manifest/grid_manifest_source_candidate_examples.csv
```

The manifest is stage 1 of the iCareFM-style hourly-grid fork. It has one row per packaged Table S3 feature tag and records broad source candidates from the source vocab, supplied vocab, and OpenICU AUMC mappings. It does not scan raw AUMC rows, decide unit conversion, or construct the grid dataset.

## Grid Dataset

```bash
grid_build_dataset dataset=aumcdb paths.parent_dir=/path/to/aumc_workspace
grid_build_dataset dataset=mimic_iv paths.parent_dir=/path/to/mimic_workspace
```

Prefer `grid_build_joint_dataset` (below) for new work, including single-dataset builds. This
command remains for exactly byte-identical, Int64-`admissionid` single-dataset output.

The grid and tokenized pipelines share the Latin-1-preserving cache under
`data/raw_shards/`. The first pipeline to run builds schema-cast parquet shards
for `numericitems`, `listitems`, and `drugitems`; later grid or pre-MEDS runs
reuse them. Set `run.rebuild_raw_shards=true` only when the raw source files or
canonical raw schemas have changed.

MIMIC-IV accepts explicit `paths.raw_data_dir`, `paths.raw_shards_dir`, `paths.output_dir`, and `paths.audit_dir` in the same dispatcher. Both datasets refuse to reuse an output containing generated grid artifacts unless `run.overwrite=true`; overwrite removes only known grid artifacts and preserves unrelated files.

The build runs the full A.4.1-A.4.3 pipeline (hourly gridding, unit harmonization,
plausibility-bound outlier removal, train-fitted scaling, forward-/zero-fill
imputation, one-hot categorical encoding; see
`src/metaicu/aumcdb/grid/data/icarefm_preprocessing_reference.md`) and adds: a
per-feature presence mask (`{tag}__observed`, 1 = real reading that hour, captured
before imputation), the derived TTE targets `pf_ratio` (= po2 / (fio2/100)) and
`urine_rate_per_weight`, and the 5 static demographics (age/weight/height/sex/adm)
prepended onto every hourly row. Inclusion criteria (A.2.2: LoS >= 4h, >= 4 numeric
measurements, max gap <= 48h) and the 80/10/10 split are always applied at the
patient (subject) level, so a patient's repeat admissions never leak across splits.

`run.unit_of_analysis` sets sample granularity: `admission` (default, one sample per
ICU admission) or `subject` (one per patient, that patient's admissions concatenated
chronologically).

Outputs under `paths.output_dir`:

```text
train|val|test/N.parquet              per-split hourly grid shards
metadata.csv                          one row per admission (or subject)
feature_schema.json                   per-column reconstruction type, unit, presence-mask column
tte_targets.json                      canonical K=34 TTE target list and order
scalers.pkl / scalers.summary.json    train-fitted scalers
categorical_encoding.csv              one-hot column layout (static + grid)
```

`feature_schema.json` also records each logical feature's `physical_columns`, including one-hot expansions and an empty list for a declared feature with no physical column. Every successful build writes `grid_integrity_summary.json` under `paths.audit_dir`; the build fails on split leakage, shard/metadata disagreement, duplicate or non-dense hour keys, schema-order drift, invalid masks/one-hot groups, non-finite values, or inconsistent TTE declarations.

## Joint Grid Dataset (pooled AUMCdb + MIMIC-IV)

```bash
grid_build_joint_dataset datasets=[mimic_iv,aumcdb] \
  dataset_configs.mimic_iv.paths.parent_dir=/path/to/mimic_workspace \
  dataset_configs.aumcdb.paths.parent_dir=/path/to/aumc_workspace \
  joint.output_dir=/path/to/joint/data joint.audit_dir=/path/to/joint/audits
```

`datasets` selects `[mimic_iv]`, `[aumcdb]`, or `[mimic_iv, aumcdb]`. Each `dataset_configs.<name>`
block is that cohort's own per-cohort **staging** build (same `paths`/`split`/`run` shape as the
standalone `grid_build_dataset`, written in full to its own `paths.output_dir`/`paths.audit_dir`).
With more than one dataset selected, every scaled tag (static age/weight/height and every grid
`direct_numeric`/`derived_output_rate`/`treatment_rate` tag with real data in at least one cohort)
is fit on **pooled, weighted** train-split statistics instead of each cohort's own split alone --
weight `w_c = 1/sqrt(n_train_admissions_c)`, normalized to sum to 1, the same weighting the
training repo uses for its per-cohort loss.

The final joint output under `joint.output_dir` always uses one flat layout, regardless of how
many datasets were selected:

```text
train|val|test/N.parquet   re-sharded hourly grid shards, concatenated across cohorts
metadata.csv               one row per admission, plus a `source` column ("aumcdb"/"mimic_iv")
feature_schema.json        identical across cohorts by construction (data-content invariant)
tte_targets.json           union of every cohort's own TTE target list
scalers.pkl                fitted normalizers (z-score mean/std, QuantileTransformer objects) --
                            with >1 dataset selected, every pooled tag's entry here is the exact
                            fit applied to BOTH cohorts; keep this alongside the joint output to
                            preprocess a future inference-time subject the same way
scalers.summary.json       human-readable provenance for scalers.pkl (pooled tags, contributing
                            cohorts, weights)
```

`admissionid`/`subject_id` are always `f"{cohort}_{id}"` **strings** (not the raw Int64 IDs) --
this is intentional even for a single selected dataset, so a consumer never needs to special-case
dataset count. `metadata.csv` also carries `native_admissionid`/`native_subject_id` -- the
original per-cohort numeric ID, before namespacing -- so tracing an admission back to its source
system never requires parsing the namespaced string yourself (`source` + `.removeprefix()` would
work, but note "mimic_iv" itself contains an underscore, so a naive split on the first "_" gives
the wrong answer). Note `outcome`'s definition differs by cohort despite matching string values
(AUMCdb: patient-level any-time death; MIMIC-IV: in-hospital-this-admission death) -- always key
off `source` before comparing `outcome` across rows. `split.unit_of_analysis=subject` (AUMCdb
only) is not supported for a joint build.

## Pre-MEDS

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace
```

Pre-MEDS creates or reuses `data/metadata/subject_splits.parquet` using the default 80/10/10 subject split, then writes:

```text
data/metadata/subject_splits.parquet   deterministic subject split
data/raw_shards/                       reusable raw parquet cache for large tables
data/pre-MEDS/                         combined source-preserving pre-MEDS
data/pre-MEDS/train|val|test/          split-specific pre-MEDS
data/pre-MEDS/train|val|test/numericitems_binned/
data/metadata/hf_numeric_inventory.csv
data/metadata/hf_numeric_binning_summary.json
audits/pre-MEDS/premeds_summary.json
```

The raw shard cache is source-preserving and shared with the grid pipeline: no patient filtering, vocab decisions, sentinel drops, or time transforms are applied there. The high-frequency inventory is fitted on train only. Causal mean-binning is then applied to each split using that frozen inventory. Rare-but-dense numeric variables, such as CRRT settings that appear in few stays but are very dense when present, are also flagged for binning; the default rare-dense gate requires 2 sampled admission/item groups plus a high row burden and a high-frequency CI above the threshold. Empty bins are not emitted.

Selected repeated categorical state streams are state-change deduplicated in pre-MEDS. Defaults include ventilation mode, CRRT modality, rhythm, oxygen/admin route, NIV program status, sputum state, pupil state, selected score components/final scores, ectopy, chest-drain state, and EVD state. The policy keeps the first value and later value changes per admission/item.

Useful QC run:

```bash
build-aumc-premeds paths.parent_dir=/path/to/aumc_workspace \
  run.num_patients=1000 run.max_rows=1000000
```

Full source-preservation and split-integrity audit:

```bash
audit-aumc-premeds --parent-dir /path/to/aumc_workspace
```

This performs streaming two-seed source-row fingerprint checks for the large
tables, reconciles documented exclusions and categorical state-change
deduplication, verifies subject-level split isolation and split-output parity,
and checks raw numeric passthrough plus causal hourly-bin invariants. Results
are written under `audits/pre-MEDS/full_integrity/`; required-check failures
produce a nonzero exit code.

## MEDS-Like QC Conversion

Split-aware MEDS conversion:

```bash
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace
```

When split pre-MEDS folders exist, this writes `data/MEDS/{train,val,test}/`. Numeric quantile boundaries are fit on train only, saved to `data/metadata/numeric_quantile_boundaries.parquet`, and reused for all splits.

Death is assigned to at most one ICU admission. `MEDS_DEATH` is emitted for an in-ICU death or a death recorded within 24 hours after discharge. Later deaths remain in `data/metadata/subjects.parquet` and `data/metadata/admissions.parquet` without extending the token timeline.

Before fitting or applying those boundaries, raw numeric values go through `tokenized/meds/numeric_qc.py`, which reuses the grid pipeline's itemid-level corrections (`grid/build/unit_conversion_overrides.py`, `plausibility_bounds.py`, and the manifest's rejected duplicates like `pt`) so the same mislabeled units, device sentinels, and implausible readings don't corrupt either pipeline's numeric values. It's keyed by itemid, the only thing the two pipelines' vocabularies actually share -- grid pools itemids into physiology tags, tokenized keeps each itemid as its own token.

One-cohort QC is still available:

```bash
build-aumc-meds paths.parent_dir=/path/to/aumc_workspace run.split_outputs=false
```

Numeric MEDS conversion uses `numericitems_binned` when present, otherwise raw `numericitems`.

## Tokenization

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace
```

This builds the token vocabulary from `data/MEDS/train` only and reuses that frozen vocabulary for `val` and `test`.
Use `vocab_scope=full_data` only when a descriptive vocabulary covering all
three splits is required:

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace vocab_scope=full_data
```

The durable vocabulary copy is written under `mappings/` as
`aumc_token_vocab_train_only_tN.csv` or `aumc_token_vocab_full_tN.csv`.
Codes seen only in `val` or `test` are mapped to the frozen `UNK` token and recorded in the tokenization unknown-code audit.

Full safetensor integrity audit:
```bash
audit-aumc-tokenized --parent-dir /path/to/aumc_workspace
```
This reconciles tensor shapes, vocabulary IDs, timeline offsets and identities, timestamp ordering, terminal tokens, shared quantile-token adjacency, stored token counts, and deterministic sampled MEDS-to-token tracebacks. It also writes sequence-length and timeline-duration histograms under `audits/tokenization/full_integrity/`.

Outputs:

```text
data/tokenized/train|val|test/*.safetensors
data/tokenized/train/vocab_t*.csv
data/tokenized/train/vocab_decoded.csv
data/tokenized/train/code_counts.csv
data/tokenized/train/interval_estimates.json
data/tokenized/metadata/codes.parquet
data/tokenized/metadata/timeline_index.parquet
data/tokenized/metadata/subjects.parquet
data/tokenized/metadata/admissions.parquet
audits/tokenization/tokenization_summary.json
```

Each tokenized timeline is one ICU admission/stay, keyed by `(subject_id, hadm_id)`. Multi-admission patients therefore produce multiple timelines, but patient/admission identity is preserved through `patient_ids`, `hadm_id`, `icustay_id`, and `timeline_index.parquet`.

The tokenized unit of analysis is configurable:

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace run.analysis_unit=stay
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace run.analysis_unit=subject
```

`stay` is the default and writes one timeline per ICU admission/stay. `subject` writes one timeline per patient, concatenating that patient's admissions chronologically. Per-token `hadm_id` and `icustay_id` are still stored, so admission identity remains recoverable.

Medication ATC detail can be coarsened at tokenization time:

```bash
build-aumc-tokenized paths.parent_dir=/path/to/aumc_workspace run.medication_atc_depth=2
```

## Tests

GitHub Actions automatically runs Ruff plus the unit and integration suites on
each push and pull request. Real-data tests remain local because hosted runners
cannot access AmsterdamUMCdb.

Install the development tools and run the same lint check locally:

```bash
uv sync --extra dev
uv run ruff check src tests scripts
```

Run fast unit tests during development:

```bash
cd /path/to/MetaICU
python -m unittest discover -s tests/unit -t . -v
```

Run fixture-based integration tests before merging:

```bash
python -m unittest discover -s tests/integration -t . -v
```

Run everything; real-data tests skip unless their documented environment variables are set:

```bash
python -m unittest discover -s tests -t . -v
```

See `tests/README.md` for the directory contract and full-data commands.

## Next Development Tasks

- Re-run bounded pre-MEDS -> MEDS -> tokenization QC after the aggressive rare-dense binning default. Confirm whether CRRT dilution/flow streams are now binned rather than raw-passthrough.
- Decide the policy for any remaining super-long ICU stays before full tokenization runs. Some stays are genuinely long, e.g. 37-95 ICU days, so hourly data alone can still produce long sequences.
