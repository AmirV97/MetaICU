# Amsterdam Vocabulary Documentation

## External Resources Used For Amsterdam Vocabulary Construction

The Amsterdam vocabulary-preparation workflow uses several external reference resources. GitHub-hosted resources can be retrieved with:

```bash
python scripts/retrieve_externals.py \
  --parent-dir /path/to/aumc_workspace
```

The OMOP/Athena vocabulary export must be downloaded manually from Athena because it requires a user account and vocabulary/license selection. The user-facing build command then receives both roots explicitly:

```bash
python scripts/build_amsterdam_vocab.py \
  step=build_vocab \
  paths.parent_dir=/path/to/aumc_workspace
```

Expected path placeholders used below:

- `{parent_dir}`: user workspace containing `AUMC_raw/`, `externals/`, and `outputs/`.
- `{external_root}`: usually `{parent_dir}/externals`, containing cloned/copied Amsterdam-related external repositories and resources.
- `{omop_vocab_dir}`: usually `{parent_dir}/externals/omop_vocab`, containing a local Athena/OMOP vocabulary export.

### Resource Families

| Resource family | Upstream source | Expected relative path | Required? | Key files | How it is used |
|---|---|---|---|---|---|
| AMSTEL mappings | AMSTEL AmsterdamUMCdb-to-OMOP mapping assets. Repository/source location should be recorded with the downloaded copy. | `{external_root}/AMSTEL/data/mappings/` | Required | `*.usagi.csv`, `source_to_concept_map.csv`, `source_to_value_map.csv`, `local_vocabularies.yaml` | Provides OMOP/standard-concept candidates from USAGI and AMSTEL source-to-concept/value maps. Used for item/value/unit/order-category mapping evidence. |
| AMSTEL source concepts | AMSTEL source concept tables distributed with the AMSTEL mapping assets. | `{external_root}/AMSTEL/data/source_concepts/` | Required | `drugitems_item.csv`, `drugitems_ordercategory.csv`, `listitems_item.csv`, `listitems_value.csv`, `numericitems_lab.csv`, `numericitems_other.csv`, `numericitems_tag.csv`, `numericitems_unit.csv`, `freetextitems_item.csv`, `freetextitems_values.csv`, `processitems_item.csv`, `procedureorderitems_item.csv` | Provides Amsterdam source vocabulary metadata, source codes, labels, approved/unmatched status, ATC/source-code evidence, and table-specific context. |
| Official AmsterdamUMCdb current dictionary | [AmsterdamUMC/AmsterdamUMCdb](https://github.com/AmsterdamUMC/AmsterdamUMCdb). Equivalent in purpose to `amsterdamumcdb.get_dictionary(legacy=False)`. | `{external_root}/AmsterdamUMCdb/amsterdamumcdb/dictionary/dictionary.csv` | Required | `dictionary.csv` | Provides official Amsterdam source concepts mapped to OHDSI vocabularies where available, including concept IDs, names, vocabulary IDs, mapping status, and equivalence. |
| Official AmsterdamUMCdb legacy dictionary | [AmsterdamUMC/AmsterdamUMCdb](https://github.com/AmsterdamUMC/AmsterdamUMCdb). Equivalent in purpose to `amsterdamumcdb.get_dictionary(legacy=True)`. | `{external_root}/AmsterdamUMCdb/amsterdamumcdb/dictionary/legacy/dictionary.csv` | Required | `dictionary.csv` | Provides legacy/raw-table item, value, and unit metadata, English labels, categories, expected ranges, and source-table context. |
| Official AmsterdamUMCdb legacy flowsheet SQL groupings | [AmsterdamUMC/AmsterdamUMCdb flowsheet SQL files](https://github.com/AmsterdamUMC/AmsterdamUMCdb/tree/master/amsterdamumcdb/sql/flowsheets/legacy). | `{external_root}/AmsterdamUMCdb/amsterdamumcdb/sql/flowsheets/legacy/` | Required for high-count local grouping policies | `get_respiration_flowsheet_itemids.sql`, `get_circulation_flowsheet_itemids.sql`, `get_nephrology_flowsheet_itemids.sql`, `get_neurology_flowsheet_itemids.sql` | Provides official clinical grouping/context for high-count flowsheet variables, especially ventilation, circulation, nephrology/CRRT, and neurology variables. These are grouping/context evidence, not direct OMOP mappings. |
| BlendedICU timeseries/user-input assets | [BlendedICU](https://github.com/USM-CHU-FGuyon/BlendedICU) or the BlendedICU resource mirror used by the project. | `{external_root}/BlendedICU/auxillary_files/user_input/` | Important curated evidence | `timeseries_variables.csv`, `medication_ingredients.csv`, `manual_icu_meds.csv`, `unit_type_v2.json`, `admission_origins_v2.json`, `discharge_location_v2.json`, `med_administration_routes.json` | Provides curated ICU variable context, unit hints, medication ingredient hints, and cross-dataset context. |
| BlendedICU medication assets | [BlendedICU](https://github.com/USM-CHU-FGuyon/BlendedICU) medication mapping resources, where available. | `{external_root}/BlendedICU/auxillary_files/medication_mapping_files/` | Optional context/evidence source | `drugnames.parquet`, `amsterdam_medications.csv`, `med_concept_ids.parquet`, `ohdsi_icu_medications.csv`, plus available dataset medication CSV/JSON references | Provides medication name context and cross-dataset medication mapping hints. Weak label-only matches should not override stronger AMSTEL/OMOP/ATC evidence. |
| OMOP / Athena local vocabulary export | [OHDSI Athena](https://athena.ohdsi.org/) vocabulary download. Users should download the vocabularies needed for OMOP/OHDSI concept validation. CPT4/UMLS-sensitive files may require appropriate licensing. | `{omop_vocab_dir}/` | Required | `CONCEPT.csv`, `CONCEPT_RELATIONSHIP.csv`, `CONCEPT_ANCESTOR.csv`, `VOCABULARY.csv`, `DOMAIN.csv`, `RELATIONSHIP.csv`, `CONCEPT_CLASS.csv`, `CONCEPT_SYNONYM.csv`, `DRUG_STRENGTH.csv` | Validates and enriches target concepts: concept labels, codes, domains, standard/non-standard status, relationships, ancestors, and ATC/RxNorm evidence. OMOP validity alone does not decide whether a token is useful for ICU trajectory modeling. |
| YAIB / ricu configs | [YAIB](https://github.com/ykim97/YAIB) / ricu-related concept configuration resources, if available. `ricu` itself is available at [eth-mds/ricu](https://github.com/eth-mds/ricu). | `{external_root}/YAIB-cohorts/ricu-extensions/configs/`, `{external_root}/ricu/` | Optional auxiliary evidence | ricu/YAIB config files and concept definitions | Provides ICU concept grouping and extraction-config hints from external ICU harmonization work. Useful as auxiliary context, not as a required source of final Amsterdam mappings. |

### Required Versus Optional Inputs

The core vocabulary-preparation workflow expects AMSTEL mappings/source concepts, official AmsterdamUMCdb dictionaries, selected AmsterdamUMCdb flowsheet SQL groupings, and a local OMOP/Athena export. BlendedICU timeseries resources are important curated ICU context. BlendedICU medication assets and YAIB/ricu configs are useful auxiliary sources and should be included when available, but should not silently become hard dependencies unless a pipeline step explicitly requires them.

### Interpretation Rules

- OMOP/Athena validates and enriches candidate targets, but OMOP validity alone does not decide model usefulness.
- AMSTEL and AmsterdamUMCdb dictionary entries can identify standard concepts, officially unmatched concepts, and source-context metadata. Preserve this evidence with provenance.
- BlendedICU label matches are useful context, but weak label-only medication matches should not override stronger AMSTEL/OMOP/ATC evidence.
- Flowsheet SQL files provide clinical grouping/context for Amsterdam source variables; they should not be treated as direct standard-concept mappings.

### Athena Vocabulary Checklist

Open [OHDSI Athena](https://athena.ohdsi.org/vocabulary/list) and select these vocabularies for the current Amsterdam ICU vocabulary workflow:

- SNOMED
- LOINC
- RxNorm
- RxNorm Extension
- ATC
- UCUM
- OMOP Extension

After Athena prepares the download, extract the archive into `{omop_vocab_dir}`. The extracted directory must contain at least:

- `CONCEPT.csv`
- `CONCEPT_RELATIONSHIP.csv`
- `CONCEPT_ANCESTOR.csv`
- `VOCABULARY.csv`
- `DOMAIN.csv`
- `RELATIONSHIP.csv`
- `CONCEPT_CLASS.csv`
- `CONCEPT_SYNONYM.csv`
- `DRUG_STRENGTH.csv`

CPT4 is not required for the current Amsterdam ICU trajectory vocabulary and may require additional UMLS licensing. Add it only if a later procedure/billing use case requires it.
