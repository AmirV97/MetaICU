# Vocabulary Policy Decisions

This file explains the supplied vocabulary artifact:

```text
mappings/aumc_supplied_vocab.csv
```

The vocabulary is source-preserving: every Amsterdam source token is kept, even when it is not emitted as a model token.

## Schema

| Column | Meaning |
|---|---|
| `dataset` | Source dataset name. |
| `source_table` | Amsterdam source table, e.g. `numericitems`, `listitems`, `drugitems`. |
| `source_itemid` | Amsterdam item ID. |
| `source_valueid` | Amsterdam categorical value ID, mainly for `listitems`. |
| `source_unitid` | Amsterdam unit ID, mainly for `numericitems`. |
| `source_ordercategoryid` | Drug/order category ID, mainly for `drugitems`. |
| `source_label` | Original Amsterdam item label. |
| `source_value` | Original categorical value label, when applicable. |
| `source_unit` | Original unit label, when applicable. |
| `source_token` | Stable source-token key used for joins and traceability. |
| `row_count` | Number of raw/pre-MEDS rows represented by this source token. |
| `harmonized_token` | Model-facing destination token if emitted. |
| `token_role` | Runtime role, e.g. `dynamic_event`, `dynamic_event/lab`, `static_context/diagnosis_context`, `metadata_only`. |
| `emit_as_model_token` | Whether this source token should become a model event/context token. |
| `non_drug_drugitem_class` | Semantic class for non-medication rows found in `drugitems`. |
| `target_vocabulary` | Target vocabulary, when mapped to a standard concept/code. |
| `target_concept_id` | OMOP concept ID, when available. |
| `target_code` | Native target code, e.g. ATC or LOINC code, when available. |
| `target_label` | Human-readable target concept/code label. |
| `mapping_source` | Evidence source used for the mapping/policy. |
| `match_strength` | Mapping strength or policy confidence category. |
| `mapping_confidence` | Coarse confidence label for downstream review/debugging. |

## Core Decisions

- `emit_as_model_token=False` rows are kept for traceability but excluded from first-pass model input.
- `freetextitems` are excluded from first-pass model input.
- `procedureorderitems` are excluded because they represent order/intent, not completed clinical events.
- `drugitems` is not pure medication. Nutrition, fluids, food/drink, blood products, research rows, and device/order metadata are handled separately.
- Medication tokens use ATC-backed hierarchical tokens where possible, e.g. `MEDICATION//C07//A//B02`. Runtime can truncate these to coarser ATC levels.
- Dose, route, rate, and solution details are not emitted as model tokens in the current version.
- Food/nutrition details are collapsed to broad categories such as `NUTRITION//ORAL`, `NUTRITION//ENTERAL`, or `NUTRITION//PARENTERAL`.
- Fluids and blood products are collapsed to broad clinically useful categories.
- Device/support states are kept only when useful for ICU trajectory modeling.
- Workflow, contact/social/admin, discharge/outcome metadata, care targets, bed type, tube size, and similar low-value metadata are dropped from model input.
- Labs are identified by Amsterdam source token prefix `LAB//`, not by LOINC alone. These use `token_role=dynamic_event/lab`.
- Non-lab LOINC-backed rows, such as fluid-output concepts, are not labeled as labs.
- Diagnosis/context rows are static clinical context. Runtime should deduplicate repeated diagnosis facts per admission.
- GCS eye/motor/verbal component rows are emitted directly as `dynamic_event/score_component`, following OpenICU-style component concepts. Runtime should not derive a GCS total by default.
- BPS component rows are not emitted directly; a later runtime stage may derive total BPS when complete component bundles are available.
- High-frequency numeric streams are identified from the train split during pre-MEDS and written as causal mean-binned `numericitems_binned` datasets for each split. Empty windows are not emitted.
- All emitted non-medication numeric values should later be converted to train-split quantile tokens.

## Runtime Notes

The vocabulary is not itself a tokenized dataset. It is the policy artifact consumed by later MEDS/tokenization code.

Runtime code should:

1. join source rows to this vocabulary using typed source keys;
2. emit only rows with `emit_as_model_token=True`;
3. emit static context once per admission/stay;
4. emit dynamic events at source timestamps;
5. compute temporal phase at runtime;
6. consume `numericitems_binned` when present, fall back to raw `numericitems` otherwise, and apply train-frozen numeric quantiles before final tokenization.
