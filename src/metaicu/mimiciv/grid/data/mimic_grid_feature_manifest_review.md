### map, Mean Arterial Blood Pressure, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=5372922, value_range=[-22767, 8.99909e+06], median=78, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220181`
  - concept_id: `21492241`
  - raw label: `Non Invasive Blood Pressure mean`
  - stats: `row_count=5372922, value_range=[-22767, 8.99909e+06], median=78, units=mmHg`

match 2:
  - decision: `reject`
  - decision reason: `cross-contaminated: this is Pulmonary Artery Pressure MEAN (belongs to `mpap`), not systemic MAP -- shares a generic LOINC pressure component with MAP but is a distinct measurement`
  - table: `chartevents_main`
  - itemid: `220061`
  - concept_id: `3028074`
  - raw label: `Pulmonary Artery Pressure mean`
  - stats: `row_count=392768, value_range=[-38, 3731], median=26, units=mmHg`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=3096934, value_range=[-135, 930000], median=76, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220052`
  - concept_id: `3027598`
  - raw label: `Arterial Blood Pressure mean`
  - stats: `row_count=3096934, value_range=[-135, 930000], median=76, units=mmHg`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=390342, value_range=[-41, 8684], median=75, units=mmHg`
  - table: `chartevents_main`
  - itemid: `225312`
  - concept_id: `3027598`
  - raw label: `ART BP Mean`
  - stats: `row_count=390342, value_range=[-41, 8684], median=75, units=mmHg`

### lact, Lactate, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmol/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=670016, value_range=[-1.1, 1.2761e+06], median=1.7, units=mmol/L`
  - table: `labs`
  - itemid: `50813`
  - concept_id: `3047181`
  - raw label: `Lactate`
  - stats: `row_count=670016, value_range=[-1.1, 1.2761e+06], median=1.7, units=mmol/L`

### age, Age, demographic, not specified
- Mapping status: `admission_context`
- Reconstruction type: `admission_context`
- Target unit: `years`
- Match method: `admission_context_fixed`
- Notes: `age at admission = admittime.year - patients.year_of_birth (MIMIC's de-identified patients.parquet has no direct anchor_age column in this pre_MEDS export).`

### weight, Weight, demographic, not specified
- Mapping status: `admission_context`
- Reconstruction type: `admission_context`
- Target unit: `kg`
- Match method: `admission_context_fixed`
- Notes: `omr.result_name='Weight (Lbs)' (outpatient, sparse) or chartevents admission-weight itemids (226512 Kg, 224639 lbs) -- candidates only, not yet decided which to prefer.`

### sex, Sex, demographic, not specified
- Mapping status: `admission_context`
- Reconstruction type: `admission_context`
- Target unit: `categorical`
- Match method: `admission_context_fixed`
- Notes: `patients.gender (F/M) -- direct column, no collapsing needed.`

### height, Height, demographic, not specified
- Mapping status: `admission_context`
- Reconstruction type: `admission_context`
- Target unit: `cm`
- Match method: `admission_context_fixed`
- Notes: `omr.result_name='Height (Inches)' (outpatient, sparse) or chartevents itemid 226730 (Height (cm)) -- candidates only, not yet decided which to prefer.`

### hr, Heart Rate, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `bpm`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=8752069, value_range=[-241395, 1e+07], median=85, units=bpm`
  - table: `chartevents_main`
  - itemid: `220045`
  - concept_id: `3027018`
  - raw label: `Heart Rate`
  - stats: `row_count=8752069, value_range=[-241395, 1e+07], median=85, units=bpm`

### fio2, FiO2, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary FiO2 source -- missed by the automated keyword search because the tokenizer strips digits ("FiO2"->"fio"), never matching a label containing "FiO2"; found by a direct d_items re-search on "fio2|inspired o2"`
  - table: `chartevents`
  - itemid: `223835`
  - raw label: `Inspired O2 Fraction`

match 2:
  - decision: `keep`
  - decision reason: `legitimate FiO2 reading under ECMO context, same analyte via a different circuit`
  - table: `chartevents`
  - itemid: `229280`
  - raw label: `FiO2 (ECMO)`
  - stats: `row_count=26636, value_range=[0, 1000], median=100, units=%`

match 3:
  - decision: `keep`
  - decision reason: `legitimate FiO2 reading, ECMO-context device`
  - table: `chartevents`
  - itemid: `229841`
  - raw label: `FiO2 (CH)`
  - stats: `row_count=4201, value_range=[10, 1000], median=100, units=%`

match 4:
  - decision: `reject`
  - decision reason: `APACHE-IV severity-score input value, redundant with the raw FiO2 reading`
  - table: `chartevents`
  - itemid: `227010`
  - raw label: `FiO2_ApacheIV`
  - stats: `row_count=6, value_range=[50, 100], median=80, units=%`

match 5:
  - decision: `reject`
  - decision reason: `0 rows -- stale/deprecated itemid`
  - table: `chartevents`
  - itemid: `227009`
  - raw label: `FiO2_ApacheIV_old`

match 6:
  - decision: `reject`
  - decision reason: `APACHE-II severity-score input value, redundant, n=13`
  - table: `chartevents`
  - itemid: `226754`
  - raw label: `FiO2ApacheIIValue`
  - stats: `row_count=13, value_range=[50, 100], median=100, units=%`

match 7:
  - decision: `reject`
  - decision reason: `one-time O2 challenge test, not continuous FiO2`
  - table: `chartevents`
  - itemid: `229238`
  - raw label: `FiO2 Challenge`

match 8:
  - decision: `reject`
  - decision reason: `one-time O2 challenge test result, not continuous FiO2`
  - table: `chartevents`
  - itemid: `229239`
  - raw label: `FiO2 Challenge Result`

### resp, Respiratory Rate, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `insp/min`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=8636655, value_range=[0, 7.0004e+06], median=19, units=insp/min`
  - table: `chartevents_main`
  - itemid: `220210`
  - concept_id: `3024171`
  - raw label: `Respiratory Rate`
  - stats: `row_count=8636655, value_range=[0, 7.0004e+06], median=19, units=insp/min`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=753531, value_range=[-1, 3634], median=20, units=insp/min`
  - table: `chartevents_main`
  - itemid: `224690`
  - concept_id: `3024171`
  - raw label: `Respiratory Rate (Total)`
  - stats: `row_count=753531, value_range=[-1, 3634], median=20, units=insp/min`

### temp, Temperature, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `C`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=174409, value_range=[0, 336.7], median=37.1, units=°C`
  - table: `chartevents_main`
  - itemid: `226329`
  - concept_id: `21490586`
  - raw label: `Blood Temperature CCO (C)`
  - stats: `row_count=174409, value_range=[0, 336.7], median=37.1, units=°C`

### crea, Creatinine, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: the stale NEEDS MANUAL REVIEW note (unit-basis/concept_id ambiguity) obscured real itemid-level bugs, found during a full sweep of all 21 tags still carrying that note -- see per-match decision reasons below.`

match 1:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates urine, not the target specimen`
  - table: `labs`
  - itemid: `51082`
  - concept_id: `3017250`
  - raw label: `Creatinine, Urine`
  - stats: `row_count=237799, value_range=[0, 1159], median=86, units=mg/dL`

match 2:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates urine, not the target specimen`
  - table: `labs`
  - itemid: `51106`
  - concept_id: `3017250`
  - raw label: `Urine Creatinine`
  - stats: `row_count=717, value_range=[7, 353], median=60.5, units=mg/dL`

match 3:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- despite the raw label 'Creatinine, Blood', d_labitems.csv.gz lists this itemid's fluid as Urine. Real blood creatinine itemids (52024/220615/50912/51081/52546) remain kept.`
  - table: `labs`
  - itemid: `51977`
  - concept_id: `3017250`
  - raw label: `Creatinine, Blood`
  - stats: `no raw-table stats queried`

match 4:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates urine, not the target specimen`
  - table: `labs`
  - itemid: `52000`
  - concept_id: `3017250`
  - raw label: `Urine  Creatinine`
  - stats: `no raw-table stats queried`

match 5:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates joint fluid, not the target specimen`
  - table: `labs`
  - itemid: `51021`
  - concept_id: `3007367`
  - raw label: `Creatinine, Joint Fluid`
  - stats: `row_count=3, value_range=[0.6, 30.3], median=1.5, units=mg/dL`

match 6:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates ascites, not the target specimen`
  - table: `labs`
  - itemid: `50841`
  - concept_id: `3016647`
  - raw label: `Creatinine, Ascites`
  - stats: `row_count=2869, value_range=[0, 178.5], median=1.1, units=mg/dL`

match 7:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates pleural, not the target specimen`
  - table: `labs`
  - itemid: `51052`
  - concept_id: `3025065`
  - raw label: `Creatinine, Pleural`
  - stats: `row_count=1842, value_range=[0, 103], median=0.9, units=mg/dL`

match 8:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates csf, not the target specimen`
  - table: `labs`
  - itemid: `51787`
  - concept_id: `3024535`
  - raw label: `Creatinine, CSF`
  - stats: `no raw-table stats queried`

match 9:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Urine, not Blood/Serum; also a 24-hour urine creatinine CLEARANCE test (mg/24hr, cumulative), not a point concentration -- not comparable to serum creatinine (mg/dL) even after unit conversion.`
  - table: `labs`
  - itemid: `51067`
  - concept_id: `3004239`
  - raw label: `24 hr Creatinine`
  - stats: `row_count=10828, value_range=[0, 16802], median=1129, units=mg/24hr`

match 10:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=15175, value_range=[0.1, 23], median=1.1, units=mg/dL`
  - table: `labs`
  - itemid: `52024`
  - concept_id: `3051825`
  - raw label: `Creatinine, Whole Blood`
  - stats: `row_count=15175, value_range=[0.1, 23], median=1.1, units=mg/dL`

match 11:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct zcat|awk count. Real blood creatinine itemids (52024/220615/50912/51081/52546) remain kept.`
  - table: `labs`
  - itemid: `52101`
  - concept_id: `3051825`
  - raw label: `Cr`
  - stats: `no raw-table stats queried`

match 12:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=590866, value_range=[-0.1, 999999], median=1, units=mg/dL`
  - table: `chartevents_main`
  - itemid: `220615`
  - concept_id: `3016723`
  - raw label: `Creatinine (serum)`
  - stats: `row_count=590866, value_range=[-0.1, 999999], median=1, units=mg/dL`

match 13:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4319091, value_range=[0, 808], median=0.9, units=mg/dL`
  - table: `labs`
  - itemid: `50912`
  - concept_id: `3016723`
  - raw label: `Creatinine`
  - stats: `row_count=4319091, value_range=[0, 808], median=0.9, units=mg/dL`

match 14:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- despite the raw label 'Creatinine, Serum', d_labitems.csv.gz lists this itemid's fluid as Urine. Real blood creatinine itemids (52024/220615/50912/52546) remain kept.`
  - table: `labs`
  - itemid: `51081`
  - concept_id: `3016723`
  - raw label: `Creatinine, Serum`
  - stats: `row_count=717, value_range=[0.1, 17.8], median=1, units=mg/dL`

match 15:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1273, value_range=[0.2, 12.3], median=0.8, units=mg/dL`
  - table: `labs`
  - itemid: `52546`
  - concept_id: `3016723`
  - raw label: `Creatinine`
  - stats: `row_count=1273, value_range=[0.2, 12.3], median=0.8, units=mg/dL`

match 16:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates body fluid, not the target specimen`
  - table: `labs`
  - itemid: `51032`
  - concept_id: `3016662`
  - raw label: `Creatinine, Body Fluid`
  - stats: `row_count=508, value_range=[0, 182], median=1.3, units=mg/dL`

match 17:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates stool, not the target specimen`
  - table: `labs`
  - itemid: `51937`
  - concept_id: `3052695`
  - raw label: `Creatinine, Stool`
  - stats: `no raw-table stats queried`

### urine_rate, Urine Rate Per Hour, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `derived_output_rate`
- Target unit: `mL/h`
- Match method: `omop_concept_match`
- Notes: `Narrowed to Foley-only 2026-08-03 (pre-training extensive audit): the other 14 itemids are one-off voiding/procedural volumes, not continuous per-hour drainage like AUMC's own single-itemid (UrineCAD) definition. scripts_review/check_urine_rate_scope_impact.py (job 547752) quantified the real impact on the 10k-admission sample before deciding: the non-Foley itemids added 49,752 admission-hours (+13.2% coverage) but at a ~25%-inflated value on those hours (median 250 vs Foley's own 80, driven by single-event volumes like a 250mL void being counted as if it were that hour's rate) -- decided coverage wasn't worth that systematic inflation.`

match 1:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- one-off drainage-bag volume, not a continuous per-hour rate like Foley; see tag-level Notes for the quantified coverage-vs-inflation tradeoff that drove this.`
  - table: `outputevents`
  - itemid: `226619`
  - concept_id: `3014315`
  - raw label: `Pigtail #1`
  - stats: `row_count=8659, value_range=[-150, 7500], median=45, units=mL`

match 2:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- one-off drainage-bag volume, not a continuous per-hour rate like Foley; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226620`
  - concept_id: `3014315`
  - raw label: `Pigtail #2`
  - stats: `row_count=2475, value_range=[-10, 1340], median=20, units=mL`

match 3:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- one-off drainage-bag volume, not a continuous per-hour rate like Foley; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `227701`
  - concept_id: `3014315`
  - raw label: `Drainage Bag`
  - stats: `row_count=15776, value_range=[-20, 7000], median=90, units=mL`

match 4:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- stent drainage volume, not urine output and not a continuous per-hour rate like Foley; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226557`
  - concept_id: `3014315`
  - raw label: `R Ureteral Stent`
  - stats: `row_count=435, value_range=[0, 1100], median=60, units=mL`

match 5:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- stent drainage volume, not urine output and not a continuous per-hour rate like Foley; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226558`
  - concept_id: `3014315`
  - raw label: `L Ureteral Stent`
  - stats: `row_count=239, value_range=[0, 1000], median=50, units=mL`

match 6:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; the ONE genuinely continuous, hourly-charted urine source -- matches AUMC's own single-itemid (UrineCAD) definition exactly. row_count=3599702, value_range=[-3765, 30331], median=80, units=mL`
  - table: `outputevents`
  - itemid: `226559`
  - concept_id: `3014315`
  - raw label: `Foley`
  - stats: `row_count=3599702, value_range=[-3765, 30331], median=80, units=mL`

match 7:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- a single voiding EVENT, not a continuous per-hour rate; counting it as that hour's rate systematically inflates the value (see tag-level Notes for the quantified impact).`
  - table: `outputevents`
  - itemid: `226560`
  - concept_id: `3014315`
  - raw label: `Void`
  - stats: `row_count=386902, value_range=[-1, 876587], median=250, units=mL`

match 8:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- device-collection volume, not a continuous per-hour rate like Foley; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226561`
  - concept_id: `3014315`
  - raw label: `Condom Cath`
  - stats: `row_count=83164, value_range=[-9, 5000], median=210, units=mL`

match 9:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- device-collection volume, not a continuous per-hour rate like Foley; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226563`
  - concept_id: `3014315`
  - raw label: `Suprapubic`
  - stats: `row_count=13567, value_range=[0, 3200], median=100, units=mL`

match 10:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- device-collection volume, not a continuous per-hour rate like Foley; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226564`
  - concept_id: `3014315`
  - raw label: `R Nephrostomy`
  - stats: `row_count=5911, value_range=[0, 3500], median=120, units=mL`

match 11:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- device-collection volume, not a continuous per-hour rate like Foley; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226565`
  - concept_id: `3014315`
  - raw label: `L Nephrostomy`
  - stats: `row_count=4992, value_range=[0, 1200], median=112.5, units=mL`

match 12:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct polars scan. Also moot after the 2026-08-03 Foley-only scope narrowing (see tag-level Notes).`
  - table: `outputevents`
  - itemid: `226566`
  - concept_id: `3014315`
  - raw label: `Urine and GU Irrigant Out`
  - stats: `no raw-table stats queried`

match 13:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- a single one-off catheterization EVENT, not a continuous per-hour rate; systematically inflates the value if counted as that hour's rate (see tag-level Notes).`
  - table: `outputevents`
  - itemid: `226567`
  - concept_id: `3014315`
  - raw label: `Straight Cath`
  - stats: `row_count=27121, value_range=[-1, 3000], median=500, units=mL`

match 14:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- total urine collected over an OR case (often several hours), not an hourly rate; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226627`
  - concept_id: `3014315`
  - raw label: `OR Urine`
  - stats: `row_count=22948, value_range=[0, 9845], median=400, units=mL`

match 15:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- total urine collected over a PACU stay (often several hours), not an hourly rate; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `226631`
  - concept_id: `3014315`
  - raw label: `PACU Urine`
  - stats: `row_count=2941, value_range=[0, 8130], median=625, units=mL`

match 16:
  - decision: `reject`
  - decision reason: `SCOPE NARROWED 2026-08-03 -- irrigant-contaminated volume (not pure urine) AND not an hourly rate; see tag-level Notes.`
  - table: `outputevents`
  - itemid: `227489`
  - concept_id: `3014315`
  - raw label: `GU Irrigant/Urine Volume Out`
  - stats: `row_count=7201, value_range=[0, 12950], median=2300, units=mL`

### po2, Partial Pressure Of Oxygen, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=698483, value_range=[-32, 4242], median=99, units=mm Hg`
  - table: `labs`
  - itemid: `50821`
  - concept_id: `3027315`
  - raw label: `pO2`
  - stats: `row_count=698483, value_range=[-32, 4242], median=99, units=mm Hg`

### ethnic, Ethnic Group, demographic, not specified
- Mapping status: `source_candidates_found`
- Reconstruction type: `unavailable`
- Target unit: `categorical`
- Match method: `admission_context_fixed`
- Notes: `MIMIC-IV admissions.race is available (unlike AUMCdb, which had no reliable ethnicity field) -- this can be resolved, unlike AUMC's 'unavailable'.`

### alb, Albumin, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `g/dL`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1032456, value_range=[0.2, 36], median=3.9, units=g/dL`
  - table: `labs`
  - itemid: `50862`
  - concept_id: `3024561`
  - raw label: `Albumin`
  - stats: `row_count=1032456, value_range=[0.2, 36], median=3.9, units=g/dL`

match 2:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct zcat|awk count. Real albumin itemid 50862 (1032456 rows, median 3.9 g/dL) remains kept.`
  - table: `labs`
  - itemid: `52022`
  - concept_id: `3024561`
  - raw label: `Albumin, Blood`
  - stats: `no raw-table stats queried`

### alp, Alkaline Phosphatase, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `IU/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1602599, value_range=[0, 5965], median=91, units=IU/L`
  - table: `labs`
  - itemid: `50863`
  - concept_id: `3035995`
  - raw label: `Alkaline Phosphatase`
  - stats: `row_count=1602599, value_range=[0, 5965], median=91, units=IU/L`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=69, value_range=[38, 286], median=74, units=IU/L`
  - table: `labs`
  - itemid: `53086`
  - concept_id: `3035995`
  - raw label: `Alkaline Phosphatase`
  - stats: `row_count=69, value_range=[38, 286], median=74, units=IU/L`

### alt, Alanine Aminotransferase, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `IU/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1826482, value_range=[0, 61854], median=24, units=IU/L`
  - table: `labs`
  - itemid: `50861`
  - concept_id: `3006923`
  - raw label: `Alanine Aminotransferase (ALT)`
  - stats: `row_count=1826482, value_range=[0, 61854], median=24, units=IU/L`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=69, value_range=[6, 332], median=21, units=IU/L`
  - table: `labs`
  - itemid: `53084`
  - concept_id: `3006923`
  - raw label: `Alanine Aminotransferase`
  - stats: `row_count=69, value_range=[6, 332], median=21, units=IU/L`

### ast, Aspartate Aminotransferase, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `IU/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1793910, value_range=[0, 42606], median=26, units=IU/L`
  - table: `labs`
  - itemid: `50878`
  - concept_id: `3013721`
  - raw label: `Asparate Aminotransferase (AST)`
  - stats: `row_count=1793910, value_range=[0, 42606], median=26, units=IU/L`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=69, value_range=[14, 186], median=28, units=IU/L`
  - table: `labs`
  - itemid: `53088`
  - concept_id: `3013721`
  - raw label: `Asparate Aminotransferase`
  - stats: `row_count=69, value_range=[14, 186], median=28, units=IU/L`

### be, Base Excess, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmol/l`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=698337, value_range=[-414, 188], median=0, units=mEq/L`
  - table: `labs`
  - itemid: `50802`
  - concept_id: `3012501`
  - raw label: `Base Excess`
  - stats: `row_count=698337, value_range=[-414, 188], median=0, units=mEq/L`

### bicar, Bicarbonate, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmol/l`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=32994, value_range=[2, 220], median=24, units=mEq/L`
  - table: `labs`
  - itemid: `50803`
  - concept_id: `3006576`
  - raw label: `Calculated Bicarbonate, Whole Blood`
  - stats: `row_count=32994, value_range=[2, 220], median=24, units=mEq/L`

match 2 (added by hand, 2026-07-28):
  - decision: `keep`
  - decision reason: `MISSING SIBLING ITEMID -- the omop concept-chain only surfaced the low-volume Blood Gas panel variant above (32,994 rows); d_labitems.csv.gz shows a separate, much higher-volume routine Chemistry panel bicarbonate itemid that the concept match never picked up. Confirmed via direct raw-table query, not just label text.`
  - table: `labs`
  - itemid: `50882`
  - raw label: `Bicarbonate, Blood, Chemistry`
  - stats: `row_count=3934240, value_range=[2, 132], median=25, units=mEq/L`

### bili, Total Bilirubin, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: the stale NEEDS MANUAL REVIEW note (unit-basis/concept_id ambiguity) obscured real itemid-level bugs, found during a full sweep of all 21 tags still carrying that note -- see per-match decision reasons below.`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1605452, value_range=[0, 87.2], median=0.5, units=mg/dL`
  - table: `labs`
  - itemid: `50885`
  - concept_id: `3024128`
  - raw label: `Bilirubin, Total`
  - stats: `row_count=1605452, value_range=[0, 87.2], median=0.5, units=mg/dL`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=69, value_range=[0.2, 3.8], median=0.7, units=mg/dL`
  - table: `labs`
  - itemid: `53089`
  - concept_id: `3024128`
  - raw label: `Bilirubin, Total`
  - stats: `row_count=69, value_range=[0.2, 3.8], median=0.7, units=mg/dL`

match 3:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates body fluid, not the target specimen`
  - table: `labs`
  - itemid: `51028`
  - concept_id: `3028193`
  - raw label: `Bilirubin, Total, Body Fluid`
  - stats: `row_count=450, value_range=[0, 257], median=2.8, units=mg/dL`

match 4:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates csf, not the target specimen`
  - table: `labs`
  - itemid: `51783`
  - concept_id: `3027110`
  - raw label: `Bilirubin, Total, CSF`
  - stats: `row_count=4, value_range=[0.1, 0.4], median=0.2, units=mg/dL`

match 5:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Urine, not Blood; units=EU/dL confirm a urine dipstick test, not serum total bilirubin.`
  - table: `labs`
  - itemid: `51464`
  - concept_id: `3018834`
  - raw label: `Bilirubin`
  - stats: `row_count=843477, units=EU/dL|N/A|mg/dL`

match 6:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates pleural, not the target specimen`
  - table: `labs`
  - itemid: `51049`
  - concept_id: `3013272`
  - raw label: `Bilirubin, Total, Pleural`
  - stats: `row_count=209, value_range=[0, 28.2], median=1.6, units=mg/dL`

match 7:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Urine, not Blood.`
  - table: `labs`
  - itemid: `51966`
  - concept_id: `3011258`
  - raw label: `Bilirubin`
  - stats: `row_count=1715, units=N/A`

match 8:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates ascites, not the target specimen`
  - table: `labs`
  - itemid: `50838`
  - concept_id: `3011004`
  - raw label: `Bilirubin, Total, Ascites`
  - stats: `row_count=3004, value_range=[0, 344], median=1.2, units=mg/dL`

match 9:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates stool, not the target specimen`
  - table: `labs`
  - itemid: `51932`
  - concept_id: `3024733`
  - raw label: `Bilirubin, Total, Stool`
  - stats: `no raw-table stats queried`

match 10:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates joint fluid, not the target specimen`
  - table: `labs`
  - itemid: `51812`
  - concept_id: `3014687`
  - raw label: `Bilirubin, Total, Joint Fluid`
  - stats: `no raw-table stats queried`

### bili_dir, Bilirubin Direct, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary direct-bilirubin lab value`
  - table: `labevents`
  - itemid: `50883`
  - raw label: `Bilirubin, Direct`
  - stats: `row_count=120044, units=mg/dL`

match 2:
  - decision: `keep`
  - decision reason: `secondary chartevents source, same analyte`
  - table: `chartevents`
  - itemid: `225651`
  - raw label: `Direct Bilirubin`
  - stats: `row_count=13158, value_range=[0, 63.7], median=2.2, units=mg/dL`

match 3:
  - decision: `reject`
  - decision reason: `mixed units including EU/dL (a urinalysis reagent-strip unit) -- this is a semi-quantitative urine dipstick test, not serum direct bilirubin`
  - table: `labevents`
  - itemid: `51464`
  - raw label: `Bilirubin`
  - stats: `row_count=843477, units=EU/dL|N/A|mg/dL`

match 4:
  - decision: `reject`
  - decision reason: `urine microscopy finding, wrong analyte entirely`
  - table: `labevents`
  - itemid: `51465`
  - raw label: `Bilirubin Crystals`

match 5:
  - decision: `reject`
  - decision reason: `0 rows; neonatal population mismatch for an adult ICU cohort`
  - table: `labevents`
  - itemid: `51568`
  - raw label: `Bilirubin, Neonatal`

match 6:
  - decision: `reject`
  - decision reason: `0 rows; neonatal population mismatch`
  - table: `labevents`
  - itemid: `51569`
  - raw label: `Bilirubin, Neonatal, Direct`

match 7:
  - decision: `reject`
  - decision reason: `0 rows; neonatal population mismatch`
  - table: `labevents`
  - itemid: `51570`
  - raw label: `Bilirubin, Neonatal, Indirect`

match 8:
  - decision: `reject`
  - decision reason: `wrong specimen AND wrong component (total, not direct)`
  - table: `labevents`
  - itemid: `51028`
  - raw label: `Bilirubin, Total, Body Fluid`

match 9:
  - decision: `reject`
  - decision reason: `wrong specimen AND wrong component (total, not direct)`
  - table: `labevents`
  - itemid: `50838`
  - raw label: `Bilirubin, Total, Ascites`

match 10:
  - decision: `reject`
  - decision reason: `wrong specimen AND wrong component (total, not direct)`
  - table: `labevents`
  - itemid: `51049`
  - raw label: `Bilirubin, Total, Pleural`

match 11:
  - decision: `reject`
  - decision reason: `wrong component -- total, not direct`
  - table: `chartevents`
  - itemid: `225690`
  - raw label: `Total Bilirubin`

match 12:
  - decision: `reject`
  - decision reason: `wrong component -- total, not direct`
  - table: `labevents`
  - itemid: `50885`
  - raw label: `Bilirubin, Total`

match 13:
  - decision: `reject`
  - decision reason: `wrong component -- indirect, not direct`
  - table: `labevents`
  - itemid: `50884`
  - raw label: `Bilirubin, Indirect`

match 14:
  - decision: `reject`
  - decision reason: `APACHE-derived severity-score input, redundant`
  - table: `chartevents`
  - itemid: `226998`
  - raw label: `Bilirubin_ApacheIV`

match 15:
  - decision: `reject`
  - decision reason: `unrelated administrative/teaching-note field, false keyword hit on "direct"`
  - table: `chartevents`
  - itemid: `225131`
  - raw label: `Teaching directed toward`

### bnd, Band Form Neutrophils, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=249689, value_range=[0, 100], median=0, units=%`
  - table: `labs`
  - itemid: `51144`
  - concept_id: `3004809`
  - raw label: `Bands`
  - stats: `row_count=249689, value_range=[0, 100], median=0, units=%`

### bun, Blood Urea Nitrogen, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary BUN itemid -- present in d_labitems and substring-matchable, but crowded out of the automated candidate list by keyword_fallback()'s head(15) truncation (generic token "blood" matched far more chartevents rows first); found by a direct d_labitems re-search`
  - table: `labevents`
  - itemid: `51006`
  - raw label: `Urea Nitrogen`
  - stats: `specimen=Blood, category=Chemistry`

match 2:
  - decision: `keep`
  - decision reason: `duplicate/alternate BUN itemid, same reasoning as 51006`
  - table: `labevents`
  - itemid: `52647`
  - raw label: `Urea Nitrogen`
  - stats: `specimen=Blood, category=Chemistry`

match 3:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `50851`
  - raw label: `Urea Nitrogen, Ascites`

match 4:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `51045`
  - raw label: `Urea Nitrogen, Body Fluid`

match 5:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `51104`
  - raw label: `Urea Nitrogen, Urine`

match 6:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `51804`
  - raw label: `Urea Nitrogen, CSF`

match 7:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `51825`
  - raw label: `Urea Nitrogen, Joint Fluid`

match 8:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `51922`
  - raw label: `Urea Nitrogen, Pleural`

match 9:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `51951`
  - raw label: `Urea Nitrogen, Stool`

match 10:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `223751`
  - raw label: `Non-Invasive Blood Pressure Alarm - High`

match 11:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `223752`
  - raw label: `Non-Invasive Blood Pressure Alarm - Low`

match 12:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220179`
  - raw label: `Non Invasive Blood Pressure systolic`

match 13:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220180`
  - raw label: `Non Invasive Blood Pressure diastolic`

match 14:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220181`
  - raw label: `Non Invasive Blood Pressure mean`

match 15:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated (dialysis circuit flow)`
  - table: `chartevents`
  - itemid: `224144`
  - raw label: `Blood Flow (ml/min)`

match 16:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220050`
  - raw label: `Arterial Blood Pressure systolic`

match 17:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220051`
  - raw label: `Arterial Blood Pressure diastolic`

match 18:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220052`
  - raw label: `Arterial Blood Pressure mean`

match 19:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220056`
  - raw label: `Arterial Blood Pressure Alarm - Low`

match 20:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220058`
  - raw label: `Arterial Blood Pressure Alarm - High`

match 21:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `224167`
  - raw label: `Manual Blood Pressure Systolic Left`

match 22:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `224643`
  - raw label: `Manual Blood Pressure Diastolic Left`

match 23:
  - decision: `reject`
  - decision reason: `0 rows; wrong domain (infusion-ingredient tracking, not a lab result)`
  - table: `ingredientevents`
  - itemid: `220435`
  - raw label: `Nitrogen`

match 24:
  - decision: `reject`
  - decision reason: `wrong domain (transfusion product, not a lab result)`
  - table: `inputevents`
  - itemid: `221013`
  - raw label: `Whole Blood`

### ca, Calcium, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates urine, not the target specimen`
  - table: `labs`
  - itemid: `51077`
  - concept_id: `3006661`
  - raw label: `Calcium, Urine`
  - stats: `row_count=6077, value_range=[0, 120.6], median=6, units=mg/dL`

match 2:
  - decision: `reject`
  - decision reason: `24-hour URINE collection total calcium -- specimen (urine) and collection-window mismatch vs a point-in-time blood/serum total calcium reading`
  - table: `labs`
  - itemid: `51066`
  - concept_id: `3007687`
  - raw label: `24 hr Calcium`
  - stats: `row_count=2537, value_range=[0, 1143], median=148, units=mg/24hr`

match 3:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates body fluid, not the target specimen`
  - table: `labs`
  - itemid: `51029`
  - concept_id: `3000822`
  - raw label: `Calcium, Body Fluid`
  - stats: `row_count=11, value_range=[2.9, 9.9], median=7.2, units=mg/dL`

match 4:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct zcat|awk count. Real total-calcium itemid 50893 (2969588 rows, median 8.8 mg/dL) remains kept.`
  - table: `labs`
  - itemid: `52034`
  - concept_id: `3032503`
  - raw label: `Total Calcium`
  - stats: `no raw-table stats queried`

match 5:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29. Same as itemid 52034.`
  - table: `labs`
  - itemid: `52035`
  - concept_id: `3032503`
  - raw label: `Total Calcium`
  - stats: `no raw-table stats queried`

match 6:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=2969588, value_range=[0, 132], median=8.8, units=mg/dL`
  - table: `labs`
  - itemid: `50893`
  - concept_id: `3006906`
  - raw label: `Calcium, Total`
  - stats: `row_count=2969588, value_range=[0, 132], median=8.8, units=mg/dL`

### cai, Calcium Ionized, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmol/L`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary ionized-calcium value`
  - table: `chartevents`
  - itemid: `225667`
  - raw label: `Ionized Calcium`
  - stats: `row_count=293569, value_range=[-0.4, 999999], median=1.12, units=mmol/L (extraction needs a plausibility bound -- 999999 is a sentinel/error code)`

match 2:
  - decision: `keep`
  - decision reason: `"Free Calcium" = the ionized fraction, same analyte, secondary source`
  - table: `labevents`
  - itemid: `50808`
  - raw label: `Free Calcium`
  - stats: `row_count=370407, value_range=[0.09, 150], median=1.12, units=mmol/L`

match 3:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `51077`
  - raw label: `Calcium, Urine`

match 4:
  - decision: `reject`
  - decision reason: `wrong component -- total, not ionized`
  - table: `labevents`
  - itemid: `50893`
  - raw label: `Calcium, Total`

match 5:
  - decision: `reject`
  - decision reason: `24h urine collection -- wrong specimen AND wrong component`
  - table: `labevents`
  - itemid: `51066`
  - raw label: `24 hr Calcium`

match 6:
  - decision: `reject`
  - decision reason: `unrelated urine microscopy finding`
  - table: `labevents`
  - itemid: `51468`
  - raw label: `Calcium Carbonate Crystals`

match 7:
  - decision: `reject`
  - decision reason: `unrelated urine microscopy finding`
  - table: `labevents`
  - itemid: `51469`
  - raw label: `Calcium Oxalate Crystals`

match 8:
  - decision: `reject`
  - decision reason: `specimen mismatch`
  - table: `labevents`
  - itemid: `51029`
  - raw label: `Calcium, Body Fluid`

match 9:
  - decision: `reject`
  - decision reason: `wrong domain -- infusion treatment, not a lab observation`
  - table: `inputevents`
  - itemid: `221456`
  - raw label: `Calcium Gluconate`

match 10:
  - decision: `reject`
  - decision reason: `wrong domain, and a stale/deprecated itemid variant`
  - table: `inputevents`
  - itemid: `228317`
  - raw label: `Calcium Gluconate (Bolus)_OLD_1`

match 11:
  - decision: `reject`
  - decision reason: `wrong domain -- infusion treatment, not a lab observation`
  - table: `inputevents`
  - itemid: `229640`
  - raw label: `Calcium Gluconate (Bolus)`

match 12:
  - decision: `reject`
  - decision reason: `wrong domain -- CRRT circuit infusion, not a lab observation`
  - table: `inputevents`
  - itemid: `227525`
  - raw label: `Calcium Gluconate (CRRT)`

match 13:
  - decision: `reject`
  - decision reason: `wrong domain -- infusion treatment, not a lab observation`
  - table: `inputevents`
  - itemid: `229618`
  - raw label: `Calcium Chloride`

match 14:
  - decision: `reject`
  - decision reason: `wrong domain -- infusion-ingredient tracking, not a lab observation`
  - table: `ingredientevents`
  - itemid: `220363`
  - raw label: `Calcium (ingr)`

### ck, Creatine Kinase, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `IU/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=334746, value_range=[1, 591950], median=104, units=IU/L`
  - table: `labs`
  - itemid: `50910`
  - concept_id: `3007220`
  - raw label: `Creatine Kinase (CK)`
  - stats: `row_count=334746, value_range=[1, 591950], median=104, units=IU/L`

### ckmb, Creatine Kinase MB, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `ng/mL`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=266856, value_range=[1, 673], median=4, units=ng/mL`
  - table: `labs`
  - itemid: `50911`
  - concept_id: `3005785`
  - raw label: `Creatine Kinase, MB Isoenzyme`
  - stats: `row_count=266856, value_range=[1, 673], median=4, units=ng/mL`

### cl, Chloride, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmol/l`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=108168, value_range=[1.9, 405], median=105, units=mEq/L`
  - table: `labs`
  - itemid: `50806`
  - concept_id: `3018572`
  - raw label: `Chloride, Whole Blood`
  - stats: `row_count=108168, value_range=[1.9, 405], median=105, units=mEq/L`

match 2 (added by hand, 2026-07-28):
  - decision: `keep`
  - decision reason: `MISSING SIBLING ITEMID -- the omop concept-chain only surfaced the low-volume Blood Gas panel variant above (108,168 rows); d_labitems.csv.gz shows a separate, much higher-volume routine Chemistry panel chloride itemid that the concept match never picked up. Confirmed via direct raw-table query, not just label text.`
  - table: `labs`
  - itemid: `50902`
  - raw label: `Chloride, Blood, Chemistry`
  - stats: `row_count=4055101, value_range=[39, 155], median=102, units=mEq/L`

### crp, C-Reactive Protein, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=178039, value_range=[0.1, 608.1], median=7.1, units=mg/L`
  - table: `labs`
  - itemid: `50889`
  - concept_id: `3020460`
  - raw label: `C-Reactive Protein`
  - stats: `row_count=178039, value_range=[0.1, 608.1], median=7.1, units=mg/L`

### dbp, Diastolic Blood Pressure, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=5377689, value_range=[-2, 114109], median=64, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220180`
  - concept_id: `21492240`
  - raw label: `Non Invasive Blood Pressure diastolic`
  - stats: `row_count=5377689, value_range=[-2, 114109], median=64, units=mmHg`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=3087261, value_range=[-41, 114100], median=57, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220051`
  - concept_id: `3012888`
  - raw label: `Arterial Blood Pressure diastolic`
  - stats: `row_count=3087261, value_range=[-41, 114100], median=57, units=mmHg`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=387891, value_range=[-40, 58196], median=56, units=mmHg`
  - table: `chartevents_main`
  - itemid: `225310`
  - concept_id: `3012888`
  - raw label: `ART BP Diastolic`
  - stats: `row_count=387891, value_range=[-40, 58196], median=56, units=mmHg`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1436, value_range=[-5, 140], median=62, units=mmHg`
  - table: `chartevents_main`
  - itemid: `224643`
  - concept_id: `3012888`
  - raw label: `Manual Blood Pressure Diastolic Left`
  - stats: `row_count=1436, value_range=[-5, 140], median=62, units=mmHg`

match 5:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1158, value_range=[7, 136], median=64, units=mmHg`
  - table: `chartevents_main`
  - itemid: `227242`
  - concept_id: `3012888`
  - raw label: `Manual Blood Pressure Diastolic Right`
  - stats: `row_count=1158, value_range=[7, 136], median=64, units=mmHg`

match 6:
  - decision: `reject`
  - decision reason: `omr outpatient "Blood Pressure Standing" is a combined systolic/diastolic string (e.g. "110/65"), not a parseable diastolic value, and is non-ICU-scoped (rc=565 vs millions in chartevents) -- redundant and lower-quality vs the chartevents candidates`
  - table: `omr`
  - itemid: `blood_pressure`
  - concept_id: `3012888`
  - raw label: `Blood Pressure Standing`
  - stats: `row_count=565`

match 7:
  - decision: `reject`
  - decision reason: `cross-contaminated: this is Pulmonary Artery Pressure DIASTOLIC (belongs to `dpap`), not systemic diastolic BP`
  - table: `chartevents_main`
  - itemid: `220060`
  - concept_id: `3017188`
  - raw label: `Pulmonary Artery Pressure diastolic`
  - stats: `row_count=398801, value_range=[-33, 2834], median=19, units=mmHg`

### fgn, Fibrinogen, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=154065, value_range=[24, 1810], median=285, units=mg/dL`
  - table: `labs`
  - itemid: `51214`
  - concept_id: `3016407`
  - raw label: `Fibrinogen, Functional`
  - stats: `row_count=154065, value_range=[24, 1810], median=285, units=mg/dL`

match 2:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct zcat|awk count. Real fibrinogen itemid 51214 (154065 rows, median 285 mg/dL) remains kept.`
  - table: `labs`
  - itemid: `51623`
  - concept_id: `3016407`
  - raw label: `Fibrinogen`
  - stats: `no raw-table stats queried`

match 3:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29.`
  - table: `labs`
  - itemid: `52115`
  - concept_id: `3016407`
  - raw label: `Fibrinoge`
  - stats: `no raw-table stats queried`

match 4:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29.`
  - table: `labs`
  - itemid: `52116`
  - concept_id: `3016407`
  - raw label: `Fibrinogen`
  - stats: `no raw-table stats queried`

### glu, Glucose, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: the stale NEEDS MANUAL REVIEW note (unit-basis/concept_id ambiguity) obscured real itemid-level bugs, found during a full sweep of all 21 tags still carrying that note -- see per-match decision reasons below.`

match 1:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates ascites, not the target specimen`
  - table: `labs`
  - itemid: `50842`
  - concept_id: `3002240`
  - raw label: `Glucose, Ascites`
  - stats: `row_count=7044, value_range=[0, 1382], median=126, units=mg/dL`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=281398, value_range=[0.12, 1.2761e+06], median=132, units=mg/dL`
  - table: `labs`
  - itemid: `50809`
  - concept_id: `3000483`
  - raw label: `Glucose`
  - stats: `row_count=281398, value_range=[0.12, 1.2761e+06], median=132, units=mg/dL`

match 3:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct zcat|awk count. Several other real glucose itemids remain kept.`
  - table: `labs`
  - itemid: `52027`
  - concept_id: `3000483`
  - raw label: `Glucose, Whole Blood`
  - stats: `no raw-table stats queried`

match 4:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates body fluid, not the target specimen`
  - table: `labs`
  - itemid: `51034`
  - concept_id: `3019210`
  - raw label: `Glucose, Body Fluid`
  - stats: `row_count=928, value_range=[0, 1540], median=90.5, units=mg/dL`

match 5:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates pleural, not the target specimen`
  - table: `labs`
  - itemid: `51053`
  - concept_id: `3003403`
  - raw label: `Glucose, Pleural`
  - stats: `row_count=9195, value_range=[0, 1053], median=112, units=mg/dL`

match 6:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Urine, not Blood.`
  - table: `labs`
  - itemid: `51981`
  - concept_id: `3020399`
  - raw label: `Glucose`
  - stats: `row_count=1715, value_range=[100, 1000], median=100, units=mg/dL`

match 7:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates urine, not the target specimen`
  - table: `labs`
  - itemid: `51084`
  - concept_id: `3020399`
  - raw label: `Glucose, Urine`
  - stats: `row_count=191, value_range=[0, 5400], median=11, units=mg/dL`

match 8:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates stool, not the target specimen`
  - table: `labs`
  - itemid: `51941`
  - concept_id: `3040980`
  - raw label: `Glucose, Stool`
  - stats: `no raw-table stats queried`

match 9:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates csf, not the target specimen`
  - table: `labs`
  - itemid: `51790`
  - concept_id: `3022548`
  - raw label: `Glucose, CSF`
  - stats: `row_count=15151, value_range=[0, 548], median=66, units=mg/dL`

match 10:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Urine, not Blood.`
  - table: `labs`
  - itemid: `51478`
  - concept_id: `3024629`
  - raw label: `Glucose`
  - stats: `row_count=843478, value_range=[30, 1000], median=300, units=mg/dL`

match 11:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=584841, value_range=[0, 999999], median=129, units=mg/dL`
  - table: `chartevents_main`
  - itemid: `220621`
  - concept_id: `3004501`
  - raw label: `Glucose (serum)`
  - stats: `row_count=584841, value_range=[0, 999999], median=129, units=mg/dL`

match 12:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=3621769, value_range=[0, 23200], median=110, units=mg/dL`
  - table: `labs`
  - itemid: `50931`
  - concept_id: `3004501`
  - raw label: `Glucose`
  - stats: `row_count=3621769, value_range=[0, 23200], median=110, units=mg/dL`

match 13:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1309, value_range=[63, 467], median=106, units=mg/dL`
  - table: `labs`
  - itemid: `52569`
  - concept_id: `3004501`
  - raw label: `Glucose`
  - stats: `row_count=1309, value_range=[63, 467], median=106, units=mg/dL`

match 14:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates joint fluid, not the target specimen`
  - table: `labs`
  - itemid: `51022`
  - concept_id: `3001978`
  - raw label: `Glucose, Joint Fluid`
  - stats: `row_count=171, value_range=[0, 540], median=83, units=mg/dL`

### hgb, Hemoglobin, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `g/dL`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=598976, value_range=[0, 999999], median=9.4, units=g/dl`
  - table: `chartevents_main`
  - itemid: `220228`
  - concept_id: `3000963`
  - raw label: `Hemoglobin`
  - stats: `row_count=598976, value_range=[0, 999999], median=9.4, units=g/dl`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4181121, value_range=[0, 24.9], median=10.9, units=g/dL`
  - table: `labs`
  - itemid: `51222`
  - concept_id: `3000963`
  - raw label: `Hemoglobin`
  - stats: `row_count=4181121, value_range=[0, 24.9], median=10.9, units=g/dL`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=144055, value_range=[0, 137], median=10.2, units=g/dL`
  - table: `labs`
  - itemid: `50811`
  - concept_id: `3000963`
  - raw label: `Hemoglobin`
  - stats: `row_count=144055, value_range=[0, 137], median=10.2, units=g/dL`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=547`
  - table: `labs`
  - itemid: `50855`
  - concept_id: `3000963`
  - raw label: `Absolute Hemoglobin`
  - stats: `row_count=547`

match 5:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=17, value_range=[8.5, 16.5], median=13.4, units=g/dL`
  - table: `labs`
  - itemid: `51640`
  - concept_id: `3000963`
  - raw label: `Hemoglobin`
  - stats: `row_count=17, value_range=[8.5, 16.5], median=13.4, units=g/dL`

match 6:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct zcat|awk count.`
  - table: `labs`
  - itemid: `52207`
  - concept_id: `3000963`
  - raw label: `TurbHbI`
  - stats: `no raw-table stats queried`

match 7:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- despite the raw label 'Hgb', d_labitems.csv.gz lists this itemid's fluid as Urine (hematuria indicator), not blood hemoglobin.`
  - table: `labs`
  - itemid: `52411`
  - concept_id: `3011397`
  - raw label: `Hgb`
  - stats: `no raw-table stats queried`

match 8:
  - decision: `reject`
  - decision reason: `WRONG ANALYTE -- MCHC (Mean Corpuscular Hemoglobin Concentration) is a derived RBC index, not the hemoglobin concentration itself`
  - table: `labs`
  - itemid: `51249`
  - concept_id: `3009744`
  - raw label: `MCHC`
  - stats: `row_count=4152226, value_range=[0, 327], median=32.8, units=%|g/dL`

match 9:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1289, value_range=[5.8, 20.4], median=13.9, units=g/dL`
  - table: `labs`
  - itemid: `51645`
  - concept_id: `3027484`
  - raw label: `Hemoglobin, Calculated`
  - stats: `row_count=1289, value_range=[5.8, 20.4], median=13.9, units=g/dL`

match 10:
  - decision: `reject`
  - decision reason: `WRONG ANALYTE -- MCH (Mean Corpuscular Hemoglobin) is a per-cell derived RBC index, not the hemoglobin concentration itself`
  - table: `labs`
  - itemid: `51248`
  - concept_id: `3012030`
  - raw label: `MCH`
  - stats: `row_count=4152104, value_range=[0, 374.6], median=30, units=pg`

### inr_pt, Prothrombin, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `INR`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1783315, value_range=[0.4, 27.5], median=1.3`
  - table: `labs`
  - itemid: `51237`
  - concept_id: `3022217`
  - raw label: `INR(PT)`
  - stats: `row_count=1783315, value_range=[0.4, 27.5], median=1.3`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=77, value_range=[0.9, 4.2], median=1.7`
  - table: `labs`
  - itemid: `51675`
  - concept_id: `3022217`
  - raw label: `INR(PT)`
  - stats: `row_count=77, value_range=[0.9, 4.2], median=1.7`

### k, Potassium, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmol/l`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=333554, value_range=[0.1, 538], median=4.2, units=mEq/L`
  - table: `labs`
  - itemid: `50822`
  - concept_id: `3005456`
  - raw label: `Potassium, Whole Blood`
  - stats: `row_count=333554, value_range=[0.1, 538], median=4.2, units=mEq/L`

match 2 (added by hand, 2026-07-28):
  - decision: `keep`
  - decision reason: `MISSING SIBLING ITEMID -- the omop concept-chain only surfaced the lower-volume Blood Gas panel variant above (333,554 rows); d_labitems.csv.gz shows a separate, much higher-volume routine Chemistry panel potassium itemid that the concept match never picked up. Confirmed via direct raw-table query, not just label text.`
  - table: `labs`
  - itemid: `50971`
  - raw label: `Potassium, Blood, Chemistry`
  - stats: `row_count=4149507, value_range=[0.7, 26.5], median=4.1, units=mEq/L`

### lymph, Lymphocytes, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Joint Fluid, not Blood.`
  - table: `labs`
  - itemid: `51375`
  - concept_id: `3003329`
  - raw label: `Lymphocytes`
  - stats: `row_count=7618, value_range=[0, 100], median=6, units=%`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1611766, value_range=[0, 100], median=21.1, units=%`
  - table: `labs`
  - itemid: `51244`
  - concept_id: `3037511`
  - raw label: `Lymphocytes`
  - stats: `row_count=1611766, value_range=[0, 100], median=21.1, units=%`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=29574, value_range=[0, 100], median=31, units=%`
  - table: `labs`
  - itemid: `51245`
  - concept_id: `3037511`
  - raw label: `Lymphocytes, Percent`
  - stats: `row_count=29574, value_range=[0, 100], median=31, units=%`

match 4:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- not present in d_labitems.csv.gz or d_items.csv.gz at all, confirmed 2026-07-29. Original decision was made on label text alone, never validated.`
  - table: `labs`
  - itemid: `51690`
  - concept_id: `3037511`
  - raw label: `Lymphocytes`
  - stats: `no raw-table stats queried`

match 5:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Other Body Fluid, not Blood.`
  - table: `labs`
  - itemid: `51427`
  - concept_id: `3028079`
  - raw label: `Lymphocytes`
  - stats: `row_count=6204, value_range=[0, 100], median=6, units=%`

match 6:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Ascites, not Blood. Wrongly pooled into the blood differential lymphocyte count.`
  - table: `labs`
  - itemid: `51116`
  - concept_id: `3004437`
  - raw label: `Lymphocytes`
  - stats: `row_count=15561, value_range=[0, 100], median=21, units=%`

match 7:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Cerebrospinal Fluid, not Blood.`
  - table: `labs`
  - itemid: `52264`
  - concept_id: `3020951`
  - raw label: `Lymphs`
  - stats: `row_count=21202, value_range=[0, 100], median=67, units=%`

match 8:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Pleural, not Blood.`
  - table: `labs`
  - itemid: `51446`
  - concept_id: `3005532`
  - raw label: `Lymphocytes`
  - stats: `row_count=10085, value_range=[0, 100], median=35, units=%`

### methb, Methemoglobin, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=5708, value_range=[0, 91], median=0, units=%`
  - table: `labs`
  - itemid: `50814`
  - concept_id: `3007930`
  - raw label: `Methemoglobin`
  - stats: `row_count=5708, value_range=[0, 91], median=0, units=%`

### mg, Magnesium, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates urine, not the target specimen`
  - table: `labs`
  - itemid: `51088`
  - concept_id: `3019738`
  - raw label: `Magnesium, Urine`
  - stats: `row_count=2287, value_range=[0, 193], median=4.7, units=mg/dL`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=2933221, value_range=[0, 160], median=2, units=mg/dL`
  - table: `labs`
  - itemid: `50960`
  - concept_id: `3001420`
  - raw label: `Magnesium`
  - stats: `row_count=2933221, value_range=[0, 160], median=2, units=mg/dL`

match 3:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates body fluid, not the target specimen`
  - table: `labs`
  - itemid: `51037`
  - concept_id: `3014175`
  - raw label: `Magnesium, Body Fluid`
  - stats: `row_count=9, value_range=[1.4, 141], median=3.8, units=mg/dL`

### na, Sodium, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmol/l`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=159073, value_range=[1.36, 1336], median=136, units=mEq/L`
  - table: `labs`
  - itemid: `50824`
  - concept_id: `3000285`
  - raw label: `Sodium, Whole Blood`
  - stats: `row_count=159073, value_range=[1.36, 1336], median=136, units=mEq/L`

match 2 (added by hand, 2026-07-28):
  - decision: `keep`
  - decision reason: `MISSING SIBLING ITEMID -- the omop concept-chain only surfaced the lower-volume Blood Gas panel variant above (159,073 rows); d_labitems.csv.gz shows a separate, much higher-volume routine Chemistry panel sodium itemid that the concept match never picked up. Confirmed via direct raw-table query, not just label text.`
  - table: `labs`
  - itemid: `50983`
  - raw label: `Sodium, Blood, Chemistry`
  - stats: `row_count=4111289, value_range=[67, 185], median=139, units=mEq/L`

### neut, Neutrophils, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=887962, value_range=[0, 880], median=4.48, units=K/uL`
  - table: `labs`
  - itemid: `52075`
  - concept_id: `3013650`
  - raw label: `Absolute Neutrophil Count`
  - stats: `row_count=887962, value_range=[0, 880], median=4.48, units=K/uL`

match 2:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- not present in d_labitems.csv.gz or d_items.csv.gz at all, confirmed 2026-07-29. Original decision was made on label text alone, never validated.`
  - table: `labs`
  - itemid: `51697`
  - concept_id: `3013650`
  - raw label: `Neutrophils`
  - stats: `no raw-table stats queried`

match 3:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- not present in d_labitems.csv.gz or d_items.csv.gz at all, confirmed 2026-07-29.`
  - table: `labs`
  - itemid: `53133`
  - concept_id: `3013650`
  - raw label: `Absolute Neutrophil`
  - stats: `no raw-table stats queried`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1611767, value_range=[0, 100], median=67, units=%`
  - table: `labs`
  - itemid: `51256`
  - concept_id: `3008342`
  - raw label: `Neutrophils`
  - stats: `row_count=1611767, value_range=[0, 100], median=67, units=%`

### pco2, CO2 Partial Pressure, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=698217, value_range=[0, 246], median=41, units=mm Hg`
  - table: `labs`
  - itemid: `50818`
  - concept_id: `3013290`
  - raw label: `pCO2`
  - stats: `row_count=698217, value_range=[0, 246], median=41, units=mm Hg`

### ph, pH Of Blood, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `pH`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=432459, value_range=[0, 999999], median=7.39, units=units`
  - table: `chartevents_main`
  - itemid: `223830`
  - concept_id: `3019977`
  - raw label: `PH (Arterial)`
  - stats: `row_count=432459, value_range=[0, 999999], median=7.39, units=units`

match 2:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct zcat|awk count. Real pH itemids 223830 (chartevents) and 50820 (754141 rows, median 7.38) remain kept.`
  - table: `labs`
  - itemid: `52041`
  - concept_id: `3019977`
  - raw label: `pH`
  - stats: `no raw-table stats queried`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=754141, value_range=[0, 8.92], median=7.38, units=units`
  - table: `labs`
  - itemid: `50820`
  - concept_id: `3010421`
  - raw label: `pH`
  - stats: `row_count=754141, value_range=[0, 8.92], median=7.38, units=units`

### phos, Phosphate, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mg/dL`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=2814319, value_range=[0, 59.7], median=3.4, units=mg/dL`
  - table: `labs`
  - itemid: `50970`
  - concept_id: `3011904`
  - raw label: `Phosphate`
  - stats: `row_count=2814319, value_range=[0, 59.7], median=3.4, units=mg/dL`

match 2:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates urine, not the target specimen`
  - table: `labs`
  - itemid: `51095`
  - concept_id: `3026729`
  - raw label: `Phosphate, Urine`
  - stats: `row_count=3990, value_range=[0, 501.8], median=36.1, units=mg/dL`

match 3:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates body fluid, not the target specimen`
  - table: `labs`
  - itemid: `51040`
  - concept_id: `3034814`
  - raw label: `Phosphate, Body Fluid`
  - stats: `row_count=11, value_range=[0.4, 24.2], median=2.8, units=mg/dL`

### plt, Platelet Count, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `G/l`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `reject`
  - decision reason: `WRONG TYPE -- "Platelet Smear" is a qualitative blood-smear morphology comment field, not a numeric platelet count`
  - table: `labs`
  - itemid: `51266`
  - concept_id: `3033641`
  - raw label: `Platelet Smear`
  - stats: `row_count=317261, value_range=[0, 63], median=0, units=N/A`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4214048, value_range=[5, 2989], median=218, units=K/uL`
  - table: `labs`
  - itemid: `51265`
  - concept_id: `3024929`
  - raw label: `Platelet Count`
  - stats: `row_count=4214048, value_range=[5, 2989], median=218, units=K/uL`

match 3:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- not present in d_labitems.csv.gz or d_items.csv.gz at all, confirmed 2026-07-29. Real platelet itemid 51265 remains kept.`
  - table: `labs`
  - itemid: `51704`
  - concept_id: `3024929`
  - raw label: `Platelet Count`
  - stats: `no raw-table stats queried`

match 4:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct zcat|awk count.`
  - table: `labs`
  - itemid: `52201`
  - concept_id: `3024929`
  - raw label: `PltScat`
  - stats: `no raw-table stats queried`

### ptt, Partial Thromboplastin Time, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `sec`
- Match method: `omop_concept_match`

match 1:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- this decision was originally made on label text alone ("no raw-table stats queried"), never data-validated. Confirmed via direct raw-table count 2026-07-28: 0 rows in the actual data extract. This itemid is not usable regardless of what d_labitems.csv.gz's catalog entry claims.`
  - table: `labs`
  - itemid: `52923`
  - concept_id: `3013466`
  - raw label: `PTT`
  - stats: `row_count=0 -- dead itemid, confirmed via direct zcat|awk count`

match 2 (added by hand, 2026-07-28):
  - decision: `keep`
  - decision reason: `real, active PTT itemid found via a direct d_items re-search after match 1 was found to be dead; the omop concept-chain never surfaced this one.`
  - table: `labs`
  - itemid: `51275`
  - raw label: `PTT, Blood, Hematology`
  - stats: `row_count=1637800, value_range=[1.2, 198.1], median=33.1, units=sec`

### sbp, Systolic Blood Pressure, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=3087686, value_range=[-94, 95119], median=116, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220050`
  - concept_id: `3004249`
  - raw label: `Arterial Blood Pressure systolic`
  - stats: `row_count=3087686, value_range=[-94, 95119], median=116, units=mmHg`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=387980, value_range=[-18, 342], median=111, units=mmHg`
  - table: `chartevents_main`
  - itemid: `225309`
  - concept_id: `3004249`
  - raw label: `ART BP Systolic`
  - stats: `row_count=387980, value_range=[-18, 342], median=111, units=mmHg`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1544, value_range=[0, 248], median=116.5, units=mmHg`
  - table: `chartevents_main`
  - itemid: `224167`
  - concept_id: `3004249`
  - raw label: `Manual Blood Pressure Systolic Left`
  - stats: `row_count=1544, value_range=[0, 248], median=116.5, units=mmHg`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1255, value_range=[3, 240], median=120, units=mmHg`
  - table: `chartevents_main`
  - itemid: `227243`
  - concept_id: `3004249`
  - raw label: `Manual Blood Pressure Systolic Right`
  - stats: `row_count=1255, value_range=[3, 240], median=120, units=mmHg`

match 5:
  - decision: `reject`
  - decision reason: `omr outpatient "Blood Pressure Standing" is a combined systolic/diastolic string (e.g. "110/65"), not a parseable systolic value, and is non-ICU-scoped (rc=565 vs millions in chartevents) -- redundant and lower-quality vs the chartevents candidates`
  - table: `omr`
  - itemid: `blood_pressure`
  - concept_id: `3004249`
  - raw label: `Blood Pressure Standing`
  - stats: `row_count=565`

match 6:
  - decision: `reject`
  - decision reason: `cross-contaminated: this is Pulmonary Artery Pressure SYSTOLIC (belongs to `spap`), not systemic systolic BP`
  - table: `chartevents_main`
  - itemid: `220059`
  - concept_id: `3005606`
  - raw label: `Pulmonary Artery Pressure systolic`
  - stats: `row_count=398701, value_range=[-15, 662], median=37, units=mmHg`

match 7:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=5378740, value_range=[-69, 1.0251e+06], median=117, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220179`
  - concept_id: `21492239`
  - raw label: `Non Invasive Blood Pressure systolic`
  - stats: `row_count=5378740, value_range=[-69, 1.0251e+06], median=117, units=mmHg`

### tnt, Troponin T, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `ng/mL`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=459872, value_range=[0, 52.4], median=0.09, units=ng/mL`
  - table: `labs`
  - itemid: `51003`
  - concept_id: `3019800`
  - raw label: `Troponin T`
  - stats: `row_count=459872, value_range=[0, 52.4], median=0.09, units=ng/mL`

### wbc, White Blood Cell Count, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `G/l`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: the stale NEEDS MANUAL REVIEW note (unit-basis/concept_id ambiguity) obscured real itemid-level bugs, found during a full sweep of all 21 tags still carrying that note -- see per-match decision reasons below.`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4157284, value_range=[0, 12500], median=7.6, units=K/uL`
  - table: `labs`
  - itemid: `51301`
  - concept_id: `3000905`
  - raw label: `White Blood Cells`
  - stats: `row_count=4157284, value_range=[0, 12500], median=7.6, units=K/uL`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=29574, value_range=[0, 236], median=5.7, units=K/uL`
  - table: `labs`
  - itemid: `51300`
  - concept_id: `3000905`
  - raw label: `WBC Count`
  - stats: `row_count=29574, value_range=[0, 236], median=5.7, units=K/uL`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=546, value_range=[0.4, 27.7], median=8, units=K/uL`
  - table: `labs`
  - itemid: `51755`
  - concept_id: `3000905`
  - raw label: `White Blood Cells`
  - stats: `row_count=546, value_range=[0.4, 27.7], median=8, units=K/uL`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=17, value_range=[2.5, 15.1], median=7.6, units=K/uL`
  - table: `labs`
  - itemid: `51756`
  - concept_id: `3000905`
  - raw label: `White Blood Cells`
  - stats: `row_count=17, value_range=[2.5, 15.1], median=7.6, units=K/uL`

match 5:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- correct specimen (Blood per d_labitems.csv.gz) but 0 rows in labevents.csv.gz; no data to extract.`
  - table: `labs`
  - itemid: `52219`
  - concept_id: `3000905`
  - raw label: `WBCScat`
  - stats: `no raw-table stats queried`

match 6:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- despite the raw label 'WBC', d_labitems.csv.gz lists this itemid's fluid as Stool, not blood.`
  - table: `labs`
  - itemid: `52407`
  - concept_id: `3014441`
  - raw label: `WBC`
  - stats: `no raw-table stats queried`

match 7:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Urine, not Blood; constant value=500 across all 843483 rows confirms a semi-quantitative urine dipstick bucket, not a real WBC count.`
  - table: `labs`
  - itemid: `51486`
  - concept_id: `3022547`
  - raw label: `Leukocytes`
  - stats: `row_count=843483, value_range=[500, 500], median=500, units=N/A`

match 8:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Urine, not Blood.`
  - table: `labs`
  - itemid: `51985`
  - concept_id: `3022547`
  - raw label: `Leukocytes`
  - stats: `row_count=1715, units=N/A`

match 9:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Urine, not Blood; units=#/hpf (per high-power-field) confirm urine microscopy, not blood WBC count (K/uL).`
  - table: `labs`
  - itemid: `51516`
  - concept_id: `3035583`
  - raw label: `WBC`
  - stats: `row_count=600831, value_range=[0, 1000], median=3, units=#/hpf`

match 10:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- despite the raw label 'Leuks', d_labitems.csv.gz lists this itemid's fluid as Urine (UTI indicator), not blood WBC.`
  - table: `labs`
  - itemid: `52413`
  - concept_id: `3035583`
  - raw label: `Leuks`
  - stats: `no raw-table stats queried`

match 11:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- despite the raw label 'LEUKS', d_labitems.csv.gz lists this itemid's fluid as Urine, not blood WBC.`
  - table: `labs`
  - itemid: `52414`
  - concept_id: `3035583`
  - raw label: `LEUKS`
  - stats: `no raw-table stats queried`

### basos, Basophils, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Ascites, not Blood. Wrongly pooled into the blood differential basophil count.`
  - table: `labs`
  - itemid: `51112`
  - concept_id: `3032363`
  - raw label: `Basophils`
  - stats: `row_count=656, value_range=[0, 18], median=1, units=%`

match 2:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Pleural, not Blood.`
  - table: `labs`
  - itemid: `51442`
  - concept_id: `3030571`
  - raw label: `Basophils`
  - stats: `row_count=780, value_range=[0, 12], median=1, units=%`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1611761, value_range=[0, 63], median=0.4, units=%`
  - table: `labs`
  - itemid: `51146`
  - concept_id: `3013869`
  - raw label: `Basophils`
  - stats: `row_count=1611761, value_range=[0, 63], median=0.4, units=%`

match 4:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Other Body Fluid, not Blood.`
  - table: `labs`
  - itemid: `51387`
  - concept_id: `3021302`
  - raw label: `Basophils`
  - stats: `row_count=311, value_range=[0, 10], median=1, units=%`

match 5:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Joint Fluid, not Blood.`
  - table: `labs`
  - itemid: `51367`
  - concept_id: `3035319`
  - raw label: `Basophils`
  - stats: `row_count=243, value_range=[0, 11], median=1, units=%`

match 6:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Cerebrospinal Fluid, not Blood.`
  - table: `labs`
  - itemid: `52225`
  - concept_id: `3020829`
  - raw label: `Basophils`
  - stats: `row_count=453, value_range=[0, 25], median=1, units=%`

### eos, Eosinophils, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid as Ascites, not Blood. Wrongly pooled into the blood differential eosinophil count.`
  - table: `labs`
  - itemid: `51114`
  - concept_id: `3019298`
  - raw label: `Eosinophils`
  - stats: `row_count=2242, value_range=[0, 73], median=1, units=%`

match 2:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Pleural, not Blood.`
  - table: `labs`
  - itemid: `51444`
  - concept_id: `3001893`
  - raw label: `Eosinophils`
  - stats: `row_count=3013, value_range=[0, 93], median=2, units=%`

match 3:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Other Body Fluid, not Blood.`
  - table: `labs`
  - itemid: `51419`
  - concept_id: `3021453`
  - raw label: `Eosinophils`
  - stats: `row_count=1982, value_range=[0, 94], median=2, units=%`

match 4:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Cerebrospinal Fluid, not Blood.`
  - table: `labs`
  - itemid: `52256`
  - concept_id: `3022640`
  - raw label: `Eosinophils`
  - stats: `row_count=1865, value_range=[0, 100], median=1, units=%`

match 5:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1611761, value_range=[0, 98], median=1.5, units=%`
  - table: `labs`
  - itemid: `51200`
  - concept_id: `3010457`
  - raw label: `Eosinophils`
  - stats: `row_count=1611761, value_range=[0, 98], median=1.5, units=%`

match 6:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- fluid is Joint Fluid, not Blood.`
  - table: `labs`
  - itemid: `51368`
  - concept_id: `3035611`
  - raw label: `Eosinophils`
  - stats: `row_count=1252, value_range=[0, 58], median=1, units=%`

### mgcs, Glasgow Coma Scale Motor, observation, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `categorical`
- Target unit: `categorical`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=2199619, value_range=[1, 6], median=6`
  - table: `chartevents_main`
  - itemid: `223901`
  - concept_id: `3008223`
  - raw label: `GCS - Motor Response`
  - stats: `row_count=2199619, value_range=[1, 6], median=6`

match 2:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2360`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, obeys commands, unspecified time`
  - stats: `row_count=13`

match 3:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2342`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, flexion withdrawal, at arrival to emergency department`
  - stats: `row_count=60`

match 4:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2352`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, localizes pain, at arrival to emergency department`
  - stats: `row_count=181`

match 5:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2331`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, abnormal flexion, in the field [EMT or ambulance]`
  - stats: `row_count=2`

match 6:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2311`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, none, in the field [EMT or ambulance]`
  - stats: `row_count=2`

match 7:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2353`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, localizes pain, at hospital admission`
  - stats: `row_count=50`

match 8:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2364`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, obeys commands, 24 hours or more after hospital admission`
  - stats: `row_count=24`

match 9:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2363`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, obeys commands, at hospital admission`
  - stats: `row_count=252`

match 10:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2321`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, extension, in the field [EMT or ambulance]`
  - stats: `row_count=1`

match 11:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2362`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, obeys commands, at arrival to emergency department`
  - stats: `row_count=836`

match 12:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2334`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, abnormal flexion, 24 hours or more after hospital admission`
  - stats: `row_count=1`

match 13:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2323`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, extension, at hospital admission`
  - stats: `row_count=10`

match 14:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2312`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, none, at arrival to emergency department`
  - stats: `row_count=83`

match 15:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2320`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, extension, unspecified time`
  - stats: `row_count=2`

match 16:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2314`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, none, 24 hours or more after hospital admission`
  - stats: `row_count=7`

match 17:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2344`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, flexion withdrawal, 24 hours or more after hospital admission`
  - stats: `row_count=5`

match 18:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2341`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, flexion withdrawal, in the field [EMT or ambulance]`
  - stats: `row_count=2`

match 19:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2332`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, abnormal flexion, at arrival to emergency department`
  - stats: `row_count=17`

match 20:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2333`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, abnormal flexion, at hospital admission`
  - stats: `row_count=5`

match 21:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2324`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, extension, 24 hours or more after hospital admission`
  - stats: `row_count=1`

match 22:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2361`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, obeys commands, in the field [EMT or ambulance]`
  - stats: `row_count=16`

match 23:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2313`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, none, at hospital admission`
  - stats: `row_count=25`

match 24:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2354`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, localizes pain, 24 hours or more after hospital admission`
  - stats: `row_count=6`

match 25:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2340`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, flexion withdrawal, unspecified time`
  - stats: `row_count=1`

match 26:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2343`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, flexion withdrawal, at hospital admission`
  - stats: `row_count=23`

match 27:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2322`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, extension, at arrival to emergency department`
  - stats: `row_count=19`

match 28:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2351`
  - concept_id: `3008223`
  - raw label: `Coma scale, best motor response, localizes pain, in the field [EMT or ambulance]`
  - stats: `row_count=2`

match 29:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223901`
  - raw label: `GCS - Motor Response`
  - raw value: `Abnormal Flexion`
  - standardized label: `M3 Abnormal flexion`

match 30:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223901`
  - raw label: `GCS - Motor Response`
  - raw value: `Abnormal extension`
  - standardized label: `M2 Extension`

match 31:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223901`
  - raw label: `GCS - Motor Response`
  - raw value: `Flex-withdraws`
  - standardized label: `M4 Withdraws from pain`

match 32:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223901`
  - raw label: `GCS - Motor Response`
  - raw value: `Localizes Pain`
  - standardized label: `M5 Localizes pain`

match 33:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223901`
  - raw label: `GCS - Motor Response`
  - raw value: `No response`
  - standardized label: `M1 None`

match 34:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223901`
  - raw label: `GCS - Motor Response`
  - raw value: `Obeys Commands`
  - standardized label: `M6 Obeys commands`

### tgcs, Glasgow Coma Scale Total, observation, neuro
- Mapping status: `no_source_candidates`
- Reconstruction type: `derived_score`
- Target unit: `categorical`
- Match method: `none`
- Notes: `Same as AUMC: no direct source, derive by summing mgcs+vgcs+egcs-equivalent MIMIC components (chartevents GCS Motor/Verbal/Eye Opening) once those are individually resolved.`

### vgcs, Glasgow Coma Scale Verbal, observation, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `categorical`
- Target unit: `categorical`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=2205121, value_range=[1, 5], median=4`
  - table: `chartevents_main`
  - itemid: `223900`
  - concept_id: `3009094`
  - raw label: `GCS - Verbal Response`
  - stats: `row_count=2205121, value_range=[1, 5], median=4`

match 2:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2222`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, incomprehensible words, at arrival to emergency department`
  - stats: `row_count=35`

match 3:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2221`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, incomprehensible words, in the field [EMT or ambulance]`
  - stats: `row_count=1`

match 4:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2252`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, at arrival to emergency department`
  - stats: `row_count=573`

match 5:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2232`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, inappropriate words, at arrival to emergency department`
  - stats: `row_count=40`

match 6:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2241`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, in the field [EMT or ambulance]`
  - stats: `row_count=2`

match 7:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2223`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, incomprehensible words, at hospital admission`
  - stats: `row_count=10`

match 8:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2210`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, unspecified time`
  - stats: `row_count=5`

match 9:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2213`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, at hospital admission`
  - stats: `row_count=105`

match 10:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2224`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, incomprehensible words, 24 hours or more after hospital admission`
  - stats: `row_count=3`

match 11:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2234`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, inappropriate words, 24 hours or more after hospital admission`
  - stats: `row_count=1`

match 12:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2242`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, at arrival to emergency department`
  - stats: `row_count=218`

match 13:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2251`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, in the field [EMT or ambulance]`
  - stats: `row_count=14`

match 14:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2214`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, 24 hours or more after hospital admission`
  - stats: `row_count=19`

match 15:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2244`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, 24 hours or more after hospital admission`
  - stats: `row_count=7`

match 16:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2243`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, at hospital admission`
  - stats: `row_count=68`

match 17:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2233`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, inappropriate words, at hospital admission`
  - stats: `row_count=10`

match 18:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2211`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, in the field [EMT or ambulance]`
  - stats: `row_count=8`

match 19:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2254`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, 24 hours or more after hospital admission`
  - stats: `row_count=14`

match 20:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2240`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, unspecified time`
  - stats: `row_count=2`

match 21:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2212`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, at arrival to emergency department`
  - stats: `row_count=327`

match 22:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2250`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, unspecified time`
  - stats: `row_count=9`

match 23:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2253`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, at hospital admission`
  - stats: `row_count=172`

match 24:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223900`
  - raw label: `GCS - Verbal Response`
  - raw value: `Confused`
  - standardized label: `V4 Confused`

match 25:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223900`
  - raw label: `GCS - Verbal Response`
  - raw value: `Inappropriate Words`
  - standardized label: `V3 Inappropriate words`

match 26:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223900`
  - raw label: `GCS - Verbal Response`
  - raw value: `Incomprehensible sounds`
  - standardized label: `V2 Incomprehensible sounds`

match 27:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223900`
  - raw label: `GCS - Verbal Response`
  - raw value: `No Response`
  - standardized label: `V1 None`

match 28:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223900`
  - raw label: `GCS - Verbal Response`
  - raw value: `No Response-ETT`
  - standardized label: `Intubated`

match 29:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `223900`
  - raw label: `GCS - Verbal Response`
  - raw value: `Oriented`
  - standardized label: `V5 Oriented`

### egcs, Glasgow Coma Scale Eye, observation, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `categorical`
- Target unit: `categorical`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=2209510, value_range=[1, 4], median=4`
  - table: `chartevents_main`
  - itemid: `220739`
  - concept_id: `3016335`
  - raw label: `GCS - Eye Opening`
  - stats: `row_count=2209510, value_range=[1, 4], median=4`

match 2:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2113`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, never, at hospital admission`
  - stats: `row_count=78`

match 3:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2131`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to sound, in the field [EMT or ambulance]`
  - stats: `row_count=2`

match 4:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2124`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to pain, 24 hours or more after hospital admission`
  - stats: `row_count=1`

match 5:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2140`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, spontaneous, unspecified time`
  - stats: `row_count=10`

match 6:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2122`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to pain, at arrival to emergency department`
  - stats: `row_count=55`

match 7:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2141`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, spontaneous, in the field [EMT or ambulance]`
  - stats: `row_count=15`

match 8:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2110`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, never, unspecified time`
  - stats: `row_count=3`

match 9:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2143`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, spontaneous, at hospital admission`
  - stats: `row_count=229`

match 10:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2134`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to sound, 24 hours or more after hospital admission`
  - stats: `row_count=14`

match 11:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2120`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to pain, unspecified time`
  - stats: `row_count=1`

match 12:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2130`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to sound, unspecified time`
  - stats: `row_count=2`

match 13:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2144`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, spontaneous, 24 hours or more after hospital admission`
  - stats: `row_count=16`

match 14:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2112`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, never, at arrival to emergency department`
  - stats: `row_count=264`

match 15:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2121`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to pain, in the field [EMT or ambulance]`
  - stats: `row_count=2`

match 16:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2142`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, spontaneous, at arrival to emergency department`
  - stats: `row_count=727`

match 17:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2123`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to pain, at hospital admission`
  - stats: `row_count=19`

match 18:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2111`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, never, in the field [EMT or ambulance]`
  - stats: `row_count=6`

match 19:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2114`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, never, 24 hours or more after hospital admission`
  - stats: `row_count=13`

match 20:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2132`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to sound, at arrival to emergency department`
  - stats: `row_count=153`

match 21:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2133`
  - concept_id: `3016335`
  - raw label: `Coma scale, eyes open, to sound, at hospital admission`
  - stats: `row_count=40`

match 22:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `220739`
  - raw label: `GCS - Eye Opening`
  - raw value: `None`
  - standardized label: `E1 None`

match 23:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `220739`
  - raw label: `GCS - Eye Opening`
  - raw value: `Spontaneously`
  - standardized label: `E4 Spontaneous`

match 24:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `220739`
  - raw label: `GCS - Eye Opening`
  - raw value: `To Pain`
  - standardized label: `E2 To pain`

match 25:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `220739`
  - raw label: `GCS - Eye Opening`
  - raw value: `To Speech`
  - standardized label: `E3 To speech`

### hct, Hematocrit, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4331615, value_range=[0, 248], median=33.3, units=%`
  - table: `labs`
  - itemid: `51221`
  - concept_id: `3023314`
  - raw label: `Hematocrit`
  - stats: `row_count=4331615, value_range=[0, 248], median=33.3, units=%`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1289, value_range=[17, 60], median=41, units=%`
  - table: `labs`
  - itemid: `51638`
  - concept_id: `3023314`
  - raw label: `Hematocrit`
  - stats: `row_count=1289, value_range=[17, 60], median=41, units=%`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=17, value_range=[27.9, 50], median=40, units=%`
  - table: `labs`
  - itemid: `51639`
  - concept_id: `3023314`
  - raw label: `Hematocrit`
  - stats: `row_count=17, value_range=[27.9, 50], median=40, units=%`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=593604, value_range=[0, 2.0112e+06], median=28.6, units=%`
  - table: `chartevents_main`
  - itemid: `220545`
  - concept_id: `3009542`
  - raw label: `Hematocrit (serum)`
  - stats: `row_count=593604, value_range=[0, 2.0112e+06], median=28.6, units=%`

### rbc, Red Blood Cell Count, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `m/uL`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: the stale NEEDS MANUAL REVIEW note (unit-basis/concept_id ambiguity) obscured real itemid-level bugs, found during a full sweep of all 21 tags still carrying that note -- see per-match decision reasons below.`

match 1:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates joint fluid, not the target specimen`
  - table: `labs`
  - itemid: `51383`
  - concept_id: `3010144`
  - raw label: `RBC, Joint Fluid`
  - stats: `row_count=6796, value_range=[0, 6.905e+06], median=7437, units=#/uL`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4152106, value_range=[0, 254], median=3.7, units=m/uL`
  - table: `labs`
  - itemid: `51279`
  - concept_id: `3020416`
  - raw label: `Red Blood Cells`
  - stats: `row_count=4152106, value_range=[0, 254], median=3.7, units=m/uL`

match 3:
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- correct specimen (Blood per d_labitems.csv.gz) but 0 rows in labevents.csv.gz; no data to extract.`
  - table: `labs`
  - itemid: `52170`
  - concept_id: `3020416`
  - raw label: `Rbc`
  - stats: `no raw-table stats queried`

match 4:
  - decision: `reject`
  - decision reason: `WRONG TYPE -- "ErytFlg" is a hematology-analyzer QC/flag field, not a numeric RBC count`
  - table: `labs`
  - itemid: `52198`
  - concept_id: `3020416`
  - raw label: `ErytFlg`
  - stats: `no raw-table stats queried`

match 5:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates ascites, not the target specimen`
  - table: `labs`
  - itemid: `51127`
  - concept_id: `3009613`
  - raw label: `RBC, Ascites`
  - stats: `row_count=15317, value_range=[0, 2.115e+06], median=852, units=#/uL`

match 6:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates csf, not the target specimen`
  - table: `labs`
  - itemid: `52285`
  - concept_id: `3027475`
  - raw label: `RBC, CSF`
  - stats: `row_count=21084, value_range=[0, 2.435e+06], median=7, units=#/uL`

match 7:
  - decision: `reject`
  - decision reason: `SPECIMEN MISMATCH -- d_labitems.csv.gz lists this itemid's fluid column as "Urine" (urine microscopy sediment RBC count, #/hpf), not blood; the raw label alone ("RBC") gave no indication of this since the specimen type lives in a separate column the original review pass didn't check. Wrongly kept 2026-07-28 in the initial pass, contaminating the blood rbc feature with 600,831 urine-sediment rows on a completely different scale (median 2 #/hpf vs ~3.7 m/uL for real blood RBC).`
  - table: `labs`
  - itemid: `51493`
  - concept_id: `3035124`
  - raw label: `RBC`
  - stats: `row_count=600831, value_range=[0, 30672], median=2, units=#/hpf -- Urine specimen, not blood`

match 8:
  - decision: `reject`
  - decision reason: `specimen mismatch -- label indicates pleural, not the target specimen`
  - table: `labs`
  - itemid: `51457`
  - concept_id: `3028308`
  - raw label: `RBC, Pleural`
  - stats: `row_count=9426, value_range=[0, 2.6475e+06], median=3975, units=#/uL`

match 9:
  - decision: `reject`
  - decision reason: `specimen mismatch -- "Other Fluid" is not blood`
  - table: `labs`
  - itemid: `51438`
  - concept_id: `3010910`
  - raw label: `RBC, Other Fluid`
  - stats: `row_count=2281, value_range=[0, 4.325e+06], median=74, units=#/uL`

### tri, Troponin I, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `ng/mL`
- Match method: `omop_concept_match`

match 0 (added by hand):
  - decision: `reject`
  - decision reason: `correct analyte but unavailable to this ICU grid: all 670 labevents rows have null hadm_id, so the required (subject_id, hadm_id) ICU-stay join emits zero rows; keep this source limitation explicit instead of declaring a physically absent feature`
  - table: `labs`
  - itemid: `52642`
  - raw label: `Troponin I`
  - stats: `row_count=670, value_range=[0, 5.51], units=ng/mL`

match 1:
  - decision: `reject`
  - decision reason: `WRONG ANALYTE -- this is Troponin T (itemid shared incorrectly via an upstream AUMC concept-mapping error; belongs to `tnt`), not Troponin I. Real Troponin I itemids are 51002/52642 -- see notes, needs a new match added`
  - table: `labs`
  - itemid: `51003`
  - concept_id: `3019800`
  - raw label: `Troponin T`
  - stats: `row_count=459872, value_range=[0, 52.4], median=0.09, units=ng/mL`

### etco2, Endtidal CO2, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED -- originally no_source_candidates because keyword_fallback() found nothing at all: name "Endtidal CO2" tokenizes to "endtidal" (the other token "co" is length 2, dropped by the len>2 filter), and "endtidal" doesn't appear anywhere in MIMIC's label ("EtCO2"). Found by a direct d_items re-search on "etco2|end-tidal|carbon dioxide".`

match 1:
  - decision: `keep`
  - decision reason: `primary EtCO2 itemid, plausible mean value; extraction needs a plausibility bound (max 2950460 is a clear sentinel/error value)`
  - table: `chartevents`
  - itemid: `228640`
  - raw label: `EtCO2`
  - stats: `row_count=159348, value_range=[-62, 2950460], mean=68.86, category=Routine Vital Signs`

### rass, Richmond Agitation Sedation Scale, observation, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `categorical`
- Target unit: `categorical`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary RASS itemid -- substring-matchable but crowded out of the automated candidate list by head(15) truncation (generic token "scale" matched many IV-site Phlebitis/Infiltration Scale rows first); found by a direct d_items re-search on "richmond|rass"`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`

match 2:
  - decision: `reject`
  - decision reason: `the sedation TARGET value, not the observed/actual RASS assessment`
  - table: `chartevents`
  - itemid: `228299`
  - raw label: `Goal Richmond-RAS Scale`

match 3:
  - decision: `reject`
  - decision reason: `a CAM-ICU delirium-assessment field that references RASS context, not the RASS score itself`
  - table: `chartevents`
  - itemid: `228302`
  - raw label: `CAM-ICU RASS LOC`

match 4:
  - decision: `reject`
  - decision reason: `a different validated instrument (Riker Sedation-Agitation Scale) -- same clinical purpose as RASS but not the same scale; would need an explicit rescaling/crosswalk policy to substitute, not a direct match`
  - table: `chartevents`
  - itemid: `223753`
  - raw label: `Riker-SAS Scale`
  - stats: `row_count=288695, value_range=[1, 7], median=4`

match 5:
  - decision: `reject`
  - decision reason: `a generic single-item agitation flag, not the full RASS scale`
  - table: `chartevents`
  - itemid: `223817`
  - raw label: `Agitation`
  - stats: `row_count=42533, value_range=[0, 7], median=1`

match 6:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228009`
  - raw label: `16 G Phlebitis Scale`

match 7:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228010`
  - raw label: `16 G Infiltration Scale`

match 8:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228013`
  - raw label: `20 G Phlebitis Scale`

match 9:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228014`
  - raw label: `20 G Infiltration Scale`

match 10:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228007`
  - raw label: `14 G Phlebitis Scale`

match 11:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228008`
  - raw label: `14 G Infiltration Scale`

match 12:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228011`
  - raw label: `18 G Phlebitis Scale`

match 13:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228012`
  - raw label: `18 G Infiltration Scale`

match 14:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228017`
  - raw label: `RIC Phlebitis Scale`

match 15:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228015`
  - raw label: `22 G Phlebitis Scale`

match 16:
  - decision: `reject`
  - decision reason: `IV-site assessment scale, unrelated -- false hit on "scale"`
  - table: `chartevents`
  - itemid: `228016`
  - raw label: `22 G Infiltration Scale`

match 17:
  - decision: `reject`
  - decision reason: `procedure-specific sedation flag, not RASS`
  - table: `chartevents`
  - itemid: `224506`
  - raw label: `Conscious sedation (THCEN)`

match 18:
  - decision: `reject`
  - decision reason: `procedure-specific sedation flag, not RASS`
  - table: `chartevents`
  - itemid: `225531`
  - raw label: `Conscious sedation used (Bronch)`

match 19:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `+1 Anxious, apprehensive, but not aggressive`
  - standardized label: `+1 Restless`

match 20:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `+2 Frequent nonpurposeful movement, fights ventilator`
  - standardized label: `+2 Agitated`

match 21:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `+3 Pulls or removes tube(s) or catheter(s); aggressive`
  - standardized label: `+3 Very agitated`

match 22:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `+4 Combative, violent, danger to staff`
  - standardized label: `+4 Combative`

match 23:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `-1 Awakens to voice (eye opening/contact) > 10 sec`
  - standardized label: `-1 Drowsy`

match 24:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `-2 Light sedation, briefly awakens to voice (eye opening/contact) < 10 sec`
  - standardized label: `-2 Light sedation`

match 25:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `-3 Moderate sedation, movement or eye opening; No eye contact`
  - standardized label: `-3 Moderate sedation`

match 26:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `-4 Deep sedation, no response to voice, but movement or eye opening to physical stimulation`
  - standardized label: `-4 Deep sedation`

match 27:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `-5 Unarousable, no response to voice or physical stimulation`
  - standardized label: `-5 Unarousable`

match 28:
  - decision: `keep`
  - decision reason: `backfilled 2026-07-29 for grid.encode's one-hot vocab -- real category confirmed via test_1k_output_v6/grid.parquet distinct values`
  - table: `chartevents`
  - itemid: `228096`
  - raw label: `Richmond-RAS Scale`
  - raw value: `0  Alert and calm`
  - standardized label: `0 Alert and calm`

### hbco, Carboxyhemoglobin, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=6661, value_range=[0, 37], median=2, units=%`
  - table: `labs`
  - itemid: `50805`
  - concept_id: `3023081`
  - raw label: `Carboxyhemoglobin`
  - stats: `row_count=6661, value_range=[0, 37], median=2, units=%`

### esr, Erythrocyte Sedimentation Rate, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mm/hr`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=64097, value_range=[0, 150], median=22, units=mm/hr`
  - table: `labs`
  - itemid: `51288`
  - concept_id: `3013707`
  - raw label: `Sedimentation Rate`
  - stats: `row_count=64097, value_range=[0, 150], median=22, units=mm/hr`

### pt, Prothrombine Time, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `sec`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary Prothrombin Time itemid -- MIMIC labels this with the bare abbreviation "PT", unmatchable by a substring search against AUMC's spelled-out name "Prothrombine Time"; found by a direct d_labitems re-search on "prothrombin"`
  - table: `labevents`
  - itemid: `51274`
  - raw label: `PT`
  - stats: `specimen=Blood, category=Hematology`

match 2:
  - decision: `reject`
  - decision reason: `QC/control value, not a patient result`
  - table: `labevents`
  - itemid: `52163`
  - raw label: `PT Control`

match 3:
  - decision: `reject`
  - decision reason: `QC/control value, not a patient result`
  - table: `labevents`
  - itemid: `52164`
  - raw label: `PT Mean`

match 4:
  - decision: `reject`
  - decision reason: `0 rows; "Z"-prefix is MIMIC's convention for a deprecated/retired chartevents itemid`
  - table: `chartevents`
  - itemid: `220560`
  - raw label: `ZProthrombin time`

match 5:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `224347`
  - raw label: `Timeout performed by (CVL)`

match 6:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `224515`
  - raw label: `Timeout performed by (PICC)`

match 7:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `224617`
  - raw label: `Timeout performed by (PA line)`

match 8:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `225490`
  - raw label: `Timeout Performed by (THCEN)`

match 9:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `225498`
  - raw label: `Timeout performed by (PACEN)`

match 10:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `225539`
  - raw label: `Timeout performed by (Bronch)`

match 11:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `225596`
  - raw label: `Timeout Performed by (LP)`

match 12:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `226188`
  - raw label: `Timeout Performed by (Intubation)`

match 13:
  - decision: `reject`
  - decision reason: `procedural safety-checklist signoff, false hit on "time"`
  - table: `chartevents`
  - itemid: `226527`
  - raw label: `Timeout performed by (A-Line)`

match 14:
  - decision: `reject`
  - decision reason: `unrelated, false hit on "time"`
  - table: `datetimeevents`
  - itemid: `226516`
  - raw label: `Discharge Date/Time`

match 15:
  - decision: `reject`
  - decision reason: `unrelated flag, false hit on "time"`
  - table: `chartevents`
  - itemid: `227061`
  - raw label: `Ventilated at any time during ICU Day 1`

match 16:
  - decision: `reject`
  - decision reason: `unrelated ventilator timing measurement, wrong analyte`
  - table: `chartevents`
  - itemid: `224738`
  - raw label: `Inspiratory Time`
  - stats: `row_count=422123, units=sec`

match 17:
  - decision: `reject`
  - decision reason: `unrelated dialysis timing measurement, wrong analyte`
  - table: `chartevents`
  - itemid: `225810`
  - raw label: `Dwell Time (Peritoneal Dialysis)`
  - stats: `row_count=2218, units=hour`

match 18:
  - decision: `reject`
  - decision reason: `a different coagulation test (point-of-care ACT, used for heparin monitoring), not PT`
  - table: `chartevents`
  - itemid: `220507`
  - raw label: `Activated Clotting Time`
  - stats: `row_count=10986`

### adm, Patient Admission Type, demographic, not specified
- Mapping status: `admission_context`
- Reconstruction type: `admission_context`
- Target unit: `categorical`
- Match method: `admission_context_fixed`
- Notes: `admissions.admission_type (urgency analogue) x admission_location (origin analogue) -- collapsing policy (top-N + Other) still to be decided, same as AUMC's adm.`

### hba1c, Hemoglobin A1C, observation, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=295978, value_range=[3.2, 23.1], median=6.1, units=%`
  - table: `labs`
  - itemid: `50852`
  - concept_id: `3004410`
  - raw label: `% Hemoglobin A1c`
  - stats: `row_count=295978, value_range=[3.2, 23.1], median=6.1, units=%`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; no raw-table stats queried`
  - table: `labs`
  - itemid: `51631`
  - concept_id: `3004410`
  - raw label: `Glycated Hemoglobin`
  - stats: `no raw-table stats queried`

### samp, Body Fluid Sampling, Detected Bacterial Growth, observation, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `categorical`
- Match method: `omop_concept_match`
- Notes: `RECLASSIFIED 2026-07-29, mirroring AUMC's own review.md precedent (2026-07-10): microbiology -> treatment_indicator. Point-event handling (any kept-match row in an hour = On, no forward-fill) is mechanically identical to abx/sed/ins_ind, so this flows through the existing extract_treatment_indicator.py pipeline instead of needing a bespoke reconstruction type. M4's manifest had inherited "microbiology" from AUMC's own summary CSV, which was itself stale relative to AUMC's review.md.`

match 1:
  - decision: `keep`
  - decision reason: `REVERSED 2026-07-29 -- this tag's true scope (per AUMC's own established samp precedent: a broad culture-ORDER flag across ~14 specimen types, not blood-only, no growth/positivity component) legitimately includes stool cultures. The generic specimen-mismatch heuristic used by the automated review pass is correct for blood-only lab tests (rbc/wbc/etc.) but was wrongly applied here.`
  - table: `proc_itemid`
  - itemid: `225814`
  - concept_id: `4024963`
  - raw label: `Stool Culture`
  - stats: `row_count=2968, units=None`

match 2:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `795.39`
  - concept_id: `4189544`
  - raw label: `Other nonspecific positive culture findings`
  - stats: `row_count=21`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=7637, units=None`
  - table: `proc_itemid`
  - itemid: `225451`
  - concept_id: `4015189`
  - raw label: `Sputum Culture`
  - stats: `row_count=7637, units=None`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=26087, units=None`
  - table: `proc_itemid`
  - itemid: `225401`
  - concept_id: `4107893`
  - raw label: `Blood Cultured`
  - stats: `row_count=26087, units=None`

match 5:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=2753, units=None`
  - table: `proc_itemid`
  - itemid: `225444`
  - concept_id: `4107893`
  - raw label: `Pan Culture`
  - stats: `row_count=2753, units=None`

match 6:
  - decision: `keep`
  - decision reason: `REVERSED 2026-07-29 -- same reasoning as the stool-culture reversal above: samp's true scope legitimately includes urine cultures, this is not a specimen mismatch for this particular tag.`
  - table: `proc_itemid`
  - itemid: `225454`
  - concept_id: `4024509`
  - raw label: `Urine Culture`
  - stats: `row_count=13638, units=None`

match 7 (added by hand, 2026-07-29):
  - decision: `keep`
  - decision reason: `mirrors AUMC's samp whitelist (CSF/Liquor is one of AUMC's 14 kept specimen types) -- never surfaced by the initial OMOP-concept matching pass, found via direct d_items.csv.gz search on "cultur" and confirmed real via direct row-count query.`
  - table: `proc_itemid`
  - itemid: `225437`
  - raw label: `CSF Culture`
  - stats: `row_count=345, units=None`

match 8 (added by hand, 2026-07-29):
  - decision: `keep`
  - decision reason: `mirrors AUMC's samp whitelist (Wound is one of AUMC's 14 kept specimen types) -- never surfaced by the initial OMOP-concept matching pass, found via direct d_items.csv.gz search and confirmed real via direct row-count query.`
  - table: `proc_itemid`
  - itemid: `225816`
  - raw label: `Wound Culture`
  - stats: `row_count=459, units=None`

match 9 (added by hand, 2026-07-29):
  - decision: `keep`
  - decision reason: `mirrors AUMC's samp whitelist (Nose is one of AUMC's 14 kept specimen types) -- never surfaced by the initial OMOP-concept matching pass, found via direct d_items.csv.gz search and confirmed real via direct row-count query.`
  - table: `proc_itemid`
  - itemid: `225966`
  - raw label: `Nasal Swab`
  - stats: `row_count=11760, units=None`

match 10 (added by hand, 2026-07-29):
  - decision: `keep`
  - decision reason: `mirrors AUMC's samp whitelist (Rectum is one of AUMC's 14 kept specimen types) -- never surfaced by the initial OMOP-concept matching pass, found via direct d_items.csv.gz search and confirmed real via direct row-count query.`
  - table: `proc_itemid`
  - itemid: `225967`
  - raw label: `Rectal Swab`
  - stats: `row_count=98, units=None`

match 11 (added by hand, 2026-07-29):
  - decision: `keep`
  - decision reason: `partial-overlap analog for AUMC's "Drain fluid" specimen type (no exact MIMIC equivalent) -- BAL fluid is a body-cavity fluid culture in the same spirit; never surfaced by the initial OMOP-concept matching pass, found via direct d_items.csv.gz search and confirmed real via direct row-count query, low volume but genuine.`
  - table: `proc_itemid`
  - itemid: `225817`
  - raw label: `BAL Fluid Culture`
  - stats: `row_count=1261, units=None`

match 12 (added by hand, 2026-07-29):
  - decision: `reject`
  - decision reason: `DEAD ITEMID -- 0 rows in the actual data extract, confirmed 2026-07-29 via direct polars scan. Would have been the closest MIMIC analog for AUMC's "Drain fluid"/Ascites specimen types alongside BAL fluid, but not usable.`
  - table: `proc_itemid`
  - itemid: `225818`
  - raw label: `Pleural Fluid Culture`
  - stats: `row_count=0`

### spo2, Pulse Oxymetry Oxygen Saturation, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary SpO2 source`
  - table: `chartevents`
  - itemid: `220277`
  - raw label: `O2 saturation pulseoxymetry`
  - stats: `row_count=8567015, value_range=[-951234, 9900000], median=97, units=% (extraction needs a plausibility bound -- clear sentinel/error values in the tails)`

match 2:
  - decision: `reject`
  - decision reason: `alarm/threshold setting, not a measurement`
  - table: `chartevents`
  - itemid: `223770`
  - raw label: `O2 Saturation Pulseoxymetry Alarm - Low`

match 3:
  - decision: `reject`
  - decision reason: `alarm/threshold setting, not a measurement`
  - table: `chartevents`
  - itemid: `223769`
  - raw label: `O2 Saturation Pulseoxymetry Alarm - High`

match 4:
  - decision: `reject`
  - decision reason: `this is SaO2 (arterial blood-gas measurement), belongs to the separate `sao2` tag, not pulse-ox SpO2`
  - table: `chartevents`
  - itemid: `220227`
  - raw label: `Arterial O2 Saturation`

match 5:
  - decision: `reject`
  - decision reason: `pulse-presence check at a body site, unrelated to SpO2 %`
  - table: `chartevents`
  - itemid: `223936`
  - raw label: `Radial Pulse R`

match 6:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223938`
  - raw label: `Ulnar Pulse R`

match 7:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223940`
  - raw label: `Femoral Pulse R`

match 8:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223942`
  - raw label: `Graft/Flap Pulse`

match 9:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223939`
  - raw label: `Brachial Pulse R`

match 10:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223944`
  - raw label: `Brachial Pulse L`

match 11:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223934`
  - raw label: `Dorsal PedPulse R`

match 12:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223945`
  - raw label: `Femoral Pulse L`

match 13:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223943`
  - raw label: `Dorsal PedPulse L`

match 14:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223941`
  - raw label: `Popliteal Pulse R`

match 15:
  - decision: `reject`
  - decision reason: `pulse-presence check, unrelated`
  - table: `chartevents`
  - itemid: `223935`
  - raw label: `PostTib. Pulses R`

### sao2, Oxygen Saturation In Arterial Blood, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary SaO2 (arterial blood-gas) source`
  - table: `chartevents`
  - itemid: `220227`
  - raw label: `Arterial O2 Saturation`
  - stats: `row_count=119101, value_range=[0, 999999], median=96, units=% (extraction needs a plausibility bound)`

match 2:
  - decision: `reject`
  - decision reason: `this is SpO2 (pulse oximetry), belongs to the separate `spo2` tag, not arterial SaO2`
  - table: `chartevents`
  - itemid: `220277`
  - raw label: `O2 saturation pulseoxymetry`

match 3:
  - decision: `reject`
  - decision reason: `wrong analyte -- this is PaO2 (partial pressure), not SaO2`
  - table: `chartevents`
  - itemid: `220224`
  - raw label: `Arterial O2 pressure`

match 4:
  - decision: `reject`
  - decision reason: `wrong analyte -- PaCO2, not SaO2`
  - table: `chartevents`
  - itemid: `220235`
  - raw label: `Arterial CO2 Pressure`

match 5:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `223751`
  - raw label: `Non-Invasive Blood Pressure Alarm - High`

match 6:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `223752`
  - raw label: `Non-Invasive Blood Pressure Alarm - Low`

match 7:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220179`
  - raw label: `Non Invasive Blood Pressure systolic`

match 8:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220180`
  - raw label: `Non Invasive Blood Pressure diastolic`

match 9:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220181`
  - raw label: `Non Invasive Blood Pressure mean`

match 10:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220052`
  - raw label: `Arterial Blood Pressure mean`

match 11:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220050`
  - raw label: `Arterial Blood Pressure systolic`

match 12:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220051`
  - raw label: `Arterial Blood Pressure diastolic`

match 13:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220056`
  - raw label: `Arterial Blood Pressure Alarm - Low`

match 14:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220058`
  - raw label: `Arterial Blood Pressure Alarm - High`

match 15:
  - decision: `reject`
  - decision reason: `wrong domain, false hit on "blood"`
  - table: `inputevents`
  - itemid: `221013`
  - raw label: `Whole Blood`

### icp, Intra Cranial Pressure, observation, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=242758, value_range=[-41, 381], median=8, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220765`
  - concept_id: `21490653`
  - raw label: `Intra Cranial Pressure`
  - stats: `row_count=242758, value_range=[-41, 381], median=8, units=mmHg`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=5124, value_range=[-30, 134], median=8, units=mmHg`
  - table: `chartevents_main`
  - itemid: `227989`
  - concept_id: `21490653`
  - raw label: `Intra Cranial Pressure #2`
  - stats: `row_count=5124, value_range=[-30, 134], median=8, units=mmHg`

### cout, Cardiac Output, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `l/min`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=188469, value_range=[-339.2, 88], median=5, units=L/min`
  - table: `chartevents_main`
  - itemid: `224842`
  - concept_id: `3005555`
  - raw label: `Cardiac Output (CCO)`
  - stats: `row_count=188469, value_range=[-339.2, 88], median=5, units=L/min`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=29568, value_range=[0, 36.2], median=4.83, units=L/min`
  - table: `chartevents_main`
  - itemid: `220088`
  - concept_id: `3005555`
  - raw label: `Cardiac Output (thermodilution)`
  - stats: `row_count=29568, value_range=[0, 36.2], median=4.83, units=L/min`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=19704, value_range=[1, 19.7], median=5.9, units=L/min`
  - table: `chartevents_main`
  - itemid: `227543`
  - concept_id: `3005555`
  - raw label: `CO (Arterial)`
  - stats: `row_count=19704, value_range=[1, 19.7], median=5.9, units=L/min`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=10047, value_range=[0, 83], median=5.5, units=L/min`
  - table: `chartevents_main`
  - itemid: `228369`
  - concept_id: `3005555`
  - raw label: `Cardiac Output (CO NICOM)`
  - stats: `row_count=10047, value_range=[0, 83], median=5.5, units=L/min`

match 5:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=3940, value_range=[0, 940], median=6.505, units=L/min`
  - table: `chartevents_main`
  - itemid: `228178`
  - concept_id: `3005555`
  - raw label: `CO (PiCCO)`
  - stats: `row_count=3940, value_range=[0, 940], median=6.505, units=L/min`

match 6:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=46, value_range=[2.1, 10], median=3.22, units=L/min`
  - table: `chartevents_main`
  - itemid: `228189`
  - concept_id: `3005555`
  - raw label: `CO-Tandem Heart Flow`
  - stats: `row_count=46, value_range=[2.1, 10], median=3.22, units=L/min`

### mpap, Mean Pulmonal Arterial Pressure, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=392768, value_range=[-38, 3731], median=26, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220061`
  - concept_id: `3028074`
  - raw label: `Pulmonary Artery Pressure mean`
  - stats: `row_count=392768, value_range=[-38, 3731], median=26, units=mmHg`

### spap, Systolic Pulmonal Arterial Pressure, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=398701, value_range=[-15, 662], median=37, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220059`
  - concept_id: `3005606`
  - raw label: `Pulmonary Artery Pressure systolic`
  - stats: `row_count=398701, value_range=[-15, 662], median=37, units=mmHg`

### dpap, Diastolic Pulmonal Arterial Pressure, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=398801, value_range=[-33, 2834], median=19, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220060`
  - concept_id: `3017188`
  - raw label: `Pulmonary Artery Pressure diastolic`
  - stats: `row_count=398801, value_range=[-33, 2834], median=19, units=mmHg`

### cvp, Central Venous Pressure, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=993375, value_range=[-41, 7785], median=11, units=mmHg`
  - table: `chartevents_main`
  - itemid: `220074`
  - concept_id: `21490675`
  - raw label: `Central Venous Pressure`
  - stats: `row_count=993375, value_range=[-41, 7785], median=11, units=mmHg`

### svo2, Mixed Venous Oxygenation, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=224779, value_range=[0, 5952], median=65, units=%`
  - table: `chartevents_main`
  - itemid: `223772`
  - concept_id: `3018465`
  - raw label: `SvO2`
  - stats: `row_count=224779, value_range=[0, 5952], median=65, units=%`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=48310, value_range=[0, 999999], median=63, units=%`
  - table: `chartevents_main`
  - itemid: `225674`
  - concept_id: `3018465`
  - raw label: `Mixed Venous O2% Sat`
  - stats: `row_count=48310, value_range=[0, 999999], median=63, units=%`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=2428, value_range=[0, 97], median=76, units=%`
  - table: `chartevents_main`
  - itemid: `227549`
  - concept_id: `3018465`
  - raw label: `ScvO2 (Presep)`
  - stats: `row_count=2428, value_range=[0, 97], median=76, units=%`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=233`
  - table: `chartevents_main`
  - itemid: `227806`
  - concept_id: `3018465`
  - raw label: `ScvO2 (Presep) SQI`
  - stats: `row_count=233`

### pcwp, Pulmonary Capillary Wedge Pressure, observation, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `mmHg`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=8827, value_range=[0, 79], median=20, units=mmHg`
  - table: `chartevents_main`
  - itemid: `223771`
  - concept_id: `21490776`
  - raw label: `PCWP`
  - stats: `row_count=8827, value_range=[0, 79], median=20, units=mmHg`

### peep, Positive End Expiratory Pressure - Mechanical Ventilation, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `cmH2O`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=258629, value_range=[-24, 1.20286e+06], median=8, units=cmH2O`
  - table: `chartevents_main`
  - itemid: `224700`
  - concept_id: `42527140`
  - raw label: `Total PEEP Level`
  - stats: `row_count=258629, value_range=[-24, 1.20286e+06], median=8, units=cmH2O`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=860161, value_range=[-5, 8.77458e+06], median=5, units=cmH2O`
  - table: `chartevents_main`
  - itemid: `220339`
  - concept_id: `3022875`
  - raw label: `PEEP set`
  - stats: `row_count=860161, value_range=[-5, 8.77458e+06], median=5, units=cmH2O`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=69302, value_range=[0, 528], median=8`
  - table: `labs`
  - itemid: `50819`
  - concept_id: `3022875`
  - raw label: `PEEP`
  - stats: `row_count=69302, value_range=[0, 528], median=8`

### peak, Peak Pressure - Mechanical Ventilation, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `cmH2O`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary peak inspiratory pressure itemid -- shared little text overlap with the generic "pressure" token, so hemodynamic pressure items (CVP/PA/arterial/BP) crowded it out of the automated candidate list; found by a direct d_items re-search on "peak insp"`
  - table: `chartevents`
  - itemid: `224695`
  - raw label: `Peak Insp. Pressure`

match 2:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated to ventilator peak pressure`
  - table: `chartevents`
  - itemid: `220074`
  - raw label: `Central Venous Pressure`

match 3:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220072`
  - raw label: `Central Venous Pressure Alarm - High`

match 4:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220073`
  - raw label: `Central Venous Pressure  Alarm - Low`

match 5:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220179`
  - raw label: `Non Invasive Blood Pressure systolic`

match 6:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220060`
  - raw label: `Pulmonary Artery Pressure diastolic`

match 7:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220059`
  - raw label: `Pulmonary Artery Pressure systolic`

match 8:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220061`
  - raw label: `Pulmonary Artery Pressure mean`

match 9:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220063`
  - raw label: `Pulmonary Artery Pressure Alarm - High`

match 10:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220066`
  - raw label: `Pulmonary Artery Pressure Alarm - Low`

match 11:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220052`
  - raw label: `Arterial Blood Pressure mean`

match 12:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220050`
  - raw label: `Arterial Blood Pressure systolic`

match 13:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220051`
  - raw label: `Arterial Blood Pressure diastolic`

match 14:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220056`
  - raw label: `Arterial Blood Pressure Alarm - Low`

match 15:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220058`
  - raw label: `Arterial Blood Pressure Alarm - High`

match 16:
  - decision: `reject`
  - decision reason: `0 rows; unrelated hemodynamic measurement anyway`
  - table: `chartevents`
  - itemid: `220069`
  - raw label: `Left Artrial Pressure`

### plateau, Plateau Pressure - Mechanical Ventilation, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `cmH2O`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary plateau pressure itemid, same reasoning as `peak` -- found by a direct d_items re-search on "plateau"`
  - table: `chartevents`
  - itemid: `224696`
  - raw label: `Plateau Pressure`

match 2:
  - decision: `reject`
  - decision reason: `intra-aortic balloon pump plateau pressure -- different device/context, not ventilator plateau pressure`
  - table: `chartevents`
  - itemid: `228866`
  - raw label: `Plateau Pressure (IABP)`

match 3:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220074`
  - raw label: `Central Venous Pressure`

match 4:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220072`
  - raw label: `Central Venous Pressure Alarm - High`

match 5:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220073`
  - raw label: `Central Venous Pressure  Alarm - Low`

match 6:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220179`
  - raw label: `Non Invasive Blood Pressure systolic`

match 7:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220060`
  - raw label: `Pulmonary Artery Pressure diastolic`

match 8:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220059`
  - raw label: `Pulmonary Artery Pressure systolic`

match 9:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220061`
  - raw label: `Pulmonary Artery Pressure mean`

match 10:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220063`
  - raw label: `Pulmonary Artery Pressure Alarm - High`

match 11:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220066`
  - raw label: `Pulmonary Artery Pressure Alarm - Low`

match 12:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220052`
  - raw label: `Arterial Blood Pressure mean`

match 13:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220050`
  - raw label: `Arterial Blood Pressure systolic`

match 14:
  - decision: `reject`
  - decision reason: `hemodynamic measurement, unrelated`
  - table: `chartevents`
  - itemid: `220051`
  - raw label: `Arterial Blood Pressure diastolic`

match 15:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220056`
  - raw label: `Arterial Blood Pressure Alarm - Low`

match 16:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220058`
  - raw label: `Arterial Blood Pressure Alarm - High`

### ps, Pressure Support - Mechanical Ventilation, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `cmH2O`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=412517, value_range=[-2, 52000], median=8, units=cmH2O`
  - table: `chartevents_main`
  - itemid: `224701`
  - concept_id: `3000461`
  - raw label: `PSV Level`
  - stats: `row_count=412517, value_range=[-2, 52000], median=8, units=cmH2O`

### tv, Tidal Volume, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `ml`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary observed tidal volume`
  - table: `chartevents`
  - itemid: `224685`
  - raw label: `Tidal Volume (observed)`
  - stats: `row_count=818760, value_range=[0, 709461], median=443, units=mL (extraction needs a plausibility bound)`

match 2:
  - decision: `keep`
  - decision reason: `ventilator setting rather than observed value, still informative secondary source`
  - table: `chartevents`
  - itemid: `224684`
  - raw label: `Tidal Volume (set)`
  - stats: `row_count=429326, value_range=[0, 6500], median=450, units=mL`

match 3:
  - decision: `keep`
  - decision reason: `spontaneous-breath component, secondary source`
  - table: `chartevents`
  - itemid: `224686`
  - raw label: `Tidal Volume (spontaneous)`
  - stats: `row_count=425528, value_range=[0, 820914], median=438, units=mL`

match 4:
  - decision: `reject`
  - decision reason: `catheter lumen priming volume, unrelated`
  - table: `chartevents`
  - itemid: `224406`
  - raw label: `VEN Lumen Volume`

match 5:
  - decision: `reject`
  - decision reason: `catheter lumen priming volume, unrelated`
  - table: `chartevents`
  - itemid: `224404`
  - raw label: `ART Lumen Volume`

match 6:
  - decision: `reject`
  - decision reason: `balloon-pump volume, unrelated`
  - table: `chartevents`
  - itemid: `225980`
  - raw label: `IABP Volume`

match 7:
  - decision: `reject`
  - decision reason: `derived RR x TV product, not TV itself`
  - table: `chartevents`
  - itemid: `224687`
  - raw label: `Minute Volume`
  - stats: `row_count=813922, units=L/min`

match 8:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220292`
  - raw label: `Minute Volume Alarm - Low`

match 9:
  - decision: `reject`
  - decision reason: `alarm setting, unrelated`
  - table: `chartevents`
  - itemid: `220293`
  - raw label: `Minute Volume Alarm - High`

match 10:
  - decision: `reject`
  - decision reason: `ET-tube cuff inflation volume, unrelated`
  - table: `chartevents`
  - itemid: `224680`
  - raw label: `Cuff Volume/units`

match 11:
  - decision: `reject`
  - decision reason: `ET-tube cuff inflation volume, unrelated`
  - table: `chartevents`
  - itemid: `224418`
  - raw label: `Cuff Volume (mL)`

match 12:
  - decision: `reject`
  - decision reason: `peritoneal dialysis fluid volume, unrelated`
  - table: `chartevents`
  - itemid: `225806`
  - raw label: `Volume In (PD)`

match 13:
  - decision: `reject`
  - decision reason: `peritoneal dialysis fluid volume, unrelated`
  - table: `chartevents`
  - itemid: `225807`
  - raw label: `Volume Out (PD)`

match 14:
  - decision: `reject`
  - decision reason: `nebulizer medication volume, unrelated`
  - table: `chartevents`
  - itemid: `224181`
  - raw label: `Small Volume Neb Drug #1`

match 15:
  - decision: `reject`
  - decision reason: `nebulizer medication dose, unrelated`
  - table: `chartevents`
  - itemid: `224178`
  - raw label: `Small Volume Neb Dose #2`

### airway, Type Of Airway Ventilation, observation, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `categorical`
- Target unit: `categorical`
- Match method: `omop_concept_match`
- Notes: `Revised 2026-07-29: itemid 223836 (match 0) is too sparse to safely forward-fill -- only 54641 rows / 3514 admissions (3.7% of stays). Verified via grid._check_airway_none_transitions.py that 70% of admissions with an invasive value (Oral/Nasotracheal/Nasal trumpet) never show a later transition to "None", meaning forward-fill would silently persist "intubated" through the rest of many stays -- the same category of risk AUMC found and fixed for its own airway feature on 2026-07-14. Replaced with itemid 226732 "O2 Delivery Device(s)" (2069683 rows, ~38x denser), collapsed into AUMC's exact 4-category schema (matches 25-43 below): Endotracheal tube, Tracheostomy, CPAP/NIV, No artificial airway (low-flow O2). T-piece and Trach mask are folded into Tracheostomy by clinical inference (both attach to an existing tube/stoma) rather than direct verification -- the one judgment call in the mapping.`

match 0 (added by hand):
  - decision: `reject`
  - decision reason: `superseded 2026-07-29 -- too sparse to safely forward-fill (see block Notes); replaced by itemid 226732, matches 25-43`
  - table: `chartevents`
  - itemid: `223836`
  - raw label: `Airway Type`
  - stats: `row_count=54641, categories: Oral=32738, None=21554, Nasal trumpet=317, Nasotracheal=32`

match 1:
  - decision: `reject`
  - decision reason: `WRONG -- this is GCS Verbal Response (belongs to `vgcs`), not airway type; cross-contaminated via a shared upstream concept_id`
  - table: `chartevents_main`
  - itemid: `223900`
  - concept_id: `3009094`
  - raw label: `GCS - Verbal Response`
  - stats: `row_count=2205121, value_range=[1, 5], median=4`

match 2:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2222`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, incomprehensible words, at arrival to emergency department`
  - stats: `row_count=35`

match 3:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2221`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, incomprehensible words, in the field [EMT or ambulance]`
  - stats: `row_count=1`

match 4:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2252`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, at arrival to emergency department`
  - stats: `row_count=573`

match 5:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2232`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, inappropriate words, at arrival to emergency department`
  - stats: `row_count=40`

match 6:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2241`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, in the field [EMT or ambulance]`
  - stats: `row_count=2`

match 7:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2223`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, incomprehensible words, at hospital admission`
  - stats: `row_count=10`

match 8:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2210`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, unspecified time`
  - stats: `row_count=5`

match 9:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2213`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, at hospital admission`
  - stats: `row_count=105`

match 10:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2224`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, incomprehensible words, 24 hours or more after hospital admission`
  - stats: `row_count=3`

match 11:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2234`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, inappropriate words, 24 hours or more after hospital admission`
  - stats: `row_count=1`

match 12:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2242`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, at arrival to emergency department`
  - stats: `row_count=218`

match 13:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2251`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, in the field [EMT or ambulance]`
  - stats: `row_count=14`

match 14:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2214`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, 24 hours or more after hospital admission`
  - stats: `row_count=19`

match 15:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2244`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, 24 hours or more after hospital admission`
  - stats: `row_count=7`

match 16:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2243`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, at hospital admission`
  - stats: `row_count=68`

match 17:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2233`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, inappropriate words, at hospital admission`
  - stats: `row_count=10`

match 18:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2211`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, in the field [EMT or ambulance]`
  - stats: `row_count=8`

match 19:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2254`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, 24 hours or more after hospital admission`
  - stats: `row_count=14`

match 20:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2240`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, confused conversation, unspecified time`
  - stats: `row_count=2`

match 21:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2212`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, none, at arrival to emergency department`
  - stats: `row_count=327`

match 22:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2250`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, unspecified time`
  - stats: `row_count=9`

match 23:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `diagnoses`
  - itemid: `R40.2253`
  - concept_id: `3009094`
  - raw label: `Coma scale, best verbal response, oriented, at hospital admission`
  - stats: `row_count=172`

match 24:
  - decision: `reject`
  - decision reason: `WRONG TYPE -- ETT Size (ID) is a device size number, not an airway-type category; real airway-type source is itemid 226732 (matches 25-43)`
  - table: `chartevents_main`
  - itemid: `223837`
  - concept_id: `21491186`
  - raw label: `ETT Size (ID)`
  - stats: `row_count=622476`

match 25:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Endotracheal tube`
  - standardized label: `Endotracheal tube`
  - stats: `row_count=633302`

match 26:
  - decision: `keep`
  - decision reason: `merged into the 'Tracheostomy' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Tracheostomy tube`
  - standardized label: `Tracheostomy`
  - stats: `row_count=127611`

match 27:
  - decision: `keep`
  - decision reason: `merged into the 'Tracheostomy' category -- a mask fitted over an existing tracheostomy stoma implies the stoma/tube is still present, mirrors AUMC's inclusion of speaking-valve/cannula accessory documentation under the same category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Trach mask`
  - standardized label: `Tracheostomy`
  - stats: `row_count=66480`

match 28:
  - decision: `keep`
  - decision reason: `merged into the 'Tracheostomy' category -- T-piece is a weaning-trial circuit attached to an existing ET/trach tube, not a distinct airway; classified as Tracheostomy since T-piece trials are predominantly used for tracheostomy weaning in MIMIC-IV ICUs -- inferred from clinical usage, not directly verified in this dataset`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `T-piece`
  - standardized label: `Tracheostomy`
  - stats: `row_count=10432`

match 29:
  - decision: `keep`
  - decision reason: `merged into the 'CPAP/NIV' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Bipap mask`
  - standardized label: `CPAP/NIV`
  - stats: `row_count=25845`

match 30:
  - decision: `keep`
  - decision reason: `merged into the 'CPAP/NIV' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `CPAP mask`
  - standardized label: `CPAP/NIV`
  - stats: `row_count=10787`

match 31:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `None`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=398249`

match 32:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Nasal cannula`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=530952`

match 33:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Aerosol-cool`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=79148`

match 34:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Face tent`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=70771`

match 35:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `High flow nasal cannula`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=48003`

match 36:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `High flow neb`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=18878`

match 37:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Oxymizer`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=17495`

match 38:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Non-rebreather`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=14250`

match 39:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Venti mask`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=6719`

match 40:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Other`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=5376`

match 41:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Medium conc mask`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=5330`

match 42:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Ultrasonic neb`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=34`

match 43:
  - decision: `keep`
  - decision reason: `merged into the 'No artificial airway (low-flow O2)' category`
  - table: `chartevents`
  - itemid: `226732`
  - raw label: `O2 Delivery Device(s)`
  - raw value: `Vapomist`
  - standardized label: `No artificial airway (low-flow O2)`
  - stats: `row_count=21`

### supp_o2_vent, Supplemental Oxygen From Ventilator, treatment, respiratory
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `%`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

NOTE: no clean single MIMIC itemid represents "supplemental O2 delivered via ventilator" directly -- same ambiguity likely existed in AUMC's own construction of this feature. A derived definition (FiO2 gated by ventilator-mode indicating active ventilation) was considered but not built -- out of scope for a manifest-level fix; revisit as a dedicated derived feature (see grid/derive_targets.py) if this concept turns out to matter downstream.

match 1:
  - decision: `reject`
  - decision reason: `CONFIRMED WRONG, 2026-07-31 distribution-diff audit -- this was kept as a "best available proxy" despite the raw itemid being categorical, not numeric: itemid 223848 is "Ventilator Type" (d_items.csv.gz param_type=Text), and its real values (verified via mimic_grid_candidate_stats.csv and the extracted grid) are the small integer codes {1,2,5,6,7}, not an O2 percentage. Casting these codes to float and treating them as target_unit=% produced a top-ranked (PSI=4.03) spurious AUMC-vs-M4 divergence (AUMC's real O2-concentration median 39% vs M4's code-median 1). Rejected outright rather than kept as a wrong-but-plausible-looking proxy; no numeric MIMIC substitute was found (see NOTE above) so this tag now has 0 keep matches and correctly falls out of scope.`
  - table: `chartevents`
  - itemid: `223848`
  - raw label: `Ventilator Type`
  - stats: `row_count=778405, value_range=[1, 7], median=1`

match 2:
  - decision: `reject`
  - decision reason: `wrong domain -- ECMO circuit, not ventilator supplemental O2`
  - table: `chartevents`
  - itemid: `228193`
  - raw label: `Oxygenator/ECMO`

match 3:
  - decision: `reject`
  - decision reason: `wrong domain -- ECMO circuit gas sweep rate`
  - table: `chartevents`
  - itemid: `228192`
  - raw label: `Oxygenator Sweep Rate`

match 4:
  - decision: `reject`
  - decision reason: `wrong domain -- ECMO circuit check`
  - table: `chartevents`
  - itemid: `229274`
  - raw label: `Oxygenator visible (ECMO)`

match 5:
  - decision: `reject`
  - decision reason: `physical O2 tank volume remaining, not delivered fraction`
  - table: `chartevents`
  - itemid: `227565`
  - raw label: `Ventilator Tank #1`

match 6:
  - decision: `reject`
  - decision reason: `physical O2 tank volume remaining, not delivered fraction`
  - table: `chartevents`
  - itemid: `227566`
  - raw label: `Ventilator Tank #2`

match 7:
  - decision: `reject`
  - decision reason: `derived severity-score input`
  - table: `chartevents`
  - itemid: `227035`
  - raw label: `OxygenScore_ApacheIV`

match 8:
  - decision: `reject`
  - decision reason: `derived severity-score input`
  - table: `chartevents`
  - itemid: `226767`
  - raw label: `OxygenApacheIIScore`

match 9:
  - decision: `reject`
  - decision reason: `unrelated administrative field`
  - table: `chartevents`
  - itemid: `228689`
  - raw label: `Discharge from ICU`

match 10:
  - decision: `reject`
  - decision reason: `unrelated administrative field`
  - table: `chartevents`
  - itemid: `227088`
  - raw label: `Admit from`

match 11:
  - decision: `reject`
  - decision reason: `one-time pre-intubation procedural flag, not continuous supplemental O2`
  - table: `chartevents`
  - itemid: `225302`
  - raw label: `Pre-Oxygentated (Intubation)`

match 12:
  - decision: `reject`
  - decision reason: `invasive brain-tissue O2 monitor, different measurement entirely`
  - table: `chartevents`
  - itemid: `229235`
  - raw label: `Brain Tissue Oxygenation`

match 13:
  - decision: `reject`
  - decision reason: `unrelated (PACU/PAR recovery-room oxygen saturation check)`
  - table: `chartevents`
  - itemid: `228232`
  - raw label: `PAR-Oxygen saturation`

match 14:
  - decision: `reject`
  - decision reason: `unrelated, false hit`
  - table: `chartevents`
  - itemid: `227957`
  - raw label: `Signs of Injury from Intervention`

### ygt, Gamma GT, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `U/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=20860, value_range=[1, 7380], median=63, units=IU/L`
  - table: `labs`
  - itemid: `50927`
  - concept_id: `3026910`
  - raw label: `Gamma Glutamyltransferase`
  - stats: `row_count=20860, value_range=[1, 7380], median=63, units=IU/L`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=69, value_range=[5, 496], median=22, units=IU/L`
  - table: `labs`
  - itemid: `53093`
  - concept_id: `3026910`
  - raw label: `Gamma Glutamyltranferase`
  - stats: `row_count=69, value_range=[5, 496], median=22, units=IU/L`

### amm, Ammonia, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `umol/L`
- Match method: `analyte_level_match`
- Notes: `Revised 2026-07-29: verified clean during the full 21-tag NEEDS MANUAL REVIEW sweep -- all keep-match itemids confirmed correct specimen/units via d_labitems.csv.gz / d_items.csv.gz (no contamination found for this tag; unrelated tags in the same sweep had real urine-specimen and dead-itemid bugs, see crea/glu/bili/wbc/rbc).`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=8364, value_range=[0, 874], median=44, units=umol/L`
  - table: `labs`
  - itemid: `50866`
  - concept_id: `3011958`
  - raw label: `Ammonia`
  - stats: `row_count=8364, value_range=[0, 874], median=44, units=umol/L`

### amyl, Amylase, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `U/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=96286, value_range=[0, 42966], median=64, units=IU/L`
  - table: `labs`
  - itemid: `50867`
  - concept_id: `3016771`
  - raw label: `Amylase`
  - stats: `row_count=96286, value_range=[0, 42966], median=64, units=IU/L`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=69, value_range=[13, 160], median=48, units=IU/L`
  - table: `labs`
  - itemid: `53087`
  - concept_id: `3016771`
  - raw label: `Amylase`
  - stats: `row_count=69, value_range=[13, 160], median=48, units=IU/L`

### lip, Lipase, observation, gastrointestinal
- Mapping status: `source_candidates_found`
- Reconstruction type: `direct_numeric`
- Target unit: `U/L`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=293247, value_range=[0, 93000], median=33, units=IU/L`
  - table: `labs`
  - itemid: `50956`
  - concept_id: `3004905`
  - raw label: `Lipase`
  - stats: `row_count=293247, value_range=[0, 93000], median=33, units=IU/L`

### ufilt, Ultrafiltration On Continuous RRT, treatment, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `ml`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `the actual ultrafiltration volume-removed measurement -- missed by the keyword search (no lexical overlap with "ultrafiltration"); found by a direct d_items re-search on "ultrafilt".`
  - table: `chartevents`
  - itemid: `226457`
  - raw label: `Ultrafiltrate Output`
  - stats: `row_count=365849, value_range=[-600, 16800], units=mL`

match 2:
  - decision: `reject`
  - decision reason: `not a numeric value -- this is the CRRT session interval (correct for `ufilt_ind`, the indicator tag, but ufilt needs a numeric rate/volume)`
  - table: `procedureevents`
  - itemid: `225802`
  - raw label: `Dialysis - CRRT`
  - stats: `row_count=5399, units=hour|min|day`

match 3:
  - decision: `reject`
  - decision reason: `not a numeric value -- "CRRT mode" is a categorical string (correct as a supplementary indicator for `ufilt_ind`, not usable as a rate)`
  - table: `chartevents`
  - itemid: `227290`
  - raw label: `CRRT mode`
  - stats: `row_count=203035`

match 4:
  - decision: `reject`
  - decision reason: `CRRT circuit medication infusion, not the UF volume/indicator itself`
  - table: `inputevents`
  - itemid: `227525`
  - raw label: `Calcium Gluconate (CRRT)`

match 5:
  - decision: `reject`
  - decision reason: `CRRT circuit medication infusion, not the UF volume/indicator itself`
  - table: `inputevents`
  - itemid: `227536`
  - raw label: `KCl (CRRT)`

match 6:
  - decision: `reject`
  - decision reason: `CRRT circuit anticoagulant infusion, not the UF volume/indicator itself`
  - table: `inputevents`
  - itemid: `230044`
  - raw label: `Heparin Sodium (CRRT-Prefilter)`

match 7:
  - decision: `reject`
  - decision reason: `status/metadata field, not the treatment volume/occurrence`
  - table: `chartevents`
  - itemid: `224091`
  - raw label: `Continuous Pressure Machine Status`

match 8:
  - decision: `reject`
  - decision reason: `metadata field, not the treatment volume/occurrence`
  - table: `chartevents`
  - itemid: `225956`
  - raw label: `Reason for CRRT Filter Change`

match 9:
  - decision: `reject`
  - decision reason: `redundant with the Dialysis-CRRT session indicator`
  - table: `procedureevents`
  - itemid: `225436`
  - raw label: `CRRT Filter Change`

match 10:
  - decision: `reject`
  - decision reason: `metadata field, not the treatment volume/occurrence`
  - table: `chartevents`
  - itemid: `230177`
  - raw label: `CRRT - Filter Type`

match 11:
  - decision: `reject`
  - decision reason: `unrelated, false hit on "Continuous"`
  - table: `procedureevents`
  - itemid: `229614`
  - raw label: `EEG (Continuous)`

### ufilt_ind, Ultrafiltration On Continuous RRT Indicator, treatment, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `the actual ultrafiltration volume-removed measurement -- missed by the keyword search (no lexical overlap with "ultrafiltration"); found by a direct d_items re-search on "ultrafilt".`
  - table: `chartevents`
  - itemid: `226457`
  - raw label: `Ultrafiltrate Output`
  - stats: `row_count=365849, value_range=[-600, 16800], units=mL`

match 2:
  - decision: `keep`
  - decision reason: `CRRT session indicator, supports ufilt_ind`
  - table: `procedureevents`
  - itemid: `225802`
  - raw label: `Dialysis - CRRT`
  - stats: `row_count=5399, units=hour|min|day`

match 3:
  - decision: `keep`
  - decision reason: `supplementary indicator signal confirming CRRT active`
  - table: `chartevents`
  - itemid: `227290`
  - raw label: `CRRT mode`
  - stats: `row_count=203035`

match 4:
  - decision: `reject`
  - decision reason: `CRRT circuit medication infusion, not the UF volume/indicator itself`
  - table: `inputevents`
  - itemid: `227525`
  - raw label: `Calcium Gluconate (CRRT)`

match 5:
  - decision: `reject`
  - decision reason: `CRRT circuit medication infusion, not the UF volume/indicator itself`
  - table: `inputevents`
  - itemid: `227536`
  - raw label: `KCl (CRRT)`

match 6:
  - decision: `reject`
  - decision reason: `CRRT circuit anticoagulant infusion, not the UF volume/indicator itself`
  - table: `inputevents`
  - itemid: `230044`
  - raw label: `Heparin Sodium (CRRT-Prefilter)`

match 7:
  - decision: `reject`
  - decision reason: `status/metadata field, not the treatment volume/occurrence`
  - table: `chartevents`
  - itemid: `224091`
  - raw label: `Continuous Pressure Machine Status`

match 8:
  - decision: `reject`
  - decision reason: `metadata field, not the treatment volume/occurrence`
  - table: `chartevents`
  - itemid: `225956`
  - raw label: `Reason for CRRT Filter Change`

match 9:
  - decision: `reject`
  - decision reason: `redundant with the Dialysis-CRRT session indicator`
  - table: `procedureevents`
  - itemid: `225436`
  - raw label: `CRRT Filter Change`

match 10:
  - decision: `reject`
  - decision reason: `metadata field, not the treatment volume/occurrence`
  - table: `chartevents`
  - itemid: `230177`
  - raw label: `CRRT - Filter Type`

match 11:
  - decision: `reject`
  - decision reason: `unrelated, false hit on "Continuous"`
  - table: `procedureevents`
  - itemid: `229614`
  - raw label: `EEG (Continuous)`

### dobu, Dobutamine, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mcg/min`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=10264, value_range=[0.0800238, 135.87], median=5, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `221653`
  - concept_id: `1337720`
  - raw label: `Dobutamine`
  - stats: `row_count=10264, value_range=[0.0800238, 135.87], median=5, units=mcg/kg/min`

match 2 (bulk, 8 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 4192.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 8): `409234488|2717510|55390056090|338107302|74234632|409234402|409234632|409202520`

### levo, Levosimendan, treatment, circulatory
- Mapping status: `no_source_candidates`
- Reconstruction type: `treatment_rate`
- Target unit: `mcg/min`
- Match method: `none`
- Notes: `Genuine dataset-availability gap, not a matching failure -- levosimendan is not FDA-approved and is not used in US ICU practice (MIMIC-IV's source hospital included); confirmed absent via a direct grep of icu/d_items.csv.gz (no hit). AUMCdb itself also shows no_source_candidates for this tag despite Levosimendan being a real AmsterdamUMCdb-era drug, per that manifest's own notes ("Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals"). The closest functional analogs used in US practice (milrinone, dobutamine) are already separate target features (milrin/milrin_ind, dobu/dobu_ind) in this same 129-feature list, not substitutes for this tag.`

### norepi, Norepinephrine, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mcg/min`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=459800, value_range=[0.000200003, 359.551], median=0.100029, units=mcg/kg/min|mg/kg/min`
  - table: `inputevents`
  - itemid: `221906`
  - concept_id: `1321341`
  - raw label: `Norepinephrine`
  - stats: `row_count=459800, value_range=[0.000200003, 359.551], median=0.100029, units=mcg/kg/min|mg/kg/min`

match 2 (bulk, 11 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 22675.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 11): `61553015311|781375595|703115303|781893285|247120004|409144304|67457085204|61553015361|74704101|61553012011`

### epi, Epinephrine, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mcg/min`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=31495, value_range=[0.000801155, 41.1429], median=0.0500064, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `221289`
  - concept_id: `1343916`
  - raw label: `Epinephrine`
  - stats: `row_count=31495, value_range=[0.000801155, 41.1429], median=0.0500064, units=mcg/kg/min`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=234`
  - table: `inputevents`
  - itemid: `229617`
  - concept_id: `1343916`
  - raw label: `Epinephrine.`
  - stats: `row_count=234`

match 3 (bulk, 35 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 15036.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 35): `409904502|409317801|49502050002|42023015925|409904517|63323048157|409492134|409317802|76329331601|409904202`

### milrin, Milrinone, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mcg/min`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `clean, single, unambiguous match`
  - table: `inputevents`
  - itemid: `221986`
  - raw label: `Milrinone`
  - stats: `row_count=10668, value_range=[0.0125, 121.7], median=0.33, units=mcg/kg/min`

### teophyllin, Theophylline, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mg/min`
- Match method: `omop_concept_match`

match 1 (bulk, 9 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 762.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 9): `68462038001|62332002531|17236032410|67781025101|42858070101|49708064490|456064416|50111048303|904588861`

### dopa, Dopamine, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mcg/min`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=18085, value_range=[0.200002, 4000], median=5.02021, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `221662`
  - concept_id: `1337860`
  - raw label: `Dopamine`
  - stats: `row_count=18085, value_range=[0.200002, 4000], median=5.02021, units=mcg/kg/min`

match 2 (bulk, 4 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 3824.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 4): `409780922|338100702|409910420|517180525`

### adh, Vasopressin, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `U/min`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `clean, single, unambiguous match`
  - table: `inputevents`
  - itemid: `222315`
  - raw label: `Vasopressin`
  - stats: `row_count=37163, value_range=[0.017, 2400], median=2.4, units=units/min|units/hour`

### hep, Heparin, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `U/h`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=157876`
  - table: `inputevents`
  - itemid: `225975`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium (Prophylaxis)`
  - stats: `row_count=157876`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=98795, value_range=[0.08, 1.5e+06], median=1242.14, units=units/hour|units/kg/hour`
  - table: `inputevents`
  - itemid: `225152`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium`
  - stats: `row_count=98795, value_range=[0.08, 1.5e+06], median=1242.14, units=units/hour|units/kg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1796, value_range=[5, 300000], median=550, units=units/min|units/hour`
  - table: `inputevents`
  - itemid: `229597`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium (Impella)`
  - stats: `row_count=1796, value_range=[5, 300000], median=550, units=units/min|units/hour`

match 4 (bulk, 38 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 712538.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 38): `63323054031|67457038599|8290306513|338055002|63323054201|8290306510|8290306424|61553094102|8290306525|64253033335`

### prop, Propofol, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mcg/min`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=498811, value_range=[-71.6637, 135794], median=32.1422, units=mcg/kg/min|mg/hour`
  - table: `inputevents`
  - itemid: `222168`
  - concept_id: `753626`
  - raw label: `Propofol`
  - stats: `row_count=498811, value_range=[-71.6637, 135794], median=32.1422, units=mcg/kg/min|mg/hour`

match 2 (bulk, 9 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 67496.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 9): `310030022|63323026929|63323027057|63323029766|63323026920|310030011|63323026965|409469930|63323029730`

### benzdia, Benzodiazepine, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mg/h`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=126814, value_range=[0.02, 3370.98], median=3.00461, units=mg/hour`
  - table: `inputevents`
  - itemid: `221668`
  - concept_id: `708298`
  - raw label: `Midazolam (Versed)`
  - stats: `row_count=126814, value_range=[0.02, 3370.98], median=3.00461, units=mg/hour`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4767`
  - table: `inputevents`
  - itemid: `221623`
  - concept_id: `723013`
  - raw label: `Diazepam (Valium)`
  - stats: `row_count=4767`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=42268, value_range=[0.12959, 9.61782], median=2.50251, units=mg/hour`
  - table: `inputevents`
  - itemid: `221385`
  - concept_id: `791967`
  - raw label: `Lorazepam (Ativan)`
  - stats: `row_count=42268, value_range=[0.12959, 9.61782], median=2.50251, units=mg/hour`

match 4 (bulk, 48 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 332640.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 48): `10019002803|70860060110|641605725|10019002804|409259605|44567061101|409230517|10019002703|61553019648|10019002710`

### sed, Other Sedatives, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=126814, value_range=[0.02, 3370.98], median=3.00461, units=mg/hour`
  - table: `inputevents`
  - itemid: `221668`
  - concept_id: `708298`
  - raw label: `Midazolam (Versed)`
  - stats: `row_count=126814, value_range=[0.02, 3370.98], median=3.00461, units=mg/hour`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=498811, value_range=[-71.6637, 135794], median=32.1422, units=mcg/kg/min|mg/hour`
  - table: `inputevents`
  - itemid: `222168`
  - concept_id: `753626`
  - raw label: `Propofol`
  - stats: `row_count=498811, value_range=[-71.6637, 135794], median=32.1422, units=mcg/kg/min|mg/hour`

match 3 (bulk, 23 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 94798.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 23): `10019002803|70860060110|641605725|10019002804|409259605|44567061101|409230517|10019002703|61553019648|10019002710`

### op_pain, Opiate Painkiller, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=80659, value_range=[0.300015, 1604.59], median=5, units=mg/hour`
  - table: `inputevents`
  - itemid: `225154`
  - concept_id: `1110410`
  - raw label: `Morphine Sulfate`
  - stats: `row_count=80659, value_range=[0.300015, 1604.59], median=5, units=mg/hour`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=236221, value_range=[0, 150000], median=100, units=mcg/hour`
  - table: `inputevents`
  - itemid: `221744`
  - concept_id: `1154029`
  - raw label: `Fentanyl`
  - stats: `row_count=236221, value_range=[0, 150000], median=100, units=mcg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=138861, value_range=[0, 150000], median=100, units=mcg/kg/hour|mcg/hour`
  - table: `inputevents`
  - itemid: `225942`
  - concept_id: `1154029`
  - raw label: `Fentanyl (Concentrate)`
  - stats: `row_count=138861, value_range=[0, 150000], median=100, units=mcg/kg/hour|mcg/hour`

match 4 (bulk, 144 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 669800.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 144): `59011010020|406055201|68084035401|904682894|59011041020|904644561|406051262|66689040150|527142636|54864816`

### nonop_pain, Non-Opioid Analgesic, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=78379, value_range=[1.81818, 4000], median=66.6667, units=mg/min|mg/hour`
  - table: `inputevents`
  - itemid: `228315`
  - concept_id: `1125315`
  - raw label: `Acetaminophen-IV`
  - stats: `row_count=78379, value_range=[1.81818, 4000], median=66.6667, units=mg/min|mg/hour`

match 2 (bulk, 72 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 844494.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 72): `63739067210|62584074601|67877031901|63739068410|50580060150|904585361|68094050361|182181089|68084070301|904585461`

### paral, Paralytic, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4624, value_range=[0.504268, 983.685], median=8.02821, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `229233`
  - concept_id: `19003953`
  - raw label: `Rocuronium`
  - stats: `row_count=4624, value_range=[0.504268, 983.685], median=8.02821, units=mcg/kg/min`

match 2 (bulk, 17 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 4325.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 17): `409662902|781341195|61553035770|67457022810|409955810|63323042610|63323042605|47781061791|55150022610|52045015`

### abx, Antibiotics, treatment, infection
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=140000`
  - table: `inputevents`
  - itemid: `225798`
  - concept_id: `1707687`
  - raw label: `Vancomycin`
  - stats: `row_count=140000`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=11537`
  - table: `inputevents`
  - itemid: `225837`
  - concept_id: `1703687`
  - raw label: `Acyclovir`
  - stats: `row_count=11537`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=18474`
  - table: `inputevents`
  - itemid: `225859`
  - concept_id: `1797513`
  - raw label: `Ciprofloxacin`
  - stats: `row_count=18474`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1682`
  - table: `inputevents`
  - itemid: `225876`
  - concept_id: `1797258`
  - raw label: `Imipenem/Cilastatin`
  - stats: `row_count=1682`

match 5:
  - decision: `reject`
  - decision reason: `one-time billing/ICD code, not a repeated measurement -- informational only`
  - table: `procedures_icd`
  - itemid: `XW033U5`
  - concept_id: `1797258`
  - raw label: `Introduction of Imipenem-cilastatin-relebactam Anti-infective into Peripheral Vein, Percutaneous Approach, New Technology Group 5`
  - stats: `row_count=1`

match 6:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4964`
  - table: `inputevents`
  - itemid: `225899`
  - concept_id: `1705674`
  - raw label: `Bactrim (SMX/TMP)`
  - stats: `row_count=4964`

match 7:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=22154`
  - table: `inputevents`
  - itemid: `225855`
  - concept_id: `1777806`
  - raw label: `Ceftriaxone`
  - stats: `row_count=22154`

match 8:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=65614`
  - table: `inputevents`
  - itemid: `225884`
  - concept_id: `1707164`
  - raw label: `Metronidazole`
  - stats: `row_count=65614`

match 9:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=45552`
  - table: `inputevents`
  - itemid: `225850`
  - concept_id: `1771162`
  - raw label: `Cefazolin`
  - stats: `row_count=45552`

match 10:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=965`
  - table: `inputevents`
  - itemid: `225866`
  - concept_id: `1746940`
  - raw label: `Erythromycin`
  - stats: `row_count=965`

match 11 (bulk, 183 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 630508.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 183): `64679098601|67457034210|338358048|409651049|65628020810|409651001|70860010520|409433201|23360015250|70860010410`

### loop_diur, Loop Diuretic, treatment, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_rate`
- Target unit: `mg/h`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4086, value_range=[0.2, 12.0968], median=2.02703, units=mg/hour`
  - table: `inputevents`
  - itemid: `229639`
  - concept_id: `932745`
  - raw label: `Bumetanide (Bumex)`
  - stats: `row_count=4086, value_range=[0.2, 12.0968], median=2.02703, units=mg/hour`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=117125, value_range=[0.05, 3000], median=5.08932, units=mg/hour`
  - table: `inputevents`
  - itemid: `221794`
  - concept_id: `956874`
  - raw label: `Furosemide (Lasix)`
  - stats: `row_count=117125, value_range=[0.05, 3000], median=5.08932, units=mg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=24590, value_range=[0.499951, 14100], median=14.9901, units=mg/hour`
  - table: `inputevents`
  - itemid: `228340`
  - concept_id: `956874`
  - raw label: `Furosemide (Lasix) 250/50`
  - stats: `row_count=24590, value_range=[0.499951, 14100], median=14.9901, units=mg/hour`

match 4 (bulk, 43 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 458692.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 43): `185012801|74141204|69238148901|50268013015|185013001|409141210|641600810|69238149101|51079089101|55390050002`

### ins_ind, Insulin, treatment, not specified
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=337446, value_range=[0.0001, 3013.04], median=4, units=units/hour`
  - table: `inputevents`
  - itemid: `223258`
  - concept_id: `1596977`
  - raw label: `Insulin - Regular`
  - stats: `row_count=337446, value_range=[0.0001, 3013.04], median=4, units=units/hour`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=864`
  - table: `inputevents`
  - itemid: `223257`
  - concept_id: `1596977`
  - raw label: `Insulin - 70/30`
  - stats: `row_count=864`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=25`
  - table: `inputevents`
  - itemid: `229619`
  - concept_id: `1596977`
  - raw label: `Insulin - U500`
  - stats: `row_count=25`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1241`
  - table: `inputevents`
  - itemid: `229299`
  - concept_id: `1567198`
  - raw label: `Insulin - Novolog`
  - stats: `row_count=1241`

match 5:
  - decision: `keep`
  - decision reason: `CONFIRMED MISSING, 2026-07-31 distribution-diff audit -- d_items.csv.gz lists 8 real inputevents insulin itemids, only 4 were in this manifest; this and matches 6-8 add the other 4. This one alone (Glargine, a once-daily basal insulin) is a very common ICU order and its omission plausibly explains much of the AUMC-vs-M4 ins_ind prevalence gap found by the audit (59.5% vs 6.3%, PSI=1.64, rank 8). row_count=37251, verified via scripts_review/compute_missing_insulin_stats.py (rate is null for all 4 new itemids -- these are charted as bolus/discrete doses, not continuous infusions, same as matches 2-4 above; irrelevant for a treatment_indicator, which only needs event presence, not a rate value).`
  - table: `inputevents`
  - itemid: `223260`
  - concept_id: `1596977`
  - raw label: `Insulin - Glargine`
  - stats: `row_count=37251`

match 6:
  - decision: `keep`
  - decision reason: `CONFIRMED MISSING, 2026-07-31 distribution-diff audit -- see match 5. Humalog is a common rapid-acting correction/mealtime insulin; row_count=97298 is larger than 3 of the 4 itemids already in this manifest, so this was a substantial coverage gap.`
  - table: `inputevents`
  - itemid: `223262`
  - concept_id: `1596977`
  - raw label: `Insulin - Humalog`
  - stats: `row_count=97298`

match 7:
  - decision: `keep`
  - decision reason: `CONFIRMED MISSING, 2026-07-31 distribution-diff audit -- see match 5.`
  - table: `inputevents`
  - itemid: `223259`
  - concept_id: `1596977`
  - raw label: `Insulin - NPH`
  - stats: `row_count=10718`

match 8:
  - decision: `keep`
  - decision reason: `CONFIRMED MISSING, 2026-07-31 distribution-diff audit -- see match 5. Smallest of the 4 (row_count=364), included anyway for completeness since it's a real inputevents insulin itemid.`
  - table: `inputevents`
  - itemid: `223261`
  - concept_id: `1596977`
  - raw label: `Insulin - Humalog 75/25`
  - stats: `row_count=364`

match 9 (bulk, 10 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 158519.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 10): `338012612|2871501|2850101|2821501|169183311|2821517|2871517|169750111|169368512|169320111`

### fluid, Fluid Administration, treatment, not specified
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

NOTE: none of the originally keyword-matched candidates represent general IV fluid administration -- the real source needed a fresh category-based search (inputevents ordercategoryname="Fluids/Intake") rather than a name-keyword match. Row counts for the kept candidates above haven't been queried against the raw table yet (found via a direct d_items category search, outside the original candidate-generation pipeline) -- flagged for a follow-up stats pass before finalizing.

match 1:
  - decision: `keep`
  - decision reason: `IV fluid administration -- part of the real "Fluids/Intake" set`
  - table: `inputevents`
  - itemid: `225158`
  - raw label: `NaCl 0.9%`

match 2:
  - decision: `keep`
  - decision reason: `IV fluid administration`
  - table: `inputevents`
  - itemid: `225159`
  - raw label: `NaCl 0.45%`

match 3:
  - decision: `keep`
  - decision reason: `IV fluid administration (Lactated Ringer's)`
  - table: `inputevents`
  - itemid: `225828`
  - raw label: `LR`

match 4:
  - decision: `keep`
  - decision reason: `IV fluid administration`
  - table: `inputevents`
  - itemid: `220949`
  - raw label: `Dextrose 5%`

match 5:
  - decision: `keep`
  - decision reason: `IV fluid administration`
  - table: `inputevents`
  - itemid: `220950`
  - raw label: `Dextrose 10%`

match 6:
  - decision: `keep`
  - decision reason: `IV fluid administration`
  - table: `inputevents`
  - itemid: `220952`
  - raw label: `Dextrose 50%`

match 7:
  - decision: `keep`
  - decision reason: `IV fluid administration`
  - table: `inputevents`
  - itemid: `225827`
  - raw label: `D5LR`

match 8:
  - decision: `keep`
  - decision reason: `IV fluid administration`
  - table: `inputevents`
  - itemid: `225823`
  - raw label: `D5 1/2NS`

match 9:
  - decision: `keep`
  - decision reason: `IV fluid administration`
  - table: `inputevents`
  - itemid: `225941`
  - raw label: `D5 1/4NS`

match 10:
  - decision: `keep`
  - decision reason: `IV fluid administration`
  - table: `inputevents`
  - itemid: `225797`
  - raw label: `Free Water`

match 11:
  - decision: `reject`
  - decision reason: `procedural fluid REMOVAL during lumbar puncture, not administration`
  - table: `chartevents`
  - itemid: `224498`
  - raw label: `Amount of fluid removed (LP)`

match 12:
  - decision: `reject`
  - decision reason: `procedural fluid removal, not administration`
  - table: `chartevents`
  - itemid: `224499`
  - raw label: `Fluid removed (LP)`

match 13:
  - decision: `reject`
  - decision reason: `procedural fluid removal, not administration`
  - table: `chartevents`
  - itemid: `225246`
  - raw label: `Fluid Removed (THCEN)`

match 14:
  - decision: `reject`
  - decision reason: `procedural fluid removal, not administration`
  - table: `chartevents`
  - itemid: `225247`
  - raw label: `Fluid Removed Description (THCEN)`

match 15:
  - decision: `reject`
  - decision reason: `procedural fluid removal, not administration`
  - table: `chartevents`
  - itemid: `225261`
  - raw label: `Fluid removed (PACEN)`

match 16:
  - decision: `reject`
  - decision reason: `procedural fluid removal, not administration`
  - table: `chartevents`
  - itemid: `225262`
  - raw label: `Fluid removed description (PACEN)`

match 17:
  - decision: `reject`
  - decision reason: `0 rows; microbiology/procedure entry, not fluid administration`
  - table: `procedureevents`
  - itemid: `225815`
  - raw label: `Peritoneal Fluid`

match 18:
  - decision: `reject`
  - decision reason: `0 rows; microbiology culture, wrong domain`
  - table: `procedureevents`
  - itemid: `225818`
  - raw label: `Pleural Fluid Culture`

match 19:
  - decision: `reject`
  - decision reason: `unrelated GI procedure`
  - table: `chartevents`
  - itemid: `228102`
  - raw label: `Enema administration`

match 20:
  - decision: `reject`
  - decision reason: `dialysis fluid QC observation, not IV fluid administration`
  - table: `chartevents`
  - itemid: `225951`
  - raw label: `Peritoneal Dialysis Fluid Appearance`

match 21:
  - decision: `reject`
  - decision reason: `net fluid REMOVAL tracking, not administration`
  - table: `chartevents`
  - itemid: `224191`
  - raw label: `Hourly Patient Fluid Removal`

match 22:
  - decision: `reject`
  - decision reason: `CRRT-specific replacement fluid, narrower/different context`
  - table: `chartevents`
  - itemid: `225976`
  - raw label: `Replacement Fluid`

match 23:
  - decision: `reject`
  - decision reason: `dialysis-specific, not general IV fluid administration`
  - table: `chartevents`
  - itemid: `225977`
  - raw label: `Dialysate Fluid`

match 24:
  - decision: `reject`
  - decision reason: `nutrition/oral intake tracking, wrong domain`
  - table: `chartevents`
  - itemid: `227955`
  - raw label: `Food and Fluid`

match 25:
  - decision: `reject`
  - decision reason: `microbiology culture, wrong domain`
  - table: `procedureevents`
  - itemid: `225817`
  - raw label: `BAL Fluid Culture`

### inf_rbc, Packed Red Blood Cells, treatment, not specified
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `the active/in-use PRBC itemid -- found by checking d_items directly; the originally-surfaced candidates are real itemids but flagged "Not In Use" in d_items and confirmed 0 rows`
  - table: `inputevents`
  - itemid: `225168`
  - raw label: `Packed Red Blood Cells`
  - stats: `row_count=61967, units=mL`

match 2:
  - decision: `reject`
  - decision reason: `0 rows -- d_items flags this itemid's category as "Fluids - Other (Not In Use)"`
  - table: `inputevents`
  - itemid: `220996`
  - raw label: `Packed Red Cells`

match 3:
  - decision: `reject`
  - decision reason: `0 rows -- also "Not In Use"`
  - table: `inputevents`
  - itemid: `220969`
  - raw label: `Filtered erytrocytes`

match 4:
  - decision: `reject`
  - decision reason: `0 rows; whole-blood transfusion is not the target (PRBC is)`
  - table: `inputevents`
  - itemid: `221013`
  - raw label: `Whole Blood`

match 5:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `223752`
  - raw label: `Non-Invasive Blood Pressure Alarm - Low`

match 6:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `223751`
  - raw label: `Non-Invasive Blood Pressure Alarm - High`

match 7:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220179`
  - raw label: `Non Invasive Blood Pressure systolic`

match 8:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220180`
  - raw label: `Non Invasive Blood Pressure diastolic`

match 9:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220181`
  - raw label: `Non Invasive Blood Pressure mean`

match 10:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220052`
  - raw label: `Arterial Blood Pressure mean`

match 11:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220050`
  - raw label: `Arterial Blood Pressure systolic`

match 12:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220051`
  - raw label: `Arterial Blood Pressure diastolic`

match 13:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220056`
  - raw label: `Arterial Blood Pressure Alarm - Low`

match 14:
  - decision: `reject`
  - decision reason: `false keyword hit on "blood", unrelated`
  - table: `chartevents`
  - itemid: `220058`
  - raw label: `Arterial Blood Pressure Alarm - High`

match 15:
  - decision: `reject`
  - decision reason: `unrelated neuro-check item, false keyword hit`
  - table: `chartevents`
  - itemid: `223828`
  - raw label: `Slurred Speech`

match 16:
  - decision: `reject`
  - decision reason: `unrelated sedation-holiday flag, false keyword hit`
  - table: `chartevents`
  - itemid: `223780`
  - raw label: `Daily Wake Up Deferred`

### ffp, Fresh Frozen Plasma, treatment, not specified
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary FFP transfusion volume/rate`
  - table: `inputevents`
  - itemid: `220970`
  - raw label: `Fresh Frozen Plasma`
  - stats: `row_count=18828, value_range=[0.84, 35640], median=318, units=mL/min|mL/hour`

match 2:
  - decision: `keep`
  - decision reason: `plasma-exchange procedure -- related plasma-product administration, keep as secondary`
  - table: `inputevents`
  - itemid: `227532`
  - raw label: `Plasma Pheresis`
  - stats: `row_count=146, value_range=[20.1, 2093.3], median=386.5, units=mL/hour|mL/min`

match 3:
  - decision: `reject`
  - decision reason: `blood-smear cell-count %, wrong analyte entirely`
  - table: `labevents`
  - itemid: `51454`
  - raw label: `Plasma Cells`

match 4:
  - decision: `reject`
  - decision reason: `blood-smear cell-count %, wrong analyte entirely`
  - table: `labevents`
  - itemid: `51263`
  - raw label: `Plasma Cells`

match 5:
  - decision: `reject`
  - decision reason: `specimen-tube handling label, not a measurement`
  - table: `labevents`
  - itemid: `50932`
  - raw label: `Gray Top Hold (plasma)`

match 6:
  - decision: `reject`
  - decision reason: `specimen-tube handling label, not a measurement`
  - table: `labevents`
  - itemid: `50933`
  - raw label: `Green Top Hold (plasma)`

match 7:
  - decision: `reject`
  - decision reason: `specimen-tube handling label, not a measurement`
  - table: `labevents`
  - itemid: `50888`
  - raw label: `Blue Top Hold Frozen`

match 8:
  - decision: `reject`
  - decision reason: `unrelated serology test, false hit on "plasma"`
  - table: `labevents`
  - itemid: `51743`
  - raw label: `Toxoplasma IgM Ab`

match 9:
  - decision: `reject`
  - decision reason: `unrelated serology test, false hit on "plasma"`
  - table: `labevents`
  - itemid: `51741`
  - raw label: `Toxoplasma IgG Ab`

match 10:
  - decision: `reject`
  - decision reason: `unrelated serology test, false hit on "plasma"`
  - table: `labevents`
  - itemid: `51742`
  - raw label: `Toxoplasma IgG Ab Value`

match 11:
  - decision: `reject`
  - decision reason: `procedure-log duplicate of the inputevents Plasma Pheresis record`
  - table: `procedureevents`
  - itemid: `227551`
  - raw label: `Plasma Pheresis.`

match 12:
  - decision: `reject`
  - decision reason: `a blood-differential/serum-index percentage, wrong analyte`
  - table: `labevents`
  - itemid: `51435`
  - raw label: `Plasma`

match 13:
  - decision: `reject`
  - decision reason: `a blood-differential/serum-index percentage, wrong analyte`
  - table: `labevents`
  - itemid: `51124`
  - raw label: `Plasma`

match 14:
  - decision: `reject`
  - decision reason: `syphilis serology test, unrelated, false hit on "plasma"`
  - table: `labevents`
  - itemid: `51710`
  - raw label: `Rapid Plasma Reagin Test`

match 15:
  - decision: `reject`
  - decision reason: `0 rows -- unused product variant`
  - table: `inputevents`
  - itemid: `220971`
  - raw label: `ESDEP (Solvent / Detergent Virus-Inactivated Plasma)`

### plat, Platelets, treatment, not specified
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `primary platelet transfusion volume/rate`
  - table: `inputevents`
  - itemid: `225170`
  - raw label: `Platelets`
  - stats: `row_count=12933, value_range=[0.5, 17640], median=293, units=mL/hour|mL/min`

match 2:
  - decision: `reject`
  - decision reason: `a blood-smear morphology finding, not a platelet-transfusion event`
  - table: `labevents`
  - itemid: `51240`
  - raw label: `Large Platelets`

### inf_alb, Albumin Infusion, treatment, not specified
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1 (bulk, 12 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 79987.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 12): `68516521102|67467064301|944049302|52769025105|944049505|68982062303|944049101|44206025110|44206031050|944049102`

### anti_delir, Anti Deliriant, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=14988`
  - table: `inputevents`
  - itemid: `221824`
  - concept_id: `766529`
  - raw label: `Haloperidol (Haldol)`
  - stats: `row_count=14988`

match 2 (bulk, 84 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 159321.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 84): `378025710|63323047401|45025501|67457042612|45025301|60687016101|378032701|51079073420|781139713|68382007901`

### oth_diur, Other Diuretics, treatment, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1 (bulk, 29 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 74080.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 29): `68084020601|904692761|51079010320|60687048701|63739054410|51079098020|143950301|51285075402|55390046001|25021081710`

### anti_coag, Other Anticoagulants, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=157876`
  - table: `inputevents`
  - itemid: `225975`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium (Prophylaxis)`
  - stats: `row_count=157876`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=98795, value_range=[0.08, 1.5e+06], median=1242.14, units=units/hour|units/kg/hour`
  - table: `inputevents`
  - itemid: `225152`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium`
  - stats: `row_count=98795, value_range=[0.08, 1.5e+06], median=1242.14, units=units/hour|units/kg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1796, value_range=[5, 300000], median=550, units=units/min|units/hour`
  - table: `inputevents`
  - itemid: `229597`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium (Impella)`
  - stats: `row_count=1796, value_range=[5, 300000], median=550, units=units/min|units/hour`

match 4 (bulk, 38 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 712538.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 38): `63323054031|67457038599|8290306513|338055002|63323054201|8290306510|8290306424|61553094102|8290306525|64253033335`

### vasod, Antihypertensive And Vasodilators, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=42005, value_range=[0.0135062, 1739.72], median=1.39468, units=mg/hour|mcg/kg/min`
  - table: `inputevents`
  - itemid: `222042`
  - concept_id: `1318137`
  - raw label: `Nicardipine`
  - stats: `row_count=42005, value_range=[0.0135062, 1739.72], median=1.39468, units=mg/hour|mcg/kg/min`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=16065, value_range=[0.0485743, 2422.25], median=1.50252, units=mcg/kg/min|mg/hour`
  - table: `inputevents`
  - itemid: `229624`
  - concept_id: `1318137`
  - raw label: `Nicardipine 40mg/200`
  - stats: `row_count=16065, value_range=[0.0485743, 2422.25], median=1.50252, units=mcg/kg/min|mg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=8381, value_range=[0.0200003, 541.67], median=0.999106, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `222051`
  - concept_id: `19020994`
  - raw label: `Nitroprusside`
  - stats: `row_count=8381, value_range=[0.0200003, 541.67], median=0.999106, units=mcg/kg/min`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=88747, value_range=[0.0100001, 735.745], median=1, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `222056`
  - concept_id: `1361711`
  - raw label: `Nitroglycerin`
  - stats: `row_count=88747, value_range=[0.0100001, 735.745], median=1, units=mcg/kg/min`

match 5 (bulk, 55 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 149876.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 55): `10122032510|4018301|49884049901|67286081201|24477032302|143968910|67286081203|781320495|24477003025|143963310`

### anti_arrhythm, Antiarrhythmic, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=178, value_range=[0.25, 60], median=4.01803, units=mg/min`
  - table: `inputevents`
  - itemid: `222151`
  - concept_id: `1351461`
  - raw label: `Procainamide`
  - stats: `row_count=178, value_range=[0.25, 60], median=4.01803, units=mg/min`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=8026, value_range=[0.0200334, 451], median=0.500953, units=mg/min|mg/hour`
  - table: `inputevents`
  - itemid: `228339`
  - concept_id: `1309944`
  - raw label: `Amiodarone 600/500`
  - stats: `row_count=8026, value_range=[0.0200334, 451], median=0.500953, units=mg/min|mg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=9944, value_range=[0.05, 600], median=0.501555, units=mg/min|mg/hour`
  - table: `inputevents`
  - itemid: `221347`
  - concept_id: `1309944`
  - raw label: `Amiodarone`
  - stats: `row_count=9944, value_range=[0.05, 600], median=0.501555, units=mg/min|mg/hour`

match 4:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=5438, value_range=[0.0320713, 150], median=0.501672, units=mg/min`
  - table: `inputevents`
  - itemid: `229654`
  - concept_id: `1309944`
  - raw label: `Amiodarone 450/250`
  - stats: `row_count=5438, value_range=[0.0320713, 150], median=0.501672, units=mg/min`

match 5 (bulk, 24 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 60746.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 24): `93911405|409190201|172234560|61570006901|409190301|68084037101|63323061603|51079090620|904655661|51672402504`

### dobu_ind, Dobutamine Indicator, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=10264, value_range=[0.0800238, 135.87], median=5, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `221653`
  - concept_id: `1337720`
  - raw label: `Dobutamine`
  - stats: `row_count=10264, value_range=[0.0800238, 135.87], median=5, units=mcg/kg/min`

match 2 (bulk, 8 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 4192.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 8): `409234488|2717510|55390056090|338107302|74234632|409234402|409234632|409202520`

### levo_ind, Levosimendan Indicator, treatment, circulatory
- Mapping status: `no_source_candidates`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `none`
- Notes: `Same gap as levo -- levosimendan is not used in US ICU practice (not FDA-approved), confirmed absent via a direct grep of icu/d_items.csv.gz. Not a matching failure; see levo's notes for detail.`

### norepi_ind, Norepinephrine Indicator, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=459800, value_range=[0.000200003, 359.551], median=0.100029, units=mcg/kg/min|mg/kg/min`
  - table: `inputevents`
  - itemid: `221906`
  - concept_id: `1321341`
  - raw label: `Norepinephrine`
  - stats: `row_count=459800, value_range=[0.000200003, 359.551], median=0.100029, units=mcg/kg/min|mg/kg/min`

match 2 (bulk, 11 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 22675.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 11): `61553015311|781375595|703115303|781893285|247120004|409144304|67457085204|61553015361|74704101|61553012011`

### epi_ind, Epinephrine Indicator, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=31495, value_range=[0.000801155, 41.1429], median=0.0500064, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `221289`
  - concept_id: `1343916`
  - raw label: `Epinephrine`
  - stats: `row_count=31495, value_range=[0.000801155, 41.1429], median=0.0500064, units=mcg/kg/min`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=234`
  - table: `inputevents`
  - itemid: `229617`
  - concept_id: `1343916`
  - raw label: `Epinephrine.`
  - stats: `row_count=234`

match 3 (bulk, 35 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 15036.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 35): `409904502|409317801|49502050002|42023015925|409904517|63323048157|409492134|409317802|76329331601|409904202`

### milrin_ind, Milrinone Indicator, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `clean, single, unambiguous match`
  - table: `inputevents`
  - itemid: `221986`
  - raw label: `Milrinone`
  - stats: `row_count=10668, value_range=[0.0125, 121.7], median=0.33, units=mcg/kg/min`

### teophyllin_ind, Theophylline Indicator, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1 (bulk, 9 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 762.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 9): `68462038001|62332002531|17236032410|67781025101|42858070101|49708064490|456064416|50111048303|904588861`

### dopa_ind, Dopamine Indicator, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=18085, value_range=[0.200002, 4000], median=5.02021, units=mcg/kg/min`
  - table: `inputevents`
  - itemid: `221662`
  - concept_id: `1337860`
  - raw label: `Dopamine`
  - stats: `row_count=18085, value_range=[0.200002, 4000], median=5.02021, units=mcg/kg/min`

match 2 (bulk, 4 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 3824.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 4): `409780922|338100702|409910420|517180525`

### adh_ind, Vasopressin Indicator, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `label_keyword_match`
- Notes: `HAND-REVIEWED (label_keyword_match tier -- no shared OMOP concept, decisions below made by hand against raw-table stats, see match blocks).`

match 1:
  - decision: `keep`
  - decision reason: `clean, single, unambiguous match`
  - table: `inputevents`
  - itemid: `222315`
  - raw label: `Vasopressin`
  - stats: `row_count=37163, value_range=[0.017, 2400], median=2.4, units=units/min|units/hour`

### hep_ind, Heparin Indicator, treatment, circulatory
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=157876`
  - table: `inputevents`
  - itemid: `225975`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium (Prophylaxis)`
  - stats: `row_count=157876`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=98795, value_range=[0.08, 1.5e+06], median=1242.14, units=units/hour|units/kg/hour`
  - table: `inputevents`
  - itemid: `225152`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium`
  - stats: `row_count=98795, value_range=[0.08, 1.5e+06], median=1242.14, units=units/hour|units/kg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=1796, value_range=[5, 300000], median=550, units=units/min|units/hour`
  - table: `inputevents`
  - itemid: `229597`
  - concept_id: `1367571`
  - raw label: `Heparin Sodium (Impella)`
  - stats: `row_count=1796, value_range=[5, 300000], median=550, units=units/min|units/hour`

match 4 (bulk, 38 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 712538.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 38): `63323054031|67457038599|8290306513|338055002|63323054201|8290306510|8290306424|61553094102|8290306525|64253033335`

### prop_ind, Propofol Indicator, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=498811, value_range=[-71.6637, 135794], median=32.1422, units=mcg/kg/min|mg/hour`
  - table: `inputevents`
  - itemid: `222168`
  - concept_id: `753626`
  - raw label: `Propofol`
  - stats: `row_count=498811, value_range=[-71.6637, 135794], median=32.1422, units=mcg/kg/min|mg/hour`

match 2 (bulk, 9 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 67496.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 9): `310030022|63323026929|63323027057|63323029766|63323026920|310030011|63323026965|409469930|63323029730`

### benzdia_ind, Benzodiazepine Indicator, treatment, neuro
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4767`
  - table: `inputevents`
  - itemid: `221623`
  - concept_id: `723013`
  - raw label: `Diazepam (Valium)`
  - stats: `row_count=4767`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=126814, value_range=[0.02, 3370.98], median=3.00461, units=mg/hour`
  - table: `inputevents`
  - itemid: `221668`
  - concept_id: `708298`
  - raw label: `Midazolam (Versed)`
  - stats: `row_count=126814, value_range=[0.02, 3370.98], median=3.00461, units=mg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=42268, value_range=[0.12959, 9.61782], median=2.50251, units=mg/hour`
  - table: `inputevents`
  - itemid: `221385`
  - concept_id: `791967`
  - raw label: `Lorazepam (Ativan)`
  - stats: `row_count=42268, value_range=[0.12959, 9.61782], median=2.50251, units=mg/hour`

match 4 (bulk, 52 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 335761.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 52): `62584081301|63857032810|228206710|62584081201|187065920|63739007310|51079028620|51079028501|904588061|409127332`

### loop_diur_ind, Loop Diuretic Indicator, treatment, metabolic_renal
- Mapping status: `source_candidates_found`
- Reconstruction type: `treatment_indicator`
- Target unit: `indicator`
- Match method: `omop_concept_match`

match 1:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=4086, value_range=[0.2, 12.0968], median=2.02703, units=mg/hour`
  - table: `inputevents`
  - itemid: `229639`
  - concept_id: `932745`
  - raw label: `Bumetanide (Bumex)`
  - stats: `row_count=4086, value_range=[0.2, 12.0968], median=2.02703, units=mg/hour`

match 2:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=117125, value_range=[0.05, 3000], median=5.08932, units=mg/hour`
  - table: `inputevents`
  - itemid: `221794`
  - concept_id: `956874`
  - raw label: `Furosemide (Lasix)`
  - stats: `row_count=117125, value_range=[0.05, 3000], median=5.08932, units=mg/hour`

match 3:
  - decision: `keep`
  - decision reason: `omop/analyte-concept-verified match; row_count=24590, value_range=[0.499951, 14100], median=14.9901, units=mg/hour`
  - table: `inputevents`
  - itemid: `228340`
  - concept_id: `956874`
  - raw label: `Furosemide (Lasix) 250/50`
  - stats: `row_count=24590, value_range=[0.499951, 14100], median=14.9901, units=mg/hour`

match 4 (bulk, 43 distinct NDC codes in `prescriptions`, class-level decision):
  - decision: `keep`
  - decision reason: `broad drug-class indicator -- MIMIC's prescriptions table is NDC-keyed (much finer granularity than AUMC's per-drug itemids), so individual NDCs are not itemized here; kept as a class -- any prescription in this NDC set counts as an 'On' hour for this indicator. Total observed prescription row count across the set: 458692.`
  - table: `prescriptions`
  - itemid (NDC list, first 10 of 43): `185012801|74141204|69238148901|50268013015|185013001|409141210|641600810|69238149101|51079089101|55390050002`
