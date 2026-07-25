# Amsterdam Vocabulary Rebuild Handoff

## Implementation Status (2026-07-25)

The rebuild described below has been implemented. Summary of what changed and what remains:

**Done:**

- `build-amsterdam-vocab` no longer copies a frozen CSV. `build_workflow.py` now calls
  `target_resolution.resolve_baseline_targets()` -> `policies.engine.apply_policy_layers()` ->
  `validation.validate_supplied_vocab()` -> write, replacing `shutil.copy2`.
- Baseline candidate ranking (the historical scripts 08/09/11/12/14/16 sub-pipeline) is
  packaged as a versioned reference (`vocab_pipeline/data/policy_manifests/
  tier0_baseline_resolution.csv`) rather than re-implemented from scratch -- this is the one
  documented scope limit; see `target_resolution.py`'s docstring. Everything after that point
  (curated policy manifests v4-v11, zero-sentinel, lab consolidation, namespace
  canonicalization, lab-role assignment, GCS component policy) is applied fresh every run via
  `policies/engine.py`, in the fixed order specified below.
- The curated, one-off clinical-curation layers (v4 through v11) were captured as versioned
  manifests by diffing the real historical artifact lineage (v1 through v16, all of which
  survive in the research checkout that produced this rebuild) rather than re-deriving the
  underlying human review. The five genuinely deterministic layers (zero-sentinel, lab
  consolidation, namespace, lab-role, GCS) were ported as real code into
  `vocab_pipeline/policies/`.
- Verified byte-for-byte: baseline + manifests + policy code reproduce the historical `v16`
  vocabulary with **zero row-level differences across all 9,014 tokens** (checked both against
  the historical artifact lineage directly and against the actual MetaICU package code).
- Ran the full build against the real raw AmsterdamUMCdb release as an HPC batch job. Found and
  fixed one real, high-impact bug
  in the process: `source_vocab.py`'s numeric-unit extraction didn't recognize the raw export's
  literal text `"None"` (not an empty/null cell) as a missing unit, mis-keying ~65M rows of
  major vitals (e.g. `Saturatie (Monitor)`, `Ademfrequentie Monitor`) under a `//None` token
  instead of `//UNKNOWN`. Fixed in `source_vocab.py` (`_is_null_text_expr`).
- After that fix, the real-raw-data build reproduces `v16` with **zero semantic differences on
  all 8,750 source tokens common to both** -- the core construction logic is proven correct
  against production data, not just the historical artifact chain.
- Promoted `v16`'s content as the new `mappings/aumc_supplied_vocab.csv` (and the packaged
  `src/metaicu/aumcdb/tokenized/data/` copy). Updated the three hardcoded counts in
  `tests/test_supplied_vocab_contract.py` (4,836->4,837 emitted, 515->516 LAB rows,
  14,301,315->14,301,350 LAB row sum) to match.
- Added `run.allow_unresolved_source_tokens` (default `false`) and `validate_supplied_vocab(...,
  strict=...)`: an uncovered source token fails the build loudly by default (per "Changed
  Dataset Releases" below); the flag exists for bounded/test/audit-only builds.
- 17 new unit tests in `tests/test_vocab_policy_layers.py`; fixed 4 pre-existing fixture-based
  CLI tests in `tests/test_vocab_evidence_normalization.py` that assumed the old copy-only
  behavior. Full suite: 97/97 passing.

**Known, deferred gap (not blocking):** the real raw-data build currently has a small residual
mismatch against `v16` outside the 8,750 common tokens: 321 tokens appear only in the fresh
build, 264 only in `v16`. Root-caused to two distinct causes, neither a vocabulary-policy bug:

1. ~256 tokens / ~10M rows: a handful of `numericitems.unit` strings containing `µ` or `°`
   decode as the U+FFFD replacement character under `pl.scan_csv(encoding="utf8-lossy", ...)` --
   the raw export appears to use a single-byte encoding (e.g. Windows-1252) for these
   characters that isn't valid UTF-8, and Polars' CSV reader only supports `"utf8"`/
   `"utf8-lossy"` (no arbitrary codec). This shadows 264 correctly-mapped historical LAB tokens
   (e.g. `LAB//10008//µg/l`) under a corrupted token instead.
2. ~65 tokens / ~200 rows: genuinely new/tail `listitems` values and `freetextitems` labels
   present in the current raw data pull that weren't in the historical curated snapshot (e.g.
   newer lab-test freetext names, a few new discharge-destination/relationship values). This is
   expected, legitimate "changed dataset release" drift, not a bug -- see "Changed Dataset
   Releases" below.

Follow-up: fix the encoding issue (likely needs a non-Polars pre-pass over just the affected
raw byte sequences, since Polars can't decode Windows-1252 directly) before treating a *live*
raw-data run as the promotion source instead of the historical `v16` reference. Until then,
`mappings/aumc_supplied_vocab.csv` is v16's content (fully verified, matches what the new code
produces for every currently-known source token) rather than this run's live output.

## Purpose

This document describes how the historical Amsterdam vocabulary artifacts were
constructed through v14 and then corrected through v16. It is an implementation
handoff for replacing the current static-copy behavior in MetaICU with a readable,
testable vocabulary build.

The intended public behavior is:

```text
AmsterdamUMCdb raw CSVs
  + external mapping resources
  + versioned clinical policy data
  -> source vocabulary
  -> mapping candidates
  -> validated target resolution
  -> clinical policy layers
  -> compact supplied vocabulary
```

The final public command should run this workflow once. Users should not run the
historical numbered scripts or know the internal v0-v16 artifact names.

## Critical Current Limitation

MetaICU currently performs the first three diagnostic stages, then copies a frozen
CSV:

```python
shutil.copy2(config.supplied_vocab, config.output_vocab)
```

The source-vocabulary, evidence, and candidate-map outputs do not influence the
installed vocabulary. Pointing the command at different raw data cannot change or
correct the result.

The implementation that replaces this copy must:

1. resolve candidates into a baseline mapping;
2. apply the retained clinical policies;
3. validate the final compact artifact;
4. write the rebuilt output;
5. fail clearly when source tokens are not covered by either a rule or a reviewed
   decision.

## Artifact Status

The relevant historical artifacts are under `amsterdam_pipeline/mappings/` in the research
checkout that produced this rebuild.

The corrected candidate for promotion is v16, not v14:

| Artifact | Role | SHA256 |
|---|---|---|
| `final_harmonized_token_map_v11_clean.csv` | Last major semantic-policy artifact | `bdc1ce521a9a26ea0d9707b0e79bf2b218ea5d772716f21734afb11b068233a8` |
| `final_harmonized_token_map_v12_sentinel_fixed.csv` | OMOP zero-sentinel correction | `273958ce447df4cb149533ca69f2c2491fd75a3420a506a7a7e68ac238a96ac8` |
| `final_harmonized_token_map_v13_lab_consolidated.csv` | Lab analyte consolidation | `53b805d93dff97d897e83cca3a13a2e5822fd15b4e33d6fd4b30abab3b47519f` |
| `final_harmonized_token_map_v14_canonical_namespace.csv` | Canonical OMOP concept namespaces | `8b7b916f076c76ea2bc8fc4db4c888961d5087b22c769dec972f465583a3dd7c` |
| `final_harmonized_token_map_v15_lab_role_fixed.csv` | Correct lab token roles | `151c48ffcda2b061d80cc6f1f6e3a94439cca74b40bf79814cc2e20125813f17` |
| `final_harmonized_token_map_v16_gcs_fixed.csv` | GCS component emission and RA_Verbal fix | `1e139f0640a4ff2fa1624d8b67bcd2fa4834fd6a327439d2c48f924bac28e5df` |

The v16 hash above is the historical-file reference. Row-by-row content comparison,
not byte identity, should be the migration acceptance criterion because CSV
serialization can change without changing values.

Note: verify the v16 hash from the actual file before using it in release metadata.
The authoritative local command is:

```bash
sha256sum amsterdam_pipeline/mappings/final_harmonized_token_map_v16_gcs_fixed.csv
```

The verified local value at the time of this handoff was:

```text
1e139f0640a4ff2fa1624d8b67bcd2fa4834fd6a327439d2c48f924bac28e5df
```

MetaICU's currently packaged `mappings/aumc_supplied_vocab.csv` is not v16:

| Comparison | Result |
|---|---:|
| Source-token rows in both | 9,014 |
| MetaICU emitted source tokens | 4,836 |
| v16 emitted source tokens | 4,837 |
| Rows with at least one compact policy-field difference | 263 |

## Final Compact Schema

Every final vocabulary row represents one Amsterdam source token. Source rows are
never physically removed. Non-model rows are retained with
`emit_as_model_token=False`.

```text
dataset
source_table
source_itemid
source_valueid
source_unitid
source_ordercategoryid
source_label
source_value
source_unit
source_token
row_count
harmonized_token
token_role
emit_as_model_token
non_drug_drugitem_class
target_vocabulary
target_concept_id
target_code
target_label
mapping_source
match_strength
mapping_confidence
```

Expected v16 dimensions:

| Quantity | Value |
|---|---:|
| Source tokens | 9,014 |
| Represented raw rows | 1,016,170,598 |
| Emitted source tokens | 4,837 |
| Emitted represented rows | 1,005,734,840 |
| Unique emitted destinations | 3,286 |

Expected v16 table counts:

| Source table | Source tokens | Represented rows | Emitted tokens | Emitted rows |
|---|---:|---:|---:|---:|
| `numericitems` | 1,723 | 977,620,425 | 976 | 973,975,200 |
| `listitems` | 4,478 | 30,549,155 | 2,803 | 26,798,171 |
| `drugitems` | 1,287 | 4,907,269 | 886 | 4,713,320 |
| `freetextitems` | 878 | 648,408 | 0 | 0 |
| `procedureorderitems` | 443 | 2,188,626 | 0 | 0 |
| `processitems` | 205 | 256,715 | 172 | 248,149 |

## Input Families

### Raw Amsterdam Data

The build uses the six source tables represented by the supplied vocabulary:

```text
numericitems.csv
listitems.csv
drugitems.csv
freetextitems.csv
processitems.csv
procedureorderitems.csv
```

Admissions and patient rows are runtime context/anchor inputs. They are not part of
the 9,014-row source-token vocabulary.

### External Evidence

The detailed acquisition layout is documented in
`docs/amsterdam_vocab_documentation.md`. The mapping build uses:

1. AMSTEL source concepts and USAGI mappings;
2. AmsterdamUMCdb current and legacy dictionaries;
3. AmsterdamUMCdb flowsheet SQL groupings;
4. BlendedICU timeseries and medication assets;
5. local OMOP/Athena vocabulary tables;
6. YAIB/ricu mappings as auxiliary context;
7. MIMIC token references only for comparison, never as Amsterdam ground truth.

OMOP/Athena is used to validate and enrich target concepts. It does not decide
whether a valid concept is useful for ICU trajectory modeling.

### Curated Policy Data

Some final decisions are clinical curation, not derivable from OMOP validity or
candidate scores. A real rebuild must package these as versioned policy data:

| Historical artifact | What must be retained |
|---|---|
| `audits/stage3j_amsterdamumcdb_unmapped_item_evidence_curated.csv` | Curated v4 actions for 3,412 previously unresolved source tokens |
| `notebooks/3L_aggressive_vocab_decisions.csv` | Keep/drop decision for all 9,014 source tokens |
| `audits/stage3n_v5_semantic_contamination_candidates.csv` | Semantic contamination action and recommended role/token |
| `audits/stage3n_v5_namespace_ambiguity.csv` | Namespace ambiguity evidence |
| `mappings/omop_only_medication_action_ready.csv` | Reviewed ATC/nutrition decision for 346 OMOP-only drug rows |
| `audits/omop_only_medication_explicit_review_decisions.csv` | Human review provenance for ambiguous medications |
| `audits/v11_value_level_listitems_decisions.csv` | Value-level listitem decisions for 2,529 rows |
| `audits/stage37_zero_sentinel_fix_affected_rows.csv` | Expected zero-sentinel cases; the rule itself should be code |
| `audits/stage38_lab_analyte_consolidation_changes.csv` | Expected lab consolidation decisions; useful as a parity fixture |
| `audits/stage39_canonicalize_omop_concept_namespace_changes.csv` | Namespace parity fixture; the rule itself should be code |
| `audits/stage40_lab_token_role_fix_affected_rows.csv` | Lab-role parity fixture; the rule itself should be code |
| `audits/stage41_gcs_score_component_fix_changes.csv` | GCS parity fixture; the rule itself should be code |

These files should be reduced into focused package-owned policy manifests. They
should not be copied wholesale into the public audit directory.

## End-To-End Historical Lineage

The clean implementation should preserve the behavior below without preserving the
historical file numbering.

### Stage 1: Source Vocabulary Extraction

Historical logic:

```text
scripts/04_mapping_coverage.py
scripts/06_harmonized_alias_coverage.py
scripts/07_drugitems_atc_coverage.py
scripts/08_final_harmonized_token_map.py
```

Current MetaICU implementation:

```text
src/metaicu/aumcdb/tokenized/vocab_pipeline/source_vocab.py
```

Source-token keys:

| Table | Key | Source-token format |
|---|---|---|
| `numericitems` | `itemid + unitid + code_prefix` | `{code_prefix}//{itemid}//{unit_or_UNKNOWN}` |
| `listitems` | `itemid + valueid` | `MEASUREMENT_CATEGORICAL//{itemid}//{valueid}` |
| `drugitems` | `itemid + ordercategoryid` | `DRUG//START//{ordercategoryid}//{itemid}` |
| `freetextitems` | `itemid` | `FREETEXT//{itemid}//1` |
| `processitems` | `itemid` | `PROCESS_INTERVAL//{itemid}` |
| `procedureorderitems` | `itemid + ordercategoryid` | `ORDER_INTENT//{ordercategoryid}//{itemid}` |

Input shape:

```text
raw event rows, more than 1 billion represented rows
```

Output shape:

```text
9,014 unique source-token rows
```

Required checks:

1. exactly one row per `source_token`;
2. positive `row_count`;
3. table-level `row_count` sums equal raw-table row counts;
4. typed source IDs are present for each table;
5. source labels, values, and units are preserved.

No mapping or emission decision belongs in this stage.

### Stage 2: Evidence Normalization

Historical logic was distributed across scripts 04, 06, 07, 14, 17, 18, and
`3j_external_search.py`.

Current MetaICU implementation:

```text
vocab_pipeline/resources.py
vocab_pipeline/evidence_normalization.py
```

This stage converts external files into a fixed evidence schema with:

```text
evidence source and file
source table
typed source IDs
source code/label
target vocabulary
target concept ID/code/label
mapping status
equivalence
match type
provenance text
```

Important rules:

1. normalize IDs as strings without `.0`;
2. normalize null/empty/`nan` consistently;
3. retain `target_concept_id == 0` as evidence meaning "no matching concept";
4. do not convert that sentinel into a real target;
5. preserve context-only and unmatched evidence;
6. fingerprint external files so a later rebuild can identify changed inputs.

### Stage 3: Candidate Map Construction

Current MetaICU implementation:

```text
vocab_pipeline/candidate_map.py
```

Typed joins:

| Table | Strong joins | Additional context joins |
|---|---|---|
| `numericitems` | `itemid + unitid` | item-only |
| `listitems` | `itemid + valueid` | item-only |
| `drugitems` | `itemid + ordercategoryid` | item-only, ordercategory-only |
| `freetextitems` | item-only | exact-label context |
| `processitems` | item-only | exact-label context |
| `procedureorderitems` | `itemid + ordercategoryid` | item-only, ordercategory-only |

Exact label matching is weak context, not a strong target assignment. Fuzzy matching
must not be introduced silently.

Output cardinality is one-to-many:

```text
one source token -> zero, one, or many candidate evidence rows
```

The candidate table is not a vocabulary. It has not selected a destination or an
emission policy.

### Stage 4: Baseline Target Resolution, v0-v3

Historical code:

```text
scripts/08_final_harmonized_token_map.py
scripts/09_omop_vocab_inventory.py
scripts/11_omop_validation_rollup_audit.py
scripts/12_review_harmonized_token_map.py
scripts/14_refresh_extended_token_map.py
scripts/16_stage3i_full_mapping_refresh.py
```

The historical v0 candidate ranking was per source token:

```text
prefer emitted candidate
then confidence: high > medium > low > unmapped
then evidence source priority
then non-empty token
then lexical token order
```

Historical source priorities:

```text
BlendedICU                       80
AMSTEL_source_concepts          75
AMSTEL                          70
AmsterdamUMCdb_dictionary       65
AMSTEL_usagi                    60
BlendedICU label context        10
```

OMOP review then:

1. verifies concept existence and validity;
2. checks standard/non-standard status;
3. applies a safe single `Maps to` replacement when source and target domains are
   compatible;
4. downgrades invalid or unsafe mappings;
5. keeps unmapped source tokens for review rather than deleting them.

v2 added process/procedure and YAIB/ricu evidence. v3 reran the same logic on the
full source vocabulary. The clean pipeline does not need to materialize v0, v1, or
v2; it needs one `resolve_baseline_targets()` stage with auditable ranking columns.

Full v3 result:

```text
9,014 source tokens
4,789 emitted source tokens
962,313,444 emitted represented rows
1,689 unique emitted destinations
```

Known defect: the ranking is independent per `source_token`. It does not coordinate
multiple item IDs representing the same lab analyte. Stage 9 below corrects this.

### Stage 5: Curated Unmapped Policy, v4

Historical code:

```text
scripts/17_stage3j_v3_review_queue_triage.py
scripts/18_amsterdamumcdb_external_inventory.py
scripts/3j_external_search.py
scripts/19_apply_stage3j_curated_policy_v4.py
```

Primary curated input:

```text
audits/stage3j_amsterdamumcdb_unmapped_item_evidence_curated.csv
```

The 3,412-token queue contained:

```text
drop   2,178
merge  1,137
unique    97
```

Durable behavior:

1. map clear local clinical families to local parent tokens;
2. use exact OMOP concepts only where the curated evidence is specific;
3. disable low-value rows without deleting source identity;
4. keep unresolved clinically meaningful rows visible for later policy;
5. do not treat a broad valid OMOP match as automatic proof of usefulness.

v4 result:

```text
5,216 emitted source tokens
1,007,440,569 emitted represented rows
```

### Stage 6: Complete Keep/Drop Review, v5

Historical code/data:

```text
scripts/20_finalize_v4_token_dictionary_review.py
scripts/21_apply_stage3l_decisions_v5.py
notebooks/3L_aggressive_vocab_decisions.csv
```

The final reviewed file contains one decision for every source token:

```text
keep  5,263
drop  3,751
```

The rule was intentionally aggressive:

1. retain high-count, trajectory-relevant concepts;
2. drop low-count rows unless clearly important;
3. preserve all source rows for traceability;
4. resolve or explicitly defer known medication conflicts;
5. exclude free text and order intent from first-pass model input.

v5 result:

```text
5,232 emitted source tokens
1,008,469,861 emitted represented rows
0 rows left with needs_review=True
```

### Stage 7: Semantic Contamination and Token Roles, v6

Historical code:

```text
utils/semantic_checks.py
utils/token_policy.py
utils/token_namespace.py
scripts/22_v5_semantic_contamination_audit.py
scripts/23_apply_stage3n_v6_vocab_cleanup.py
```

The audit assigned one of:

```text
no_flag
hard_drop
collapse_to_broad_token
keep_review_device_support
keep_as_static_context
```

Core policies:

1. drop contact/family/social/admin metadata;
2. drop nursing workflow and discharge checklists;
3. drop order intent;
4. drop specimen storage and no-result workflow statuses;
5. drop outcome/discharge metadata from predictors;
6. drop hospital-flow, isolation, restraint, TED, and mobilization workflow;
7. collapse oral, enteral, and parenteral nutrition;
8. keep broad fluid and blood-product categories;
9. retain relevant lines, catheters, drains, tubes, and tracheostomy as device
   support;
10. assign explicit token roles;
11. distinguish OMOP concept IDs from native LOINC codes;
12. protect clinical false positives such as "follows commands."

v6 result:

```text
5,005 emitted source tokens
1,008,153,378 emitted represented rows
1,727 unique emitted destinations
```

### Stage 8: Targeted Device, Outcome, and Respiratory Policies, v7-v9

Historical code:

```text
scripts/24_v6_targeted_refinement_audit.py
scripts/25_apply_stage3p_vocab_refinements_v8.py
scripts/26_apply_v9_cleanup.py
```

v7/v8 decisions:

1. fix four known medication conflicts using source-label/ingredient congruence;
2. correct the Procainamide source mapping;
3. avoid dozens of CRRT leaf tokens;
4. collapse CRRT/device concepts at clinically useful coarse levels;
5. drop `Overleden voor IC-opname`.

v9 decisions:

1. drop every Glasgow Outcome Score value as outcome metadata;
2. keep useful `NICE Opname type` values as static admission context;
3. drop clinician targets/setpoints represented by `SNOMED//602639`;
4. split the broad respiratory device parent into coarse signal-bearing children;
5. drop respiratory workflow/barrier rows.

v9 result:

```text
4,973 emitted source tokens
1,008,001,315 emitted represented rows
1,742 unique emitted destinations
```

### Stage 9: Medication Normalization, v10

Historical evidence and review code:

```text
scripts/29_map_omop_only_medications_to_atc.py
scripts/30_audit_unmapped_omop_medication_atc_misses.py
scripts/31_resolve_omop_only_medication_atc_candidates.py
scripts/32_finalize_omop_only_medication_atc_decisions.py
```

Important reproducibility gap:

```text
There is no retained single script that assembles final_harmonized_token_map_v10_clean.csv.
```

The candidate and decision artifacts are retained, so the clean implementation can
reconstruct the step explicitly.

Medication partition:

| Action | Source tokens |
|---|---:|
| Normalize existing ATC-backed medication | 267 |
| Apply reviewed OMOP-to-ATC decision | 340 |
| Correct nutrition mixtures | 6 |
| Preserve broad non-medication policy | 273 |

Output policy:

1. ATC-backed medications use the most detailed hierarchical token:
   `C07AB02 -> MEDICATION//C07//A//B02`;
2. complete ATC code remains in `target_code`;
3. runtime can truncate the hierarchy;
4. no descriptive drug class is invented;
5. nutrition, fluids, blood products, devices, and metadata remain non-medication
   categories;
6. dose, rate, route, and solution detail are not model tokens.

v10 result:

```text
607 emitted ATC-backed medication source tokens
384 unique most-detailed medication destinations
4,973 emitted source tokens overall
```

The v10 implementation in MetaICU should join the reviewed action-ready medication
manifest to v9 policy state and populate the compact schema. It must not use v10
itself as an input.

### Stage 10: Value-Level Listitem Cleanup, v11

Historical code:

```text
scripts/36_apply_v11_value_level_listitems_cleanup.py
```

Inputs:

```text
final_harmonized_token_map_v10_clean.csv
audits/aumc_meds_bounded_qc/listitems_value_level_mapping_missed_assessment.csv
omop_vocab/CONCEPT.csv
```

Decision audit:

```text
audits/v11_value_level_listitems_decisions.csv
```

Main actions:

| Action | Source tokens |
|---|---:|
| Diagnosis context mapping | 2,010 |
| Drop score components under the old policy | 105 |
| Drop residual tails | 180 |
| Ventilation mode family | 44 |
| Chest-drain state | 36 |
| AMSTEL value-level standard | 31 |
| Tube-size drop | 26 |
| Temperature-site drop | 19 |
| Chest-drain placement collapse | 18 |
| Body-position drop | 13 |
| RASS score | 10 |
| Bed-type drop | 8 |
| Ventilation-mode drop | 7 |
| Ramsay score | 6 |
| CRRT modality collapse | 5 |
| Admission-type preservation | 4 |
| IABP-trigger drop | 4 |
| Weight-source drop | 3 |

Durable mappings:

1. ventilation values map to pressure-support, pressure-control, volume-control,
   SIMV, NIV, or NAVA families;
2. standby/off/disconnected ventilation values are not emitted;
3. `MFT_Behandeling` values collapse to `DEVICE//CRRT`;
4. chest-drain placements collapse to `DEVICE//CHEST_DRAIN`;
5. suction/water-seal/clamped states use broad state tokens;
6. RASS and Ramsay final scores are preserved;
7. D/APACHE/NICE diagnoses become static diagnosis context;
8. low-value provenance, care-position, bed, tube-size, and device-configuration
   details are dropped;
9. selected AMSTEL value concepts are retained only when value-specific and
   clinically useful.

v11 result:

```text
9,014 source tokens
4,748 emitted source tokens
1,004,857,075 emitted represented rows
0 residual review tokens
```

Important superseded policy: v11 dropped GCS component rows. v16 reverses this and
emits GCS eye/motor/verbal components directly.

### Stage 11: OMOP Zero-Sentinel Fix, v12

Historical code:

```text
scripts/37_fix_target_concept_id_zero_sentinel.py
```

Rule:

```text
target_concept_id == 0
  -> no target concept
  -> harmonized target fields null
  -> emit_as_model_token=False
  -> token_role=metadata_only
  -> mapping_confidence=unmapped
```

Affected rows:

```text
23 total
12 procedureorderitems
11 processitems
```

No source rows are deleted and no emitted count changes, because these rows should
already be non-model metadata.

This rule belongs in shared target normalization and should be applied before final
policy output, not as a late version patch.

### Stage 12: Cross-Item Lab Analyte Consolidation, v13

Historical code:

```text
scripts/38_apply_lab_analyte_consolidation.py
```

Problem:

```text
baseline resolution selected a target independently per source token
```

This allowed a high-priority alias on one item ID to fragment an analyte even when
AMSTEL and the Amsterdam dictionary agreed across multiple item IDs.

Historical algorithm:

1. select `LAB//` rows with mapped target concepts;
2. load real concept names from `CONCEPT.csv`;
3. derive a coarse base analyte by removing bracket qualifiers and text after
   `" in "`;
4. find base-analyte groups with more than one target concept;
5. pool all retained alias candidates for every source token in a group;
6. rank target concepts by:
   - emitted evidence,
   - number of corroborating item IDs,
   - represented row count,
   - confidence,
   - source priority,
   - token availability;
7. apply the group winner to every group member;
8. keep quantile boundaries separated by source token/unit at runtime.

Result:

```text
50 fragmented groups detected
197 source tokens changed
34 groups resolved
16 groups left unchanged due to missing candidate evidence
1 additional source token emitted
35 additional represented rows emitted
```

Important limitation: script 38 loads
`mappings/harmonized_alias_candidates.csv`, which is the smaller historical
candidate file, not `stage3i_full_harmonized_alias_candidates.csv`. Exact v13/v16
parity therefore requires preserving the 197 reviewed outcomes. A future improved
analyte-resolution version can use the full candidate table, but that would be a
new vocabulary policy and should not be mixed into the parity refactor.

### Stage 13: Canonical OMOP Namespace, v14

Historical code:

```text
scripts/39_canonicalize_omop_concept_namespace.py
```

Original implementation gap:

```text
the prior policy_replay.py that performed this operation was lost
```

The rule was reverse-engineered by comparing every legacy row with the packaged
MetaICU vocabulary and found to be deterministic:

```text
OMOP//OMOP_CONCEPT//{concept_id}
  + CONCEPT.csv vocabulary_id
  -> OMOP_CONCEPT//{vocabulary_id}//{concept_id}
```

The same `vocabulary_id` is written to `target_vocabulary`. Emission and concept ID
do not change.

v14 result:

```text
1,342 legacy-prefix rows found
1,282 canonicalized
60 left legacy because concept ID was absent from the local Athena export
0 emitted legacy-prefix rows
4,749 emitted source tokens
1,004,857,110 emitted represented rows
3,280 unique emitted destinations
```

The 60 unresolved legacy rows are non-emitted. Exact v16 parity keeps them as they
are. Removing their stale target strings would be a separate cleanup decision.

### Stage 14: Lab Role Correction, v15

Historical code:

```text
scripts/40_fix_lab_token_role.py
```

Rule:

```text
emit_as_model_token=True
and source_token starts with LAB//
  -> token_role=dynamic_event/lab
```

The rule depends on the Amsterdam source prefix, not the target vocabulary. A
non-lab row mapped to LOINC, such as `SUBJECT_FLUID_OUTPUT//...`, must not receive
the lab role.

Affected rows:

```text
319 roles changed in v14
516 emitted LAB// rows correct after the stage
```

The other 197 lab rows already received the role during v13 consolidation.

### Stage 15: GCS Component Correction, v16

Historical code:

```text
scripts/41_fix_gcs_score_component_emission.py
```

Rules:

1. listitem rows mapped to the six accepted GCS eye/motor/verbal component concepts
   are emitted;
2. their role is `dynamic_event/score_component`;
3. itemid `14482` (`RA_Verbal`) maps to verbal concept `3013144`, not motor concept
   `3026549`.

Accepted component concept IDs:

```text
3016335
3026019
3008223
3026549
3009094
3013144
```

Result:

```text
88 GCS source-token rows emitted
877,730 represented rows restored
3 RA_Verbal rows corrected
4,837 emitted source tokens overall
```

This supersedes the v11 policy that expected runtime total-GCS derivation.

## Version Summary

| Artifact | Emitted tokens | Emitted rows | Unique destinations | Main change |
|---|---:|---:|---:|---|
| v3 | 4,789 | 962,313,444 | 1,689 | Full baseline candidate resolution |
| v4 | 5,216 | 1,007,440,569 | 1,767 | Curated unmapped policy |
| v5 | 5,232 | 1,008,469,861 | 1,770 | Complete keep/drop review |
| v6 | 5,005 | 1,008,153,378 | 1,727 | Semantic contamination and roles |
| v7 | 5,004 | 1,008,153,376 | 1,727 | Tiny outcome-leakage correction |
| v8 | 5,004 | 1,008,153,376 | 1,737 | Medication conflicts and coarse CRRT |
| v9 | 4,973 | 1,008,001,315 | 1,742 | Outcome, target, admission, respiratory cleanup |
| v10 | 4,973 | 1,008,001,315 | 1,776 | ATC-backed medication normalization |
| v11 | 4,748 | 1,004,857,075 | 3,394 | Value-level listitem cleanup |
| v12 | 4,748 | 1,004,857,075 | 3,394 | OMOP zero sentinel |
| v13 | 4,749 | 1,004,857,110 | 3,280 | Cross-item lab consolidation |
| v14 | 4,749 | 1,004,857,110 | 3,280 | Canonical namespaces |
| v15 | 4,749 | 1,004,857,110 | 3,280 | Lab role |
| v16 | 4,837 | 1,005,734,840 | 3,286 | GCS component policy |

## Proposed MetaICU Module Layout

Do not port the numbered scripts as numbered package modules. Keep the existing
source/evidence/candidate code and add explicit resolution and policy layers:

```text
src/metaicu/aumcdb/tokenized/vocab_pipeline/
  build_workflow.py
  source_vocab.py
  resources.py
  evidence_normalization.py
  candidate_map.py
  target_resolution.py
  omop_validation.py
  schema.py
  validation.py
  policies/
    __init__.py
    engine.py
    table_exclusions.py
    semantic_contamination.py
    device_support.py
    admission_outcome.py
    medications.py
    listitem_values.py
    diagnosis_context.py
    laboratory.py
    score_components.py
    namespace.py
  data/
    source_policy_overrides.csv
    medication_atc_decisions.csv
    listitem_value_decisions.csv
    lab_consolidation_decisions.csv
```

Responsibilities:

| Module | Responsibility |
|---|---|
| `source_vocab.py` | Extract canonical source-token rows and counts |
| `evidence_normalization.py` | Normalize external files without selecting targets |
| `candidate_map.py` | Build one-to-many candidate evidence |
| `omop_validation.py` | Resolve concept metadata and standard/valid status |
| `target_resolution.py` | Rank baseline candidates and expose ranking columns |
| `policies/engine.py` | Apply policy layers in a fixed order and record ownership |
| `policies/medications.py` | Apply ATC and non-drug drugitem policies |
| `policies/listitem_values.py` | Apply ventilation, CRRT, drain, score, and residual policies |
| `policies/laboratory.py` | Apply analyte consolidation and lab roles |
| `policies/namespace.py` | Canonicalize concept namespaces |
| `validation.py` | Enforce the supplied-vocabulary contract |

The exact filenames can change. The important boundary is:

```text
evidence generation != target resolution != clinical policy != validation
```

## Policy Manifest Contract

Clinical decisions should be package data, not hard-coded across long `if/elif`
blocks and not hidden inside the final CSV.

Recommended common columns:

```text
source_token
policy_layer
action
harmonized_token
token_role
emit_as_model_token
target_vocabulary
target_concept_id
target_code
target_label
mapping_source
match_strength
mapping_confidence
reason
evidence_reference
```

Not every manifest needs every target field. Deterministic families should remain
code:

```text
freetext exclusion
procedure-order exclusion
target_concept_id=0 normalization
LAB// role assignment
OMOP namespace canonicalization
GCS component role assignment
ATC token construction from target_code
```

Reviewed exceptions should remain data:

```text
source-token-specific medication ATC decisions
selected listitem value decisions
lab consolidation outcomes needed for exact parity
curated local parent-token assignments
source-token drops that cannot be inferred safely
```

Every final field should have one owning policy layer. The policy decision audit
should record:

```text
source_token
field
before
after
policy_layer
reason
```

## Single-Command Orchestration

The public command remains:

```bash
build-amsterdam-vocab paths.parent_dir=/path/to/aumc_workspace
```

Internally it should execute:

```text
1/7 validate raw inputs and external resource fingerprints
2/7 extract canonical source vocabulary
3/7 normalize mapping evidence
4/7 construct and validate candidate targets
5/7 resolve baseline targets
6/7 apply clinical policy layers
7/7 validate and write supplied vocabulary
```

Pseudocode:

```python
def build_vocabulary(config):
    resources = validate_and_fingerprint_resources(config)

    source_vocab = extract_source_vocabulary(
        raw_data_dir=config.raw_data_dir,
    )

    evidence = normalize_external_evidence(
        external_root=config.external_root,
        omop_vocab_dir=config.omop_vocab_dir,
    )

    candidates = construct_candidates(
        source_vocab=source_vocab,
        evidence=evidence,
    )

    validated_candidates = validate_omop_targets(
        candidates=candidates,
        omop_vocab_dir=config.omop_vocab_dir,
    )

    baseline = resolve_baseline_targets(
        source_vocab=source_vocab,
        candidates=validated_candidates,
    )

    final_vocab, decisions = apply_policy_layers(
        baseline=baseline,
        candidates=validated_candidates,
        policy_data=config.policy_data_dir,
        omop_vocab_dir=config.omop_vocab_dir,
    )

    report = validate_supplied_vocab(
        source_vocab=source_vocab,
        final_vocab=final_vocab,
    )

    write_vocab(final_vocab, config.output_vocab)
    write_build_audits(resources, source_vocab, candidates, decisions, report)
```

The final stage must never read a prebuilt supplied vocabulary as its source.

## Policy Layer Order

Use a fixed order so later specific policies can intentionally override earlier
general policies:

```text
1. baseline target resolution
2. target sentinel normalization
3. table-level exclusions
4. broad semantic contamination and token-role policy
5. curated local parent/device/nutrition policy
6. medication ATC and non-drug drugitem policy
7. admission/outcome/care-target policy
8. listitem value-level policy
9. diagnosis-context policy
10. cross-item lab consolidation
11. canonical namespace formatting
12. source-derived role assignment
13. GCS score-component policy
14. compact-schema normalization
```

Each layer receives and returns the same 9,014-row table. A layer may change
mapping/emission fields, but not source identity or `row_count`.

## Validation Contract

### Structural Invariants

1. source-token rows equal extracted source-token rows;
2. `source_token` is unique and non-empty;
3. source identity columns and `row_count` are unchanged by policy layers;
4. every emitted row has a non-empty `harmonized_token` and `token_role`;
5. no non-emitted row is silently used as a model token;
6. no emitted target uses `target_concept_id=0`;
7. every populated OMOP concept ID is checked against the configured Athena export;
8. no emitted token starts with `OMOP//OMOP_CONCEPT//`;
9. no emitted `freetextitems` or `procedureorderitems`;
10. all emitted `LAB//` rows have `dynamic_event/lab`;
11. no non-`LAB//` source row has `dynamic_event/lab`;
12. all accepted GCS components are emitted as
    `dynamic_event/score_component`;
13. `RA_Verbal` resolves to concept `3013144`;
14. medication hierarchy tokens reconstruct from `target_code`;
15. known metoprolol/pantoprazole and procainamide/neostigmine conflicts are absent.

### Full Migration Parity

During refactoring, compare rebuilt output with v16 by normalized source token:

```text
source identity columns
harmonized_token
token_role
emit_as_model_token
non_drug_drugitem_class
target_vocabulary
target_concept_id
target_code
target_label
mapping_source
match_strength
mapping_confidence
```

Acceptance for the current Amsterdam release:

```text
missing source tokens = 0
extra source tokens = 0
different policy rows = 0
unowned policy fields = 0
```

Once parity is achieved, v16 remains a development test oracle only. The public
build must not read it.

### Changed Dataset Releases

Exact 9,014-row parity applies to the current Amsterdam release. For a changed
release:

1. known source tokens receive existing rules/curated decisions;
2. new source tokens receive candidate evidence but no silent fallback emission;
3. unresolved new tokens are written to a review audit;
4. final build fails by default if emitted policy is incomplete;
5. an explicit audit-only/incomplete mode may write candidates without calling the
   result a supplied vocabulary.

Row-count changes alone do not invalidate an existing mapping, but must appear in
the build summary.

## Required Build Audits

The one-command build should write:

```text
run_config.json
external_resource_fingerprints.csv
source_vocab.csv
source_vocab_summary.json
mapping_evidence_summary.json
candidate_summary.json
candidate_unmatched_source_tokens.csv
target_resolution_summary.json
policy_decisions.csv
policy_coverage_summary.json
final_vocab_summary.json
final_vocab_validation.json
```

Useful summary fields:

```text
raw rows by table
source tokens by table
candidate coverage by table/family
valid and invalid OMOP targets
policy actions by layer
emitted/non-emitted token and row counts
unresolved source tokens
namespace violations
source-token identity changes
external resource hashes/versions
```

Audits explain the build. They are not additional user decisions or required
manual stages.

## Tests To Implement

### Unit Tests

1. source-token construction for all six tables;
2. typed candidate joins and evidence specificity;
3. OMOP zero-sentinel normalization;
4. standard/non-standard target validation;
5. candidate ranking with explicit tie-breaks;
6. semantic contamination rules;
7. medication ATC token construction;
8. non-drug drugitem routing;
9. ventilation, CRRT, and chest-drain policies;
10. diagnosis-context token construction;
11. lab analyte group ranking;
12. OMOP namespace canonicalization;
13. lab role assignment by source prefix;
14. GCS component emission and RA_Verbal correction;
15. policy ownership and conflict detection.

### Bounded Integration Test

Use tiny raw fixtures containing:

```text
one numeric lab with two item IDs
one bedside numeric row
one categorical ventilation mode
one GCS verbal row
one medication
one nutrition drugitem
one freetext item
one process interval
one procedure order
one OMOP zero-sentinel candidate
```

Verify the exact compact output and all stage summaries.

### Full Regression Test

Run the complete build on the current Amsterdam release and compare to v16. This
should be an HPC job because source-vocabulary extraction scans the raw tables.

The regression test should report differences rather than only assert a checksum.
For each difference, include source token, old value, new value, and owning policy
layer.

## Historical Code Migration Map

| Historical scripts | Clean destination |
|---|---|
| `04`, `06`, `07` | Existing evidence normalization and candidate construction |
| `08`, `11`, `12`, `14`, `16` | `target_resolution.py` and `omop_validation.py` |
| `17`, `18`, `3j_external_search` | Development evidence reports; do not expose as public stages |
| `19`, `20`, `21` | Curated source-policy manifests plus policy engine |
| `22`, `23` | Semantic contamination policy modules |
| `24`, `25`, `26` | Device, outcome, admission, care-target, and respiratory policies |
| `29`, `30`, `31`, `32` | Medication policy module plus reviewed medication manifest |
| `36` | Listitem value policy module plus reviewed listitem manifest |
| `37` | Shared target normalization |
| `38` | Lab analyte policy module |
| `39` | Namespace formatting module |
| `40` | Source-derived role assignment |
| `41` | Score-component policy module |

## Files Not To Port As Pipeline Stages

Do not recreate:

1. one CLI per historical artifact version;
2. bounded and full variants of the same mapping logic;
3. notebooks as runtime dependencies;
4. exploratory semantic samples as required build steps;
5. historical extended vocabularies with 40-79 stage-specific columns;
6. v0-v15 intermediate CSVs in user workspaces;
7. a final `copy2()` of a packaged vocabulary.

Keep historical artifacts under research provenance until full v16 parity is
achieved. After that, the clean build code, policy data, final contract tests, and
current supplied vocabulary are the maintained implementation.

## Recommended Implementation Sequence

1. Freeze v16 as the internal migration oracle and add a normalized diff helper.
2. Add package-owned policy manifests extracted from the retained curated audits.
3. Implement OMOP validation and baseline target resolution after candidate-map
   construction.
4. Implement table, semantic, device, outcome, and admission policy modules.
5. Implement medication normalization from the action-ready ATC decisions.
6. Implement listitem value policies and diagnosis context.
7. Integrate zero-sentinel, lab consolidation, namespace, lab-role, and GCS rules
   as normal policy layers.
8. Replace `shutil.copy2()` with the actual resolver and policy engine.
9. Run bounded fixtures.
10. Run full source-token and cell-level parity against v16.
11. Promote the rebuilt output to `mappings/aumc_supplied_vocab.csv`.
12. Update contract counts from 4,836/515/14,301,315 to the corrected v16 values
    4,837/516/14,301,350.
13. Remove v-version names from active user-facing code after parity is proven.

## Failure Modes

1. **Candidate table mistaken for final vocabulary**: candidates have evidence,
   not policy.
2. **Static artifact copied after diagnostics**: raw data has no effect on output.
3. **Curated decisions omitted**: OMOP validation alone reintroduces social/admin
   contamination and loses local device meaning.
4. **Evidence priority used as semantic truth**: a high-priority alias can beat
   cross-item consensus.
5. **`target_concept_id=0` treated as a concept**: creates false OMOP tokens.
6. **Concept ID treated as native LOINC code**: corrupts namespace semantics.
7. **Medication table treated as pure medication**: misclassifies nutrition,
   fluids, blood products, and workflow rows.
8. **Item-level list mapping loses value meaning**: collapses ventilation, pupil,
   rhythm, score, and drain states.
9. **Lab role inferred from LOINC target**: mislabels non-lab fluid-output rows.
10. **GCS v11 behavior retained accidentally**: drops component rows that v16
    intentionally emits.
11. **Unpinned external resources**: target labels or candidate rankings can change
    without a policy change.
12. **New source tokens silently emitted**: changed dataset releases bypass review.
13. **Exact hash used as the only test**: harmless CSV formatting changes look like
    semantic failures.
14. **Only aggregate counts tested**: equal counts can hide row-level mapping
    swaps.

## Definition Of Done

The cleaned MetaICU vocabulary orchestration is complete when:

1. `build-amsterdam-vocab` does not read a supplied vocabulary as an input;
2. raw data, external evidence, and packaged policy manifests determine the output;
3. every final field has a recorded policy owner;
4. the current Amsterdam release reproduces v16 with zero row-level policy
   differences;
5. the final artifact passes all structural and semantic contract tests;
6. users run one command and receive one compact vocabulary plus audits;
7. no historical numbered mapping scripts are required by the installed package.
