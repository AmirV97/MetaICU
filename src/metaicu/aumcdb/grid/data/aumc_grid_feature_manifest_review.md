# AUMC Grid Feature Manifest Candidate Review

Source manifest: the reviewed AUMC grid feature manifest generated during development.
Source candidate examples: the accompanying grid-manifest audit export generated during development.

This file is for manual review of stage-1 candidate matching for the iCareFM-style hourly-grid fork.
Matches are Amsterdam source-vocab rows. Mapping tables such as supplied vocab and OpenICU are evidence routes for finding those source rows, not separate duplicate matches.
The matches are broad source candidates, not final extraction decisions. A noisy match here means stage 2 needs stricter per-feature source selection.

## Format Template

```text
### tag, name, type, organ system
Decision: [MTO/OTO]
Target unit: ...
Reconstruction type: ...
Mapping status: ...
Notes: ...
OpenICU evidence: mapping file and OMOP concept IDs, if available

match 1:
  - decision: [keep/reject/needs_policy]
  - decision reason: ...
  - table: ...
  - itemid/valueid/ordercategoryid: ...
  - source token: ...
  - row count: ...
  - evidence: ...
  - matched by: ...
  - raw label/value/unit: ...

match 2:
  - ...
```

ID fields mean Amsterdam source identifiers from the raw/source vocabulary:

- `itemid`: Amsterdam item identifier.
- `valueid`: Amsterdam categorical value identifier when present.
- `ordercategoryid`: Amsterdam drug/order category identifier when present.
- `source token`: current source-token key from the vocabulary pipeline.
- `row count`: rows represented by that source token in the source vocabulary.
- `matched_by`: why the broad matcher pulled in the candidate, e.g. OpenICU OMOP ID or a text term.

Total features: 129 (128 in this working copy -- see "Claude pass" note below)
Features with recorded match rows: 103 (117 after the claude pass below)
Total recorded match rows: 669 (752 after the claude pass below; 757 after the batch-apply pass below, which added 3 new matches: supp_o2_vent +1, ufilt +2)

Claude pass: added source-vocab candidates for 14 of the 21 originally-unmatched features
(neut, tri, rass, icp, spap, dpap, svo2, peep, peak, plateau, ps, norepi, norepi_ind, ethnic)
by searching `aumc_supplied_vocab.csv` source-side columns directly; extended `samp` with
bacteria-specific candidates; confirmed levo/levo_ind/milrin/milrin_ind/adh/adh_ind
genuinely absent from AmsterdamUMCdb via cross-check against the official AmsterdamUMCdb
OMOP dictionary.

Decision pass (features 1-30 of the Table S3 order: map..crp, i.e. all features up to and
including crp): feature-level Decision and per-match decision/decision reason resolved for
these 26 features with candidates (the 4 admission_context demographics -- age/weight/sex/
height -- have no matches to decide). Each was drafted then independently verified against
the doctrine below by a separate review pass; 11 of 130 match calls were revised during
verification (mostly draft "keep" downgraded to "needs_policy" on a closer methodology/
scope read -- e.g. ECMO FiO2 vs ventilator FiO2, spontaneous-only vs total respiratory
rate, Jaffe vs enzymatic creatinine, nephrostomy urine output, pH-corrected vs uncorrected
ionized calcium). All remaining features beyond crp still carry unresolved
`[keep/reject/needs_policy]` placeholders.

Decision doctrine applied: (1) compartment/specimen matching -- keep blood/bloed candidates
for a blood-intent feature, reject urine/CSF/dialysate/other-fluid candidates as a different
clinical concept, not merely deprioritized; a no-compartment-stated legacy itemid is safe to
keep as blood if its sibling primary item is explicitly (bloed) and units match; (2) multi-
instrument MTO -- the same concept via concurrent devices (arterial line/PiCCO/IABP,
different ventilator brands, different blood-gas-analyzer generations) is legitimate keep,
not noise; (3) assay/analyte identity -- reject a different analyte pulled in by a shared
text fragment (e.g. Noradrenaline via an Adrenaline query), but same-analyte-different-method
is fine to keep/needs_policy; (4) wrong physical quantity/dimension -- reject a candidate
whose label implies a different physical quantity than the target unit; (5) ordered/set vs
measured/actual -- ventilator "(Set)" values are needs_policy, not an outright keep/reject;
(6) measurement-site accuracy -- less-accurate peripheral sites (e.g. axillary/oral temp) are
needs_policy, not reject; (7) duplicate/secondary-device "(2)" channels keep alongside the
primary; (8) reject not-actually-a-measurement rows (target/goal values, diagnosis codes,
procedure orders, mode-selection fields); (9) fluid-output type matching -- reject every
non-matching fluid type for a specific-fluid feature, allow multiple routes of the same
target fluid; (10) same itemid via two extraction routes -> needs_policy (pick one canonical
route, don't double count); (11) "unsure: <reason>" for genuine not-confident-what-this-is
cases (ambiguous abbreviation, row count 1-5 with an uninformative label) as distinct from
needs_policy (understood, but needs an explicit downstream rule); (12) feature Decision is
MTO when more than one match is kept/needs_policy as concurrent/complementary sources, OTO
otherwise.

Schema decision: `tgcs` (Glasgow Coma Scale Total) is REMOVED from this working copy.
It never had a direct source row (derived_score with no matched itemid), and its role is
fully covered by the three already-existing, already-matched component features `egcs`
(eye), `vgcs` (verbal), `mgcs` (motor) -- no renaming of those three tags. On `vgcs`,
"Geintubeerd" (intubated) is kept as its own valid category (decision: keep) rather than
imputed to V=1, so there is no forced numeric total to derive in the first place. This
change is staged in this `_claude.md` copy only; the canonical
`aumc_grid_feature_manifest.csv` and the original `aumc_grid_feature_manifest_review.md`
are untouched pending your decision to commit it.

Batch-apply pass: resolved feature-level and per-match decisions for ~100 remaining features
via `apply_batch_policy.py` / `apply_batch_policy_part2.py` (kept next to this file), following
a full diagnostic-plot review (6-30 patients per feature, generated via SLURM), raw
unit-field checks against the drugitems/numericitems parquet, and histogram comparisons for
ambiguous cases. New patterns caught and fixed this pass: (a) drugitems `rate` is sometimes
mL/h pump flow rather than the target dose-rate unit (heparin, loop diuretics, propofol,
theophylline) -- reconstruct as `dose / duration` instead; (b) fixed 1-minute
`duration`/`stop-start` is AmsterdamUMCdb's bolus-logging artifact, not a real rate window --
bolus matches route to the paired `_ind` indicator instead of the rate feature; (c) broad
category/prefix matchers (`term:Diuretic` on ordercategory text, `term:BLOOD_PRODUCT`,
`term:CVVH`, `MFT_` device prefix) sweep in unrelated drugs/products/parameters -- `oth_diur`,
`ffp`, `inf_alb`, `plat`, `ufilt`/`ufilt_ind` all had most of their candidate pool rejected as
wrong-concept; (d) blood/lab concentration measurements (`(bloed)`, `(serum)`, `(plasma)`) and
admission-diagnosis-category codes (APACHE IV) are not administration events, even inside
binary-indicator features that are otherwise presence-only (`anti_arrhythm`, `anti_delir`,
`benzdia_ind`, `sed`, `nonop_pain`, `dopa_ind`, `epi_ind`, `teophyllin_ind`, `ins_ind`); (e)
unit-equivalence/conversion pairs resolved: `10^9/l = G/l` (plt, wbc), `E/l = U/L` (lipase,
amylase), `mmol/l -> mg/dL` via analyte molar mass (phos x3.097, mg x2.43-family), `%<->mmol/mol`
NGSP/IFCC formula (hba1c), `kPa -> mmHg` x7.50062 (pco2), `mbar -> cmH2O` x1.0197
(peep/peak/ps); (f) cross-drug potency standardization for rate features with non-equipotent
drugs sharing one channel: benzodiazepines simplified to midazolam-only for the rate (other
benzos captured via `benzdia_ind` instead), loop diuretics standardized to furosemide-
equivalent (bumetanide x40), theophylline includes an aminophylline x0.8 conversion;
(g) `tri` (Troponin I) confirmed genuinely absent from AmsterdamUMCdb (checked
`aumc_supplied_vocab.csv`, the official OMOP `dictionary_map.csv`, and the raw
AmsterdamUMCdb `dictionary.csv`) -- Troponin T accepted as an explicit cross-assay
substitute, not presented as real Troponin I; (h) `egcs`/`vgcs`/`mgcs` and `airway` each
got a `standardized label` line added per match, translating the raw Dutch/categorical value
into the standard GCS E/V/M scale or an Endotracheal-tube/Tracheostomy category, without
altering the raw Dutch value; (i) two candidate-pool gaps closed with new inserted matches:
`supp_o2_vent` +1 (itemid 12279, O2 concentratie -- missing because this feature's matcher
required a literal "FiO2" substring) and `ufilt` +2 (itemid 8805, CVVH Onttrokken, both table
routes -- the real net-ultrafiltration-removed signal; the feature's own dominant match
("UF Totaal (ingesteld)") turned out to be ~99.99% zero-valued and was rejected instead).
Features not covered by this pass (still carrying the original `[keep/reject/needs_policy]`
placeholder) were out of scope for this session and untouched: `abx`, `amm`, `dobu`/`dobu_ind`,
`dpap`, `esr`, `glu`, `hct`, `hgb`, `mpap`, `pcwp`, `ph`, `plateau`, `pt`, `samp`, `sao2`,
`spap`, `spo2`, `ygt`, plus `levo`/`levo_ind`/`milrin`/`milrin_ind`/`adh`/`adh_ind` (already
confirmed absent from AmsterdamUMCdb in an earlier pass) and the four admission_context
demographics (age/weight/sex/height, no matches to decide). The feature-level
`Decision: [MTO/OTO]` field remains an unfilled placeholder for the large majority of
features file-wide (including many resolved this pass) -- this was already true before this
session and wasn't part of today's per-match review; left untouched pending a separate pass.

Decision labels:

- `MTO`: many-to-one; multiple Amsterdam source candidates may reconstruct the same grid feature.
- `OTO`: one-to-one; one Amsterdam source candidate should reconstruct the grid feature.

### map, Mean Arterial Blood Pressure, observation, circulatory

- Decision: `MTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/mean_arterial_pressure.yml`; OMOP concept IDs `21490852|21492241`

match 1:
  - decision: `keep`
  - decision reason: `"ABP gemiddeld" = arterial blood pressure mean (Dutch 'gemiddeld'=mean/average); dominant-volume primary arterial-line MAP in mmHg, directly matches target concept and unit. Draft confirmed.`
  - table: `numericitems`
  - itemid: `6642`
  - source token: `MEASUREMENT_BEDSIDE//6642//mmHg`
  - row count: `33352770`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:ABP gemiddeld`
  - raw label: `ABP gemiddeld`
  - raw unit: `mmHg`

match 2:
  - decision: `keep`
  - decision reason: `"ABP gemiddeld II" is a second arterial-line/catheter channel (numeric-suffix duplicate device pattern per doctrine 7), same concept and unit as match 1 — legitimate concurrent source (e.g. second arterial catheter site), not noise. Draft confirmed.`
  - table: `numericitems`
  - itemid: `8843`
  - source token: `MEASUREMENT_BEDSIDE//8843//mmHg`
  - row count: `56028`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `ABP gemiddeld II`
  - raw unit: `mmHg`

match 3:
  - decision: `keep`
  - decision reason: `"PiCCO APm" = PiCCO-system arterial pressure mean, a different device/method (pulse-contour/transpulmonary thermodilution monitor) measuring the same MAP concept in mmHg — textbook multi-instrument MTO example per doctrine 2. Draft confirmed.`
  - table: `numericitems`
  - itemid: `14058`
  - source token: `MEASUREMENT_BEDSIDE//14058//mmHg`
  - row count: `3970`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PiCCO APm`
  - raw unit: `mmHg`

### lact, Lactate, observation, circulatory

- Decision: `MTO`
- Target unit: `mmol/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/lactate.yml`; OMOP concept IDs `3014111|3047181`

match 1:
  - decision: `keep`
  - decision reason: `Explicit '(bloed)' compartment, correct mmol/L unit, primary high-volume blood lactate assay -- unambiguous match to target concept.`
  - table: `numericitems`
  - itemid: `10053`
  - source token: `LAB//10053//mmol/l`
  - row count: `182155`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lactate`
  - raw label: `Lactaat (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated, but sibling primary item (match 1) is explicitly '(bloed)' and units match (mmol/l) -- fits the documented legacy-itemid-no-compartment-stated pattern (doctrine #1), consistent with a pre-upgrade duplicate itemid rather than a different specimen.`
  - table: `numericitems`
  - itemid: `6837`
  - source token: `LAB//6837//mmol/l`
  - row count: `1476`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Laktaat`
  - raw unit: `mmol/l`

match 3:
  - decision: `keep`
  - decision reason: `'Astrup' is the classic (Poul Astrup) blood-gas/acid-base analysis method used in Dutch/European ICUs -- this is blood lactate measured by a blood-gas analyzer rather than the central lab analyzer, i.e. same analyte via a different instrument (doctrine #2), not a different compartment or analyte.`
  - table: `numericitems`
  - itemid: `9580`
  - source token: `LAB//9580//mmol/l`
  - row count: `917`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Laktaat Astrup`
  - raw unit: `mmol/l`

### age, Age, demographic, not specified

- Decision: `OTO`
- Target unit: `years`
- Reconstruction type: `admission_context`
- Mapping status: `source_candidates_found`
- Notes: `Recover from admissions.csv, column agegroup (6 bins, no blanks). POLICY (resolved): map each bin to its median -- for the closed bins this is the true numeric midpoint; the open-ended top bin "80+" is treated as spanning 80-89 (mirroring the 10-year width of every other bin) so it also gets a midpoint rather than an arbitrary point value. Mapping table: 18-39 (n=2551) -> 28.5; 40-49 (n=2177) -> 44.5; 50-59 (n=3952) -> 54.5; 60-69 (n=6091) -> 64.5; 70-79 (n=6074) -> 74.5; 80+ (n=2261) -> 84.5. Note the 18-39 bin is 22 years wide (vs. 10 years for the rest), so its point estimate carries more error than the others -- flag this asymmetry if age is used in any severity scoring.`

No itemid-vocabulary match applies here (source is a static admissions-table column, not a vocab-matched observation) -- see Notes for the exact source column, bin table, and median-recovery policy.

### weight, Weight, demographic, not specified

- Decision: `OTO`
- Target unit: `kg`
- Reconstruction type: `admission_context`
- Mapping status: `source_candidates_found`
- Notes: `Recover from admissions.csv, column weightgroup; 946 blank -> leave as missing, do not impute. POLICY (resolved): map each bin to its median -- both open-ended bins ("59-", "110+") are treated as spanning the same 10kg width as their neighbors (50-59 and 110-119 respectively) so they also get a midpoint. Mapping table: 59- (n=1845) -> 54.5; 60-69 (n=3683) -> 64.5; 70-79 (n=6035) -> 74.5; 80-89 (n=5563) -> 84.5; 90-99 (n=2948) -> 94.5; 100-109 (n=1168) -> 104.5; 110+ (n=918) -> 114.5. Reliability metadata still available but not folded into the point estimate: companion column weightsource (Anamnestisch=patient-reported/least reliable [9885], Geschat=clinician-estimated [5782], Gemeten=actually measured/most reliable [1711], 5728 blank) -- carry this through as an optional confidence flag if the downstream pipeline wants it, no action needed for the point value itself.`

No itemid-vocabulary match applies here -- see Notes for the exact source column, bin table, and median-recovery policy.

### sex, Sex, demographic, not specified

- Decision: `OTO`
- Target unit: `categorical`
- Reconstruction type: `admission_context`
- Mapping status: `admission_context`
- Notes: `Verified against admissions.csv. Source column: gender, values "Man" (14735) / "Vrouw" (7875) / blank (496). Clean, unbinned, unambiguous categorical source -- no policy question, unlike age/weight/height.`

No itemid-vocabulary match applies here -- source is `admissions.csv:gender` directly.

### height, Height, demographic, not specified

- Decision: `OTO`
- Target unit: `cm`
- Reconstruction type: `admission_context`
- Mapping status: `source_candidates_found`
- Notes: `Recover from admissions.csv, column heightgroup; 1482 blank -> leave as missing, do not impute. POLICY (resolved): map each bin to its median -- both open-ended bins ("159-", "190+") are treated as spanning the same 10cm width as their neighbors (149-159 and 190-199 respectively) so they also get a midpoint. Mapping table: 159- (n=1139) -> 154.0; 160-169 (n=5290) -> 164.5; 170-179 (n=8496) -> 174.5; 180-189 (n=5671) -> 184.5; 190+ (n=1028) -> 194.5. Same reliability metadata pattern as weight: companion column heightsource (Anamnestisch/Geschat/Gemeten, 5992 blank) available as an optional confidence flag, not folded into the point estimate.`

No itemid-vocabulary match applies here -- see Notes for the exact source column, bin table, and median-recovery policy.

### hr, Heart Rate, observation, circulatory

- Decision: `MTO`
- Target unit: `bpm`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/heart_rate.yml`; OMOP concept IDs `21490872|3027018`

match 1:
  - decision: `keep`
  - decision reason: `"Hartfrequentie" (Dutch for heart rate) from the standard ECG monitor, unit /min matches bpm, dominant row count confirms this is the primary continuous HR source.`
  - table: `numericitems`
  - itemid: `6640`
  - source token: `MEASUREMENT_BEDSIDE//6640///min`
  - row count: `37732398`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Hartfrequentie`
  - raw unit: `/min`

match 2:
  - decision: `keep`
  - decision reason: `"IABP HF" -- HF is the standard Dutch abbreviation for Hartfrequentie (heart rate); this is the intra-aortic balloon pump's own trigger-derived HR channel, a legitimate concurrent device per doctrine #2, not a different concept.`
  - table: `numericitems`
  - itemid: `12440`
  - source token: `MEASUREMENT_BEDSIDE//12440///min`
  - row count: `83321`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `IABP HF`
  - raw unit: `/min`

match 3:
  - decision: `keep`
  - decision reason: `"PiCCO HF Hartfrequentie" is PiCCO's arterial-waveform-derived heart rate channel -- same concept measured by a different concurrent hemodynamic-monitoring device, consistent with doctrine #2's explicit PiCCO/IABP example.`
  - table: `numericitems`
  - itemid: `14055`
  - source token: `MEASUREMENT_BEDSIDE//14055///min`
  - row count: `4559`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PiCCO HF Hartfrequentie`
  - raw unit: `/min`

### fio2, FiO2, observation, respiratory

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/fraction_of_inspired_oxygen.yml`; OMOP concept IDs `3020716|3025408`

match 1:
  - decision: `keep`
  - decision reason: `"O2 concentratie" with dominant row count (15.6M) is consistent with the primary/default-frequency vent FiO2 channel in this dataset; unitless 'Geen' is a common raw-vocabulary quirk for this field, not a red flag.`
  - table: `numericitems`
  - itemid: `12279`
  - source token: `MEASUREMENT_BEDSIDE//12279//Geen`
  - row count: `15645395`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `O2 concentratie`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `Explicit 'FiO2 %' label directly matches target concept and unit; legitimate secondary/monitor channel.`
  - table: `numericitems`
  - itemid: `6699`
  - source token: `MEASUREMENT_BEDSIDE//6699//Geen`
  - row count: `91881`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `FiO2 %`
  - raw unit: `Geen`

match 3:
  - decision: `reject`
  - decision reason: `'O2 Volume' with no unit reads as an O2 flow/volume quantity, not a fraction/percentage -- wrong physical dimension for this % feature, per doctrine 4.`
  - table: `numericitems`
  - itemid: `8869`
  - source token: `MEASUREMENT_BEDSIDE//8869//UNKNOWN`
  - row count: `85386`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `O2 Volume`

match 4:
  - decision: `reject`
  - decision reason: `A_FiO2 -- revised: excluded per the later, more considered pass on this feature (superseding the earlier keep from the original 24-MTO-feature pass).`
  - table: `numericitems`
  - itemid: `13076`
  - source token: `MEASUREMENT_BEDSIDE//13076//Geen`
  - row count: `10817`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `A_FiO2`
  - raw unit: `Geen`

match 5:
  - decision: `keep`
  - decision reason: `Explicit 'FiO2' label on a distinct MCA_-prefixed device/monitor family; concurrent legitimate source.`
  - table: `numericitems`
  - itemid: `16629`
  - source token: `MEASUREMENT_BEDSIDE//16629//Geen`
  - row count: `1951`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `MCA_FiO2`
  - raw unit: `Geen`

match 6:
  - decision: `reject`
  - decision reason: `ECMO - FiO2 -- revised: distinct oxygenator-circuit concept, not ventilator FiO2 (superseding the earlier needs_policy call).`
  - table: `numericitems`
  - itemid: `20656`
  - source token: `MEASUREMENT_BEDSIDE//20656//Geen`
  - row count: `478`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `ECMO - FiO2`
  - raw unit: `Geen`

match 7:
  - decision: `keep`
  - decision reason: `Zephyros transport ventilator FiO2 channel -- legitimate concurrent device source (same family as its PEEP/pressure siblings elsewhere).`
  - table: `numericitems`
  - itemid: `16246`
  - source token: `MEASUREMENT_BEDSIDE//16246//Geen`
  - row count: `239`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `Zephyros FiO2`
  - raw unit: `Geen`

match 8:
  - decision: `keep`
  - decision reason: `Explicit 'FiO2' label on a distinct RA_-prefixed device/context family (e.g. recovery-area monitor); legitimate low-volume concurrent source, not a red flag by itself.`
  - table: `numericitems`
  - itemid: `14471`
  - source token: `MEASUREMENT_BEDSIDE//14471//Geen`
  - row count: `76`
  - evidence: `source_vocab`
  - matched by: `term:FiO2`
  - raw label: `RA_FiO2`
  - raw unit: `Geen`

match 9:
  - decision: `reject`
  - decision reason: `Zephyros O2i -- revised: ambiguous, may not be FiO2 at all (superseding the earlier unsure call).`
  - table: `numericitems`
  - itemid: `16245`
  - source token: `MEASUREMENT_BEDSIDE//16245//Geen`
  - row count: `52`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Zephyros O2i`
  - raw unit: `Geen`

match 10:
  - decision: `keep`
  - decision reason: `Label 'Breathing FiO2(%)' is explicit and unambiguous despite low row count (14) -- doctrine 11's low-count-unsure exception applies to generic/uninformative labels, which this is not.`
  - table: `numericitems`
  - itemid: `20134`
  - source token: `MEASUREMENT_BEDSIDE//20134//UNKNOWN`
  - row count: `14`
  - evidence: `source_vocab`
  - matched by: `term:FiO2`
  - raw label: `Breathing FiO2(%)`

match 11:
  - decision: `reject`
  - decision reason: `Secondary-device duplicate of match 3, which itself is a wrong-physical-quantity item (O2 volume/flow, not fraction) -- doctrine 7's 'keep duplicate alongside primary' only applies when the primary is a valid match, which it is not here.`
  - table: `numericitems`
  - itemid: `9664`
  - source token: `MEASUREMENT_BEDSIDE//9664//UNKNOWN`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `O2 Volume(2)`

### resp, Respiratory Rate, observation, respiratory

- Decision: `MTO`
- Target unit: `insp/min`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/respiratory_rate.yml`; OMOP concept IDs `3007646|3024171|3026892`

match 1:
  - decision: `keep`
  - decision reason: `Primary bedside-monitor measured respiratory rate; dominant volume, correct unit and concept.`
  - table: `numericitems`
  - itemid: `8874`
  - source token: `MEASUREMENT_BEDSIDE//8874//UNKNOWN`
  - row count: `25776086`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ademfrequentie Monitor`

match 2:
  - decision: `keep`
  - decision reason: `Abbreviated label for the same monitor/ventilator-measured actual rate, unit /min matches target; a genuine second high-volume concurrent channel.`
  - table: `numericitems`
  - itemid: `12266`
  - source token: `MEASUREMENT_BEDSIDE//12266///min`
  - row count: `15613362`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Respiratory Rate`
  - raw label: `Ademfreq.`
  - raw unit: `/min`

match 3:
  - decision: `needs_policy`
  - decision reason: `'(Set)' is the ventilator's ordered/backup rate, equal to actual rate only under fully controlled ventilation and diverging once the patient breathes spontaneously above it -- needs an explicit rule for when/if it may substitute for a missing measured rate.`
  - table: `numericitems`
  - itemid: `12283`
  - source token: `MEASUREMENT_BEDSIDE//12283///min`
  - row count: `4216281`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Respiratory Rate`
  - raw label: `Adem Frequentie (Set)`
  - raw unit: `/min`

match 4:
  - decision: `keep`
  - decision reason: `Evita ventilators report total measured frequency (spontaneous+mandatory) as their plain 'Ademfrequentie' channel, distinct from their own '(Set)' and 'Spontaan' sub-channels seen elsewhere in this list -- a legitimate concurrent total-rate source from a different device.`
  - table: `numericitems`
  - itemid: `8873`
  - source token: `MEASUREMENT_BEDSIDE//8873//UNKNOWN`
  - row count: `85780`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ademfrequentie Evita`

match 5:
  - decision: `needs_policy`
  - decision reason: `'Spontaan' counts only patient-triggered breaths, not the total breath count; in SIMV-type modes with a mandatory backup rate this systematically undercounts true respiratory rate, and only equals total rate in fully spontaneous modes (CPAP/PSV) -- this is a component-vs-total scope mismatch, not a plain concurrent-device duplicate, so it needs an explicit equivalence/substitution policy rather than a blanket keep.`
  - table: `numericitems`
  - itemid: `7726`
  - source token: `MEASUREMENT_BEDSIDE//7726//UNKNOWN`
  - row count: `44843`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ademfrequentie Spontaan`

match 6:
  - decision: `needs_policy`
  - decision reason: `Newer/relabeled ('nieuw') variant of the same spontaneous-only channel as itemid 7726; inherits the identical component-vs-total scope ambiguity, so should resolve under the same policy, not be kept outright.`
  - table: `numericitems`
  - itemid: `12577`
  - source token: `MEASUREMENT_BEDSIDE//12577///min`
  - row count: `330`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ademfreq. Spontaan nieuw`
  - raw unit: `/min`

match 7:
  - decision: `keep`
  - decision reason: `Bipap Vision is a real NIV device; its 'Rate' channel is the device's own detected breathing rate (not labeled Set), a valid concurrent measurement source.`
  - table: `numericitems`
  - itemid: `12372`
  - source token: `MEASUREMENT_BEDSIDE//12372///min`
  - row count: `214`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Rate (Bipap Vision)`
  - raw unit: `/min`

match 8:
  - decision: `keep`
  - decision reason: `Transport ventilator's own measured-frequency channel (not labeled Set), consistent with the multi-instrument doctrine despite very low row count.`
  - table: `numericitems`
  - itemid: `16241`
  - source token: `MEASUREMENT_BEDSIDE//16241///min`
  - row count: `62`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Zephyros Frequentie`
  - raw unit: `/min`

match 9:
  - decision: `keep`
  - decision reason: `'(2)' suffix denotes a secondary physical monitor/device channel of the same abbreviated-rate type (itemid 12266), per the duplicate-channel doctrine.`
  - table: `numericitems`
  - itemid: `12348`
  - source token: `MEASUREMENT_BEDSIDE//12348///min`
  - row count: `52`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ademfreq.(2)`
  - raw unit: `/min`

match 10:
  - decision: `needs_policy`
  - decision reason: `Secondary-device duplicate of the 'Ademfrequentie Spontaan' channel (itemid 7726, match 5); it inherits the same spontaneous-only vs total-rate scope ambiguity, so it should follow whatever policy is set for match 5 rather than being kept unconditionally.`
  - table: `numericitems`
  - itemid: `9654`
  - source token: `MEASUREMENT_BEDSIDE//9654//UNKNOWN`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ademfrequentie Spontaan(2)`

match 11:
  - decision: `unsure`
  - decision reason: `Row count of 1 with a generic label lacking the usual 'Adem' respiratory qualifier -- cannot confidently tell if this is a genuine distinct legacy channel or a data artifact/mis-tagged field.`
  - table: `numericitems`
  - itemid: `8876`
  - source token: `MEASUREMENT_BEDSIDE//8876//UNKNOWN`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Frequentie Spontaan`

### temp, Temperature, observation, infection

- Decision: `MTO`
- Target unit: `C`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/temperature.yml`; OMOP concept IDs `21490586|21490588|21490870|3006322|3022060|3025085|3025163`

match 1:
  - decision: `keep`
  - decision reason: `Temp Bloed (blood temperature) is a core-temperature site with matching unit (°C); dominant-volume primary source. Draft confirmed.`
  - table: `numericitems`
  - itemid: `8658`
  - source token: `MEASUREMENT_BEDSIDE//8658//°C`
  - row count: `1999754`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Temperature`
  - raw label: `Temp Bloed`
  - raw unit: `°C`

match 2:
  - decision: `keep`
  - decision reason: `Temp Blaas (bladder) is a well-validated ICU core-temperature surrogate site, unit matches. Draft confirmed.`
  - table: `numericitems`
  - itemid: `13952`
  - source token: `MEASUREMENT_BEDSIDE//13952//°C`
  - row count: `927689`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Temp Blaas`
  - raw unit: `°C`

match 3:
  - decision: `keep`
  - decision reason: `Temp Oesophagus is a standard core-temperature site, unit matches. Draft confirmed.`
  - table: `numericitems`
  - itemid: `16110`
  - source token: `MEASUREMENT_BEDSIDE//16110//°C`
  - row count: `833973`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Temp Oesophagus`
  - raw unit: `°C`

match 4:
  - decision: `keep`
  - decision reason: `Temp Rectaal -- rectum is explicitly listed among core-temperature sites in doctrine #6 (alongside blood/bladder/esophagus), so an outright keep alongside the other core sites is correct. Draft confirmed.`
  - table: `numericitems`
  - itemid: `13058`
  - source token: `MEASUREMENT_BEDSIDE//13058//°C`
  - row count: `387259`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Temp Rectaal`
  - raw unit: `°C`

match 5:
  - decision: `needs_policy`
  - decision reason: `Axillary is a canonical peripheral site named in doctrine #6 that systematically underreads core temp; real measurement but needs a site-priority rule rather than outright keep/reject. Draft confirmed.`
  - table: `numericitems`
  - itemid: `13060`
  - source token: `MEASUREMENT_BEDSIDE//13060//°C`
  - row count: `202198`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Temp Axillair`
  - raw unit: `°C`

match 6:
  - decision: `needs_policy`
  - decision reason: `Tympanic/ear is a peripheral site (also named in doctrine #6) with known reliability issues vs core sites; same site-priority handling as axillary. Draft confirmed.`
  - table: `numericitems`
  - itemid: `13062`
  - source token: `MEASUREMENT_BEDSIDE//13062//°C`
  - row count: `52540`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Temp Oor`
  - raw unit: `°C`

match 7:
  - decision: `keep`
  - decision reason: `PiCCO Tb is the thermodilution catheter's own blood-temperature channel -- a core site measured via a different device, matching the multi-instrument MTO pattern (doctrine #2); low row count alone is not disqualifying.`
  - table: `numericitems`
  - itemid: `14047`
  - source token: `MEASUREMENT_BEDSIDE//14047//°C`
  - row count: `4733`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PiCCO Tb blood temperature`
  - raw unit: `°C`

match 8:
  - decision: `needs_policy`
  - decision reason: `Temp Oraal is a peripheral site (named explicitly in doctrine #6); row_count=546 is low but the label is clear/unambiguous (not the 1-5-row generic-label 'unsure' scenario in doctrine #11), so needs_policy rather than unsure or reject is correct. Draft confirmed.`
  - table: `numericitems`
  - itemid: `13061`
  - source token: `MEASUREMENT_BEDSIDE//13061//°C`
  - row count: `546`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Temp Oraal`
  - raw unit: `°C`

### crea, Creatinine, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/creatinine.yml`; OMOP concept IDs `3020564`

match 1:
  - decision: `keep`
  - decision reason: `Explicit blood compartment ("bloed"), dominant row count, standard primary creatinine lab assay -- clear keep.`
  - table: `numericitems`
  - itemid: `9941`
  - source token: `LAB//9941//µmol/l`
  - row count: `196186`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Creatinine`
  - raw label: `Kreatinine (bloed)`
  - raw unit: `µmol/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated but unit (µmol, a truncated form of µmol/l) matches the explicit-blood sibling primary item (match 1), fitting the doctrine's legacy-itemid-safe-to-keep pattern exactly.`
  - table: `numericitems`
  - itemid: `6836`
  - source token: `LAB//6836//µmol`
  - row count: `6481`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Kreatinine`
  - raw unit: `µmol`

match 3:
  - decision: `needs_policy`
  - decision reason: `Explicit blood compartment confirms same specimen, but Jaffe (implied primary/legacy method) vs enzymatic creatinine assays are well-documented as non-interchangeable on the same numeric scale -- Jaffe is subject to positive interference from bilirubin/glucose/ketones/proteins common in ICU patients, causing systematic overestimation, which is exactly the non-interchangeable-scale caveat in doctrine point 3. Revised from an unqualified keep to needs_policy so a canonical-method or bias-adjustment rule is decided before merging into one direct_numeric series.`
  - table: `numericitems`
  - itemid: `14216`
  - source token: `LAB//14216//µmol/l`
  - row count: `33`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `KREAT enzym. (bloed)`
  - raw unit: `µmol/l`

### urine_rate, Urine Rate Per Hour, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mL/h`
- Reconstruction type: `derived_output_rate`
- Mapping status: `source_candidates_found`
- Notes: `Raw fluid-output rows exist; hourly urine-rate construction is a derived step.`

match 1:
  - decision: `keep`
  - decision reason: `UrineCAD (indwelling catheter, 'catheter a demeure') is the correct specimen and dominant volume channel for urine output; ml unit is appropriate for the derived rate.`
  - table: `numericitems`
  - itemid: `8794`
  - source token: `SUBJECT_FLUID_OUTPUT//8794//ml`
  - row count: `1605279`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:UrineCAD`
  - raw label: `UrineCAD`
  - raw unit: `ml`

match 2:
  - decision: `reject`
  - decision reason: `Thoracic drain output is pleural fluid, a completely different fluid than urine; correctly excluded.`
  - table: `numericitems`
  - itemid: `8699`
  - source token: `SUBJECT_FLUID_OUTPUT//8699//ml`
  - row count: `176066`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Thoraxdrain1 Productie`
  - raw unit: `ml`

match 3:
  - decision: `reject`
  - decision reason: `Ontlasting is stool output, unrelated to urine.`
  - table: `numericitems`
  - itemid: `8789`
  - source token: `SUBJECT_FLUID_OUTPUT//8789//ml`
  - row count: `98698`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Ontlasting`
  - raw unit: `ml`

match 4:
  - decision: `reject`
  - decision reason: `CVVH ultrafiltrate is machine-driven dialysis fluid removal, mechanistically distinct from kidney-produced urine; correctly excluded.`
  - table: `numericitems`
  - itemid: `8805`
  - source token: `SUBJECT_FLUID_OUTPUT//8805//ml`
  - row count: `92266`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `CVVH Onttrokken`
  - raw unit: `ml`

match 5:
  - decision: `reject`
  - decision reason: `Ventricular drain output is CSF, not urine.`
  - table: `numericitems`
  - itemid: `8770`
  - source token: `SUBJECT_FLUID_OUTPUT//8770//ml`
  - row count: `56491`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Ventrikeldrain1 Uit`
  - raw unit: `ml`

match 6:
  - decision: `reject`
  - decision reason: `Gastric suction output is GI fluid, unrelated to urine.`
  - table: `numericitems`
  - itemid: `8774`
  - source token: `SUBJECT_FLUID_OUTPUT//8774//ml`
  - row count: `53396`
  - evidence: `source_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Maaghevel`
  - raw unit: `ml`

match 7:
  - decision: `reject`
  - decision reason: `Discarded gastric residual is GI fluid, unrelated to urine.`
  - table: `numericitems`
  - itemid: `8777`
  - source token: `SUBJECT_FLUID_OUTPUT//8777//ml`
  - row count: `29453`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `MaagRetentieWeg`
  - raw unit: `ml`

match 8:
  - decision: `keep`
  - decision reason: `Revised: same itemid (8794, UrineCAD) via a different table route -- kept alongside match 1 with an explicit dedup rule downstream (pick one canonical route, don't sum) rather than rejected outright.`
  - table: `numericitems`
  - itemid: `8794`
  - source token: `MEASUREMENT_BEDSIDE//8794//ml`
  - row count: `27268`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:UrineCAD`
  - raw label: `UrineCAD`
  - raw unit: `ml`

match 9:
  - decision: `reject`
  - decision reason: `Second thoracic drain output is still pleural fluid, not urine.`
  - table: `numericitems`
  - itemid: `8700`
  - source token: `SUBJECT_FLUID_OUTPUT//8700//ml`
  - row count: `24169`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Thoraxdrain2 Productie`
  - raw unit: `ml`

match 10:
  - decision: `reject`
  - decision reason: `Wound drain output is not urine.`
  - table: `numericitems`
  - itemid: `8717`
  - source token: `SUBJECT_FLUID_OUTPUT//8717//ml`
  - row count: `23484`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Wonddrain1 Productie`
  - raw unit: `ml`

match 11:
  - decision: `keep`
  - decision reason: `UrineSupraPubis is a legitimate alternate urine-collection route (suprapubic catheter) -- same target fluid, different device, valid concurrent MTO source per the multi-route doctrine.`
  - table: `numericitems`
  - itemid: `8796`
  - source token: `SUBJECT_FLUID_OUTPUT//8796//ml`
  - row count: `15381`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:UrineSupraPubis`
  - raw label: `UrineSupraPubis`
  - raw unit: `ml`

match 12:
  - decision: `keep`
  - decision reason: `UrineSpontaan is spontaneously voided urine -- a valid concurrent route used when the patient is not catheterized.`
  - table: `numericitems`
  - itemid: `8798`
  - source token: `SUBJECT_FLUID_OUTPUT//8798//ml`
  - row count: `14230`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `UrineSpontaan`
  - raw unit: `ml`

match 13:
  - decision: `reject`
  - decision reason: `Second wound drain output is not urine.`
  - table: `numericitems`
  - itemid: `8719`
  - source token: `SUBJECT_FLUID_OUTPUT//8719//ml`
  - row count: `9715`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Wonddrain2 Productie`
  - raw unit: `ml`

match 14:
  - decision: `reject`
  - decision reason: `Wound leakage is not urine.`
  - table: `numericitems`
  - itemid: `9626`
  - source token: `SUBJECT_FLUID_OUTPUT//9626//ml`
  - row count: `6884`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Wondlekkage`
  - raw unit: `ml`

match 15:
  - decision: `keep`
  - decision reason: `ml unit and the 'Urine' label prefix confirm this is a urine-volume channel, following the same naming pattern as the confirmed UrineCAD/UrineSupraPubis/UrineSpontaan items; keep as another concurrent urine collection/measurement route even though the exact meaning of the 'UP' suffix is not fully documented -- specimen and quantity are clear, unlike a true undocumented-device case.`
  - table: `numericitems`
  - itemid: `8803`
  - source token: `SUBJECT_FLUID_OUTPUT//8803//ml`
  - row count: `6499`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `UrineUP`
  - raw unit: `ml`

match 16:
  - decision: `reject`
  - decision reason: `Lumbar drain output is CSF, not urine.`
  - table: `numericitems`
  - itemid: `9360`
  - source token: `SUBJECT_FLUID_OUTPUT//9360//ml`
  - row count: `5798`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Lumbaaldrain Uit`
  - raw unit: `ml`

match 17:
  - decision: `reject`
  - decision reason: `Vomit (Braken) is GI fluid, not urine.`
  - table: `numericitems`
  - itemid: `8780`
  - source token: `SUBJECT_FLUID_OUTPUT//8780//ml`
  - row count: `4848`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Braken`
  - raw unit: `ml`

match 18:
  - decision: `reject`
  - decision reason: `Ileostomy output is enteric fluid, not urine.`
  - table: `numericitems`
  - itemid: `8786`
  - source token: `SUBJECT_FLUID_OUTPUT//8786//ml`
  - row count: `4829`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Ileostoma`
  - raw unit: `ml`

match 19:
  - decision: `keep`
  - decision reason: `Revised: nephrostomy output is physiologically urine via a different route, additive to contralateral bladder urine for an obstructed kidney -- kept, with an explicit additive-combination rule downstream rather than a plain reject or naive sum.`
  - table: `numericitems`
  - itemid: `10745`
  - source token: `SUBJECT_FLUID_OUTPUT//10745//ml`
  - row count: `3854`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Nefrodrain re Uit`
  - raw unit: `ml`

match 20:
  - decision: `reject`
  - decision reason: `Third thoracic drain output is still pleural fluid, not urine.`
  - table: `numericitems`
  - itemid: `8701`
  - source token: `SUBJECT_FLUID_OUTPUT//8701//ml`
  - row count: `3557`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:SUBJECT_FLUID_OUTPUT`
  - raw label: `Thoraxdrain3 Productie`
  - raw unit: `ml`

### po2, Partial Pressure Of Oxygen, observation, respiratory

- Decision: `MTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/O2_partial_pressure.yml`; OMOP concept IDs `3027315|3027801`

match 1:
  - decision: `keep`
  - decision reason: `itemid=9996 "PO2 (bloed)" in mmHg is the explicit, dominant blood-compartment PO2 measurement -- unambiguous primary source.`
  - table: `numericitems`
  - itemid: `9996`
  - source token: `LAB//9996//mmHg`
  - row count: `654417`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PO2 (bloed)`
  - raw unit: `mmHg`

match 2:
  - decision: `keep`
  - decision reason: `itemid=7433 "PO2" has no compartment in its label, but per the doctrine's safe-legacy-pattern rule its sibling primary item (match 1) is explicitly "(bloed)" and units match exactly (mmHg=mmHg), so it is correctly inferred as the same blood PO2 measurement from a legacy pipeline path rather than a different specimen.`
  - table: `numericitems`
  - itemid: `7433`
  - source token: `LAB//7433//mmHg`
  - row count: `25372`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PO2`
  - raw unit: `mmHg`

match 3:
  - decision: `keep`
  - decision reason: `itemid=21214 "PO2 (bloed) - kPa" is the same blood-compartment PO2 analyte recorded in the alternate SI unit kPa (standard in Dutch clinical practice); kPa-to-mmHg is an exact linear conversion (~x7.5), so this is a legitimate concurrent source needing unit normalization at extraction, not a different concept or a non-interchangeable-scale issue that would warrant needs_policy.`
  - table: `numericitems`
  - itemid: `21214`
  - source token: `LAB//21214//kPa`
  - row count: `9392`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PO2 (bloed) - kPa`
  - raw unit: `kPa`

### ethnic, Ethnic Group, demographic, not specified

- Decision: `OTO`
- Target unit: `categorical`
- Reconstruction type: `unavailable`
- Mapping status: `needs_policy`
- Notes: `Confirmed no true ethnicity/race field exists in AmsterdamUMCdb -- checked supplied_vocab.csv and the official AmsterdamUMCdb OMOP dictionary. The closest available item is "PatientNationaliteit" (patient nationality/citizenship, listitems itemid 10468), which the official dictionary loosely crosswalks to SNOMED "Ethnicity / related nationality data" (186034007) purely for lack of a better OMOP target -- nationality is legally and conceptually distinct from ethnicity in the Netherlands (e.g. a Dutch-born patient of Moroccan or Turkish descent still records as "Nederlandse"), and the distribution is heavily skewed to Dutch (>75% of the ~750 recorded rows). One value ("Japanse") is inconsistently mapped to an actual Race concept instead of the generic Ethnicity crosswalk, underscoring how ad hoc this mapping is. Listed below for policy review, not as a validated ethnicity source -- most likely reject.`

match 1:
  - decision: `reject`
  - decision reason: `Nationality (Nederlandse) is a citizenship/administrative attribute, not ethnicity; per the established feature notes this is a conceptually distinct variable in the Dutch context and must be rejected outright, not used as a proxy, regardless of its large row count.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `8`
  - source token: `MEASUREMENT_CATEGORICAL//10468//8`
  - row count: `454`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Nederlandse`

match 2:
  - decision: `reject`
  - decision reason: `Same PatientNationaliteit item, value 'NL' -- still nationality, not ethnicity; reject for the same conceptual-mismatch reason as the rest of the item.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `10`
  - source token: `MEASUREMENT_CATEGORICAL//10468//10`
  - row count: `145`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `NL`

match 3:
  - decision: `reject`
  - decision reason: `'Overig (Other)' is a residual nationality bucket, not an ethnicity category; rejecting the whole source item applies uniformly here too.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `23`
  - source token: `MEASUREMENT_CATEGORICAL//10468//23`
  - row count: `59`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Overig (Other)`

match 4:
  - decision: `reject`
  - decision reason: `German nationality is a citizenship value, not an ethnicity/race concept; reject consistent with the rest of the item.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `13`
  - source token: `MEASUREMENT_CATEGORICAL//10468//13`
  - row count: `15`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Duitse (German)`

match 5:
  - decision: `reject`
  - decision reason: `Turkish nationality is citizenship, not self-identified ethnicity; a Turkish citizen and a Dutch-born person of Turkish descent are not distinguished by this field, reinforcing the conceptual mismatch. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `18`
  - source token: `MEASUREMENT_CATEGORICAL//10468//18`
  - row count: `15`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Turkse (Turkish)`

match 6:
  - decision: `reject`
  - decision reason: `English nationality -- same nationality-vs-ethnicity mismatch as all other values under itemid 10468. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `14`
  - source token: `MEASUREMENT_CATEGORICAL//10468//14`
  - row count: `13`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Engelse (English)`

match 7:
  - decision: `reject`
  - decision reason: `Moroccan nationality is citizenship, not ethnicity; reject for consistency with the item-wide conceptual rejection.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `17`
  - source token: `MEASUREMENT_CATEGORICAL//10468//17`
  - row count: `8`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Marokkaanse (Moroccan)`

match 8:
  - decision: `reject`
  - decision reason: `Italian nationality -- citizenship value, not ethnicity. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `16`
  - source token: `MEASUREMENT_CATEGORICAL//10468//16`
  - row count: `6`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Italiaanse (Italian)`

match 9:
  - decision: `reject`
  - decision reason: `Belgian nationality -- citizenship value, not ethnicity; low row count (4) does not change the conceptual rejection basis. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `11`
  - source token: `MEASUREMENT_CATEGORICAL//10468//11`
  - row count: `4`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Belgische (Belgian)`

match 10:
  - decision: `reject`
  - decision reason: `French nationality -- citizenship value, not ethnicity. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `12`
  - source token: `MEASUREMENT_CATEGORICAL//10468//12`
  - row count: `3`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Franse (French)`

match 11:
  - decision: `reject`
  - decision reason: `Spanish nationality -- citizenship value, not ethnicity. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `15`
  - source token: `MEASUREMENT_CATEGORICAL//10468//15`
  - row count: `2`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Spaanse (Spanish)`

match 12:
  - decision: `reject`
  - decision reason: `'Marokkaanse_U_1' is a legacy/duplicate list-code variant of Moroccan nationality (the '_U_1' suffix likely denotes an alternate/unknown-subtype coding in the raw list, not a distinct concept); regardless of that suffix's exact meaning, it is still a nationality value and is rejected on the same conceptual grounds, not for being unclear.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `7`
  - source token: `MEASUREMENT_CATEGORICAL//10468//7`
  - row count: `2`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Marokkaanse_U_1`

match 13:
  - decision: `reject`
  - decision reason: `Russian nationality -- citizenship value, not ethnicity; row_count=1 does not create ambiguity here since the value itself is clearly a nationality label, not an uninterpretable artifact. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `20`
  - source token: `MEASUREMENT_CATEGORICAL//10468//20`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Russische (Russian)`

match 14:
  - decision: `reject`
  - decision reason: `Japanese nationality; note the official dictionary inconsistently crosswalks this specific value to an actual Race concept (38003584) unlike the generic-crosswalk treatment of the other rows -- but since the whole nationality field is being rejected as a non-equivalent proxy for this feature, that inconsistency doesn't change the outcome here. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `21`
  - source token: `MEASUREMENT_CATEGORICAL//10468//21`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Japanse (Japanese) -- mapped to Race concept 38003584, inconsistent with the other rows' Ethnicity-crosswalk mapping`

match 15:
  - decision: `reject`
  - decision reason: `'Duitse_U_1' is a legacy/duplicate list-code variant of German nationality; still a nationality value, rejected on the same conceptual-mismatch grounds as the rest of the item, not for interpretability reasons.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `4`
  - source token: `MEASUREMENT_CATEGORICAL//10468//4`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Duitse_U_1`

match 16:
  - decision: `reject`
  - decision reason: `Iraqi nationality -- citizenship value, not ethnicity; single-row count doesn't matter since the value is unambiguous and the rejection basis is conceptual. Reject.`
  - table: `listitems`
  - itemid: `10468`
  - valueid: `6`
  - source token: `MEASUREMENT_CATEGORICAL//10468//6`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Nationaliteit`
  - raw label: `PatiëntNationaliteit`
  - raw value: `Irakees (Iraqi)`


### alb, Albumin, observation, gastrointestinal

- Decision: `MTO`
- Target unit: `g/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/albumin.yml`; OMOP concept IDs `3024561|3028286`

match 1:
  - decision: `keep`
  - decision reason: `Dominant blood albumin via chemical (colorimetric) assay; compartment '(bloed)' and unit g/l both correct for target serum albumin.`
  - table: `numericitems`
  - itemid: `9937`
  - source token: `LAB//9937//g/l`
  - row count: `104004`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Alb.Chem (bloed)`
  - raw unit: `g/l`

match 2:
  - decision: `keep`
  - decision reason: `Legacy itemid with no compartment stated, but sibling primary (match 1) is explicit '(bloed)' with the same 'chemisch' assay label pattern and identical g/l unit -- matches the documented legacy carve-out.`
  - table: `numericitems`
  - itemid: `6801`
  - source token: `LAB//6801//g/l`
  - row count: `3064`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Albumine chemisch`
  - raw unit: `g/l`

match 3:
  - decision: `reject`
  - decision reason: `CSF (liquor) albumin is a blood-brain-barrier permeability marker (used for e.g. Reibergram/albumin ratio), a fundamentally different clinical concept from serum albumin.`
  - table: `numericitems`
  - itemid: `10116`
  - source token: `LAB//10116//mg/l`
  - row count: `329`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Albumin`
  - raw label: `Albumine (imm.) (liquor)`
  - raw unit: `mg/l`

match 4:
  - decision: `reject`
  - decision reason: `Urine microalbumin is a proteinuria/renal marker, not serum albumin.`
  - table: `numericitems`
  - itemid: `10382`
  - source token: `LAB//10382//mg/l`
  - row count: `216`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Albumin`
  - raw label: `Micro-albumine (urine)`
  - raw unit: `mg/l`

match 5:
  - decision: `needs_policy`
  - decision reason: `Blood compartment and analyte match, but this is explicitly an immunoassay ('imm.') method versus the dominant chemical/BCG-type assay in matches 1-2 -- immunoassay and BCG-type colorimetric albumin methods are known to diverge (BCG overestimates in hypoalbuminemic ICU patients), so keep as a concurrent source but flag for an explicit method-priority/harmonization rule rather than a blind numeric merge.`
  - table: `numericitems`
  - itemid: `9975`
  - source token: `LAB//9975//g/l`
  - row count: `77`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Albumine (imm.) (bloed)`
  - raw unit: `g/l`

match 6:
  - decision: `keep`
  - decision reason: `Blood-compartment albumin fraction ('Fr') assay with matching g/l unit -- same analyte, distinct method from match 1, but on the same absolute concentration scale as target_unit.`
  - table: `numericitems`
  - itemid: `14349`
  - source token: `LAB//14349//g/l`
  - row count: `71`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Alb-Fr (bloed)`
  - raw unit: `g/l`

match 7:
  - decision: `unsure`
  - decision reason: `Same 'ALB.FR.' label family and blood compartment as match 6, but raw_unit is 'Geen' (none) rather than g/l -- this is atypical for a concentration test and may indicate this itemid actually stores a percentage/fraction value (different physical quantity from target g/dL) rather than an absolute concentration; cannot confirm scale compatibility from available metadata, so this is a genuine not-confident case rather than a policy question.`
  - table: `numericitems`
  - itemid: `11705`
  - source token: `LAB//11705//Geen`
  - row count: `59`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `ALB.FR. (bloed)`
  - raw unit: `Geen`

match 8:
  - decision: `reject`
  - decision reason: `24h-collection urine microalbumin -- same wrong compartment/concept as match 4.`
  - table: `numericitems`
  - itemid: `12241`
  - source token: `LAB//12241//mg/24uur`
  - row count: `30`
  - evidence: `source_vocab`
  - matched by: `term:Albumin`
  - raw label: `Micro-albumine (verz. urine)`
  - raw unit: `mg/24uur`

match 9:
  - decision: `reject`
  - decision reason: `Dialysate-fluid microalbumin reflects dialysis membrane clearance/adequacy, not serum albumin.`
  - table: `numericitems`
  - itemid: `10384`
  - source token: `LAB//10384//mg/l`
  - row count: `8`
  - evidence: `source_vocab`
  - matched by: `term:Albumin`
  - raw label: `Micro-albumine dialysaat (overig)`
  - raw unit: `mg/l`

### alp, Alkaline Phosphatase, observation, gastrointestinal

- Decision: `MTO`
- Target unit: `IU/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/alkaline_phosphatase.yml`; OMOP concept IDs `3035995`

match 1:
  - decision: `keep`
  - decision reason: `Raw label explicitly states blood compartment ("bloed") and unit E/l (eenheden per liter) matches target IU/L; this is the primary/dominant blood ALP source.`
  - table: `numericitems`
  - itemid: `11984`
  - source token: `LAB//11984//E/l`
  - row count: `59711`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Alkaline Phosphatase`
  - raw label: `Alk.Fosf. (bloed)`
  - raw unit: `E/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated in label, but per doctrine this is safe to keep as blood since its sibling primary itemid (11984) is explicitly "(bloed)" and units match (IE/l = Internationale Eenheden/l = IU/L, same as E/l). Legitimate legacy/secondary evidence route for the same analyte, not a double count of the same itemid.`
  - table: `numericitems`
  - itemid: `6803`
  - source token: `LAB//6803//IE/l`
  - row count: `1971`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Alk. Fosfatase`
  - raw unit: `IE/l`

### alt, Alanine Aminotransferase, observation, gastrointestinal

- Decision: `MTO`
- Target unit: `IU/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/alanine_aminotransferase.yml`; OMOP concept IDs `3006923`

match 1:
  - decision: `keep`
  - decision reason: `Explicitly blood-compartment ("bloed"), correct analyte (ALAT=ALT), unit E/l is Dutch shorthand for U/L which is dimensionally equivalent to target IU/L for enzyme activity; dominant primary source.`
  - table: `numericitems`
  - itemid: `11978`
  - source token: `LAB//11978//E/l`
  - row count: `77264`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `ALAT (bloed)`
  - raw unit: `E/l`

match 2:
  - decision: `keep`
  - decision reason: `Legacy itemid with no compartment stated, but sibling primary item (11978) is explicitly blood, and unit IE/l (Internationale Eenheden/l = IU/L) matches target unit exactly -- fits the documented safe legacy-itemid pattern rather than being a red flag.`
  - table: `numericitems`
  - itemid: `6800`
  - source token: `LAB//6800//IE/l`
  - row count: `2185`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `ALAT`
  - raw unit: `IE/l`

### ast, Aspartate Aminotransferase, observation, gastrointestinal

- Decision: `MTO`
- Target unit: `IU/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/aspartate_aminotransferase.yml`; OMOP concept IDs `3013721`

match 1:
  - decision: `keep`
  - decision reason: `ASAT (bloed) = Aspartate Aminotransferase, blood compartment explicitly stated, unit E/l is the Dutch enzyme-unit equivalent of IU/L. Clear direct match to target.`
  - table: `numericitems`
  - itemid: `11990`
  - source token: `LAB//11990//E/l`
  - row count: `76229`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `ASAT (bloed)`
  - raw unit: `E/l`

match 2:
  - decision: `keep`
  - decision reason: `Legacy itemid with no compartment stated, but its sibling primary item (match 1) is explicitly (bloed) and units match (IE/l = E/l = IU/L, both Dutch notations for international/enzyme units) — fits doctrine rule 1's safe-legacy-blood pattern exactly.`
  - table: `numericitems`
  - itemid: `6806`
  - source token: `LAB//6806//IE/l`
  - row count: `2187`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `ASAT`
  - raw unit: `IE/l`

### be, Base Excess, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mmol/l`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/base_excess.yml`; OMOP concept IDs `3012501`

match 1:
  - decision: `keep`
  - decision reason: `Explicit blood-compartment label "B.E. (bloed)" with correct unit (mmol/l) and by far the dominant volume; unambiguous direct match for blood base excess.`
  - table: `numericitems`
  - itemid: `9994`
  - source token: `LAB//9994//mmol/l`
  - row count: `654665`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `B.E. (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated, but its sibling primary itemid 9994 is explicitly "(bloed)" and units match exactly (mmol/l) -- per doctrine this is the standard legacy-itemid pattern in this vocabulary, safe to keep as blood, not a red flag despite the ~26x lower row count.`
  - table: `numericitems`
  - itemid: `6807`
  - source token: `LAB//6807//mmol/l`
  - row count: `25210`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `B.E.`
  - raw unit: `mmol/l`

### bicar, Bicarbonate, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mmol/l`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/bicarbonate.yml`; OMOP concept IDs `3006576`

match 1:
  - decision: `keep`
  - decision reason: `"Act.HCO3 (bloed)" is actual bicarbonate from a blood-gas analyzer, explicit blood compartment, units match target (mmol/l), and it is the dominant-volume primary source. Draft confirmed.`
  - table: `numericitems`
  - itemid: `9992`
  - source token: `LAB//9992//mmol/l`
  - row count: `657442`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Bicarbonate`
  - raw label: `Act.HCO3 (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `"HCO3" states no compartment but its sibling primary item (9992) is explicitly blood and units match (mmol/l=mmol/l), fitting the doctrine's safe-legacy-itemid pattern; row-count gap is expected for a legacy/superseded itemid, not a red flag. Draft confirmed.`
  - table: `numericitems`
  - itemid: `6810`
  - source token: `LAB//6810//mmol/l`
  - row count: `25251`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `HCO3`
  - raw unit: `mmol/l`

### bili, Total Bilirubin, observation, gastrointestinal

- Decision: `MTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/total_bilirubin.yml`; OMOP concept IDs `3006140|40757494`

match 1:
  - decision: `keep`
  - decision reason: `Raw label explicitly states blood compartment ('bloed'), matching the target serum/blood total bilirubin concept; unit µmol/L is directly convertible to mg/dL (÷17.1). Dominant row count as expected for the primary/current-era item.`
  - table: `numericitems`
  - itemid: `9945`
  - source token: `LAB//9945//µmol/l`
  - row count: `57386`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Bilirubine (bloed)`
  - raw unit: `µmol/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated in the label, but per doctrine this is safe to treat as blood since the sibling primary item (match 1) is explicitly '(bloed)' and the unit is consistent (raw 'µmol' is a truncated form of µmol/L -- a total-body µmol figure would not make sense for a lab result and no urine/CSF/dialysate qualifier is present). Legacy itemid for the same analyte, likely an earlier-era equivalent of the primary item.`
  - table: `numericitems`
  - itemid: `6813`
  - source token: `LAB//6813//µmol`
  - row count: `1720`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Bili Totaal`
  - raw unit: `µmol`

### bili_dir, Bilirubin Direct, observation, gastrointestinal

- Decision: `OTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/bilirubin_direct.yml`; OMOP concept IDs `3043744`

match 1:
  - decision: `unsure`
  - decision reason: `Confirmed: 'Gecon.Bili (bloed)' = geconjugeerd (conjugated) bilirubin in blood, which is the standard clinical proxy for 'direct' bilirubin (diazo-direct-reacting ~ conjugated fraction) and correct compartment -- concept and specimen match are sound. But raw_unit 'x TOT' is not a recognized concentration unit (not umol/L or mg/dL); it plausibly denotes a dimensionless ratio/fraction of total bilirubin (a real secondary lab metric some Dutch labs report alongside the absolute value), which would be a wrong-dimension candidate per the physical-quantity-mismatch rule rather than a direct_numeric concentration. Cannot confirm from the label alone whether 'x TOT' is a genuine ratio channel or a data-dictionary artifact for a mislabeled molar unit -- this needs inspection of the actual value distribution (ratio would cluster ~0-1; a molar concentration would show typical bilirubin ranges) before treating it as a valid mg/dL source. Draft's 'unsure' call is correct and is kept as final.`
  - table: `numericitems`
  - itemid: `12079`
  - source token: `LAB//12079//x TOT`
  - row count: `4317`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Gecon.Bili (bloed)`
  - raw unit: `x TOT`

### bnd, Band Form Neutrophils, observation, infection

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/band_form_neutrophils.yml`; OMOP concept IDs `3004809`

match 1:
  - decision: `keep`
  - decision reason: `"Staaf % (bloed)" is explicitly blood compartment, dominant row volume (1905), and raw_unit 'Geen' (dimensionless) is the typical AUMCdb pattern for a % value with no separate unit tag -- matches target_unit=% directly.`
  - table: `numericitems`
  - itemid: `11586`
  - source token: `LAB//11586//Geen`
  - row count: `1905`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Staaf % (bloed)`
  - raw unit: `Geen`

match 2:
  - decision: `needs_policy`
  - decision reason: `Label 'Staafkernig' (band-form/rod nucleus neutrophils) is the same analyte and its sibling primary item is explicitly '(bloed)', which per doctrine #1 would normally support keep -- but unlike match 1, no raw_unit at all is given here (not even 'Geen'), so it's unconfirmed whether this legacy item reports % or an absolute differential count; combined with the very low row count (7), verify the numeric scale against actual values before merging it as an MTO source for the % feature rather than defaulting to keep.`
  - table: `numericitems`
  - itemid: `6796`
  - source token: `LAB//6796//UNKNOWN`
  - row count: `7`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Staafkernig`

### bun, Blood Urea Nitrogen, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/blood_urea_nitrogen.yml`; OMOP concept IDs `43534077`

match 1:
  - decision: `keep`
  - decision reason: `Raw label explicitly states blood compartment ("bloed"), correct analyte for BUN (urea nitrogen is derived from serum urea), and unit mismatch (mmol/L vs target mg/dL) is a routine extraction-time conversion (BUN mg/dL = urea mmol/L x 2.8), not a concept mismatch. Draft is correct.`
  - table: `numericitems`
  - itemid: `9943`
  - source token: `LAB//9943//mmol/l`
  - row count: `107581`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Blood Urea Nitrogen`
  - raw label: `Ureum (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated, but per doctrine rule 1 this is safe to treat as blood because its sibling primary item (match 1) is explicitly "(bloed)" and the units match exactly (mmol/l vs mmol/l) -- classic legacy-itemid pattern in this dataset, not a red flag. Draft is correct.`
  - table: `numericitems`
  - itemid: `6850`
  - source token: `LAB//6850//mmol/l`
  - row count: `3138`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ureum`
  - raw unit: `mmol/l`

### ca, Calcium, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/calcium.yml`; OMOP concept IDs `3015377`

match 1:
  - decision: `keep`
  - decision reason: `Explicitly blood-compartment total calcium ('(bloed)'), dominant row count, correct unit family -- clearly the primary serum calcium source.`
  - table: `numericitems`
  - itemid: `9933`
  - source token: `LAB//9933//mmol/l`
  - row count: `140461`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Calcium`
  - raw label: `Calcium totaal (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated, but sibling primary item (9933) is explicitly '(bloed)' and units match (mmol/l) -- fits the documented legacy-itemid pattern for this dataset, safe to treat as blood total calcium.`
  - table: `numericitems`
  - itemid: `6817`
  - source token: `LAB//6817//mmol/l`
  - row count: `5339`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Calcium`
  - raw unit: `mmol/l`

match 3:
  - decision: `reject`
  - decision reason: `Explicit '(urine)' compartment -- urine total calcium is a renal/stone-risk marker, a different clinical concept from serum calcium.`
  - table: `numericitems`
  - itemid: `10275`
  - source token: `LAB//10275//mmol/l`
  - row count: `70`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Calcium`
  - raw label: `Calcium totaal (urine)`
  - raw unit: `mmol/l`

match 4:
  - decision: `reject`
  - decision reason: `'(overig)'/other is a stated non-blood compartment per doctrine; must be rejected outright like other other-fluid candidates, not merely deprioritized.`
  - table: `numericitems`
  - itemid: `9934`
  - source token: `LAB//9934//mmol/l`
  - row count: `28`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Calcium`
  - raw label: `CALCIUM (overig)`
  - raw unit: `mmol/l`

match 5:
  - decision: `reject`
  - decision reason: `24h urine-collection calcium -- same wrong renal-handling concept as match 3, not serum calcium.`
  - table: `numericitems`
  - itemid: `10276`
  - source token: `LAB//10276//mmol/l`
  - row count: `22`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Calcium`
  - raw label: `CALCIUM (verz. urine)`
  - raw unit: `mmol/l`

match 6:
  - decision: `reject`
  - decision reason: `24h urine-collection total calcium (units mmol/24uur confirm timed urine collection) -- same wrong concept as match 3.`
  - table: `numericitems`
  - itemid: `12217`
  - source token: `LAB//12217//mmol/24uur`
  - row count: `19`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Calcium`
  - raw label: `Calcium totaal (verz. urine)`
  - raw unit: `mmol/24uur`

match 7:
  - decision: `reject`
  - decision reason: `Dialysate-fluid calcium reflects the dialysis solution composition, not the patient's serum calcium -- different clinical concept entirely.`
  - table: `numericitems`
  - itemid: `18852`
  - source token: `LAB//18852//mmol/l`
  - row count: `11`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Calcium`
  - raw label: `Calcium (dialysaat)`
  - raw unit: `mmol/l`

match 8:
  - decision: `reject`
  - decision reason: `Despite the ambiguous '(overig)' tag, the µmol/24uur unit indicates a timed (24h) collection rather than a blood spot sample, consistent with a non-blood specimen like match 4/6 -- reject rather than unsure since the unit itself is diagnostic of a non-blood collection, even at n=1.`
  - table: `numericitems`
  - itemid: `12216`
  - source token: `LAB//12216//µmol/24uur`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Calcium`
  - raw label: `CALCIUM      (overig)`
  - raw unit: `µmol/24uur`

### cai, Calcium Ionized, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mmol/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/calcium_ionized.yml`; OMOP concept IDs `3021119|3048816`

match 1:
  - decision: `keep`
  - decision reason: `Explicit blood compartment '(bloed)' and explicit pH-7.4 correction, matching unit (mmol/l), and by far the dominant volume -- clearly the primary source.`
  - table: `numericitems`
  - itemid: `10267`
  - source token: `LAB//10267//mmol/l`
  - row count: `480104`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ca-ion (7.4) (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `needs_policy`
  - decision reason: `Label 'Ca++ Astrup' omits the '(7.4)' correction marker present in matches 1/3/4, indicating this is likely the measured/uncorrected ionized calcium at the sample's actual pH rather than the pH-7.4-standardized value -- same analyte but a potentially non-interchangeable numeric scale (doctrine #3), so pooling it with the corrected channels needs an explicit rule rather than a blanket keep.`
  - table: `numericitems`
  - itemid: `9560`
  - source token: `LAB//9560//mmol/l`
  - row count: `16774`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ca++ Astrup`
  - raw unit: `mmol/l`

match 3:
  - decision: `keep`
  - decision reason: `Explicit '(7.4)' pH-correction marker puts it on the same numeric scale as the primary; a different Astrup-analyzer generation is a legitimate concurrent MTO source (doctrine #2).`
  - table: `numericitems`
  - itemid: `9561`
  - source token: `LAB//9561//mmol/l`
  - row count: `13584`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CA++(7.4) Astrup`
  - raw unit: `mmol/l`

match 4:
  - decision: `keep`
  - decision reason: `Legacy itemid with no compartment stated, but explicit '(7.4)' correction matches the primary's scale/units and the sibling primary item is explicitly blood -- doctrine #1's safe-legacy-itemid pattern applies; 38 rows is low but above the 1-5 'unsure' threshold.`
  - table: `numericitems`
  - itemid: `8915`
  - source token: `LAB//8915//mmol/l`
  - row count: `38`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CA++(7.4)`
  - raw unit: `mmol/l`

### ck, Creatine Kinase, observation, circulatory

- Decision: `MTO`
- Target unit: `IU/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/creatine_kinase.yml`; OMOP concept IDs `3007220`

match 1:
  - decision: `keep`
  - decision reason: `Raw label explicitly states blood compartment ("CK (bloed)"), unit E/l (Units/L) matches target IU/L, dominant row count as primary source. Draft confirmed.`
  - table: `numericitems`
  - itemid: `11998`
  - source token: `LAB//11998//E/l`
  - row count: `107983`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CK (bloed)`
  - raw unit: `E/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated, but per doctrine point 1 this is safe to keep as blood since its sibling primary itemid (11998) is explicitly "(bloed)" and units match (IE/l = Internationale Eenheden/l = IU/L, same as E/l). Classic legacy-itemid pattern in this dataset, not a red flag. Draft confirmed.`
  - table: `numericitems`
  - itemid: `6822`
  - source token: `LAB//6822//IE/l`
  - row count: `4355`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CK`
  - raw unit: `IE/l`

### ckmb, Creatine Kinase MB, observation, circulatory

- Decision: `MTO`
- Target unit: `ng/mL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/creatine_kinase_MB.yml`; OMOP concept IDs `3005785|3029790`

match 1:
  - decision: `keep`
  - decision reason: `MB-Massa (bloed) in µg/l is numerically identical to ng/mL (1 µg/L = 1 ng/mL), directly matching the target unit; blood compartment stated, dominant volume confirms this is the primary modern CK-MB mass immunoassay. Draft confirmed.`
  - table: `numericitems`
  - itemid: `10413`
  - source token: `LAB//10413//µg/l`
  - row count: `59014`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `MB-Massa (bloed)`
  - raw unit: `µg/l`

match 2:
  - decision: `needs_policy`
  - decision reason: `IE/l is a classic enzyme-activity-based CK-MB unit, not mass concentration -- same protein as match 1 but a non-interchangeable numeric scale (activity vs mass), exactly the doctrine's called-out CK-MB two-methods case. Draft confirmed.`
  - table: `numericitems`
  - itemid: `6824`
  - source token: `LAB//6824//IE/l`
  - row count: `2315`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CK-MB`
  - raw unit: `IE/l`

match 3:
  - decision: `needs_policy`
  - decision reason: `Revised from unsure: "MB (bloed)" with unit E/l (= eenheden/liter, same unit family as match 2's IE/l) is the same enzyme-activity-based CK-MB pattern as match 2, with blood compartment explicitly stated and an omop_id match specifically to the CKMB concept -- not a generic/ambiguous label once cross-referenced against match 2. Most likely a legacy duplicate itemid from one of AUMCdb's two merged source-hospital LIS systems (AMC/VUmc), rarely used (3 rows) before phase-out. It should be grouped with match 2 under the same activity-vs-mass scale-reconciliation policy rather than left as an unresolved unsure.`
  - table: `numericitems`
  - itemid: `12048`
  - source token: `LAB//12048//E/l`
  - row count: `3`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `MB (bloed)`
  - raw unit: `E/l`

### cl, Chloride, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mmol/l`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/chloride.yml`; OMOP concept IDs `3014576|3018572`

match 1:
  - decision: `keep`
  - decision reason: `Explicit "(bloed)" compartment, ISE method, mmol/l matches target unit and is the dominant modern blood chloride channel.`
  - table: `numericitems`
  - itemid: `14413`
  - source token: `LAB//14413//mmol/l`
  - row count: `343919`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Cl (onv.ISE) (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `Explicit "(bloed)" compartment, same analyte via an alternate/older method; interchangeable mmol/l scale, valid concurrent source per multi-method MTO doctrine.`
  - table: `numericitems`
  - itemid: `9930`
  - source token: `LAB//9930//mmol/l`
  - row count: `178659`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Chloor (bloed)`
  - raw unit: `mmol/l`

match 3:
  - decision: `keep`
  - decision reason: `"Astrup" is Dutch clinical shorthand for blood-gas analysis (named after Poul Astrup), inherently performed on arterial/venous blood, so compartment is blood despite no explicit "(bloed)" tag; same analyte, matching unit, consistent with the doctrine's allowance for same-analyte-different-blood-gas-analyzer sources.`
  - table: `numericitems`
  - itemid: `9558`
  - source token: `LAB//9558//mmol/l`
  - row count: `2899`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Chloor Astrup`
  - raw unit: `mmol/l`

match 4:
  - decision: `keep`
  - decision reason: `Legacy itemid "Chloor" with no stated compartment, but sibling primary item (itemid 9930) is explicitly "(bloed)" with matching mmol/l units, satisfying the doctrine's exception for uncompartmented legacy itemids to default to blood.`
  - table: `numericitems`
  - itemid: `6819`
  - source token: `LAB//6819//mmol/l`
  - row count: `1443`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Chloor`
  - raw unit: `mmol/l`

### crp, C-Reactive Protein, observation, infection

- Decision: `MTO`
- Target unit: `mg/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/C_reactive_protein.yml`; OMOP concept IDs `3020460`

match 1:
  - decision: `keep`
  - decision reason: `Explicit blood compartment "(bloed)", unit mg/l matches target mg/L, and it is the dominant-volume itemid — correct keep, no revision.`
  - table: `numericitems`
  - itemid: `10079`
  - source token: `LAB//10079//mg/l`
  - row count: `82347`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CRP (bloed)`
  - raw unit: `mg/l`

match 2:
  - decision: `keep`
  - decision reason: `No compartment stated, but per doctrine point 1 a compartment-less legacy itemid is safe to keep as blood when its sibling primary item is explicitly "(bloed)" and units match (mg/l = mg/l here); CRP is not a test typically run on non-blood specimens, so no compartment ambiguity concern applies.`
  - table: `numericitems`
  - itemid: `6825`
  - source token: `LAB//6825//mg/l`
  - row count: `399`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CRP`
  - raw unit: `mg/l`

### dbp, Diastolic Blood Pressure, observation, circulatory

- Decision: `MTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/diastolic_blood_pressure.yml`; OMOP concept IDs `21490851|21492240`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6643`
  - source token: `MEASUREMENT_BEDSIDE//6643//mmHg`
  - row count: `33343274`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diastolic Blood Pressure`
  - raw label: `ABP diastolisch`
  - raw unit: `mmHg`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6680`
  - source token: `MEASUREMENT_BEDSIDE//6680//mmHg`
  - row count: `190431`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diastolic Blood Pressure`
  - raw label: `Niet invasieve bloeddruk diastolisch`
  - raw unit: `mmHg`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `8842`
  - source token: `MEASUREMENT_BEDSIDE//8842//mmHg`
  - row count: `54598`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `ABP diastolisch II`
  - raw unit: `mmHg`

match 4:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `14057`
  - source token: `MEASUREMENT_BEDSIDE//14057//mmHg`
  - row count: `4628`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PiCCO APd`
  - raw unit: `mmHg`

### fgn, Fibrinogen, observation, circulatory

- Decision: `MTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/fibrinogen.yml`; OMOP concept IDs `3016407`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags.`
  - table: `numericitems`
  - itemid: `10175`
  - source token: `LAB//10175//g/l`
  - row count: `2744`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Fibrinogeen  (bloed)`
  - raw unit: `g/l`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags.`
  - table: `numericitems`
  - itemid: `9989`
  - source token: `LAB//9989//g/l`
  - row count: `1444`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Fibrinogeen (bloed)`
  - raw unit: `g/l`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags.`
  - table: `numericitems`
  - itemid: `6776`
  - source token: `LAB//6776//g/l`
  - row count: `35`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Fibrinogen`
  - raw label: `Fibrinogeen`
  - raw unit: `g/l`

### glu, Glucose, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/glucose.yml`; OMOP concept IDs `3020491`

match 1:
  - decision: `keep`
  - decision reason: `Glucose (bloed) -- blood, primary channel.`
  - table: `numericitems`
  - itemid: `9947`
  - source token: `LAB//9947//mmol/l`
  - row count: `820898`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Glucose (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `reject`
  - decision reason: `GRIP - RelativeGlucoseAfterFilter -- an advisory/computed ratio from the glycemic protocol (values cluster near 0-2, not raw glucose concentration), not a raw measurement.`
  - table: `numericitems`
  - itemid: `16821`
  - source token: `MEASUREMENT_BEDSIDE//16821//UNKNOWN`
  - row count: `88845`
  - evidence: `source_vocab`
  - matched by: `term:Glucose`
  - raw label: `GRIP - RelativeGlucoseAfterFilter`

match 3:
  - decision: `keep`
  - decision reason: `Glucose Astrup -- blood gas analyzer, tracks consistently with match 1.`
  - table: `numericitems`
  - itemid: `9557`
  - source token: `LAB//9557//mmol/l`
  - row count: `20195`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Glucose Astrup`
  - raw unit: `mmol/l`

match 4:
  - decision: `keep`
  - decision reason: `Glucose Bloed -- blood, duplicate/legacy code, tracks consistently with match 1.`
  - table: `numericitems`
  - itemid: `6833`
  - source token: `LAB//6833//mmol/l`
  - row count: `7892`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Glucose Bloed`
  - raw unit: `mmol/l`

match 5:
  - decision: `reject`
  - decision reason: `Glucose (liquor) -- CSF, wrong compartment.`
  - table: `numericitems`
  - itemid: `9949`
  - source token: `LAB//9949//mmol/l`
  - row count: `3218`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose (liquor)`
  - raw unit: `mmol/l`

match 6:
  - decision: `reject`
  - decision reason: `Glucose (overig) -- n=1 total, too little to be worth keeping regardless of the specimen ambiguity.`
  - table: `numericitems`
  - itemid: `9948`
  - source token: `LAB//9948//mmol/l`
  - row count: `317`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose (overig)`
  - raw unit: `mmol/l`

match 7:
  - decision: `reject`
  - decision reason: `Glucose pleuravocht -- pleural fluid, wrong compartment.`
  - table: `numericitems`
  - itemid: `18368`
  - source token: `LAB//18368//mmol/l`
  - row count: `176`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose pleuravocht (pleurapunct.)`
  - raw unit: `mmol/l`

match 8:
  - decision: `reject`
  - decision reason: `Glucose in Liquor -- CSF, wrong compartment, same issue as match 5.`
  - table: `numericitems`
  - itemid: `7796`
  - source token: `LAB//7796//mmol/l`
  - row count: `34`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose in Liquor`
  - raw unit: `mmol/l`

match 9:
  - decision: `reject`
  - decision reason: `Glucose ascitesvocht -- ascitic fluid, wrong compartment.`
  - table: `numericitems`
  - itemid: `18366`
  - source token: `LAB//18366//mmol/l`
  - row count: `27`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose ascitesvocht (ascitesvocht)`
  - raw unit: `mmol/l`

match 10:
  - decision: `reject`
  - decision reason: `GRIP - Glucose Management Groepsnummer -- a protocol group ID/classification code, not a glucose measurement at all.`
  - table: `numericitems`
  - itemid: `16494`
  - source token: `MEASUREMENT_BEDSIDE//16494//UNKNOWN`
  - row count: `19`
  - evidence: `source_vocab`
  - matched by: `term:Glucose`
  - raw label: `GRIP - Glucose Management Groepsnummer`

match 11:
  - decision: `reject`
  - decision reason: `Glucose drainvocht -- drain fluid, wrong compartment.`
  - table: `numericitems`
  - itemid: `18859`
  - source token: `LAB//18859//mmol/l`
  - row count: `17`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose drainvocht (drain)`
  - raw unit: `mmol/l`

### hgb, Hemoglobin, observation, circulatory

- Decision: `MTO`
- Target unit: `g/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/hemoglobin.yml`; OMOP concept IDs `40758903|40762351`

match 1:
  - decision: `keep`
  - decision reason: `blood hemoglobin, tracks consistently with the other matches across all 6 sampled patients.`
  - table: `numericitems`
  - itemid: `10286`
  - source token: `LAB//10286//mmol/l`
  - row count: `493874`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Hb(v.Bgs) (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `blood hemoglobin, tracks consistently with the other matches across all 6 sampled patients.`
  - table: `numericitems`
  - itemid: `9960`
  - source token: `LAB//9960//mmol/l`
  - row count: `216027`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Hemoglobin`
  - raw label: `Hb (bloed)`
  - raw unit: `mmol/l`

match 3:
  - decision: `keep`
  - decision reason: `blood hemoglobin, tracks consistently with the other matches across all 6 sampled patients.`
  - table: `numericitems`
  - itemid: `9553`
  - source token: `LAB//9553//mmol/l`
  - row count: `21409`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CtHB Astrup`
  - raw unit: `mmol/l`

match 4:
  - decision: `keep`
  - decision reason: `blood hemoglobin, tracks consistently with the other matches across all 6 sampled patients.`
  - table: `numericitems`
  - itemid: `6778`
  - source token: `LAB//6778//mmol/l`
  - row count: `7603`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Hemoglobine`
  - raw unit: `mmol/l`

match 5:
  - decision: `keep`
  - decision reason: `blood hemoglobin, tracks consistently with the other matches across all 6 sampled patients.`
  - table: `numericitems`
  - itemid: `19703`
  - source token: `LAB//19703//mmol/l`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Hb poct (bloed)`
  - raw unit: `mmol/l`

### inr_pt, Prothrombin, observation, circulatory

- Decision: `MTO`
- Target unit: `INR`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/prothrombin_time_international_normalized_ratio.yml`; OMOP concept IDs `3032080`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `11894`
  - source token: `LAB//11894//INR`
  - row count: `126843`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Prothrombinetijd  (bloed)`
  - raw unit: `INR`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `11893`
  - source token: `LAB//11893//INR`
  - row count: `66847`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Prothrombinetijd (bloed)`
  - raw unit: `INR`

### k, Potassium, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mmol/l`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/potassium.yml`; OMOP concept IDs `3005456|3023103`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `10285`
  - source token: `LAB//10285//mmol/l`
  - row count: `542007`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `K (onv.ISE) (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `9927`
  - source token: `LAB//9927//mmol/l`
  - row count: `220787`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Kalium (bloed)`
  - raw unit: `mmol/l`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `9556`
  - source token: `LAB//9556//mmol/l`
  - row count: `20082`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Kalium Astrup`
  - raw unit: `mmol/l`

match 4:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6835`
  - source token: `LAB//6835//mmol/l`
  - row count: `8612`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Kalium`
  - raw unit: `mmol/l`

### lymph, Lymphocytes, observation, infection

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/lymphocytes.yml`; OMOP concept IDs `3002030`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `11846`
  - source token: `LAB//11846//Geen`
  - row count: `4606`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Lymfocyten % (bloed)`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6781`
  - source token: `LAB//6781//UNKNOWN`
  - row count: `48`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Lymfocyten`

### methb, Methemoglobin, observation, circulatory

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/methemoglobin.yml`; OMOP concept IDs `3007930`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `14412`
  - source token: `LAB//14412//Geen`
  - row count: `334013`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Met-Hb  (bloed)`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `11692`
  - source token: `LAB//11692//Geen`
  - row count: `2714`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Met-Hb (bloed)`
  - raw unit: `Geen`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `7004`
  - source token: `LAB//7004//UNKNOWN`
  - row count: `145`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `FMetHb`

### mg, Magnesium, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/magnesium.yml`; OMOP concept IDs `3012095|3033836`

match 1:
  - decision: `keep`
  - decision reason: `Magnesium (bloed) -- blood, primary channel.`
  - table: `numericitems`
  - itemid: `9952`
  - source token: `LAB//9952//mmol/l`
  - row count: `127345`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Magnesium (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `Magnesium, unqualified specimen -- treated as implicit blood/serum per the same precedent used for ca/wbc/plt's unqualified duplicate codes.`
  - table: `numericitems`
  - itemid: `6839`
  - source token: `LAB//6839//mmol/l`
  - row count: `4633`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Magnesium`
  - raw unit: `mmol/l`

match 3:
  - decision: `reject`
  - decision reason: `urine, wrong compartment.`
  - table: `numericitems`
  - itemid: `10294`
  - source token: `LAB//10294//mmol/l`
  - row count: `62`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Magnesium`
  - raw label: `Magnesium (urine)`
  - raw unit: `mmol/l`

match 4:
  - decision: `keep`
  - decision reason: `Magnesium (overig) -- accepted per user policy.`
  - table: `numericitems`
  - itemid: `9953`
  - source token: `LAB//9953//mmol/l`
  - row count: `24`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Magnesium`
  - raw label: `Magnesium (overig)`
  - raw unit: `mmol/l`

match 5:
  - decision: `reject`
  - decision reason: `dialysaat, wrong compartment.`
  - table: `numericitems`
  - itemid: `18862`
  - source token: `LAB//18862//mmol/l`
  - row count: `10`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Magnesium`
  - raw label: `Magnesium (dialysaat)`
  - raw unit: `mmol/l`

match 6:
  - decision: `reject`
  - decision reason: `pooled urine, wrong compartment.`
  - table: `numericitems`
  - itemid: `10295`
  - source token: `LAB//10295//mmol/l`
  - row count: `7`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Magnesium`
  - raw label: `Magnesium  (verz. urine)`
  - raw unit: `mmol/l`

match 7:
  - decision: `reject`
  - decision reason: `pooled urine (24h total), wrong compartment and wrong unit (mmol/24uur, not a concentration).`
  - table: `numericitems`
  - itemid: `12232`
  - source token: `LAB//12232//mmol/24uur`
  - row count: `7`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Magnesium`
  - raw label: `Magnesium (verz. urine)`
  - raw unit: `mmol/24uur`

### na, Sodium, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mmol/l`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/sodium.yml`; OMOP concept IDs `3000285|3019550`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `10284`
  - source token: `LAB//10284//mmol/l`
  - row count: `527724`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Na (onv.ISE) (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `9924`
  - source token: `LAB//9924//mmol/l`
  - row count: `226219`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Natrium (bloed)`
  - raw unit: `mmol/l`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `9555`
  - source token: `LAB//9555//mmol/l`
  - row count: `19785`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Natrium Astrup`
  - raw unit: `mmol/l`

match 4:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6840`
  - source token: `LAB//6840//mmol/l`
  - row count: `8602`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Natrium`
  - raw unit: `mmol/l`

### neut, Neutrophils, observation, infection

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Found via supplied_vocab source-label search (term matcher missed these); not cross-checked against an independent source-vocab pull.`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `11856`
  - source token: `LAB//11856//Geen`
  - row count: `2805`
  - evidence: `supplied_vocab`
  - matched by: `term:Neutro`
  - raw label: `Neutro's % app (bloed)`
  - raw unit: `Geen (=%)`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `14254`
  - source token: `LAB//14254//10^9/l`
  - row count: `9382`
  - evidence: `supplied_vocab`
  - matched by: `term:Neutro`
  - raw label: `Neutro's app (bloed)`
  - raw unit: `10^9/l`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6786`
  - source token: `LAB//6786//UNKNOWN`
  - row count: `40`
  - evidence: `supplied_vocab`
  - matched by: `term:Neutrofielen`
  - raw label: `Neutrofielen`
  - raw unit: ``


### pco2, CO2 Partial Pressure, observation, respiratory

- Decision: `MTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/CO2_partial_pressure.yml`; OMOP concept IDs `3013290|3027946`

match 1:
  - decision: `keep`
  - decision reason: `pCO2 (bloed) -- already mmHg.`
  - table: `numericitems`
  - itemid: `9990`
  - source token: `LAB//9990//mmHg`
  - row count: `659807`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `pCO2 (bloed)`
  - raw unit: `mmHg`

match 2:
  - decision: `keep`
  - decision reason: `PCO2 -- already mmHg.`
  - table: `numericitems`
  - itemid: `6846`
  - source token: `LAB//6846//mmHg`
  - row count: `25348`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PCO2`
  - raw unit: `mmHg`

match 3:
  - decision: `keep`
  - decision reason: `PCO2 (bloed) - kPa -- convert to mmHg (x7.50062); plot confirms scale (~2-10 vs ~25-60 for matches 1/2, consistent with kPa vs mmHg).`
  - table: `numericitems`
  - itemid: `21213`
  - source token: `LAB//21213//kPa`
  - row count: `9464`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PCO2 (bloed) - kPa`
  - raw unit: `kPa`

### ph, pH Of Blood, observation, metabolic_renal

- Decision: `OTO`
- Target unit: `pH`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/pH_of_blood.yml`; OMOP concept IDs `3010421`
- Notes: `Revised 2026-07-14: originally only had match 1 (25371 rows), a suspiciously small pool given po2/pco2 (this feature's blood-gas-panel siblings) each have ~650-660k rows on their dominant primary channel. Match 1 turned out to be the same low-volume "legacy/no-compartment" pattern as po2's itemid 7433 and pco2's itemid 6846 (~25k rows each) -- the equivalent dominant "(bloed)" primary channel was missing entirely. Added match 2 below after a direct raw-label search (grid/_check_open_flags.py) found it.`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 25371 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `6848`
  - source token: `LAB//6848//UNKNOWN`
  - row count: `25371`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PH`

match 2:
  - decision: `keep`
  - decision reason: `pH (bloed) -- found 2026-07-14 via a direct raw numericitems label search, not the original matcher: this is the dominant primary blood-compartment pH channel, analogous to po2's itemid 9996 and pco2's itemid 9990 (match 1 above is only their low-volume legacy/no-compartment sibling pattern). Verified directly against the raw values: bulk range (p1-p99 = 7.14-7.54) is exactly physiological pH, and its outlier tail (0, negative, ~7500) already falls outside this feature's existing plausibility bound (6.0, 7.8), so no separate cleanup needed beyond the filter already in place. raw_unit 'Geen' correctly means dimensionless here (pH has no physical unit, matching the target) -- not a red flag, unlike hct's unrelated 'Geen' issue earlier this session.`
  - table: `numericitems`
  - itemid: `12310`
  - source token: `MEASUREMENT_BEDSIDE//12310//Geen`
  - row count: `577975`
  - evidence: `direct_raw_data_check`
  - matched by: `raw_label_search:pH`
  - raw label: `pH (bloed)`
  - raw unit: `Geen`

### phos, Phosphate, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `mg/dL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/phosphate.yml`; OMOP concept IDs `3003458`

match 1:
  - decision: `keep`
  - decision reason: `Fosfaat (bloed) -- convert mmol/L -> mg/dL (x3.097, based on phosphorus atomic weight ~31 g/mol).`
  - table: `numericitems`
  - itemid: `9935`
  - source token: `LAB//9935//mmol/l`
  - row count: `139031`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Phosphate`
  - raw label: `Fosfaat (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `Fosfaat -- same conversion as match 1, OMOP-linked secondary channel.`
  - table: `numericitems`
  - itemid: `6828`
  - source token: `LAB//6828//mmol/l`
  - row count: `5212`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Fosfaat`
  - raw unit: `mmol/l`

### plt, Platelet Count, observation, circulatory

- Decision: `MTO`
- Target unit: `G/l`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/platelet_count.yml`; OMOP concept IDs `3007461`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `9964`
  - source token: `LAB//9964//10^9/l`
  - row count: `214452`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Thrombo's (bloed)`
  - raw unit: `10^9/l`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6797`
  - source token: `LAB//6797//10^9/l`
  - row count: `7201`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Thrombocyten`
  - raw unit: `10^9/l`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `10409`
  - source token: `LAB//10409//10^9/l`
  - row count: `60`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Thrombo's citr. bloed (bloed)`
  - raw unit: `10^9/l`

### ptt, Partial Thromboplastin Time, observation, circulatory

- Decision: `MTO`
- Target unit: `sec`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/partial_thromboplastin_time.yml`; OMOP concept IDs `3013466`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags.`
  - table: `numericitems`
  - itemid: `11944`
  - source token: `LAB//11944//sec`
  - row count: `130281`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `APTT  (bloed)`
  - raw unit: `sec`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags.`
  - table: `numericitems`
  - itemid: `17982`
  - source token: `LAB//17982//sec`
  - row count: `68230`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `APTT (bloed)`
  - raw unit: `sec`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags.`
  - table: `numericitems`
  - itemid: `6771`
  - source token: `LAB//6771//sec`
  - row count: `5975`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Cephalinetyd`
  - raw unit: `sec`

match 4:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags.`
  - table: `numericitems`
  - itemid: `11945`
  - source token: `LAB//11945//sec`
  - row count: `386`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `CEF-KAOL.T (bloed)`
  - raw unit: `sec`

### sbp, Systolic Blood Pressure, observation, circulatory

- Decision: `MTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/systolic_blood_pressure.yml`; OMOP concept IDs `21490853|21492239`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6641`
  - source token: `MEASUREMENT_BEDSIDE//6641//mmHg`
  - row count: `33343613`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Systolic Blood Pressure`
  - raw label: `ABP systolisch`
  - raw unit: `mmHg`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6678`
  - source token: `MEASUREMENT_BEDSIDE//6678//mmHg`
  - row count: `192123`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Systolic Blood Pressure`
  - raw label: `Niet invasieve bloeddruk systolisch`
  - raw unit: `mmHg`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `8841`
  - source token: `MEASUREMENT_BEDSIDE//8841//mmHg`
  - row count: `54602`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `ABP systolisch II`
  - raw unit: `mmHg`

match 4:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `14056`
  - source token: `MEASUREMENT_BEDSIDE//14056//mmHg`
  - row count: `4646`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `PiCCO APs`
  - raw unit: `mmHg`

### tnt, Troponin T, observation, circulatory

- Decision: `MTO`
- Target unit: `ng/mL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/troponin_t.yml`; OMOP concept IDs `3019800|3048529`

match 1:
  - decision: `keep`
  - decision reason: `TroponineT (bloed) -- explicit Troponin T, primary channel. Unit ug/l = ng/mL already, no conversion needed.`
  - table: `numericitems`
  - itemid: `10407`
  - source token: `LAB//10407//µg/l`
  - row count: `23805`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `TroponineT (bloed)`
  - raw unit: `µg/l`

match 2:
  - decision: `keep`
  - decision reason: `Troponine (generic label) -- linked via the same reliable openicu_omop_id evidence as match 1; plot confirms near-identical concurrent values at matching timestamps across all 6 sampled patients, ruling out a different troponin isoform.`
  - table: `numericitems`
  - itemid: `8115`
  - source token: `LAB//8115//ng/ml`
  - row count: `617`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Troponine`
  - raw unit: `ng/ml`

### wbc, White Blood Cell Count, observation, infection

- Decision: `MTO`
- Target unit: `G/l`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/white_blood_cell_count.yml`; OMOP concept IDs `3010813`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `9965`
  - source token: `LAB//9965//10^9/l`
  - row count: `191174`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Leuco's (bloed)`
  - raw unit: `10^9/l`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6779`
  - source token: `LAB//6779//10^9/l`
  - row count: `6474`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Leucocyten`
  - raw unit: `10^9/l`

### basos, Basophils, observation, infection

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/basophils.yml`; OMOP concept IDs `3022096`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `11710`
  - source token: `LAB//11710//Geen`
  - row count: `3937`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Baso % (bloed)`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6768`
  - source token: `LAB//6768//UNKNOWN`
  - row count: `36`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Basofielen`

### eos, Eosinophils, observation, infection

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/eosinophils.yml`; OMOP concept IDs `3006504`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `11790`
  - source token: `LAB//11790//Geen`
  - row count: `4633`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Eo % (bloed)`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6773`
  - source token: `LAB//6773//UNKNOWN`
  - row count: `44`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Eosinofielen`

### mgcs, Glasgow Coma Scale Motor, observation, neuro

- Decision: `MTO`
- Target unit: `categorical`
- Reconstruction type: `categorical`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/GCS_motor.yml`; OMOP concept IDs `3008223|3026549`

match 1:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M6 Obeys commands.`
  - table: `listitems`
  - itemid: `6734`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//6734//1`
  - row count: `112307`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste motore reactie van de armen`
  - raw value: `Volgt verbale commando's op`
  - standardized label: `M6 Obeys commands`

match 2:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M6 Obeys commands.`
  - table: `listitems`
  - itemid: `19639`
  - valueid: `18.0`
  - source token: `MEASUREMENT_CATEGORICAL//19639//18`
  - row count: `39843`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_Opname`
  - raw value: `Volgt verbale commando's op`
  - standardized label: `M6 Obeys commands`

match 3:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M1 None.`
  - table: `listitems`
  - itemid: `6734`
  - valueid: `6.0`
  - source token: `MEASUREMENT_CATEGORICAL//6734//6`
  - row count: `32463`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste motore reactie van de armen`
  - raw value: `Geen reactie`
  - standardized label: `M1 None`

match 4:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M3 Abnormal flexion.`
  - table: `listitems`
  - itemid: `6734`
  - valueid: `3.0`
  - source token: `MEASUREMENT_CATEGORICAL//6734//3`
  - row count: `23361`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste motore reactie van de armen`
  - raw value: `Spastische reactie (terugtrekken)`
  - standardized label: `M3 Abnormal flexion`

match 5:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M5 Localizes pain.`
  - table: `listitems`
  - itemid: `6734`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//6734//2`
  - row count: `19694`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste motore reactie van de armen`
  - raw value: `Localiseert pijn`
  - standardized label: `M5 Localizes pain`

match 6:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M6 Obeys commands.`
  - table: `listitems`
  - itemid: `19636`
  - valueid: `12.0`
  - source token: `MEASUREMENT_CATEGORICAL//19636//12`
  - row count: `15062`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_24uur`
  - raw value: `Volgt verbale commando's op`
  - standardized label: `M6 Obeys commands`

match 7:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M6 Obeys commands.`
  - table: `listitems`
  - itemid: `13072`
  - valueid: `6.0`
  - source token: `MEASUREMENT_CATEGORICAL//13072//6`
  - row count: `8316`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Motoriek`
  - raw value: `Voert opdrachten uit`
  - standardized label: `M6 Obeys commands`

match 8:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M1 None.`
  - table: `listitems`
  - itemid: `19639`
  - valueid: `13.0`
  - source token: `MEASUREMENT_CATEGORICAL//19639//13`
  - row count: `7510`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_Opname`
  - raw value: `Geen reactie`
  - standardized label: `M1 None`

match 9:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M2 Extension.`
  - table: `listitems`
  - itemid: `6734`
  - valueid: `5.0`
  - source token: `MEASUREMENT_CATEGORICAL//6734//5`
  - row count: `7128`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste motore reactie van de armen`
  - raw value: `Strekken`
  - standardized label: `M2 Extension`

match 10:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M5 Localizes pain.`
  - table: `listitems`
  - itemid: `19639`
  - valueid: `17.0`
  - source token: `MEASUREMENT_CATEGORICAL//19639//17`
  - row count: `4372`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_Opname`
  - raw value: `Localiseert pijn`
  - standardized label: `M5 Localizes pain`

match 11:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M3 Abnormal flexion.`
  - table: `listitems`
  - itemid: `6734`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//6734//4`
  - row count: `3368`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste motore reactie van de armen`
  - raw value: `Decortatie reflex (abnormaal buigen)`
  - standardized label: `M3 Abnormal flexion`

match 12:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M6 Obeys commands.`
  - table: `listitems`
  - itemid: `16634`
  - valueid: `12.0`
  - source token: `MEASUREMENT_CATEGORICAL//16634//12`
  - row count: `1673`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `MCA_Motoriek`
  - raw value: `Voert opdrachten uit`
  - standardized label: `M6 Obeys commands`

match 13:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M1 None.`
  - table: `listitems`
  - itemid: `19636`
  - valueid: `7.0`
  - source token: `MEASUREMENT_CATEGORICAL//19636//7`
  - row count: `1438`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_24uur`
  - raw value: `Geen reactie`
  - standardized label: `M1 None`

match 14:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M4 Withdraws from pain.`
  - table: `listitems`
  - itemid: `19639`
  - valueid: `16.0`
  - source token: `MEASUREMENT_CATEGORICAL//19639//16`
  - row count: `1356`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_Opname`
  - raw value: `Spastische reactie (terugtrekken)`
  - standardized label: `M4 Withdraws from pain`

match 15:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M1 None.`
  - table: `listitems`
  - itemid: `13072`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//13072//1`
  - row count: `1331`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Motoriek`
  - raw value: `Geen reactie`
  - standardized label: `M1 None`

match 16:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M5 Localizes pain.`
  - table: `listitems`
  - itemid: `19636`
  - valueid: `11.0`
  - source token: `MEASUREMENT_CATEGORICAL//19636//11`
  - row count: `566`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_24uur`
  - raw value: `Localiseert pijn`
  - standardized label: `M5 Localizes pain`

match 17:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M5 Localizes pain.`
  - table: `listitems`
  - itemid: `13072`
  - valueid: `5.0`
  - source token: `MEASUREMENT_CATEGORICAL//13072//5`
  - row count: `552`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Motoriek`
  - raw value: `Localiseren pijn`
  - standardized label: `M5 Localizes pain`

match 18:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M3 Abnormal flexion.`
  - table: `listitems`
  - itemid: `19639`
  - valueid: `15.0`
  - source token: `MEASUREMENT_CATEGORICAL//19639//15`
  - row count: `330`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_Opname`
  - raw value: `Decortatie reflex (abnormaal buigen)`
  - standardized label: `M3 Abnormal flexion`

match 19:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M4 Withdraws from pain.`
  - table: `listitems`
  - itemid: `13072`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//13072//4`
  - row count: `280`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Motoriek`
  - raw value: `Terugtrekken bij pijn`
  - standardized label: `M4 Withdraws from pain`

match 20:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Motor M4 Withdraws from pain.`
  - table: `listitems`
  - itemid: `19636`
  - valueid: `10.0`
  - source token: `MEASUREMENT_CATEGORICAL//19636//10`
  - row count: `237`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `M_EMV_NICE_24uur`
  - raw value: `Spastische reactie (terugtrekken)`
  - standardized label: `M4 Withdraws from pain`

### tgcs, Glasgow Coma Scale Total -- REMOVED from this working copy, observation, neuro

`tgcs` is dropped as a standalone feature. It never had a direct source row (derived_score,
no matched itemid), and its role is fully covered by the three already-existing, already-matched
component features `egcs` (eye), `mgcs` (motor), `vgcs` (verbal) -- see those sections. On `vgcs`,
"Geintubeerd" (intubated) is kept as its own valid category (decision: keep) rather than imputed
to V=1, so GCS is exposed as three independent categorical channels with no derived/imputed total.
See the header note above for staging status (this copy only, not yet in the canonical CSV).

### vgcs, Glasgow Coma Scale Verbal, observation, neuro

- Decision: `MTO`
- Target unit: `categorical`
- Reconstruction type: `categorical`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/GCS_verbal.yml`; OMOP concept IDs `3009094|3013144`

match 1:
  - decision: `keep`
  - decision reason: `keep -- intubation retained as its own valid GCS-V category (not merged into V=1); avoids the systematic downward bias of imputing a numeric substitute for an intubated-but-possibly-neurologically-intact patient. Per user decision: GCS is exploded into separate M/V/E channels rather than forcing a single imputed numeric total.`
  - table: `listitems`
  - itemid: `6735`
  - valueid: `8.0`
  - source token: `MEASUREMENT_CATEGORICAL//6735//8`
  - row count: `101764`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste verbale reactie`
  - raw value: `Geïntubeerd`
  - standardized label: `Intubated`

match 2:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V5 Oriented.`
  - table: `listitems`
  - itemid: `6735`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//6735//1`
  - row count: `59420`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste verbale reactie`
  - raw value: `Helder en adequaat (communicatie mogelijk)`
  - standardized label: `V5 Oriented`

match 3:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V5 Oriented.`
  - table: `listitems`
  - itemid: `19640`
  - valueid: `20.0`
  - source token: `MEASUREMENT_CATEGORICAL//19640//20`
  - row count: `48400`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_Opname`
  - raw value: `Helder en adequaat (communicatie mogelijk)`
  - standardized label: `V5 Oriented`

match 4:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V1 None.`
  - table: `listitems`
  - itemid: `6735`
  - valueid: `5.0`
  - source token: `MEASUREMENT_CATEGORICAL//6735//5`
  - row count: `18623`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste verbale reactie`
  - raw value: `Geen reactie (geen zichtbare poging tot praten)`
  - standardized label: `V1 None`

match 5:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V5 Oriented.`
  - table: `listitems`
  - itemid: `19637`
  - valueid: `14.0`
  - source token: `MEASUREMENT_CATEGORICAL//19637//14`
  - row count: `15509`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_24uur`
  - raw value: `Helder en adequaat (communicatie mogelijk)`
  - standardized label: `V5 Oriented`

match 6:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V4 Confused.`
  - table: `listitems`
  - itemid: `6735`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//6735//2`
  - row count: `13303`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste verbale reactie`
  - raw value: `Verwarde conversatie`
  - standardized label: `V4 Confused`

match 7:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V2 Incomprehensible sounds.`
  - table: `listitems`
  - itemid: `6735`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//6735//4`
  - row count: `9115`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste verbale reactie`
  - raw value: `Onbegrijpelijke geluiden`
  - standardized label: `V2 Incomprehensible sounds`

match 8:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V1 None.`
  - table: `listitems`
  - itemid: `19640`
  - valueid: `16.0`
  - source token: `MEASUREMENT_CATEGORICAL//19640//16`
  - row count: `8948`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_Opname`
  - raw value: `Geen reactie (geen zichtbare poging tot praten)`
  - standardized label: `V1 None`

match 9:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V5 Oriented.`
  - table: `listitems`
  - itemid: `13066`
  - valueid: `5.0`
  - source token: `MEASUREMENT_CATEGORICAL//13066//5`
  - row count: `7860`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Verbal`
  - raw value: `Georiënteerd`
  - standardized label: `V5 Oriented`

match 10:
  - decision: `keep`
  - decision reason: `keep -- intubation retained as its own valid GCS-V category (not merged into V=1); avoids the systematic downward bias of imputing a numeric substitute for an intubated-but-possibly-neurologically-intact patient. Per user decision: GCS is exploded into separate M/V/E channels rather than forcing a single imputed numeric total.`
  - table: `listitems`
  - itemid: `19640`
  - valueid: `15.0`
  - source token: `MEASUREMENT_CATEGORICAL//19640//15`
  - row count: `3794`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_Opname`
  - raw value: `Geïntubeerd`
  - standardized label: `Intubated`

match 11:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V3 Inappropriate words.`
  - table: `listitems`
  - itemid: `6735`
  - valueid: `3.0`
  - source token: `MEASUREMENT_CATEGORICAL//6735//3`
  - row count: `3783`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Beste verbale reactie`
  - raw value: `Onduidelijke woorden (pogingen tot communicatie, maar onduidelijk)`
  - standardized label: `V3 Inappropriate words`

match 12:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V4 Confused.`
  - table: `listitems`
  - itemid: `19640`
  - valueid: `19.0`
  - source token: `MEASUREMENT_CATEGORICAL//19640//19`
  - row count: `3257`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_Opname`
  - raw value: `Verwarde conversatie`
  - standardized label: `V4 Confused`

match 13:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V2 Incomprehensible sounds.`
  - table: `listitems`
  - itemid: `19640`
  - valueid: `17.0`
  - source token: `MEASUREMENT_CATEGORICAL//19640//17`
  - row count: `2530`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_Opname`
  - raw value: `Onbegrijpelijke geluiden`
  - standardized label: `V2 Incomprehensible sounds`

match 14:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V1 None.`
  - table: `listitems`
  - itemid: `13066`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//13066//1`
  - row count: `1770`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Verbal`
  - raw value: `Geen geluid`
  - standardized label: `V1 None`

match 15:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V5 Oriented.`
  - table: `listitems`
  - itemid: `16640`
  - valueid: `10.0`
  - source token: `MEASUREMENT_CATEGORICAL//16640//10`
  - row count: `1647`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `MCA_Verbal`
  - raw value: `Georiënteerd`
  - standardized label: `V5 Oriented`

match 16:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V1 None.`
  - table: `listitems`
  - itemid: `19637`
  - valueid: `10.0`
  - source token: `MEASUREMENT_CATEGORICAL//19637//10`
  - row count: `1351`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_24uur`
  - raw value: `Geen reactie (geen zichtbare poging tot praten)`
  - standardized label: `V1 None`

match 17:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V3 Inappropriate words.`
  - table: `listitems`
  - itemid: `19640`
  - valueid: `18.0`
  - source token: `MEASUREMENT_CATEGORICAL//19640//18`
  - row count: `1052`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_Opname`
  - raw value: `Onduidelijke woorden (pogingen tot communicatie, maar onduidelijk)`
  - standardized label: `V3 Inappropriate words`

match 18:
  - decision: `keep`
  - decision reason: `keep -- intubation retained as its own valid GCS-V category (not merged into V=1); avoids the systematic downward bias of imputing a numeric substitute for an intubated-but-possibly-neurologically-intact patient. Per user decision: GCS is exploded into separate M/V/E channels rather than forcing a single imputed numeric total.`
  - table: `listitems`
  - itemid: `19637`
  - valueid: `9.0`
  - source token: `MEASUREMENT_CATEGORICAL//19637//9`
  - row count: `813`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_24uur`
  - raw value: `Geïntubeerd`
  - standardized label: `Intubated`

match 19:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V4 Confused.`
  - table: `listitems`
  - itemid: `19637`
  - valueid: `13.0`
  - source token: `MEASUREMENT_CATEGORICAL//19637//13`
  - row count: `639`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `V_EMV_NICE_24uur`
  - raw value: `Verwarde conversatie`
  - standardized label: `V4 Confused`

match 20:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Verbal V4 Confused.`
  - table: `listitems`
  - itemid: `13066`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//13066//4`
  - row count: `557`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Verbal`
  - raw value: `Verwarde taal`
  - standardized label: `V4 Confused`

### egcs, Glasgow Coma Scale Eye, observation, neuro

- Decision: `MTO`
- Target unit: `categorical`
- Reconstruction type: `categorical`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/GCS_eye.yml`; OMOP concept IDs `3016335|3026019`

match 1:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E4 Spontaneous.`
  - table: `listitems`
  - itemid: `6732`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//6732//1`
  - row count: `103268`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Actief openen van de ogen`
  - raw value: `Spontane reactie`
  - standardized label: `E4 Spontaneous`

match 2:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E3 To speech.`
  - table: `listitems`
  - itemid: `6732`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//6732//2`
  - row count: `47877`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Actief openen van de ogen`
  - raw value: `Reactie op verbale prikkel`
  - standardized label: `E3 To speech`

match 3:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E1 None.`
  - table: `listitems`
  - itemid: `6732`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//6732//4`
  - row count: `44421`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Actief openen van de ogen`
  - raw value: `Geen reactie`
  - standardized label: `E1 None`

match 4:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E4 Spontaneous.`
  - table: `listitems`
  - itemid: `19638`
  - valueid: `12.0`
  - source token: `MEASUREMENT_CATEGORICAL//19638//12`
  - row count: `38303`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `E_EMV_NICE_Opname`
  - raw value: `Spontane reactie`
  - standardized label: `E4 Spontaneous`

match 5:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E4 Spontaneous.`
  - table: `listitems`
  - itemid: `19635`
  - valueid: `8.0`
  - source token: `MEASUREMENT_CATEGORICAL//19635//8`
  - row count: `14830`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `E_EMV_NICE_24uur`
  - raw value: `Spontane reactie`
  - standardized label: `E4 Spontaneous`

match 6:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E2 To pain.`
  - table: `listitems`
  - itemid: `6732`
  - valueid: `3.0`
  - source token: `MEASUREMENT_CATEGORICAL//6732//3`
  - row count: `12101`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Actief openen van de ogen`
  - raw value: `Reactie op pijnprikkel`
  - standardized label: `E2 To pain`

match 7:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E1 None.`
  - table: `listitems`
  - itemid: `19638`
  - valueid: `9.0`
  - source token: `MEASUREMENT_CATEGORICAL//19638//9`
  - row count: `9988`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `E_EMV_NICE_Opname`
  - raw value: `Geen reactie`
  - standardized label: `E1 None`

match 8:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E4 Spontaneous.`
  - table: `listitems`
  - itemid: `13077`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//13077//4`
  - row count: `8317`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Eye`
  - raw value: `Spontaan`
  - standardized label: `E4 Spontaneous`

match 9:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E3 To speech.`
  - table: `listitems`
  - itemid: `19638`
  - valueid: `11.0`
  - source token: `MEASUREMENT_CATEGORICAL//19638//11`
  - row count: `3249`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `E_EMV_NICE_Opname`
  - raw value: `Reactie op verbale prikkel`
  - standardized label: `E3 To speech`

match 10:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E1 None.`
  - table: `listitems`
  - itemid: `19635`
  - valueid: `5.0`
  - source token: `MEASUREMENT_CATEGORICAL//19635//5`
  - row count: `1705`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `E_EMV_NICE_24uur`
  - raw value: `Geen reactie`
  - standardized label: `E1 None`

match 11:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E4 Spontaneous.`
  - table: `listitems`
  - itemid: `16628`
  - valueid: `8.0`
  - source token: `MEASUREMENT_CATEGORICAL//16628//8`
  - row count: `1680`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `MCA_Eye`
  - raw value: `Spontaan`
  - standardized label: `E4 Spontaneous`

match 12:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E1 None.`
  - table: `listitems`
  - itemid: `13077`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//13077//1`
  - row count: `1610`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Eye`
  - raw value: `Niet`
  - standardized label: `E1 None`

match 13:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E2 To pain.`
  - table: `listitems`
  - itemid: `19638`
  - valueid: `10.0`
  - source token: `MEASUREMENT_CATEGORICAL//19638//10`
  - row count: `1148`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `E_EMV_NICE_Opname`
  - raw value: `Reactie op pijnprikkel`
  - standardized label: `E2 To pain`

match 14:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E3 To speech.`
  - table: `listitems`
  - itemid: `19635`
  - valueid: `7.0`
  - source token: `MEASUREMENT_CATEGORICAL//19635//7`
  - row count: `679`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `E_EMV_NICE_24uur`
  - raw value: `Reactie op verbale prikkel`
  - standardized label: `E3 To speech`

match 15:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E3 To speech.`
  - table: `listitems`
  - itemid: `13077`
  - valueid: `3.0`
  - source token: `MEASUREMENT_CATEGORICAL//13077//3`
  - row count: `508`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Eye`
  - raw value: `Op aanspreken`
  - standardized label: `E3 To speech`

match 16:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E2 To pain.`
  - table: `listitems`
  - itemid: `19635`
  - valueid: `6.0`
  - source token: `MEASUREMENT_CATEGORICAL//19635//6`
  - row count: `218`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `E_EMV_NICE_24uur`
  - raw value: `Reactie op pijnprikkel`
  - standardized label: `E2 To pain`

match 17:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E2 To pain.`
  - table: `listitems`
  - itemid: `13077`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//13077//2`
  - row count: `202`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `A_Eye`
  - raw value: `Op pijn`
  - standardized label: `E2 To pain`

match 18:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E3 To speech.`
  - table: `listitems`
  - itemid: `16628`
  - valueid: `7.0`
  - source token: `MEASUREMENT_CATEGORICAL//16628//7`
  - row count: `177`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `MCA_Eye`
  - raw value: `Op aanspreken`
  - standardized label: `E3 To speech`

match 19:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E4 Spontaneous.`
  - table: `listitems`
  - itemid: `14470`
  - valueid: `8.0`
  - source token: `MEASUREMENT_CATEGORICAL//14470//8`
  - row count: `57`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RA_Eye`
  - raw value: `Spontaan`
  - standardized label: `E4 Spontaneous`

match 20:
  - decision: `keep`
  - decision reason: `maps to standard GCS-Eye E1 None.`
  - table: `listitems`
  - itemid: `16628`
  - valueid: `5.0`
  - source token: `MEASUREMENT_CATEGORICAL//16628//5`
  - row count: `55`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `MCA_Eye`
  - raw value: `Niet`
  - standardized label: `E1 None`

### hct, Hematocrit, observation, circulatory

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/hematocrit.yml`; OMOP concept IDs `42869588`

match 1:
  - decision: `keep`
  - decision reason: `blood hematocrit, tracks consistently with the other matches.`
  - table: `numericitems`
  - itemid: `11545`
  - source token: `LAB//11545//Geen`
  - row count: `494384`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ht(v.Bgs) (bloed)`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `blood hematocrit, tracks consistently with the other matches.`
  - table: `numericitems`
  - itemid: `11423`
  - source token: `LAB//11423//Geen`
  - row count: `200516`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ht (bloed)`
  - raw unit: `Geen`

match 3:
  - decision: `keep`
  - decision reason: `blood hematocrit, tracks consistently with the other matches.`
  - table: `numericitems`
  - itemid: `6777`
  - source token: `LAB//6777//l`
  - row count: `7511`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Hematocriet`
  - raw unit: `l`

### rbc, Red Blood Cell Count, observation, circulatory

- Decision: `MTO`
- Target unit: `m/uL`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/red_blood_cell_count.yml`; OMOP concept IDs `3026361`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `9962`
  - source token: `LAB//9962//10^12/l`
  - row count: `12476`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Ery's (bloed)`
  - raw unit: `10^12/l`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6774`
  - source token: `LAB//6774//10^12/l`
  - row count: `251`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Erythrocyten`
  - raw unit: `10^12/l`

### tri, Troponin I, observation, circulatory

- Decision: `MTO`
- Target unit: `ng/mL`
- Reconstruction type: `direct_numeric`
- Mapping status: `needs_policy`
- Notes: `No Troponin I assay exists anywhere in AmsterdamUMCdb -- checked supplied_vocab.csv, the official AmsterdamUMCdb OMOP dictionary_map.csv, and the raw amsterdamumcdb/dictionary/dictionary.csv. All troponin items below are officially dictionary-mapped to Troponin T (LOINC 6598-7 / 48425-3), including itemid 8115 whose raw label is the generic "Troponine". This is consistent with Troponin T (not I) being the standard assay in Dutch hospital labs. Needs a policy decision: accept Troponin T as a cross-assay substitute for this feature, or leave AUMC unmapped for tri.`

match 1:
  - decision: `keep`
  - decision reason: `mirrors tnt match 1 -- Troponin I doesn't exist in AmsterdamUMCdb (confirmed absent in supplied_vocab.csv, the OMOP dictionary_map, and the raw AmsterdamUMCdb dictionary.csv); Troponin T accepted as the cross-assay substitute.`
  - table: `numericitems`
  - itemid: `10407`
  - source token: `LAB//10407//µg/l`
  - row count: `23805`
  - evidence: `supplied_vocab`
  - matched by: `term:Troponin`
  - raw label: `TroponineT (bloed)`
  - raw unit: `µg/l (=ng/mL) -- Troponin T, not I`

match 2:
  - decision: `keep`
  - decision reason: `mirrors tnt match 2, same substitution rationale.`
  - table: `numericitems`
  - itemid: `8115`
  - source token: `LAB//8115//ng/ml`
  - row count: `617`
  - evidence: `supplied_vocab`
  - matched by: `term:Troponin`
  - raw label: `Troponine`
  - raw unit: `ng/ml -- dictionary-mapped to Troponin T, not I`

match 3:
  - decision: `reject`
  - decision reason: `TroponineT (overig) -- non-blood specimen, wrong compartment, independent of the Troponin T/I substitution question.`
  - table: `numericitems`
  - itemid: `10408`
  - source token: `LAB//10408//µg/l`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Troponin`
  - raw label: `TroponineT (overig)`
  - raw unit: `µg/l -- Troponin T, non-blood compartment`


### etco2, Endtidal CO2, observation, respiratory

- Decision: `MTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/endtidal_CO2.yml`; OMOP concept IDs `3017485|3035357`

match 1:
  - decision: `reject`
  - decision reason: `EtCO2 (%) -- '%' unit, per iCareFM's intended unit (mmHg) for this feature.`
  - table: `numericitems`
  - itemid: `12805`
  - source token: `MEASUREMENT_BEDSIDE//12805//Geen`
  - row count: `14868918`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `EtCO2 (%)`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `End tidal CO2 concentratie -- mmHg.`
  - table: `numericitems`
  - itemid: `6707`
  - source token: `MEASUREMENT_BEDSIDE//6707//mmHg`
  - row count: `10327178`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `End tidal CO2 concentratie`
  - raw unit: `mmHg`

match 3:
  - decision: `keep`
  - decision reason: `End Tidal CO2 mmHG -- mmHg.`
  - table: `numericitems`
  - itemid: `8885`
  - source token: `MEASUREMENT_BEDSIDE//8885//mmHg`
  - row count: `409`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `End Tidal CO2 mmHG`
  - raw unit: `mmHg`

match 4:
  - decision: `keep`
  - decision reason: `End tidal CO2 concentratie (2) -- mmHg, duplicate device channel.`
  - table: `numericitems`
  - itemid: `12356`
  - source token: `MEASUREMENT_BEDSIDE//12356//mmHg`
  - row count: `381`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `End tidal CO2 concentratie (2)`
  - raw unit: `mmHg`

match 5:
  - decision: `reject`
  - decision reason: `End Tidal CO2 % -- '%' unit, wrong unit per iCareFM's mmHg target.`
  - table: `numericitems`
  - itemid: `8884`
  - source token: `MEASUREMENT_BEDSIDE//8884//UNKNOWN`
  - row count: `64`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `End Tidal CO2 %`

match 6:
  - decision: `reject`
  - decision reason: `End Tidal CO2% (2) -- '%' unit, wrong unit per iCareFM's mmHg target.`
  - table: `numericitems`
  - itemid: `9658`
  - source token: `MEASUREMENT_BEDSIDE//9658//UNKNOWN`
  - row count: `15`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `End Tidal CO2% (2)`

### rass, Richmond Agitation Sedation Scale, observation, neuro

- Decision: `MTO`
- Target unit: `categorical`
- Reconstruction type: `categorical`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/Richmond_agitation_sedation_scale.yml`; OMOP concept IDs `36684829`
- Notes: `Only 8 of the 10 standard RASS levels (-5..+2) appear in the source vocab for itemid 14444; +3 and +4 (very agitated / combative) are absent from this item's valueid list.`

match 1:
  - decision: `keep`
  - decision reason: `maps exactly to standard RASS -4 Deep sedation.`
  - table: `listitems`
  - itemid: `14444`
  - valueid: `9`
  - source token: `MEASUREMENT_CATEGORICAL//14444//9`
  - row count: `10468`
  - evidence: `supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RASS score`
  - raw value: `-4 diepe sedatie`
  - standardized label: `-4 Deep sedation`

match 2:
  - decision: `keep`
  - decision reason: `maps exactly to standard RASS -1 Drowsy.`
  - table: `listitems`
  - itemid: `14444`
  - valueid: `6`
  - source token: `MEASUREMENT_CATEGORICAL//14444//6`
  - row count: `17284`
  - evidence: `supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RASS score`
  - raw value: `-1 slaperig`
  - standardized label: `-1 Drowsy`

match 3:
  - decision: `keep`
  - decision reason: `maps exactly to standard RASS 0 Alert and calm.`
  - table: `listitems`
  - itemid: `14444`
  - valueid: `5`
  - source token: `MEASUREMENT_CATEGORICAL//14444//5`
  - row count: `21972`
  - evidence: `supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RASS score`
  - raw value: `0 alert en kalm`
  - standardized label: `0 Alert and calm`

match 4:
  - decision: `keep`
  - decision reason: `maps exactly to standard RASS +1 Restless.`
  - table: `listitems`
  - itemid: `14444`
  - valueid: `4`
  - source token: `MEASUREMENT_CATEGORICAL//14444//4`
  - row count: `9933`
  - evidence: `supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RASS score`
  - raw value: `+1 onrustig`
  - standardized label: `+1 Restless`

match 5:
  - decision: `keep`
  - decision reason: `maps exactly to standard RASS -2 Light sedation.`
  - table: `listitems`
  - itemid: `14444`
  - valueid: `7`
  - source token: `MEASUREMENT_CATEGORICAL//14444//7`
  - row count: `5539`
  - evidence: `supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RASS score`
  - raw value: `-2 lichte sedatie`
  - standardized label: `-2 Light sedation`

match 6:
  - decision: `keep`
  - decision reason: `maps exactly to standard RASS -3 Moderate sedation.`
  - table: `listitems`
  - itemid: `14444`
  - valueid: `8`
  - source token: `MEASUREMENT_CATEGORICAL//14444//8`
  - row count: `5342`
  - evidence: `supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RASS score`
  - raw value: `-3 matige sedatie`
  - standardized label: `-3 Moderate sedation`

match 7:
  - decision: `keep`
  - decision reason: `maps exactly to standard RASS -5 Unarousable.`
  - table: `listitems`
  - itemid: `14444`
  - valueid: `10`
  - source token: `MEASUREMENT_CATEGORICAL//14444//10`
  - row count: `4541`
  - evidence: `supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RASS score`
  - raw value: `-5 niet wekbaar`
  - standardized label: `-5 Unarousable`

match 8:
  - decision: `keep`
  - decision reason: `maps exactly to standard RASS +2 Agitated.`
  - table: `listitems`
  - itemid: `14444`
  - valueid: `3`
  - source token: `MEASUREMENT_CATEGORICAL//14444//3`
  - row count: `1423`
  - evidence: `supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `RASS score`
  - raw value: `+2 geagiteerd`
  - standardized label: `+2 Agitated`


### hbco, Carboxyhemoglobin, observation, circulatory

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `11690`
  - source token: `LAB//11690//Geen`
  - row count: `335485`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:20563-3`
  - raw label: `CO-Hb (bloed)`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6984`
  - source token: `LAB//6984//UNKNOWN`
  - row count: `126`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FCOHb`
  - raw label: `FCOHb`

### esr, Erythrocyte Sedimentation Rate, observation, infection

- Decision: `MTO`
- Target unit: `mm/hr`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/erythrocyte_sedimentation_rate.yml`; OMOP concept IDs `3015183`

match 1:
  - decision: `keep`
  - decision reason: `blood ESR, tracks consistently with the other matches.`
  - table: `numericitems`
  - itemid: `11902`
  - source token: `LAB//11902//mm/uur`
  - row count: `18425`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Bezinking (bloed)`
  - raw unit: `mm/uur`

match 2:
  - decision: `keep`
  - decision reason: `blood ESR, tracks consistently with the other matches.`
  - table: `numericitems`
  - itemid: `11906`
  - source token: `LAB//11906//mm/uur`
  - row count: `207`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Micro-Bse (bloed)`
  - raw unit: `mm/uur`

match 3:
  - decision: `keep`
  - decision reason: `blood ESR, tracks consistently with the other matches.`
  - table: `numericitems`
  - itemid: `6808`
  - source token: `LAB//6808//mm`
  - row count: `172`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Bezinking`
  - raw unit: `mm`

### pt, Prothrombine Time, observation, circulatory

- Decision: `OTO`
- Target unit: `sec`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/prothrombine_time.yml`; OMOP concept IDs `3034426`

match 1:
  - decision: `reject`
  - decision reason: `REVISED 2026-07-13: raw_unit metadata says 'sec' but the actual values are not seconds. At the 809 admission-hours where this itemid and inr_pt's source itemids (11893/11894 -- same underlying Dutch lab test "Prothrombinetijd (bloed)", unit 'INR') were both measured, the ratio between them is exactly 1 from the 1st through the 90th percentile (verified via a raw-CSV scan, not just aggregate percentile comparison -- see grid/_check_pt_vs_inr.py). This itemid is a legacy duplicate of the INR channel with a mislabeled unit, not an independent PT-in-seconds source; its ~1.8% non-ratio-scale tail (up to 1903) is unrecoverable contamination, not genuine seconds data. No valid PT-in-seconds source exists in this dataset -- inr_pt already covers this clinical concept with far better coverage (7.8% missing vs this feature's 95.5%). Superseding the original keep.`
  - table: `numericitems`
  - itemid: `6789`
  - source token: `LAB//6789//sec`
  - row count: `5800`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `Protrombinetijd`
  - raw unit: `sec`

### adm, Patient Admission Type, demographic, not specified

- Decision: `MTO`
- Target unit: `categorical`
- Reconstruction type: `admission_context`
- Mapping status: `source_candidates_found`
- Notes: `RESOLVED (2026-07-10): recover from admissions.csv, two columns combined -- urgency
  (binary, 0=Elective/1=Emergency, no nulls, 16860/6246 split) and origin (transfer source
  location, 16 raw categories + null, 61% missing overall). origin alone is too sparse/off-
  topic to use raw (it answers "where did the patient come from," not "what type of
  admission was this," and is missing for the majority of rows); collapsed to its top-4
  most-frequent raw categories + "Other" for everything else: (missing) [14075],
  Verpleegafdeling zelfde ziekenhuis/ward-same-hospital [5027], Eerste Hulp afdeling zelfde
  ziekenhuis/ED-same-hospital [2661], CCU/IC zelfde ziekenhuis/ICU-CCU-same-hospital [296],
  Other [1047, everything else -- recovery/OR/other-hospital-transfers/ambulance, each
  individually <240]. Cross-tabbed against urgency to confirm internal consistency before
  adopting: ED-origin is 100% Emergency (0 Elective rows, clinically sensible -- nobody
  schedules an elective ED visit), ward-origin is ~90% Elective, and origin's missingness
  rate differs by urgency (68% missing for Elective vs. 42% for Emergency, i.e. elective
  admissions more often arrive with no transfer history to log) -- these patterns look real,
  not noisy. Final adm categorical = urgency (2 states) x origin-collapsed (5 states) = up to
  10 joint states, with one combination (ED-origin x Elective) structurally empty. One minor
  source inconsistency noted, not fixed: "Recovery zelfde ziekenhuis (alleen bij niet
  geplande IC-opname)" ["...only for unplanned ICU admission"] has 140/217 (65%) rows marked
  urgency=Elective, contradicting its own label -- a pre-existing AmsterdamUMCdb data-quality
  issue, out of scope to correct here.`

No itemid-vocabulary match applies here -- source is `admissions.csv:urgency` and
`admissions.csv:origin` directly, see Notes for the exact category collapse and cross-tab
validation.

### hba1c, Hemoglobin A1C, observation, metabolic_renal

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/Hemoglobin_A1C.yml`; OMOP concept IDs `3004410`

match 1:
  - decision: `keep`
  - decision reason: `already in target unit (%), use raw value as-is.`
  - table: `numericitems`
  - itemid: `11812`
  - source token: `LAB//11812//Geen`
  - row count: `298`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `HbA1c (bloed)`
  - raw unit: `Geen`

match 2:
  - decision: `keep`
  - decision reason: `convert before merging: % = 0.09148 x mmol/mol + 2.152 (standard NGSP<->IFCC formula); plot confirms match 1 and match 2 fire at the same timestamp (dual-unit reporting of the same draw, not independent measurements) and the formula checks out against the observed value pairs across all 6 sampled patients.`
  - table: `numericitems`
  - itemid: `16166`
  - source token: `LAB//16166//mmol/mol`
  - row count: `201`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `HbA1c  (bloed)`
  - raw unit: `mmol/mol`

### samp, Body Fluid Sampling, Detected Bacterial Growth, observation, infection

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `REVISED (P2b policy): samp = binary culture-order flag from a 14-itemid procedureorderitems whitelist (see match decisions below), no forward-fill, no growth/positivity component. Supersedes the original Missing/Negative/Urine/Blood growth-reconstruction attempt earlier in this review -- abandoned after confirming (dictionary/vocab/OMOP cross-check + literature: ricu concept-dict.json, van Doorn et al. PLOS ONE 2024, Fleuren et al.) that AmsterdamUMCdb has no systematic structured or free-text growth/positivity signal. This binary order-flag definition is what feeds the downstream Sepsis-3 suspected-infection window logic (see context.md), matching ricu's own actual aumc samp semantics (also just an order flag) rather than the paper's stated 'detected bacterial growth' wording. RECLASSIFIED (2026-07-10): Reconstruction type changed from 'microbiology' to 'treatment_indicator' -- mechanically identical to abx/sed/ins_ind's point-event handling (any procedureorderitems row in an hour = On, no forward-fill), not a distinct category; this is what lets it flow through the existing extract_treatment_indicator.py pipeline instead of needing bespoke code. Its kept matches are all procedureorderitems rather than the usual drugitems, so it will show up as a flagged cross-table anomaly in parse_manifest_features.py -- expected and harmless, same accepted pattern as ufilt_ind/ins_ind's point-event matches.`

match 1:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10780`
  - source token: `FREETEXT//10780//1`
  - row count: `103`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (sputum)`

match 2:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10766`
  - source token: `FREETEXT//10766//1`
  - row count: `70`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (br.-alv.lav)`

match 3:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10768`
  - source token: `FREETEXT//10768//1`
  - row count: `40`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (blaasjesv.)`

match 4:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10771`
  - source token: `FREETEXT//10771//1`
  - row count: `33`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (huiduitstr.)`

match 5:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10880`
  - source token: `FREETEXT//10880//1`
  - row count: `28`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (keel)`

match 6:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10921`
  - source token: `FREETEXT//10921//1`
  - row count: `18`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (overig)`

match 7:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10932`
  - source token: `FREETEXT//10932//1`
  - row count: `16`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (liquor)`

match 8:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10918`
  - source token: `FREETEXT//10918//1`
  - row count: `12`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (faeces)`

match 9:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10910`
  - source token: `FREETEXT//10910//1`
  - row count: `10`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (biopt)`

match 10:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10773`
  - source token: `FREETEXT//10773//1`
  - row count: `8`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (monduitstr.)`

match 11:
  - decision: `reject`
  - decision reason: `Superseded by the P2b policy revision -- `samp` is now a pure procedureorderitems order-flag (14-itemid whitelist), not a growth-detection feature, so this free-text Gram-stain comment field (7 admissions total, an incidental documentation habit, not a systematic field) is out of scope. Not because the match itself is wrong, but because the feature it would have served (growth detection) has been retired as unreliable.`
  - table: `freetextitems`
  - itemid: `19907`
  - source token: `FREETEXT//19907//1`
  - row count: `7`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `Bloedkweek preparaat toelichting (bloed)`

match 12:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10908`
  - source token: `FREETEXT//10908//1`
  - row count: `5`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (pus)`

match 13:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10779`
  - source token: `FREETEXT//10779//1`
  - row count: `4`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (pleurapunct.)`

match 14:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10887`
  - source token: `FREETEXT//10887//1`
  - row count: `2`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (oog)`

match 15:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10926`
  - source token: `FREETEXT//10926//1`
  - row count: `2`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (urine)`

match 16:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10775`
  - source token: `FREETEXT//10775//1`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (nasophar.wat)`

match 17:
  - decision: `reject`
  - decision reason: `VIRUSkweek -- viral pathogen, wrong pathogen type for a feature titled 'Detected Bacterial Growth'.`
  - table: `freetextitems`
  - itemid: `10786`
  - source token: `FREETEXT//10786//1`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `VIRUSkweek (punctaat)`

match 18:
  - decision: `reject`
  - decision reason: `Leptospirose kweek (bloed) -- n=1 total -- too little to be worth keeping regardless of specimen relevance.`
  - table: `freetextitems`
  - itemid: `20975`
  - source token: `FREETEXT//20975//1`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:kweek`
  - raw label: `Leptospirose kweek (bloed)`

match 19:
  - decision: `reject`
  - decision reason: `not a blood specimen -- scope narrowed to blood-only bacterial detection per the paper author's own approach (their dataset excluded samp entirely due to free-text/specimen-mixing unreliability in non-blood cultures; blood-only was their stated fallback intent).`
  - table: `freetextitems`
  - itemid: `10901`
  - source token: `FREETEXT//10901//1`
  - row count: `3453`
  - evidence: `supplied_vocab`
  - matched by: `term:Bact.`
  - raw label: `Bact. (urine)`
  - raw value: `free text -- urine sediment bacteria finding`

match 20:
  - decision: `reject`
  - decision reason: `not a blood specimen -- scope narrowed to blood-only bacterial detection per the paper author's own approach (their dataset excluded samp entirely due to free-text/specimen-mixing unreliability in non-blood cultures; blood-only was their stated fallback intent).`
  - table: `freetextitems`
  - itemid: `20024`
  - source token: `FREETEXT//20024//1`
  - row count: `6`
  - evidence: `supplied_vocab`
  - matched by: `term:Bacteriele PCR`
  - raw label: `Bacteriële PCR IS-pro (biopt)`

match 21:
  - decision: `reject`
  - decision reason: `not a blood specimen -- scope narrowed to blood-only bacterial detection per the paper author's own approach (their dataset excluded samp entirely due to free-text/specimen-mixing unreliability in non-blood cultures; blood-only was their stated fallback intent).`
  - table: `freetextitems`
  - itemid: `20054`
  - source token: `FREETEXT//20054//1`
  - row count: `6`
  - evidence: `supplied_vocab`
  - matched by: `term:Bacteriele PCR`
  - raw label: `Bacteriële PCR IS-pro (punctaat)`

match 22:
  - decision: `reject`
  - decision reason: `not a blood specimen -- scope narrowed to blood-only bacterial detection per the paper author's own approach (their dataset excluded samp entirely due to free-text/specimen-mixing unreliability in non-blood cultures; blood-only was their stated fallback intent).`
  - table: `freetextitems`
  - itemid: `20055`
  - source token: `FREETEXT//20055//1`
  - row count: `5`
  - evidence: `supplied_vocab`
  - matched by: `term:Bacteriele PCR`
  - raw label: `Bacteriële PCR IS-pro (pus)`

match 23:
  - decision: `reject`
  - decision reason: `not a blood specimen -- scope narrowed to blood-only bacterial detection per the paper author's own approach (their dataset excluded samp entirely due to free-text/specimen-mixing unreliability in non-blood cultures; blood-only was their stated fallback intent).`
  - table: `freetextitems`
  - itemid: `20037`
  - source token: `FREETEXT//20037//1`
  - row count: `4`
  - evidence: `supplied_vocab`
  - matched by: `term:Bacteriele PCR`
  - raw label: `Bacteriële PCR IS-pro (liquor)`

match 24:
  - decision: `reject`
  - decision reason: `not a blood specimen -- scope narrowed to blood-only bacterial detection per the paper author's own approach (their dataset excluded samp entirely due to free-text/specimen-mixing unreliability in non-blood cultures; blood-only was their stated fallback intent).`
  - table: `freetextitems`
  - itemid: `20053`
  - source token: `FREETEXT//20053//1`
  - row count: `4`
  - evidence: `supplied_vocab`
  - matched by: `term:Bacteriele PCR`
  - raw label: `Bacteriële PCR IS-pro (pleurapunct.)`

match 25:
  - decision: `reject`
  - decision reason: `not a blood specimen -- scope narrowed to blood-only bacterial detection per the paper author's own approach (their dataset excluded samp entirely due to free-text/specimen-mixing unreliability in non-blood cultures; blood-only was their stated fallback intent).`
  - table: `freetextitems`
  - itemid: `20049`
  - source token: `FREETEXT//20049//1`
  - row count: `2`
  - evidence: `supplied_vocab`
  - matched by: `term:Bacteriele PCR`
  - raw label: `Bacteriële PCR IS-pro (overig)`

match 26:
  - decision: `reject`
  - decision reason: `Bact PCR IS-pro (bloed) -- n=1 total -- too little to be worth keeping regardless of specimen relevance.`
  - table: `freetextitems`
  - itemid: `20028`
  - source token: `FREETEXT//20028//1`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Bacteriele PCR`
  - raw label: `Bacteriële PCR IS-pro (bloed)`

match 27:
  - decision: `reject`
  - decision reason: `not a blood specimen -- scope narrowed to blood-only bacterial detection per the paper author's own approach (their dataset excluded samp entirely due to free-text/specimen-mixing unreliability in non-blood cultures; blood-only was their stated fallback intent).`
  - table: `freetextitems`
  - itemid: `20048`
  - source token: `FREETEXT//20048//1`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Bacteriele PCR`
  - raw label: `Bacteriële PCR IS-pro (oor)`

match 28:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (8097, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `8097`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//8097`
  - row count: `10397`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Sputumkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 29:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9194, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9194`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9194`
  - row count: `1084`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Liquorkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 30:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9192, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9192`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9192`
  - row count: `782`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Faeceskweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 31:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9193, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9193`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9193`
  - row count: `706`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `X-Kweek nader te bepalen`
  - raw value: `Opdr. Kweken afnemen -- unspecified-site culture order`

match 32:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9190, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9190`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9190`
  - row count: `645`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Cathetertipkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 33:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (8418, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `8418`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//8418`
  - row count: `504`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Urinekweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 34:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9200, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9200`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9200`
  - row count: `318`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Wondkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 35:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9191, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9191`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9191`
  - row count: `205`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Drainvochtkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 36:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9203, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9203`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9203`
  - row count: `90`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Keelkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 37:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9195, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9195`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9195`
  - row count: `56`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Neuskweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 38:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9202, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9202`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9202`
  - row count: `43`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Ascitesvochtkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 39:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9198, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9198`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9198`
  - row count: `25`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Rectumkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`

match 40:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9197, ?) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9197`
  - ordercategoryid: `74`
  - source token: `PROCEDURE//74//9197`
  - row count: `6`
  - evidence: `supplied_vocab`
  - matched by: `term:kweek afnemen`
  - raw label: `Perineumkweek afnemen`
  - raw value: `Opdr. Kweken afnemen -- ORDER event, not a growth result`
match 41:
  - decision: `keep`
  - decision reason: `P2b policy revision: `samp` is redefined as a pure culture-ORDER flag (binary, no forward-fill -- an hour is TRUE iff an order timestamp for one of the 14 whitelisted procedureorderitems itemids falls in it, FALSE otherwise; never carried forward, same rule as the treatment_indicator features). This specific itemid (9189, Bloedkweken afnemen) is one of the 14 -- kept. The earlier growth-detection ambition (freetextitems parsing for organism/positivity) is abandoned: confirmed via dictionary/vocab/OMOP-map cross-check and independent literature review (ricu concept-dict.json shows AmsterdamUMCdb's own 'samp' concept is ALSO just an order flag, not growth; van Doorn et al. PLOS ONE 2024 and Fleuren et al. use antibiotics+order or antibiotic-escalation instead of growth for this exact dataset) that no systematic growth/positivity signal exists in this database.`
  - table: `procedureorderitems`
  - itemid: `9189`
  - source token: `PROCEDUREORDER//9189//1`
  - row count: `5439`
  - evidence: `source_vocab`
  - matched by: `manual_review -- missing from original candidate pool, found via direct data query`
  - raw label: `Bloedkweken afnemen`

### spo2, Pulse Oxymetry Oxygen Saturation, observation, respiratory

- Decision: `OTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- OpenICU evidence: mapping file `config/datasets/aumc/1.5.0/mappings/oxygen_saturation.yml`; OMOP concept IDs `40762499`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 36411768 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `6709`
  - source token: `MEASUREMENT_BEDSIDE//6709//UNKNOWN`
  - row count: `36411768`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Saturatie (Monitor)`
  - raw label: `Saturatie (Monitor)`

### sao2, Oxygen Saturation In Arterial Blood, observation, respiratory

- Decision: `OTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 652901 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `12311`
  - source token: `LAB//12311//Geen`
  - row count: `652901`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:O2-Saturatie (bloed)`
  - raw label: `O2-Saturatie (bloed)`
  - raw unit: `Geen`

### icp, Intra Cranial Pressure, observation, neuro

- Decision: `MTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Excluded from candidates: itemid 15290 "Streef Bovenwaarde ICP" (a clinician-set target/goal value, not a measurement) and NICE/APACHE intracranial-hemorrhage diagnosis listitems (comorbidity flags, not ICP readings).`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `8835`
  - source token: `MEASUREMENT_BEDSIDE//8835//mmHg`
  - row count: `895599`
  - evidence: `supplied_vocab`
  - matched by: `term:Intracraniele druk`
  - raw label: `Intracraniële druk`
  - raw unit: `mmHg`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `13940`
  - source token: `MEASUREMENT_BEDSIDE//13940//mmHg`
  - row count: `826`
  - evidence: `supplied_vocab`
  - matched by: `term:Intracraniele druk`
  - raw label: `Intracraniële druk(2)`
  - raw unit: `mmHg`


### cout, Cardiac Output, observation, circulatory

- Decision: `MTO`
- Target unit: `l/min`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6656`
  - source token: `MEASUREMENT_BEDSIDE//6656//l/min`
  - row count: `52738`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Cardiac Output`
  - raw label: `Cardiac Output`
  - raw unit: `l/min`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `13151`
  - source token: `MEASUREMENT_BEDSIDE//13151//l/min`
  - row count: `1427`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Cardiac Output`
  - raw label: `PiCCO CO (Cardiac Output)`
  - raw unit: `l/min`

### mpap, Mean Pulmonal Arterial Pressure, observation, circulatory

- Decision: `OTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 1819309 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `6645`
  - source token: `MEASUREMENT_BEDSIDE//6645//mmHg`
  - row count: `1819309`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:AP gemiddeld`
  - raw label: `PAP gemiddeld`
  - raw unit: `mmHg`

### spap, Systolic Pulmonal Arterial Pressure, observation, circulatory

- Decision: `OTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Sibling itemid of mpap's already-matched 6645 "PAP gemiddeld" (6644=systolic, 6645=mean, 6646=diastolic); original matcher apparently only had a "mean pulmonary" term and missed the systolic/diastolic siblings.`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 1818402 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `6644`
  - source token: `MEASUREMENT_BEDSIDE//6644//mmHg`
  - row count: `1818402`
  - evidence: `supplied_vocab`
  - matched by: `term:PAP systolisch`
  - raw label: `PAP systolisch`
  - raw unit: `mmHg`


### dpap, Diastolic Pulmonal Arterial Pressure, observation, circulatory

- Decision: `OTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Sibling itemid of mpap's already-matched 6645 "PAP gemiddeld" (6644=systolic, 6645=mean, 6646=diastolic); original matcher apparently only had a "mean pulmonary" term and missed the systolic/diastolic siblings.`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 1811489 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `6646`
  - source token: `MEASUREMENT_BEDSIDE//6646//mmHg`
  - row count: `1811489`
  - evidence: `supplied_vocab`
  - matched by: `term:PAP diastolisch`
  - raw label: `PAP diastolisch`
  - raw unit: `mmHg`


### cvp, Central Venous Pressure, observation, circulatory

- Decision: `MTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `20926`
  - source token: `MEASUREMENT_BEDSIDE//20926//mmHg`
  - row count: `4961791`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVD`
  - raw label: `CVDm-gekoppeld`
  - raw unit: `mmHg`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `6655`
  - source token: `MEASUREMENT_BEDSIDE//6655//mmHg`
  - row count: `483942`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVD`
  - raw label: `CVD`
  - raw unit: `mmHg`

### svo2, Mixed Venous Oxygenation, observation, circulatory

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Three different measurement contexts: dedicated continuous SvO2 catheter (Vigilance), ECMO-circuit venous saturation, and a low-volume legacy item.`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `12534`
  - source token: `MEASUREMENT_BEDSIDE//12534//Geen`
  - row count: `323`
  - evidence: `supplied_vocab`
  - matched by: `term:SvO2`
  - raw label: `SvO2 Vigilance`
  - raw unit: `Geen (=%)`

match 2:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `20658`
  - source token: `MEASUREMENT_BEDSIDE//20658//Geen`
  - row count: `478`
  - evidence: `supplied_vocab`
  - matched by: `term:veneuze saturatie`
  - raw label: `ECMO - Veneuze saturatie`
  - raw unit: `Geen (=%) -- ECMO-circuit venous sat, not PAC-measured mixed venous`

match 3:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `numericitems`
  - itemid: `8507`
  - source token: `MEASUREMENT_BEDSIDE//8507//UNKNOWN`
  - row count: `4`
  - evidence: `supplied_vocab`
  - matched by: `term:SVO2`
  - raw label: `SVO2`
  - raw unit: ``


### pcwp, Pulmonary Capillary Wedge Pressure, observation, circulatory

- Decision: `OTO`
- Target unit: `mmHg`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 53751 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `6657`
  - source token: `MEASUREMENT_BEDSIDE//6657//mmHg`
  - row count: `53751`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:PCWP`
  - raw label: `PCWP wedge`
  - raw unit: `mmHg`

### peep, Positive End Expiratory Pressure - Mechanical Ventilation, observation, respiratory

- Decision: `MTO`
- Target unit: `cmH2O`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Excluded: "PC/PS boven PEEP (Set)" items (driving pressure ABOVE PEEP -- a different quantity, belongs to a pressure-control/pressure-support feature, not PEEP itself), "T peep (Set)" (a time parameter, sec, wrong dimension), and a procedure-order "Intrinsic PEEP en Airtrap bepalen" (an order event, not a measurement). "Intrinsic PEEP" (auto-PEEP from air trapping) is included but is conceptually distinct from applied/set PEEP -- flag for likely reject or needs_policy.`

match 1:
  - decision: `keep`
  - decision reason: `PEEP (Set) -- cmH2O, primary channel.`
  - table: `numericitems`
  - itemid: `12284`
  - source token: `MEASUREMENT_BEDSIDE//12284//cmH2O`
  - row count: `15646826`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `PEEP (Set)`
  - raw unit: `cmH2O`

match 2:
  - decision: `keep`
  - decision reason: `PEEP/CPAP -- mbar, apply x1.0197 conversion to cmH2O (near-identical scale already).`
  - table: `numericitems`
  - itemid: `8862`
  - source token: `MEASUREMENT_BEDSIDE//8862//mbar`
  - row count: `85923`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `PEEP/CPAP`
  - raw unit: `mbar`

match 3:
  - decision: `keep`
  - decision reason: `PEEP (gemeten) -- mbar, apply x1.0197 conversion to cmH2O.`
  - table: `numericitems`
  - itemid: `8879`
  - source token: `MEASUREMENT_BEDSIDE//8879//mbar`
  - row count: `83693`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `PEEP (gemeten)`
  - raw unit: `mbar`

match 4:
  - decision: `keep`
  - decision reason: `PEEP tot -- cmH2O.`
  - table: `numericitems`
  - itemid: `12301`
  - source token: `MEASUREMENT_BEDSIDE//12301//cmH2O`
  - row count: `7302`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `PEEP tot`
  - raw unit: `cmH2O`

match 5:
  - decision: `reject`
  - decision reason: `Intrinsic PEEP -- auto-PEEP from air trapping, a different physiological concept from applied/set PEEP; plot showed it sitting distinctly above the concurrent measured PEEP, consistent with a genuinely different signal.`
  - table: `numericitems`
  - itemid: `8882`
  - source token: `MEASUREMENT_BEDSIDE//8882//mbar`
  - row count: `2149`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `Intrinsic PEEP`
  - raw unit: `mbar -- auto-PEEP, different concept from applied PEEP`

match 6:
  - decision: `keep`
  - decision reason: `CPAP PEEP (cmH2O)=7.5 -- categorical preset with an embedded numeric value; validated against the plot (matches the concurrent primary channel).`
  - table: `listitems`
  - itemid: `15142`
  - valueid: `1`
  - source token: `MEASUREMENT_CATEGORICAL//15142//1`
  - row count: `1901`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `CPAP PEEP (cmH2O)`
  - raw value: `7.5`

match 7:
  - decision: `keep`
  - decision reason: `CPAP PEEP (cmH2O)=10 -- same as match 6.`
  - table: `listitems`
  - itemid: `15142`
  - valueid: `2`
  - source token: `MEASUREMENT_CATEGORICAL//15142//2`
  - row count: `1336`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `CPAP PEEP (cmH2O)`
  - raw value: `10`

match 8:
  - decision: `keep`
  - decision reason: `Zephyros PEEP -- cmH2O, transport-vent channel.`
  - table: `numericitems`
  - itemid: `16250`
  - source token: `MEASUREMENT_BEDSIDE//16250//cmH2O`
  - row count: `241`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `Zephyros PEEP`
  - raw unit: `cmH2O`

match 9:
  - decision: `keep`
  - decision reason: `PEEP (Set) (2) -- cmH2O, duplicate device channel.`
  - table: `numericitems`
  - itemid: `12336`
  - source token: `MEASUREMENT_BEDSIDE//12336//cmH2O`
  - row count: `72`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `PEEP (Set) (2)`
  - raw unit: `cmH2O`

match 10:
  - decision: `keep`
  - decision reason: `PEEP (gemeten)(2) -- mbar, apply x1.0197 conversion to cmH2O.`
  - table: `numericitems`
  - itemid: `9666`
  - source token: `MEASUREMENT_BEDSIDE//9666//mbar`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:PEEP`
  - raw label: `PEEP (gemeten)(2)`
  - raw unit: `mbar`


### peak, Peak Pressure - Mechanical Ventilation, observation, respiratory

- Decision: `MTO`
- Target unit: `cmH2O`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `Piek druk -- cmH2O, primary channel.`
  - table: `numericitems`
  - itemid: `12281`
  - source token: `MEASUREMENT_BEDSIDE//12281//cmH2O`
  - row count: `15622631`
  - evidence: `supplied_vocab`
  - matched by: `term:Piek druk`
  - raw label: `Piek druk`
  - raw unit: `cmH2O`

match 2:
  - decision: `keep`
  - decision reason: `Peak druk -- mbar, apply x1.0197 conversion for precision (numerically near-identical to cmH2O already).`
  - table: `numericitems`
  - itemid: `8877`
  - source token: `MEASUREMENT_BEDSIDE//8877//mbar`
  - row count: `85106`
  - evidence: `supplied_vocab`
  - matched by: `term:Peak druk`
  - raw label: `Peak druk`
  - raw unit: `mbar`

match 3:
  - decision: `keep`
  - decision reason: `Zephyros Ppeak -- cmH2O, transport-vent channel.`
  - table: `numericitems`
  - itemid: `16239`
  - source token: `MEASUREMENT_BEDSIDE//16239//cmH2O`
  - row count: `64`
  - evidence: `supplied_vocab`
  - matched by: `term:Ppeak`
  - raw label: `Zephyros Ppeak`
  - raw unit: `cmH2O`

match 4:
  - decision: `keep`
  - decision reason: `Piek druk (2) -- cmH2O, duplicate device channel.`
  - table: `numericitems`
  - itemid: `12365`
  - source token: `MEASUREMENT_BEDSIDE//12365//cmH2O`
  - row count: `54`
  - evidence: `supplied_vocab`
  - matched by: `term:Piek druk`
  - raw label: `Piek druk (2)`
  - raw unit: `cmH2O`


### plateau, Plateau Pressure - Mechanical Ventilation, observation, respiratory

- Decision: `OTO`
- Target unit: `cmH2O`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Only one source item found; low row count relative to PEEP/peak is expected since plateau pressure requires an inspiratory-hold maneuver rather than being continuously displayed.`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 20958 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `8878`
  - source token: `MEASUREMENT_BEDSIDE//8878//mbar`
  - row count: `20958`
  - evidence: `supplied_vocab`
  - matched by: `term:Plateau druk`
  - raw label: `Plateau druk`
  - raw unit: `mbar`


### ps, Pressure Support - Mechanical Ventilation, observation, respiratory

- Decision: `MTO`
- Target unit: `cmH2O`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Excluded: "Trigger/ASB(curve)" (trigger-sensitivity waveform parameter, not the PS level) and "Flow trigger ASB" (unit l/min, wrong dimension), plus all "Ventilatie Mode (Set)"/"Type Beademing" listitems whose values merely contain the substring "PS"/"ASB" as part of a ventilation-mode name (categorical mode selection, not a numeric PS level).`

match 1:
  - decision: `keep`
  - decision reason: `PS boven PEEP (Set) -- cmH2O, standard PS-above-PEEP setting, dominant channel.`
  - table: `numericitems`
  - itemid: `12286`
  - source token: `MEASUREMENT_BEDSIDE//12286//cmH2O`
  - row count: `10799693`
  - evidence: `supplied_vocab`
  - matched by: `term:PS boven PEEP`
  - raw label: `PS boven PEEP (Set)`
  - raw unit: `cmH2O`

match 2:
  - decision: `keep`
  - decision reason: `ASB -- mbar; 'ASB' (Assistierte Spontanatmung) is just a different ventilator brand's term for Pressure Support; apply x1.0197 conversion.`
  - table: `numericitems`
  - itemid: `8865`
  - source token: `MEASUREMENT_BEDSIDE//8865//mbar`
  - row count: `74582`
  - evidence: `supplied_vocab`
  - matched by: `term:ASB`
  - raw label: `ASB`
  - raw unit: `mbar`

match 3:
  - decision: `keep`
  - decision reason: `PS boven P hoog (Set) -- same PS quantity, referenced against BIPAP's P-high baseline instead of PEEP; numerically the same 'extra pressure above baseline' concept.`
  - table: `numericitems`
  - itemid: `12298`
  - source token: `MEASUREMENT_BEDSIDE//12298//cmH2O`
  - row count: `9303`
  - evidence: `supplied_vocab`
  - matched by: `term:PS boven P hoog`
  - raw label: `PS boven P hoog (Set)`
  - raw unit: `cmH2O -- PS superimposed on BIPAP P-high, not plain PEEP`

match 4:
  - decision: `keep`
  - decision reason: `PS boven P hoog (Set) (2) -- same as match 3, duplicate device channel.`
  - table: `numericitems`
  - itemid: `12337`
  - source token: `MEASUREMENT_BEDSIDE//12337//cmH2O`
  - row count: `11`
  - evidence: `supplied_vocab`
  - matched by: `term:PS boven P hoog`
  - raw label: `PS boven P hoog (Set) (2)`
  - raw unit: `cmH2O`

match 5:
  - decision: `keep`
  - decision reason: `PS boven PEEP (Set) (2) -- same as match 1, duplicate device channel.`
  - table: `numericitems`
  - itemid: `12338`
  - source token: `MEASUREMENT_BEDSIDE//12338//cmH2O`
  - row count: `2`
  - evidence: `supplied_vocab`
  - matched by: `term:PS boven PEEP`
  - raw label: `PS boven PEEP (Set) (2)`
  - raw unit: `cmH2O`


### tv, Tidal Volume, observation, respiratory

- Decision: `MTO`
- Target unit: `ml`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `Exp. tidal volume -- realistic mL-scale values.`
  - table: `numericitems`
  - itemid: `12275`
  - source token: `MEASUREMENT_BEDSIDE//12275//ml`
  - row count: `15621567`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tidal Volume`
  - raw label: `Exp. tidal volume`
  - raw unit: `ml`

match 2:
  - decision: `keep`
  - decision reason: `Insp. tidal volume -- realistic mL-scale values.`
  - table: `numericitems`
  - itemid: `12277`
  - source token: `MEASUREMENT_BEDSIDE//12277//ml`
  - row count: `15613545`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tidal Volume`
  - raw label: `Insp. tidal volume`
  - raw unit: `ml`

match 3:
  - decision: `keep`
  - decision reason: `Tidal Volume (Set) -- metadata claims unit 'ml' but the actual values are L-scale (clean bimodal 0.5/2.0 clustering, confirmed on both 5k and 20k-sample histograms); convert x1000 (L->mL) before merging with matches 1/2/4/5.`
  - table: `numericitems`
  - itemid: `8851`
  - source token: `MEASUREMENT_BEDSIDE//8851//ml`
  - row count: `43121`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tidal Volume`
  - raw label: `Tidal Volume (Set)`
  - raw unit: `ml`

match 4:
  - decision: `keep`
  - decision reason: `Exp. tidal volume (2) -- realistic mL-scale duplicate device channel.`
  - table: `numericitems`
  - itemid: `12358`
  - source token: `MEASUREMENT_BEDSIDE//12358//ml`
  - row count: `68`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tidal Volume`
  - raw label: `Exp. tidal volume (2)`
  - raw unit: `ml`

match 5:
  - decision: `keep`
  - decision reason: `Insp. tidal volume (2) -- realistic mL-scale duplicate device channel.`
  - table: `numericitems`
  - itemid: `12360`
  - source token: `MEASUREMENT_BEDSIDE//12360//ml`
  - row count: `51`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tidal Volume`
  - raw label: `Insp. tidal volume (2)`
  - raw unit: `ml`

match 6:
  - decision: `reject`
  - decision reason: `Tidal Volume Spirometer -- n=13 total rows, too sparse to characterize or trust.`
  - table: `numericitems`
  - itemid: `8872`
  - source token: `MEASUREMENT_BEDSIDE//8872//ml`
  - row count: `13`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tidal Volume`
  - raw label: `Tidal Volume Spirometer`
  - raw unit: `ml`

match 7:
  - decision: `reject`
  - decision reason: `Tidal Volume (set)(2) -- n=1 total row, too sparse to characterize or trust.`
  - table: `numericitems`
  - itemid: `9646`
  - source token: `MEASUREMENT_BEDSIDE//9646//ml`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tidal Volume`
  - raw label: `Tidal Volume (set)(2)`
  - raw unit: `ml`

### airway, Type Of Airway Ventilation, observation, respiratory

- Decision: `MTO`
- Target unit: `categorical`
- Reconstruction type: `categorical`
- Mapping status: `source_candidates_found`
- Notes: `Revised 2026-07-14: every match below this point up to match 20 is a documentation field that only exists once an ETT/tracheostomy is already in place ("tube depth", "tube route", speaking-valve/cannula accessories) -- there was no category representing "no artificial airway" at all, which matters because categorical features are forward-filled indefinitely (unlike treatment_indicator, which reverts to 0 with no new event). This meant a real extubation had nowhere to register, silently persisting "Endotracheal tube" for the rest of the admission. Found (grid/_check_airway_categories.py) that itemid 8189 "Toedieningsweg" (delivery route) has 16 other valueids never matched at all, overwhelmingly non-invasive O2-delivery methods (nasal cannula, mask, HME, room air, etc.) -- ~570k rows (~64% of this itemid's total volume) previously unused. Added as matches 21-33 below: "No artificial airway (low-flow O2)" (valueids 1,2,3,4,7,8,9,10,11,12,13,14) and a separate "CPAP/NIV" category (valueid 16), since CPAP is a meaningfully different respiratory-support level than plain O2 delivery. valueid 11 "Trach.stoma" (1440 rows) was ambiguous -- checked the pattern across all 96 affected admissions (grid/_check_trach_stoma.py): 47.9% transition to a non-invasive delivery event immediately after (the largest single bucket, though not a majority -- 30.2%/28.1% show a tracheostomy accessory before/after too, so this sometimes reflects transient trach-care events rather than permanent decannulation). Given the plurality signal and the small volume either way, classified as "no artificial airway" -- the safer default since it avoids re-introducing the exact invasive-airway overstatement this fix targets.`

match 1:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `6735`
  - valueid: `8.0`
  - source token: `MEASUREMENT_CATEGORICAL//6735//8`
  - row count: `101764`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Beste verbale reactie`
  - raw value: `Geïntubeerd`
  - standardized label: `Endotracheal tube`

match 2:
  - decision: `keep`
  - decision reason: `merged into the 'Tracheostomy' category.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `19.0`
  - source token: `MEASUREMENT_CATEGORICAL//8189//19`
  - row count: `56393`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tracheostomy`
  - raw label: `Toedieningsweg`
  - raw value: `Spreekklepje`
  - standardized label: `Tracheostomy`

match 3:
  - decision: `keep`
  - decision reason: `merged into the 'Tracheostomy' category.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `18.0`
  - source token: `MEASUREMENT_CATEGORICAL//8189//18`
  - row count: `16066`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tracheostomy`
  - raw label: `Toedieningsweg`
  - raw value: `Spreekcanule`
  - standardized label: `Tracheostomy`

match 4:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12751`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//12751//1`
  - row count: `8737`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube referentiepunt`
  - raw value: `Mondhoek`
  - standardized label: `Endotracheal tube`

match 5:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12625`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//12625//1`
  - row count: `8701`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube route`
  - raw value: `Oraal`
  - standardized label: `Endotracheal tube`

match 6:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12623`
  - valueid: `5.0`
  - source token: `MEASUREMENT_CATEGORICAL//12623//5`
  - row count: `4741`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube diepte`
  - raw value: `23`
  - standardized label: `Endotracheal tube`

match 7:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `19640`
  - valueid: `15.0`
  - source token: `MEASUREMENT_CATEGORICAL//19640//15`
  - row count: `3794`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `V_EMV_NICE_Opname`
  - raw value: `Geïntubeerd`
  - standardized label: `Endotracheal tube`

match 8:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12624`
  - valueid: `6.0`
  - source token: `MEASUREMENT_CATEGORICAL//12624//6`
  - row count: `3415`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube maat`
  - raw value: `8.5`
  - standardized label: `Endotracheal tube`

match 9:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12623`
  - valueid: `3.0`
  - source token: `MEASUREMENT_CATEGORICAL//12623//3`
  - row count: `3315`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube diepte`
  - raw value: `21`
  - standardized label: `Endotracheal tube`

match 10:
  - decision: `reject`
  - decision reason: `Fixatie reden = 'Verwijderen tube, lijnen' -- a restraint-reason safety flag, not an airway type.`
  - table: `listitems`
  - itemid: `13397`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//13397//1`
  - row count: `2777`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Fixatie reden`
  - raw value: `Verwijderen tube, lijnen`

match 11:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12623`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//12623//4`
  - row count: `2661`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube diepte`
  - raw value: `22`
  - standardized label: `Endotracheal tube`

match 12:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12623`
  - valueid: `6.0`
  - source token: `MEASUREMENT_CATEGORICAL//12623//6`
  - row count: `2633`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube diepte`
  - raw value: `24`
  - standardized label: `Endotracheal tube`

match 13:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12624`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//12624//4`
  - row count: `2332`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube maat`
  - raw value: `7.5`
  - standardized label: `Endotracheal tube`

match 14:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12624`
  - valueid: `5.0`
  - source token: `MEASUREMENT_CATEGORICAL//12624//5`
  - row count: `1909`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube maat`
  - raw value: `8`
  - standardized label: `Endotracheal tube`

match 15:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12751`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//12751//2`
  - row count: `1721`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube referentiepunt`
  - raw value: `Tandenrij`
  - standardized label: `Endotracheal tube`

match 16:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12623`
  - valueid: `7.0`
  - source token: `MEASUREMENT_CATEGORICAL//12623//7`
  - row count: `1659`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube diepte`
  - raw value: `25`
  - standardized label: `Endotracheal tube`

match 17:
  - decision: `keep`
  - decision reason: `merged into the 'Tracheostomy' category.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `11.0`
  - source token: `MEASUREMENT_CATEGORICAL//8189//11`
  - row count: `1446`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tracheostomy`
  - raw label: `Toedieningsweg`
  - raw value: `Trach.stoma`
  - standardized label: `Tracheostomy`

match 18:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `19637`
  - valueid: `9.0`
  - source token: `MEASUREMENT_CATEGORICAL//19637//9`
  - row count: `813`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `V_EMV_NICE_24uur`
  - raw value: `Geïntubeerd`
  - standardized label: `Endotracheal tube`

match 19:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12624`
  - valueid: `3.0`
  - source token: `MEASUREMENT_CATEGORICAL//12624//3`
  - row count: `797`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube maat`
  - raw value: `7`
  - standardized label: `Endotracheal tube`

match 20:
  - decision: `keep`
  - decision reason: `merged into the 'Endotracheal tube' category -- Geintubeerd flag plus tube depth/size/route/reference-point documentation, all only present when an ETT is in place.`
  - table: `listitems`
  - itemid: `12623`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//12623//2`
  - row count: `762`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Tube`
  - raw label: `Tube diepte`
  - raw value: `20`
  - standardized label: `Endotracheal tube`

match 21:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- found 2026-07-14, see feature Notes above. Deep nasal cannula, a non-invasive O2-delivery route.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `1.0`
  - row count: `15704`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Diep Nasaal`
  - standardized label: `No artificial airway (low-flow O2)`

match 22:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `2.0`
  - row count: `3432`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Nasaal`
  - standardized label: `No artificial airway (low-flow O2)`

match 23:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. Face mask, non-invasive.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `3.0`
  - row count: `52462`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Kapje`
  - standardized label: `No artificial airway (low-flow O2)`

match 24:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. HME filter ("artificial nose"), used without an artificial airway.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `4.0`
  - row count: `99359`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Kunstneus`
  - standardized label: `No artificial airway (low-flow O2)`

match 25:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. Nasal cannula, the single largest delivery-route value in this itemid (336525 rows).`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `7.0`
  - row count: `336525`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `O2-bril`
  - standardized label: `No artificial airway (low-flow O2)`

match 26:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. Chin-strap mask, non-invasive.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `8.0`
  - row count: `9073`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Kinnebak`
  - standardized label: `No artificial airway (low-flow O2)`

match 27:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `9.0`
  - row count: `261`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Nebulizer`
  - standardized label: `No artificial airway (low-flow O2)`

match 28:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. Humidification set.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `10.0`
  - row count: `61`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Waterset`
  - standardized label: `No artificial airway (low-flow O2)`

match 29:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- ambiguous, classified here on balance of evidence, see feature Notes above (grid/_check_trach_stoma.py: 47.9% of affected admissions transition to a non-invasive delivery route immediately after this event, the largest single pattern though not a majority).`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `11.0`
  - row count: `1440`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Trach.stoma`
  - standardized label: `No artificial airway (low-flow O2)`

match 30:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. Ambient/room air.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `12.0`
  - row count: `12644`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `B.Lucht`
  - standardized label: `No artificial airway (low-flow O2)`

match 31:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. Bag-valve-mask, non-invasive (used transiently, not an indwelling airway device).`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `13.0`
  - row count: `19`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Ambu`
  - standardized label: `No artificial airway (low-flow O2)`

match 32:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. Guedel oropharyngeal airway adjunct -- not an artificial airway in the ETT/tracheostomy sense.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `14.0`
  - row count: `81`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Guedel`
  - standardized label: `No artificial airway (low-flow O2)`

match 33:
  - decision: `keep`
  - decision reason: `merged into the new 'No artificial airway (low-flow O2)' category -- see match 21. Non-rebreather mask, non-invasive.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `17.0`
  - row count: `36444`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `Non-Rebreathing masker`
  - standardized label: `No artificial airway (low-flow O2)`

match 34:
  - decision: `keep`
  - decision reason: `new 'CPAP/NIV' category -- found 2026-07-14, see feature Notes above. Kept separate from the low-flow O2 bucket since CPAP is a meaningfully different respiratory-support level, not just a delivery-route variant.`
  - table: `listitems`
  - itemid: `8189`
  - valueid: `16.0`
  - row count: `4471`
  - evidence: `direct_raw_data_check`
  - raw label: `Toedieningsweg`
  - raw value: `CPAP`
  - standardized label: `CPAP/NIV`

### supp_o2_vent, Supplemental Oxygen From Ventilator, treatment, respiratory

- Decision: `MTO`
- Target unit: `%`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`
- Notes: `Although Table S3 marks this as treatment, source candidates are ventilator FiO2 numeric settings.`

match 1:
  - decision: `keep`
  - decision reason: `FiO2 % -- mirrors fio2 match 2; treatment feature uses same source, zero-filled instead of forward-filled.`
  - table: `numericitems`
  - itemid: `6699`
  - source token: `MEASUREMENT_BEDSIDE//6699//Geen`
  - row count: `91881`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `FiO2 %`
  - raw unit: `Geen`

match 2:
  - decision: `reject`
  - decision reason: `A_FiO2 -- excluded, mirrors fio2.`
  - table: `numericitems`
  - itemid: `13076`
  - source token: `MEASUREMENT_BEDSIDE//13076//Geen`
  - row count: `10817`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `A_FiO2`
  - raw unit: `Geen`

match 3:
  - decision: `keep`
  - decision reason: `MCA_FiO2 -- mirrors fio2 match 5.`
  - table: `numericitems`
  - itemid: `16629`
  - source token: `MEASUREMENT_BEDSIDE//16629//Geen`
  - row count: `1951`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `MCA_FiO2`
  - raw unit: `Geen`

match 4:
  - decision: `reject`
  - decision reason: `ECMO - FiO2 -- excluded, mirrors fio2.`
  - table: `numericitems`
  - itemid: `20656`
  - source token: `MEASUREMENT_BEDSIDE//20656//Geen`
  - row count: `478`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `ECMO - FiO2`
  - raw unit: `Geen`

match 5:
  - decision: `keep`
  - decision reason: `Zephyros FiO2 -- mirrors fio2 match 7.`
  - table: `numericitems`
  - itemid: `16246`
  - source token: `MEASUREMENT_BEDSIDE//16246//Geen`
  - row count: `239`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FiO2`
  - raw label: `Zephyros FiO2`
  - raw unit: `Geen`

match 6:
  - decision: `keep`
  - decision reason: `RA_FiO2 -- mirrors fio2 match 8.`
  - table: `numericitems`
  - itemid: `14471`
  - source token: `MEASUREMENT_BEDSIDE//14471//Geen`
  - row count: `76`
  - evidence: `source_vocab`
  - matched by: `term:FiO2`
  - raw label: `RA_FiO2`
  - raw unit: `Geen`

match 7:
  - decision: `keep`
  - decision reason: `Breathing FiO2(%) -- mirrors fio2 match 10.`
  - table: `numericitems`
  - itemid: `20134`
  - source token: `MEASUREMENT_BEDSIDE//20134//UNKNOWN`
  - row count: `14`
  - evidence: `source_vocab`
  - matched by: `term:FiO2`
  - raw label: `Breathing FiO2(%)`

match 8:
  - decision: `keep`
  - decision reason: `O2 concentratie -- added to close the gap left by this feature's term:FiO2 matcher missing the dominant ventilator-FiO2 channel (only linked via OMOP concept ID in fio2, not a literal 'FiO2' label match); mirrors fio2 match 1.`
  - table: `numericitems`
  - itemid: `12279`
  - source token: `MEASUREMENT_BEDSIDE//12279//Geen`
  - row count: `15645395`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `openicu_omop_id`
  - raw label: `O2 concentratie`
  - raw unit: `Geen`

### ygt, Gamma GT, observation, gastrointestinal

- Decision: `OTO`
- Target unit: `U/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 2001 >= 10 -- sufficient volume, no competing matches.`
  - table: `numericitems`
  - itemid: `6831`
  - source token: `LAB//6831//E/l`
  - row count: `2001`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Gamma GT`
  - raw label: `Gamma GT`
  - raw unit: `E/l`

### amm, Ammonia, observation, gastrointestinal

- Decision: `MTO`
- Target unit: `umol/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `Ammoniak (bloed) -- blood, primary channel.`
  - table: `numericitems`
  - itemid: `10052`
  - source token: `LAB//10052//µmol/l`
  - row count: `1704`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Ammonia`
  - raw label: `Ammoniak (bloed)`
  - raw unit: `µmol/l`

match 2:
  - decision: `keep`
  - decision reason: `Ammoniak -- tracks closely with match 1's values/timestamps.`
  - table: `numericitems`
  - itemid: `6805`
  - source token: `LAB//6805//µmol`
  - row count: `47`
  - evidence: `source_vocab`
  - matched by: `term:Ammonia`
  - raw label: `Ammoniak`
  - raw unit: `µmol`

match 3:
  - decision: `reject`
  - decision reason: `Ammoniak (urine) -- wrong compartment, and a ~86,000 outlier value confirms it's not blood-comparable.`
  - table: `numericitems`
  - itemid: `10381`
  - source token: `LAB//10381//µmol/l`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:Ammonia`
  - raw label: `Ammoniak  (urine)`
  - raw unit: `µmol/l`

### amyl, Amylase, observation, gastrointestinal

- Decision: `MTO`
- Target unit: `U/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `Amylase (bloed) -- blood, primary channel.`
  - table: `numericitems`
  - itemid: `11986`
  - source token: `LAB//11986//E/l`
  - row count: `35727`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amylase`
  - raw label: `Amylase (bloed)`
  - raw unit: `E/l`

match 2:
  - decision: `keep`
  - decision reason: `Plasma Amylase -- plasma, compatible compartment.`
  - table: `numericitems`
  - itemid: `6845`
  - source token: `LAB//6845//E/l`
  - row count: `1138`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amylase`
  - raw label: `Plasma Amylase`
  - raw unit: `E/l`

match 3:
  - decision: `keep`
  - decision reason: `AMYLASE (overig) -- accepted alongside bloed/plasma per user policy.`
  - table: `numericitems`
  - itemid: `11987`
  - source token: `LAB//11987//E/l`
  - row count: `351`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amylase`
  - raw label: `AMYLASE (overig)`
  - raw unit: `E/l`

match 4:
  - decision: `reject`
  - decision reason: `drain fluid, wrong compartment.`
  - table: `numericitems`
  - itemid: `17980`
  - source token: `LAB//17980//E/l`
  - row count: `310`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amylase`
  - raw label: `Amylase drainvocht (drain)`
  - raw unit: `E/l`

match 5:
  - decision: `reject`
  - decision reason: `urine, wrong compartment.`
  - table: `numericitems`
  - itemid: `11988`
  - source token: `LAB//11988//E/l`
  - row count: `170`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amylase`
  - raw label: `Amylase (urine)`
  - raw unit: `E/l`

match 6:
  - decision: `reject`
  - decision reason: `ascitic fluid, wrong compartment.`
  - table: `numericitems`
  - itemid: `17979`
  - source token: `LAB//17979//E/l`
  - row count: `35`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amylase`
  - raw label: `Amylase ascitesvocht (ascitesvocht)`
  - raw unit: `E/l`

match 7:
  - decision: `reject`
  - decision reason: `pleural fluid, wrong compartment.`
  - table: `numericitems`
  - itemid: `18849`
  - source token: `LAB//18849//E/l`
  - row count: `32`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amylase`
  - raw label: `Amylase pleuravocht (pleurapunct.)`
  - raw unit: `E/l`

match 8:
  - decision: `reject`
  - decision reason: `urine, wrong compartment, and wrong unit (mmol/l vs E/l).`
  - table: `numericitems`
  - itemid: `8922`
  - source token: `LAB//8922//mmol/l`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amylase`
  - raw label: `Amylase in Urine`
  - raw unit: `mmol/l`

### lip, Lipase, observation, gastrointestinal

- Decision: `OTO`
- Target unit: `U/L`
- Reconstruction type: `direct_numeric`
- Mapping status: `source_candidates_found`

match 1:
  - decision: `keep`
  - decision reason: `Lipase (bloed) -- blood, primary channel; unit E/l = U/L already, no conversion needed.`
  - table: `numericitems`
  - itemid: `12043`
  - source token: `LAB//12043//E/l`
  - row count: `3436`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lipase`
  - raw label: `Lipase (bloed)`
  - raw unit: `E/l`

match 2:
  - decision: `reject`
  - decision reason: `Lipase (overig) -- ambiguous non-blood specimen category, consistent with the ca 'CALCIUM (overig)' precedent.`
  - table: `numericitems`
  - itemid: `12044`
  - source token: `LAB//12044//E/l`
  - row count: `63`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lipase`
  - raw label: `Lipase (overig)`
  - raw unit: `E/l`

match 3:
  - decision: `reject`
  - decision reason: `drain fluid, wrong compartment (real clinical test for pancreatic leak, but not blood lipase).`
  - table: `numericitems`
  - itemid: `18450`
  - source token: `LAB//18450//E/l`
  - row count: `11`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lipase`
  - raw label: `Lipase drainvocht (drain)`
  - raw unit: `E/l`

match 4:
  - decision: `reject`
  - decision reason: `ascitic fluid, wrong compartment.`
  - table: `numericitems`
  - itemid: `18449`
  - source token: `LAB//18449//E/l`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lipase`
  - raw label: `Lipase ascitesvocht (ascitesvocht)`
  - raw unit: `E/l`

match 5:
  - decision: `reject`
  - decision reason: `n=1, unit not even recorded -- too little to trust.`
  - table: `numericitems`
  - itemid: `7810`
  - source token: `LAB//7810//UNKNOWN`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lipase`
  - raw label: `Lipase`

### ufilt, Ultrafiltration On Continuous RRT, treatment, metabolic_renal

- Decision: `OTO`
- Target unit: `ml`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `MFT_Filtraat druk -- filtrate pressure (mmHg), wrong physical dimension entirely.`
  - table: `numericitems`
  - itemid: `14836`
  - source token: `MEASUREMENT_BEDSIDE//14836//mmHg`
  - row count: `2086046`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Filtraat`
  - raw label: `MFT_Filtraat druk`
  - raw unit: `mmHg`

match 2:
  - decision: `reject`
  - decision reason: `MFT_UF Totaal (ingesteld) -- ~99.99% zero-valued (2 nonzero values out of a 20k sample), uninformative despite the label match.`
  - table: `numericitems`
  - itemid: `14851`
  - source token: `MEASUREMENT_BEDSIDE//14851//ml`
  - row count: `1796778`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_UF totaal`
  - raw label: `MFT_UF Totaal (ingesteld)`
  - raw unit: `ml`

match 3:
  - decision: `reject`
  - decision reason: `MFT_Filtraatvolume_totaal -- total filtrate volume includes replacement fluid, a broader concept than net ultrafiltration; also a cumulative per-session counter that resets (sawtooth pattern), not usable as a rate without differencing.`
  - table: `numericitems`
  - itemid: `20079`
  - source token: `MEASUREMENT_BEDSIDE//20079//l`
  - row count: `1664541`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Filtraat`
  - raw label: `MFT_Filtraatvolume_totaal`
  - raw unit: `l`

match 4:
  - decision: `reject`
  - decision reason: `MFT_Filtraatvolume_huidig -- same issue as match 3.`
  - table: `numericitems`
  - itemid: `20078`
  - source token: `MEASUREMENT_BEDSIDE//20078//l`
  - row count: `1664478`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Filtraat`
  - raw label: `MFT_Filtraatvolume_huidig`
  - raw unit: `l`

match 5:
  - decision: `reject`
  - decision reason: `MFT_Predilutievolume_totaal -- replacement fluid added BEFORE the filter, wrong direction (fluid in, not removed).`
  - table: `numericitems`
  - itemid: `20707`
  - source token: `MEASUREMENT_BEDSIDE//20707//l`
  - row count: `906320`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Predilutie`
  - raw label: `MFT_Predilutievolume_totaal`
  - raw unit: `l`

match 6:
  - decision: `reject`
  - decision reason: `MFT_Predilutievolume_huidig -- same wrong-direction issue as match 5.`
  - table: `numericitems`
  - itemid: `20706`
  - source token: `MEASUREMENT_BEDSIDE//20706//l`
  - row count: `906298`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Predilutie`
  - raw label: `MFT_Predilutievolume_huidig`
  - raw unit: `l`

match 7:
  - decision: `reject`
  - decision reason: `MFT_Postdilutievolume_totaal -- replacement fluid added AFTER the filter, wrong direction; also a reset-counter (0->50000 ramps).`
  - table: `numericitems`
  - itemid: `20709`
  - source token: `MEASUREMENT_BEDSIDE//20709//l`
  - row count: `900252`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Postdilutie`
  - raw label: `MFT_Postdilutievolume_totaal`
  - raw unit: `l`

match 8:
  - decision: `reject`
  - decision reason: `MFT_Postdilutievolume_huidig -- same wrong-direction issue as match 7.`
  - table: `numericitems`
  - itemid: `20708`
  - source token: `MEASUREMENT_BEDSIDE//20708//l`
  - row count: `900237`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Postdilutie`
  - raw label: `MFT_Postdilutievolume_huidig`
  - raw unit: `l`

match 9:
  - decision: `reject`
  - decision reason: `MFT_Predilutieflow (ingesteld) -- rate of fluid being ADDED (pre-dilution), wrong direction.`
  - table: `numericitems`
  - itemid: `20710`
  - source token: `MEASUREMENT_BEDSIDE//20710//ml/uur`
  - row count: `829771`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Predilutie`
  - raw label: `MFT_Predilutieflow (ingesteld)`
  - raw unit: `ml/uur`

match 10:
  - decision: `reject`
  - decision reason: `MFT_Postdilutieflow (ingesteld) -- rate of fluid being ADDED (post-dilution), wrong direction.`
  - table: `numericitems`
  - itemid: `20716`
  - source token: `MEASUREMENT_BEDSIDE//20716//ml/uur`
  - row count: `818547`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Postdilutie`
  - raw label: `MFT_Postdilutieflow (ingesteld)`
  - raw unit: `ml/uur`

match 11:
  - decision: `reject`
  - decision reason: `REVISED (2026-07-10): resolved empirically rather than left as a low-confidence keep. Label ('behandel afspraken' = treatment arrangements/orders) already hinted this is a prescribed target, not an achieved measurement -- confirmed: only 533 rows/98 admissions (sparse), 38% exactly zero, non-zero values suspiciously round (100/150/250/1000, consistent with a dialed-in prescription increment). Checked the 71 admissions with both this and match 12 (itemid 8805) directly: itemid 20543 appears as a SINGLE static entry per admission (e.g. admission 10243: logged twice at the identical timestamp, value 200.0), never a recurring stream, versus match 12's dense ~1-2h-interval continuously-varying readings for the same admission. Same 'ordered/set vs measured/actual' pattern (doctrine #5) that already got 'UF Totaal (ingesteld)' rejected earlier in this feature -- reject for the same reason.`
  - table: `numericitems`
  - itemid: `20543`
  - source token: `MEASUREMENT_BEDSIDE//20543//ml/uur`
  - row count: `533`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Ultrafiltration`
  - raw label: `CVVH behandel afspraken Onttrekken`
  - raw unit: `ml/uur`

match 12:
  - decision: `keep`
  - decision reason: `CVVH Onttrokken -- 'withdrawn', the actual net fluid removed via CVVH; a more direct measure of achieved ultrafiltration than match 2's dead 'UF Totaal (ingesteld)' set-target field. Well-populated, continuously-varying distribution (median 110, IQR 70-200) consistent with real hourly withdrawal amounts. Added to close a candidate-pool gap -- this itemid was only caught by ufilt_ind's broader term:CVVH matcher, never by ufilt's own term:MFT_/term:Ultrafiltration matchers.`
  - table: `numericitems`
  - itemid: `8805`
  - source token: `SUBJECT_FLUID_OUTPUT//8805//ml`
  - row count: `92266`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `CVVH Onttrokken`
  - raw unit: `ml`

match 13:
  - decision: `reject`
  - decision reason: `REVISED (2026-07-10): resolved the double-ingestion question empirically rather than deferring it -- checked raw values directly. This MEASUREMENT_BEDSIDE route of itemid 8805 is 100.00% zero (6117/6117 rows, min=p50=p90=max=0.0), a dead channel exactly like match 2's already-rejected 'UF Totaal (ingesteld)'. Match 12's SUBJECT_FLUID_OUTPUT route is the real signal (0% zero, median 120, up to 4565) and is confirmed as the sole canonical route -- not a genuine duplicate-route dedup case, just another dead channel sharing the itemid. No timestamp overlap exists between the two routes' rows either way (0 shared (admissionid,measuredat) pairs across 613 admissions with both), so summing would not have double-counted real data, but would have diluted the real signal with zeros.`
  - table: `numericitems`
  - itemid: `8805`
  - source token: `MEASUREMENT_BEDSIDE//8805//ml`
  - row count: `6117`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `CVVH Onttrokken`
  - raw unit: `ml`

### ufilt_ind, Ultrafiltration On Continuous RRT Indicator, treatment, metabolic_renal

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `MFT_Arteriele bovengrens -- static alarm-limit setting, not a reliable presence signal.`
  - table: `numericitems`
  - itemid: `14842`
  - source token: `MEASUREMENT_BEDSIDE//14842//mmHg`
  - row count: `2007033`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_Arteriele bovengrens`
  - raw unit: `mmHg`

match 2:
  - decision: `reject`
  - decision reason: `MFT_TMP bovengrens -- static alarm-limit setting.`
  - table: `numericitems`
  - itemid: `14840`
  - source token: `MEASUREMENT_BEDSIDE//14840//mmHg`
  - row count: `2007019`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_TMP bovengrens`
  - raw unit: `mmHg`

match 3:
  - decision: `reject`
  - decision reason: `MFT_Arteriele ondergrens -- static alarm-limit setting.`
  - table: `numericitems`
  - itemid: `14841`
  - source token: `MEASUREMENT_BEDSIDE//14841//mmHg`
  - row count: `2007019`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_Arteriele ondergrens`
  - raw unit: `mmHg`

match 4:
  - decision: `reject`
  - decision reason: `MFT_Veneuze bovengrens -- static alarm-limit setting.`
  - table: `numericitems`
  - itemid: `14843`
  - source token: `MEASUREMENT_BEDSIDE//14843//mmHg`
  - row count: `2007019`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_Veneuze bovengrens`
  - raw unit: `mmHg`

match 5:
  - decision: `reject`
  - decision reason: `MFT_TMP ondergrens -- static alarm-limit setting.`
  - table: `numericitems`
  - itemid: `14845`
  - source token: `MEASUREMENT_BEDSIDE//14845//mmHg`
  - row count: `2007018`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_TMP ondergrens`
  - raw unit: `mmHg`

match 6:
  - decision: `reject`
  - decision reason: `MFT_Veneuze ondergrens -- static alarm-limit setting.`
  - table: `numericitems`
  - itemid: `14844`
  - source token: `MEASUREMENT_BEDSIDE//14844//mmHg`
  - row count: `2007015`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_Veneuze ondergrens`
  - raw unit: `mmHg`

match 7:
  - decision: `keep`
  - decision reason: `MFT_UF Totaal (ingesteld) -- presence (not value) confirms UF is configured/running.`
  - table: `numericitems`
  - itemid: `14851`
  - source token: `MEASUREMENT_BEDSIDE//14851//ml`
  - row count: `1796778`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_UF Totaal (ingesteld)`
  - raw unit: `ml`

match 8:
  - decision: `keep`
  - decision reason: `MFT_Behandelingsduur -- treatment-duration counter, presence = treatment running.`
  - table: `numericitems`
  - itemid: `20080`
  - source token: `MEASUREMENT_BEDSIDE//20080//uur`
  - row count: `1664550`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Behandeling`
  - raw label: `MFT_Behandelingsduur`
  - raw unit: `uur`

match 9:
  - decision: `keep`
  - decision reason: `MFT_Filtraatvolume_huidig -- presence confirms filtration running.`
  - table: `numericitems`
  - itemid: `20078`
  - source token: `MEASUREMENT_BEDSIDE//20078//l`
  - row count: `1664478`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_Filtraatvolume_huidig`
  - raw unit: `l`

match 10:
  - decision: `keep`
  - decision reason: `MFT_FilterLooptijd -- filter-runtime counter, presence = filter running.`
  - table: `numericitems`
  - itemid: `20340`
  - source token: `MEASUREMENT_BEDSIDE//20340//uur`
  - row count: `1164528`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_FilterLooptijd`
  - raw unit: `uur`

match 11:
  - decision: `keep`
  - decision reason: `MFT_Behandeling=CVVH -- cleanest direct mode-selection signal.`
  - table: `listitems`
  - itemid: `14846`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//14846//2`
  - row count: `1095375`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Behandeling`
  - raw label: `MFT_Behandeling`
  - raw value: `CVVH`

match 12:
  - decision: `keep`
  - decision reason: `MFT_Behandeling=HVCVVH -- same as match 11, other mode variant.`
  - table: `listitems`
  - itemid: `14846`
  - valueid: `3.0`
  - source token: `MEASUREMENT_CATEGORICAL//14846//3`
  - row count: `1058632`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MFT_Behandeling`
  - raw label: `MFT_Behandeling`
  - raw value: `HVCVVH`

match 13:
  - decision: `keep`
  - decision reason: `MFT_Predilutievolume_huidig -- presence confirms CVVH circuit active (direction doesn't matter for an indicator).`
  - table: `numericitems`
  - itemid: `20706`
  - source token: `MEASUREMENT_BEDSIDE//20706//l`
  - row count: `906298`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_Predilutievolume_huidig`
  - raw unit: `l`

match 14:
  - decision: `keep`
  - decision reason: `MFT_Postdilutievolume_huidig -- same as match 13.`
  - table: `numericitems`
  - itemid: `20708`
  - source token: `MEASUREMENT_BEDSIDE//20708//l`
  - row count: `900237`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `MFT_Postdilutievolume_huidig`
  - raw unit: `l`

match 15:
  - decision: `keep`
  - decision reason: `CVVH Onttrokken -- genuine net fluid withdrawn, strong presence signal.`
  - table: `numericitems`
  - itemid: `8805`
  - source token: `SUBJECT_FLUID_OUTPUT//8805//ml`
  - row count: `92266`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `CVVH Onttrokken`
  - raw unit: `ml`

match 16:
  - decision: `keep`
  - decision reason: `CVVH-Vochtverlies stand -- fluid-loss counter, presence signal.`
  - table: `numericitems`
  - itemid: `12091`
  - source token: `MEASUREMENT_BEDSIDE//12091//ml`
  - row count: `83945`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `CVVH-Vochtverlies stand`
  - raw unit: `ml`

match 17:
  - decision: `reject`
  - decision reason: `Vit B/C per CVVH-protocol -- a vitamin supplement given because of CVVH, not evidence CVVH is running.`
  - table: `drugitems`
  - itemid: `9475`
  - ordercategoryid: `67.0`
  - source token: `DRUG//START//67//9475`
  - row count: `7755`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `Vit B/C (vlgs CVVH-protocol)`
  - raw value: `Injecties Hormonen/Vitaminen/Mineralen`

match 18:
  - decision: `keep`
  - decision reason: `CVVH Onttrokken (duplicate table route) -- same as match 15.`
  - table: `numericitems`
  - itemid: `8805`
  - source token: `MEASUREMENT_BEDSIDE//8805//ml`
  - row count: `6117`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `CVVH Onttrokken`
  - raw unit: `ml`

match 19:
  - decision: `keep`
  - decision reason: `CVVH (processitems session interval) -- literal session start/stop marker, cleanest signal of all.`
  - table: `processitems`
  - itemid: `12465`
  - source token: `PROCESS_INTERVAL//12465`
  - row count: `5355`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `CVVH`

match 20:
  - decision: `keep`
  - decision reason: `CVVH-Vocht teruggave -- fluid return during CVVH, presence signal.`
  - table: `drugitems`
  - itemid: `10738`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//10738`
  - row count: `566`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:CVVH`
  - raw label: `CVVH-Vocht teruggave`
  - raw value: `Infuus - Crystalloid`

### dobu, Dobutamine, treatment, circulatory

- Decision: `OTO`
- Target unit: `mcg/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 9168 >= 10 -- sufficient volume, no competing matches.`
  - table: `drugitems`
  - itemid: `7178`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7178`
  - row count: `9168`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Dobutamine`
  - raw label: `Dobutamine (Dobutrex)`
  - raw value: `2. Spuitpompen`

### levo, Levosimendan, treatment, circulatory

- Decision: `[MTO/OTO]`
- Target unit: `mcg/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `no_source_candidates`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals. Verified genuinely absent from AmsterdamUMCdb: no drugitems row for Levosimendan (Simdax) in supplied_vocab.csv, the official AmsterdamUMCdb OMOP dictionary_map.csv, or the raw amsterdamumcdb/dictionary/dictionary.csv (checked brand names and INN synonyms too).`

No source-candidate matches recorded.

### norepi, Norepinephrine, treatment, circulatory

- Decision: `OTO`
- Target unit: `mcg/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals. Same two source rows apply to both norepi and norepi_ind (identical pattern to epi/epi_ind, dopa/dopa_ind). NB: itemid 7229 (Noradrenaline) is *also* currently listed under the epi/epi_ind (Epinephrine) sections -- apparent term-matcher cross-contamination ("Nor-ADRENALINE" contains "adrenaline"); recommend rejecting those rows from epi/epi_ind during stage 2.`

match 1:
  - decision: `keep`
  - decision reason: `genuine Noradrenaline syringe-pump infusion, dominant channel.`
  - table: `drugitems`
  - itemid: `7229`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7229`
  - row count: `261506`
  - evidence: `supplied_vocab`
  - matched by: `term:Noradrenaline`
  - raw label: `Noradrenaline (Norepinefrine)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `n=1, ordercategory 'Niet iv CZS/Sedatie/Analgetica' is clinically implausible for a vasopressor -- likely miscoded; not trusted as a real administration record.`
  - table: `drugitems`
  - itemid: `7229`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7229`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Noradrenaline`
  - raw label: `Noradrenaline (Norepinefrine)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica -- likely miscoded (non-IV route for a vasopressor is clinically implausible)`


### epi, Epinephrine, treatment, circulatory

- Decision: `OTO`
- Target unit: `mcg/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `Noradrenaline, not epinephrine -- term-matcher cross-contamination ('Nor-ADRENALINE' contains 'adrenaline'); this drug is norepi's, not epi's.`
  - table: `drugitems`
  - itemid: `7229`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7229`
  - row count: `261506`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Noradrenaline (Norepinefrine)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `genuine epinephrine (Adrenaline) administration record.`
  - table: `drugitems`
  - itemid: `6818`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//6818`
  - row count: `2195`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Adrenaline (Epinefrine)`
  - raw value: `2. Spuitpompen`

match 3:
  - decision: `reject`
  - decision reason: `REVISED (2026-07-10, treatment_rate strategy check): ordercategoryid=24 ('Injecties Circulatie/Diuretica') is the bolus-injection route, not continuous infusion -- confirmed empirically, 520/520 rows (100%) have duration==1min, the same fixed bolus-logging-artifact signature already established for heparin/propofol/furosemide injection routes elsewhere in this manifest. Was previously kept into the rate feature without this check; corrected to reject and routed to epi_ind instead, consistent with doctrine (bolus events are presence-only, not a real rate window).`
  - table: `drugitems`
  - itemid: `6818`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6818`
  - row count: `520`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Adrenaline (Epinefrine)`
  - raw value: `Injecties Circulatie/Diuretica`

match 4:
  - decision: `reject`
  - decision reason: `blood concentration lab test, not an administration record. (Noradrenaline serum level.)`
  - table: `numericitems`
  - itemid: `10196`
  - source token: `LAB//10196//nmol/l`
  - row count: `26`
  - evidence: `source_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Noradrenaline (serum)`
  - raw unit: `nmol/l`

match 5:
  - decision: `reject`
  - decision reason: `blood concentration lab test, not an administration record. (Adrenaline blood level.)`
  - table: `numericitems`
  - itemid: `10197`
  - source token: `LAB//10197//nmol/l`
  - row count: `26`
  - evidence: `source_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Adrenaline  (bloed)`
  - raw unit: `nmol/l`

match 6:
  - decision: `reject`
  - decision reason: `Noradrenaline, not epinephrine -- term-matcher cross-contamination ('Nor-ADRENALINE' contains 'adrenaline'); this drug is norepi's, not epi's.`
  - table: `drugitems`
  - itemid: `7229`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7229`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Noradrenaline (Norepinefrine)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 7:
  - decision: `reject`
  - decision reason: `blood concentration lab test, not an administration record. (Noradrenaline plasma level.)`
  - table: `numericitems`
  - itemid: `10198`
  - source token: `LAB//10198//nmol/l`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Noradrenaline (plasma)`
  - raw unit: `nmol/l`

match 8:
  - decision: `reject`
  - decision reason: `blood concentration lab test, not an administration record. (Adrenaline blood level.)`
  - table: `numericitems`
  - itemid: `10199`
  - source token: `LAB//10199//nmol/l`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Adrenaline (bloed)`
  - raw unit: `nmol/l`

### milrin, Milrinone, treatment, circulatory

- Decision: `[MTO/OTO]`
- Target unit: `mcg/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `no_source_candidates`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals. Verified genuinely absent from AmsterdamUMCdb: no drugitems row for Milrinone (Corotrop) in supplied_vocab.csv, the official AmsterdamUMCdb OMOP dictionary_map.csv, or the raw amsterdamumcdb/dictionary/dictionary.csv (checked brand names and INN synonyms too).`

No source-candidate matches recorded.

### teophyllin, Theophylline, treatment, circulatory

- Decision: `MTO`
- Target unit: `mg/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `Theofylline/Spuitpompen -- genuine continuous infusion (real, variable durations, not the fixed-1-minute bolus artifact); reconstruct as dose / duration.`
  - table: `drugitems`
  - itemid: `13000`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//13000`
  - row count: `138`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Theofylline`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `Theolair retard/oral -- discrete sustained-release tablet dose (fixed duration=1min artifact, tightly clustered at standard tablet strengths), not a rate.`
  - table: `drugitems`
  - itemid: `9143`
  - ordercategoryid: `70.0`
  - source token: `DRUG//START//70//9143`
  - row count: `101`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Theolair retard (Theofylline)`
  - raw value: `Niet iv Tractus Respiratorius`

match 3:
  - decision: `keep`
  - decision reason: `Aminofylline/Spuitpompen -- genuine continuous infusion like match 1; reconstruct as dose / duration, PLUS convert aminophylline -> theophylline (x0.8, aminophylline is ~79-80% theophylline by weight). Histogram validation (plot_dose_conversion_validation.py) confirms the converted distribution overlaps Theofylline's real distribution's core cluster (~0.5-10 mg/h) well.`
  - table: `drugitems`
  - itemid: `7023`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7023`
  - row count: `59`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Aminofylline (Theofylline)`
  - raw value: `2. Spuitpompen`

match 4:
  - decision: `reject`
  - decision reason: `Theolin retard/oral -- discrete sustained-release tablet dose, same bolus-artifact pattern as match 2.`
  - table: `drugitems`
  - itemid: `9144`
  - ordercategoryid: `70.0`
  - source token: `DRUG//START//70//9144`
  - row count: `42`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Theolin retard (Theofylline)`
  - raw value: `Niet iv Tractus Respiratorius`

match 5:
  - decision: `reject`
  - decision reason: `Theofylline (bloed) -- blood concentration lab test, not an administration record.`
  - table: `numericitems`
  - itemid: `9808`
  - source token: `LAB//9808//mg/l`
  - row count: `20`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Theofylline (bloed)`
  - raw unit: `mg/l`

match 6:
  - decision: `reject`
  - decision reason: `Aminofylline/oral, n=1 -- discrete bolus dose, negligible volume.`
  - table: `drugitems`
  - itemid: `7023`
  - ordercategoryid: `70.0`
  - source token: `DRUG//START//70//7023`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Aminofylline (Theofylline)`
  - raw value: `Niet iv Tractus Respiratorius`

### dopa, Dopamine, treatment, circulatory

- Decision: `OTO`
- Target unit: `mcg/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `confirmed via diagnostic plot review, no red flags -- no change from candidate matches.`
  - table: `drugitems`
  - itemid: `7179`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7179`
  - row count: `31443`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Dopamine`
  - raw label: `Dopamine (Inotropin)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `REVISED (2026-07-10, treatment_rate strategy check): blood/lab concentration measurement (nmol/L), not an administration rate -- dimensionally incompatible with the target unit (mcg/min) and confirmed empirically via dual-channel plots to have zero temporal overlap with the real rate channel (itemid 7179) across all checked admissions (only 11 rows total in the whole database). Was previously kept via a generic "no red flags" bulk-review pass that missed this; dopa_ind's own copy of this same itemid was already correctly rejected ("blood/lab concentration measurement, not an administration event") -- this brings dopa's rate feature into line with that.`
  - table: `numericitems`
  - itemid: `15640`
  - source token: `LAB//15640//nmol/l`
  - row count: `11`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Dopamine`
  - raw label: `Dopamine (bloed)`
  - raw unit: `nmol/l`

### adh, Vasopressin, treatment, circulatory

- Decision: `[MTO/OTO]`
- Target unit: `U/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `no_source_candidates`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals. Verified genuinely absent from AmsterdamUMCdb: no drugitems row for Vasopressin (argipressine/Pitressin) in supplied_vocab.csv, the official AmsterdamUMCdb OMOP dictionary_map.csv, or the raw amsterdamumcdb/dictionary/dictionary.csv (checked brand names and INN synonyms too). Two related-but-distinct drugs ARE present and should NOT be substituted: Desmopressine (Minrin, itemid 6992, a different indication/ATC H01BA02) and Terlipressine (Glypressin, itemid 12467, ATC H01BA04, used for variceal bleeding/hepatorenal syndrome, not septic-shock vasopressor support).`

No source-candidate matches recorded.

### hep, Heparin, treatment, circulatory

- Decision: `OTO`
- Target unit: `U/h`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `Heparine/Spuitpompen -- use dose field (IE), not rate (mL/h pump flow, wrong unit).`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7930`
  - row count: `52658`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `Heparine/injection -- genuine bolus (2500/5000 IE spikes), but the AmsterdamUMCdb-logged duration is a fixed 1-minute placeholder, so dose/duration gives a non-physiological rate; not convertible into this rate feature.`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `25.0`
  - source token: `DRUG//START//25//7930`
  - row count: `2281`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `Injecties Haematologisch`

match 3:
  - decision: `reject`
  - decision reason: `Heparinoiden (Hirudoid)/topical -- dose unit 'Lik' (a smear/application count), not a heparin quantity at all; wrong route/concept.`
  - table: `drugitems`
  - itemid: `9079`
  - ordercategoryid: `69.0`
  - source token: `DRUG//START//69//9079`
  - row count: `47`
  - evidence: `source_vocab`
  - matched by: `term:Heparin`
  - raw label: `Heparinoïden (Hirudoid)`
  - raw value: `Niet iv Zalven/Crèmes/Druppels`

match 4:
  - decision: `reject`
  - decision reason: `CVVH anticoag. protocol='Heparine' -- categorical protocol-selection flag, not an administration event.`
  - table: `listitems`
  - itemid: `20536`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//20536//2`
  - row count: `41`
  - evidence: `source_vocab`
  - matched by: `term:Heparine`
  - raw label: `CVVH behandel afspraken Antistolling`
  - raw value: `Heparine`

match 5:
  - decision: `reject`
  - decision reason: `CVVH anticoag. protocol='Citraat en Heparine' -- same as match 4.`
  - table: `listitems`
  - itemid: `20536`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//20536//4`
  - row count: `23`
  - evidence: `source_vocab`
  - matched by: `term:Heparine`
  - raw label: `CVVH behandel afspraken Antistolling`
  - raw value: `Citraat en Heparine`

match 6:
  - decision: `reject`
  - decision reason: `Drukzak/pressure bag -- dose only in mL (saline volume); heparin content unrecoverable without an assumed concentration.`
  - table: `drugitems`
  - itemid: `8943`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//8943`
  - row count: `13`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Drukzak Heparine`
  - raw value: `Infuus - Crystalloid`

match 7:
  - decision: `reject`
  - decision reason: `Heparine/Infuus-Crystalloid -- real IE dose but delivered via a crystalloid carrier, same vehicle-vs-therapeutic-intent ambiguity as fluid matches 16/18/20; excluded from the rate feature.`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7930`
  - row count: `11`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `Infuus - Crystalloid`

### prop, Propofol, treatment, neuro

- Decision: `OTO`
- Target unit: `mcg/min`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `Propofol/Spuitpompen -- reconstruct as dose / duration x 1000 (mg/min -> mcg/min); dose is the total mg delivered over the interval, duration confirms real (non-artifact) variable lengths.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7480`
  - row count: `152707`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `Propofol/Injecties CZS-Sedatie-Analgetica -- bolus dose (fixed duration=1min artifact), not a rate.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7480`
  - row count: `825`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 3:
  - decision: `reject`
  - decision reason: `Propofol/Infuus-Colloid, n=1 -- negligible volume, odd ordercategory for propofol.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `17.0`
  - source token: `DRUG//START//17//7480`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `Infuus - Colloid`

### benzdia, Benzodiazepine, treatment, neuro

- Decision: `MTO`
- Target unit: `mg/h`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `Midazolam -- kept as the sole reference drug for the rate feature; other benzodiazepines are captured via benzdia_ind instead of attempting a potency-equivalence conversion for the rate.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7194`
  - row count: `132665`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `non-midazolam benzodiazepine -- rate feature simplified to midazolam-only; this drug's presence is still captured via benzdia_ind.`
  - table: `drugitems`
  - itemid: `6883`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//6883`
  - row count: `33358`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Oxazepam`
  - raw label: `Oxazepam (Seresta)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 3:
  - decision: `reject`
  - decision reason: `non-midazolam benzodiazepine -- rate feature simplified to midazolam-only; this drug's presence is still captured via benzdia_ind.`
  - table: `drugitems`
  - itemid: `7165`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7165`
  - row count: `12197`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lorazepam`
  - raw label: `Lorazepam (Temesta)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 4:
  - decision: `reject`
  - decision reason: `non-midazolam benzodiazepine -- rate feature simplified to midazolam-only; this drug's presence is still captured via benzdia_ind.`
  - table: `drugitems`
  - itemid: `7165`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7165`
  - row count: `8116`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lorazepam`
  - raw label: `Lorazepam (Temesta)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 5:
  - decision: `keep`
  - decision reason: `Lorazepam/Spuitpompen -- revised: histogram validation (dose/duration, converted x2.0) shows this drug's converted rate distribution overlaps Midazolam's real distribution well (both cluster ~0.1-10 mg/h); include in the rate feature rather than indicator-only, per the author's guidance to apply conversions when reasonable and validate via distribution histograms.`
  - table: `drugitems`
  - itemid: `7165`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7165`
  - row count: `1913`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lorazepam`
  - raw label: `Lorazepam (Temesta)`
  - raw value: `2. Spuitpompen`

match 6:
  - decision: `keep`
  - decision reason: `Midazolam -- kept as the sole reference drug for the rate feature; other benzodiazepines are captured via benzdia_ind instead of attempting a potency-equivalence conversion for the rate.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7194`
  - row count: `1681`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 7:
  - decision: `reject`
  - decision reason: `non-midazolam benzodiazepine -- rate feature simplified to midazolam-only; this drug's presence is still captured via benzdia_ind.`
  - table: `drugitems`
  - itemid: `7170`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7170`
  - row count: `867`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Diazepam (Valium)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 8:
  - decision: `keep`
  - decision reason: `Midazolam -- kept as the sole reference drug for the rate feature; other benzodiazepines are captured via benzdia_ind instead of attempting a potency-equivalence conversion for the rate.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7194`
  - row count: `339`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 9:
  - decision: `reject`
  - decision reason: `non-midazolam benzodiazepine -- rate feature simplified to midazolam-only; this drug's presence is still captured via benzdia_ind.`
  - table: `drugitems`
  - itemid: `7170`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7170`
  - row count: `226`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Diazepam (Valium)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 10:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `18671`
  - valueid: `140.0`
  - source token: `MEASUREMENT_CATEGORICAL//18671//140`
  - row count: `111`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Benzodiazepine`
  - raw label: `NICE APACHEIV diagnosen`
  - raw value: `Non-operative neurologic - Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 11:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `17004`
  - valueid: `23.0`
  - source token: `MEASUREMENT_CATEGORICAL//17004//23`
  - row count: `84`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Benzodiazepine`
  - raw label: `APACHEIV Non-operative neurologic`
  - raw value: `Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 12:
  - decision: `reject`
  - decision reason: `blinded research-trial arm -- per-row drug identity unknown, may be placebo.`
  - table: `drugitems`
  - itemid: `14648`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//14648`
  - row count: `81`
  - evidence: `source_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Research  Midazolam/Placebo`
  - raw value: `2. Spuitpompen`

match 13:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `17025`
  - valueid: `51.0`
  - source token: `MEASUREMENT_CATEGORICAL//17025//51`
  - row count: `9`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Benzodiazepine`
  - raw label: `SEC_APACHEIV Non-operative neurologic`
  - raw value: `Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 14:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9766`
  - source token: `LAB//9766//µg/l`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (bloed)`
  - raw unit: `µg/l`

match 15:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `18673`
  - valueid: `592.0`
  - source token: `MEASUREMENT_CATEGORICAL//18673//592`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Benzodiazepine`
  - raw label: `NICE SEC APACHEIV diagnosen`
  - raw value: `Non-operative neurologic - Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 16:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `12164`
  - source token: `LAB//12164//µg/l`
  - row count: `6`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Diazepam (bloed)`
  - raw unit: `µg/l`

match 17:
  - decision: `keep`
  - decision reason: `Diazepam/Spuitpompen -- revised: same validation as match 5 (converted x0.4); n=5 is tiny but the converted values still land within Midazolam's real distribution range. Include in the rate feature.`
  - table: `drugitems`
  - itemid: `7170`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7170`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Diazepam (Valium)`
  - raw value: `2. Spuitpompen`

match 18:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9718`
  - source token: `LAB//9718//mg/l`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Oxazepam`
  - raw label: `Oxazepam (bloed)`
  - raw unit: `mg/l`

match 19:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9717`
  - source token: `LAB//9717//µg/l`
  - row count: `4`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Nordiazepam (bloed)`
  - raw unit: `µg/l`

match 20:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9754`
  - source token: `LAB//9754//µg/l`
  - row count: `2`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lorazepam`
  - raw label: `Lorazepam (bloed)`
  - raw unit: `µg/l`

### sed, Other Sedatives, treatment, neuro

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7480`
  - row count: `152707`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7194`
  - row count: `132665`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `2. Spuitpompen`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7194`
  - row count: `1681`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7480`
  - row count: `825`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 5:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7194`
  - row count: `339`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 6:
  - decision: `reject`
  - decision reason: `blinded research-trial arm -- per-row drug identity unknown, may be placebo.`
  - table: `drugitems`
  - itemid: `14649`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//14649`
  - row count: `130`
  - evidence: `source_vocab`
  - matched by: `term:Dexmedetomidine`
  - raw label: `Research Dexmedetomidine/Placebo`
  - raw value: `2. Spuitpompen`

match 7:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `18671`
  - valueid: `140.0`
  - source token: `MEASUREMENT_CATEGORICAL//18671//140`
  - row count: `111`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:sedative`
  - raw label: `NICE APACHEIV diagnosen`
  - raw value: `Non-operative neurologic - Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 8:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `17004`
  - valueid: `23.0`
  - source token: `MEASUREMENT_CATEGORICAL//17004//23`
  - row count: `84`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:sedative`
  - raw label: `APACHEIV Non-operative neurologic`
  - raw value: `Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 9:
  - decision: `reject`
  - decision reason: `blinded research-trial arm -- per-row drug identity unknown, may be placebo.`
  - table: `drugitems`
  - itemid: `14648`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//14648`
  - row count: `81`
  - evidence: `source_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Research  Midazolam/Placebo`
  - raw value: `2. Spuitpompen`

match 10:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `17025`
  - valueid: `51.0`
  - source token: `MEASUREMENT_CATEGORICAL//17025//51`
  - row count: `9`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:sedative`
  - raw label: `SEC_APACHEIV Non-operative neurologic`
  - raw value: `Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 11:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9766`
  - source token: `LAB//9766//µg/l`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (bloed)`
  - raw unit: `µg/l`

match 12:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `18673`
  - valueid: `592.0`
  - source token: `MEASUREMENT_CATEGORICAL//18673//592`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:sedative`
  - raw label: `NICE SEC APACHEIV diagnosen`
  - raw value: `Non-operative neurologic - Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 13:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `17.0`
  - source token: `DRUG//START//17//7194`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `Infuus - Colloid`

match 14:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `17.0`
  - source token: `DRUG//START//17//7480`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `Infuus - Colloid`

match 15:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `18465`
  - source token: `LAB//18465//µg/l`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam + Midazolam, 4-hydroxy (bloed)`
  - raw unit: `µg/l`

match 16:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9767`
  - source token: `LAB//9767//µg/l`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam, 4-hydroxy (bloed)`
  - raw unit: `µg/l`

### op_pain, Opiate Painkiller, treatment, neuro

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7219`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7219`
  - row count: `132502`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Fentanyl`
  - raw label: `Fentanyl`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7225`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7225`
  - row count: `42151`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Morfine`
  - raw label: `Morfine`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7219`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7219`
  - row count: `2491`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Fentanyl`
  - raw label: `Fentanyl`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7225`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7225`
  - row count: `1618`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Morfine`
  - raw label: `Morfine`
  - raw value: `2. Spuitpompen`

match 5:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `12940`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//12940`
  - row count: `650`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Fentanyl`
  - raw label: `Fentanyl pleister`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `9620`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//9620`
  - row count: `647`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Fentanyl`
  - raw label: `Bupivacaïne/Fentanyl`
  - raw value: `2. Spuitpompen`

match 7:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `13883`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//13883`
  - row count: `526`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Oxycodon`
  - raw label: `Oxycodon (OxyNorm)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 8:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `19221`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//19221`
  - row count: `413`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Oxycodon`
  - raw label: `Oxycodon (OxyContin)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 9:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `12402`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//12402`
  - row count: `284`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Fentanyl`
  - raw label: `Remifentanyl`
  - raw value: `2. Spuitpompen`

match 10:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7225`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7225`
  - row count: `107`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Morfine`
  - raw label: `Morfine`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 11:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `19163`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//19163`
  - row count: `82`
  - evidence: `source_vocab`
  - matched by: `term:Morfine`
  - raw label: `Morfine drank (Oramorph)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 12:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `21242`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//21242`
  - row count: `35`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Sufentanil`
  - raw label: `Bupivacaïne/Sufentanil`
  - raw value: `2. Spuitpompen`

match 13:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7014`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7014`
  - row count: `11`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Sufentanil`
  - raw label: `Sufentanil (Sufenta)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 14:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7020`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7020`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Fentanyl`
  - raw label: `Thalamonal (Droperidol)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 15:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7221`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7221`
  - row count: `2`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Morfine`
  - raw label: `Nicomorfine (Vilan)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 16:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `9099`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//9099`
  - row count: `2`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Morphine`
  - raw label: `MS Contin`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

### nonop_pain, Non-Opioid Analgesic, treatment, neuro

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `6891`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//6891`
  - row count: `166397`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Paracetamol`
  - raw label: `Paracetamol`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `6891`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//6891`
  - row count: `29595`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Paracetamol`
  - raw label: `Paracetamol`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9063`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//9063`
  - row count: `1736`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diclofenac`
  - raw label: `Diclofenac natrium (Voltaren)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9124`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//9124`
  - row count: `370`
  - evidence: `source_vocab`
  - matched by: `term:Paracetamol`
  - raw label: `Paracetamol-codeïne`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 5:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `10024`
  - source token: `LAB//10024//mg/l`
  - row count: `192`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Paracetamol`
  - raw label: `Paracetamol (bloed)`
  - raw unit: `mg/l`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9081`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//9081`
  - row count: `136`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Ibuprofen`
  - raw label: `Ibuprofen`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 7:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9064`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//9064`
  - row count: `64`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diclofenac`
  - raw label: `Diclofenac Retard (Voltaren)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 8:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `8324`
  - source token: `LAB//8324//mg/l`
  - row count: `2`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Paracetamol`
  - raw label: `Paracetamol spiegel`
  - raw unit: `mg/l`

### paral, Paralytic, treatment, neuro

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `6960`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//6960`
  - row count: `2950`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Rocuronium`
  - raw label: `Rocuronium (Esmeron)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `6960`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//6960`
  - row count: `274`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Rocuronium`
  - raw label: `Rocuronium (Esmeron)`
  - raw value: `2. Spuitpompen`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `9141`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//9141`
  - row count: `25`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Suxamethonium`
  - raw label: `Suxamethonium (Succinylcholine)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `9013`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//9013`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Atracurium`
  - raw label: `Atracurium (Tracrium)`
  - raw value: `2. Spuitpompen`

### abx, Antibiotics, treatment, infection

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `8268`
  - ordercategoryid: `21.0`
  - source token: `DRUG//START//21//8268`
  - row count: `196878`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `SDD drank (4 x dgs)`
  - raw value: `Niet iv Antimicrobiele middelen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `9138`
  - ordercategoryid: `21.0`
  - source token: `DRUG//START//21//9138`
  - row count: `196389`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `SDD pasta (4 x dgs)`
  - raw value: `Niet iv Antimicrobiele middelen`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `6919`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//6919`
  - row count: `29321`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Cefotaxim (Claforan)`
  - raw value: `Injecties Antimicrobiele middelen`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `7187`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//7187`
  - row count: `26231`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Metronidazol (Flagyl)`
  - raw value: `Injecties Antimicrobiele middelen`

match 5:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `12408`
  - ordercategoryid: `21.0`
  - source token: `DRUG//START//21//12408`
  - row count: `25395`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `SDD drank (8 x dgs)`
  - raw value: `Niet iv Antimicrobiele middelen`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `9152`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//9152`
  - row count: `24241`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Cefazoline (Kefzol)`
  - raw value: `Injecties Antimicrobiele middelen`

match 7:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `7064`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//7064`
  - row count: `23868`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Vancomycine`
  - raw value: `Injecties Antimicrobiele middelen`

match 8:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `7208`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//7208`
  - row count: `22577`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Erythromycine (Erythrocine)`
  - raw value: `Injecties Antimicrobiele middelen`

match 9:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `12407`
  - ordercategoryid: `21.0`
  - source token: `DRUG//START//21//12407`
  - row count: `21351`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `SDD pasta (8 x dgs)`
  - raw value: `Niet iv Antimicrobiele middelen`

match 10:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `13171`
  - ordercategoryid: `21.0`
  - source token: `DRUG//START//21//13171`
  - row count: `20946`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `SDD pasta Tracheostoma (4 x dgs)`
  - raw value: `Niet iv Antimicrobiele middelen`

match 11:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `9133`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//9133`
  - row count: `20563`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Ceftriaxon (Rocephin)`
  - raw value: `Injecties Antimicrobiele middelen`

match 12:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `6948`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//6948`
  - row count: `14924`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Ciprofloxacine (Ciproxin)`
  - raw value: `Injecties Antimicrobiele middelen`

match 13:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `7123`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//7123`
  - row count: `14593`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Imipenem (Tienam)`
  - raw value: `Injecties Antimicrobiele middelen`

match 14:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `9029`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//9029`
  - row count: `12102`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Amoxicilline/Clavulaanzuur (Augmentin)`
  - raw value: `Injecties Antimicrobiele middelen`

match 15:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `7227`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//7227`
  - row count: `12070`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Flucloxacilline (Stafoxil/Floxapen)`
  - raw value: `Injecties Antimicrobiele middelen`

match 16:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `6847`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//6847`
  - row count: `11262`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Amoxicilline (Clamoxyl/Flemoxin)`
  - raw value: `Injecties Antimicrobiele middelen`

match 17:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `8394`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//8394`
  - row count: `8064`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Co-Trimoxazol (Bactrimel)`
  - raw value: `Injecties Antimicrobiele middelen`

match 18:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `6811`
  - ordercategoryid: `15.0`
  - source token: `DRUG//START//15//6811`
  - row count: `7846`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `Aciclovir (Zovirax)`
  - raw value: `Injecties Antimicrobiele middelen`

match 19:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `7227`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7227`
  - row count: `6790`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:MEDICATION//J01`
  - raw label: `Flucloxacilline (Stafoxil/Floxapen)`
  - raw value: `2. Spuitpompen`

match 20:
  - decision: `keep`
  - decision reason: `binary indicator: genuine antimicrobial administration record, presence-only so route/formulation/dose don't matter.`
  - table: `drugitems`
  - itemid: `10586`
  - ordercategoryid: `21.0`
  - source token: `DRUG//START//21//10586`
  - row count: `6745`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Antimicrobiele`
  - raw label: `SDD drank (6 x dgs)`
  - raw value: `Niet iv Antimicrobiele middelen`

### loop_diur, Loop Diuretic, treatment, metabolic_renal

- Decision: `MTO`
- Target unit: `mg/h`
- Reconstruction type: `treatment_rate`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `Furosemide/Spuitpompen -- use dose field, not rate (mL/h pump flow, wrong unit/concentration-dependent).`
  - table: `drugitems`
  - itemid: `7244`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7244`
  - row count: `29079`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Furosemide`
  - raw label: `Furosemide (Lasix)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `Furosemide/injection -- bolus dose, not a rate.`
  - table: `drugitems`
  - itemid: `7244`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7244`
  - row count: `16612`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Furosemide`
  - raw label: `Furosemide (Lasix)`
  - raw value: `Injecties Circulatie/Diuretica`

match 3:
  - decision: `reject`
  - decision reason: `Furosemide/non-iv -- bolus dose, not a rate.`
  - table: `drugitems`
  - itemid: `7244`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//7244`
  - row count: `2449`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Furosemide`
  - raw label: `Furosemide (Lasix)`
  - raw value: `Niet iv Circulatie/Diurese`

match 4:
  - decision: `reject`
  - decision reason: `Bumetanide/non-iv -- bolus dose, not a rate.`
  - table: `drugitems`
  - itemid: `6882`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//6882`
  - row count: `595`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Bumetanide`
  - raw label: `Bumetanide (Burinex)`
  - raw value: `Niet iv Circulatie/Diurese`

match 5:
  - decision: `reject`
  - decision reason: `Bumetanide/injection -- bolus dose, not a rate.`
  - table: `drugitems`
  - itemid: `6882`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6882`
  - row count: `59`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Bumetanide`
  - raw label: `Bumetanide (Burinex)`
  - raw value: `Injecties Circulatie/Diuretica`

match 6:
  - decision: `keep`
  - decision reason: `Bumetanide/Spuitpompen -- use dose field like match 1; standardize to furosemide-equivalent (x40) before summing. Histogram validation (plot_dose_conversion_validation.py) shows the converted distribution's core cluster (~0.3-3 mg/h) overlaps Furosemide's real distribution well, but a notable fraction of converted values land at 100-1e6 mg/h -- far beyond any real furosemide dose. Given n=39 is tiny, this is likely a handful of noisy/erroneous dose or duration rows amplified by the x40 factor rather than the factor itself being wrong. FLAG for outlier clipping during the outlier-removal step (per iCareFM's own 'big margins' outlier policy) rather than rejecting this match outright.`
  - table: `drugitems`
  - itemid: `6882`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//6882`
  - row count: `39`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Bumetanide`
  - raw label: `Bumetanide (Burinex)`
  - raw value: `2. Spuitpompen`

### ins_ind, Insulin, treatment, not specified

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7624`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7624`
  - row count: `153866`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Actrapid (Insuline)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `GRIP-protocol advisory/recommended/computed value, not an administered dose.`
  - table: `numericitems`
  - itemid: `16818`
  - source token: `MEASUREMENT_BEDSIDE//16818//ml/uur`
  - row count: `91082`
  - evidence: `source_vocab`
  - matched by: `term:Insuline`
  - raw label: `GRIP - AVGInsuline4Hours`
  - raw unit: `ml/uur`

match 3:
  - decision: `reject`
  - decision reason: `GRIP-protocol advisory/recommended/computed value, not an administered dose.`
  - table: `numericitems`
  - itemid: `16825`
  - source token: `MEASUREMENT_BEDSIDE//16825//UNKNOWN`
  - row count: `88839`
  - evidence: `source_vocab`
  - matched by: `term:Insulin`
  - raw label: `GRIP - InsulinAdviceBeforeRestrictions`

match 4:
  - decision: `reject`
  - decision reason: `GRIP-protocol advisory/recommended/computed value, not an administered dose.`
  - table: `numericitems`
  - itemid: `16826`
  - source token: `MEASUREMENT_BEDSIDE//16826//UNKNOWN`
  - row count: `88838`
  - evidence: `source_vocab`
  - matched by: `term:Insulin`
  - raw label: `GRIP - InsulinAdviceAfterRestrictions`

match 5:
  - decision: `reject`
  - decision reason: `GRIP-protocol advisory/recommended/computed value, not an administered dose.`
  - table: `numericitems`
  - itemid: `16802`
  - source token: `MEASUREMENT_BEDSIDE//16802//ml/uur`
  - row count: `87788`
  - evidence: `source_vocab`
  - matched by: `term:Insulin`
  - raw label: `GRIP - InsulinAdviceRate`
  - raw unit: `ml/uur`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `numericitems`
  - itemid: `16805`
  - source token: `MEASUREMENT_BEDSIDE//16805//ml/uur`
  - row count: `85285`
  - evidence: `source_vocab`
  - matched by: `term:Insulin`
  - raw label: `GRIP - InsulinActualRate`
  - raw unit: `ml/uur`

match 7:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `19129`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//19129`
  - row count: `75538`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Insuline aspart (Novorapid)`
  - raw value: `2. Spuitpompen`

match 8:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9014`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//9014`
  - row count: `50613`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Velosuline (Insuline)`
  - raw value: `2. Spuitpompen`

match 9:
  - decision: `reject`
  - decision reason: `GRIP-protocol advisory/recommended/computed value, not an administered dose.`
  - table: `numericitems`
  - itemid: `16813`
  - source token: `MEASUREMENT_BEDSIDE//16813//UNKNOWN`
  - row count: `2559`
  - evidence: `source_vocab`
  - matched by: `term:Insulin`
  - raw label: `GRIP - InsulinResistance`

match 10:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7624`
  - ordercategoryid: `67.0`
  - source token: `DRUG//START//67//7624`
  - row count: `670`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Actrapid (Insuline)`
  - raw value: `Injecties Hormonen/Vitaminen/Mineralen`

match 11:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `19129`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//19129`
  - row count: `563`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Insuline aspart (Novorapid)`
  - raw value: `Infuus - Crystalloid`

match 12:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7624`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7624`
  - row count: `550`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Actrapid (Insuline)`
  - raw value: `Infuus - Crystalloid`

match 13:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `19129`
  - ordercategoryid: `67.0`
  - source token: `DRUG//START//67//19129`
  - row count: `388`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Insuline aspart (Novorapid)`
  - raw value: `Injecties Hormonen/Vitaminen/Mineralen`

match 14:
  - decision: `reject`
  - decision reason: `categorical protocol-selection flag, not an administration event.`
  - table: `listitems`
  - itemid: `16952`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//16952//1`
  - row count: `282`
  - evidence: `source_vocab`
  - matched by: `term:Insuline`
  - raw label: `SEPSIS_INSULINE_THERAPIE`
  - raw value: `Ja`

match 15:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9014`
  - ordercategoryid: `67.0`
  - source token: `DRUG//START//67//9014`
  - row count: `224`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Velosuline (Insuline)`
  - raw value: `Injecties Hormonen/Vitaminen/Mineralen`

match 16:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `10755`
  - ordercategoryid: `67.0`
  - source token: `DRUG//START//67//10755`
  - row count: `170`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Insulatard (Insuline)`
  - raw value: `Injecties Hormonen/Vitaminen/Mineralen`

match 17:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9014`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//9014`
  - row count: `118`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Insuline`
  - raw label: `Velosuline (Insuline)`
  - raw value: `Infuus - Crystalloid`

match 18:
  - decision: `reject`
  - decision reason: `categorical protocol-selection flag, not an administration event.`
  - table: `listitems`
  - itemid: `16952`
  - valueid: `3.0`
  - source token: `MEASUREMENT_CATEGORICAL//16952//3`
  - row count: `112`
  - evidence: `source_vocab`
  - matched by: `term:Insuline`
  - raw label: `SEPSIS_INSULINE_THERAPIE`
  - raw value: `N.V.T.`

match 19:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9095`
  - ordercategoryid: `67.0`
  - source token: `DRUG//START//67//9095`
  - row count: `93`
  - evidence: `source_vocab`
  - matched by: `term:Insuline`
  - raw label: `Mixtard (Insuline) 30-70`
  - raw value: `Injecties Hormonen/Vitaminen/Mineralen`

match 20:
  - decision: `reject`
  - decision reason: `categorical protocol-selection flag, not an administration event.`
  - table: `listitems`
  - itemid: `16952`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//16952//2`
  - row count: `60`
  - evidence: `source_vocab`
  - matched by: `term:Insuline`
  - raw label: `SEPSIS_INSULINE_THERAPIE`
  - raw value: `Nee`

### fluid, Fluid Administration, treatment, not specified

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `blood glucose lab test, not fluid administration -- term:Glucose false positive.`
  - table: `numericitems`
  - itemid: `9947`
  - source token: `LAB//9947//mmol/l`
  - row count: `820898`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose (bloed)`
  - raw unit: `mmol/l`

match 2:
  - decision: `keep`
  - decision reason: `genuine crystalloid/colloid fluid administration.`
  - table: `drugitems`
  - itemid: `9424`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//9424`
  - row count: `166829`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:NaCl`
  - raw label: `NaCL 0,9% spuit`
  - raw value: `2. Spuitpompen`

match 3:
  - decision: `keep`
  - decision reason: `genuine crystalloid/colloid fluid administration.`
  - table: `drugitems`
  - itemid: `7291`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7291`
  - row count: `133053`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `NaCl 0,45%/Glucose 2,5%`
  - raw value: `Infuus - Crystalloid`

match 4:
  - decision: `reject`
  - decision reason: `GRIP glycemic-monitoring value, not fluid administration.`
  - table: `numericitems`
  - itemid: `16821`
  - source token: `MEASUREMENT_BEDSIDE//16821//UNKNOWN`
  - row count: `88845`
  - evidence: `source_vocab`
  - matched by: `term:Glucose`
  - raw label: `GRIP - RelativeGlucoseAfterFilter`

match 5:
  - decision: `keep`
  - decision reason: `genuine crystalloid/colloid fluid administration.`
  - table: `drugitems`
  - itemid: `7293`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7293`
  - row count: `76772`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `NaCl 0,9 %`
  - raw value: `Infuus - Crystalloid`

match 6:
  - decision: `reject`
  - decision reason: `Druppelen NaCl selector field (value='geen'/none) -- an order/status field, not a measured administration; this variant is the explicit negative.`
  - table: `listitems`
  - itemid: `8897`
  - valueid: `9.0`
  - source token: `MEASUREMENT_CATEGORICAL//8897//9`
  - row count: `73577`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:NaCl`
  - raw label: `Druppelen NaCl`
  - raw value: `geen`

match 7:
  - decision: `keep`
  - decision reason: `genuine crystalloid/colloid fluid administration.`
  - table: `drugitems`
  - itemid: `8937`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//8937`
  - row count: `65470`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Drukzak`
  - raw value: `Infuus - Crystalloid`

match 8:
  - decision: `keep`
  - decision reason: `genuine crystalloid/colloid fluid administration.`
  - table: `drugitems`
  - itemid: `7252`
  - ordercategoryid: `17.0`
  - source token: `DRUG//START//17//7252`
  - row count: `47257`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Gelofusine`
  - raw value: `Infuus - Colloid`

match 9:
  - decision: `reject`
  - decision reason: `peripheral IV line placement (processitems), not a fluid administration event.`
  - table: `processitems`
  - itemid: `9422`
  - source token: `PROCESS_INTERVAL//9422`
  - row count: `39480`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Perifeer infuus`

match 10:
  - decision: `keep`
  - decision reason: `genuine crystalloid/colloid fluid administration.`
  - table: `drugitems`
  - itemid: `7316`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7316`
  - row count: `36561`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Ri-Lac (Ringers lactaat)`
  - raw value: `Infuus - Crystalloid`

match 11:
  - decision: `keep`
  - decision reason: `genuine crystalloid/colloid fluid administration.`
  - table: `drugitems`
  - itemid: `7257`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7257`
  - row count: `28568`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Glucose 5 %`
  - raw value: `Infuus - Crystalloid`

match 12:
  - decision: `reject`
  - decision reason: `Druppelen NaCl selector field (value='1x') -- same selector-field issue as match 6.`
  - table: `listitems`
  - itemid: `8897`
  - valueid: `1.0`
  - source token: `MEASUREMENT_CATEGORICAL//8897//1`
  - row count: `25306`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:NaCl`
  - raw label: `Druppelen NaCl`
  - raw value: `1x`

match 13:
  - decision: `reject`
  - decision reason: `packed red blood cell transfusion -- belongs to inf_rbc, not fluid.`
  - table: `drugitems`
  - itemid: `8429`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8429`
  - row count: `20834`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Gefiltreerde Ery's`
  - raw value: `Infuus - Bloedproducten`

match 14:
  - decision: `reject`
  - decision reason: `point-of-care blood gas glucose measurement, not fluid administration.`
  - table: `numericitems`
  - itemid: `9557`
  - source token: `LAB//9557//mmol/l`
  - row count: `20195`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose Astrup`
  - raw unit: `mmol/l`

match 15:
  - decision: `reject`
  - decision reason: `Druppelen NaCl selector field (value='2x') -- same selector-field issue as match 6/12.`
  - table: `listitems`
  - itemid: `8897`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//8897//2`
  - row count: `15275`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:NaCl`
  - raw label: `Druppelen NaCl`
  - raw value: `2x`

match 16:
  - decision: `reject`
  - decision reason: `crystalloid used as a medication-line flush/vehicle, not a deliberate fluid-therapy order.`
  - table: `drugitems`
  - itemid: `8939`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//8939`
  - row count: `15086`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Medicijnlijn medicatie`
  - raw value: `Infuus - Crystalloid`

match 17:
  - decision: `keep`
  - decision reason: `genuine crystalloid/colloid fluid administration.`
  - table: `drugitems`
  - itemid: `9569`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//9569`
  - row count: `10450`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Glucose`
  - raw label: `Glucose 5% spuit`
  - raw value: `2. Spuitpompen`

match 18:
  - decision: `reject`
  - decision reason: `Magnesium sulfate -- an electrolyte medication where crystalloid is just the diluent, not fluid therapy.`
  - table: `drugitems`
  - itemid: `7148`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7148`
  - row count: `8866`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Magnesiumsulfaat (MgSO4)`
  - raw value: `Infuus - Crystalloid`

match 19:
  - decision: `reject`
  - decision reason: `administrative discharge-checklist flag ('IV policy already arranged'), not a clinical event.`
  - table: `listitems`
  - itemid: `15709`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//15709//2`
  - row count: `8436`
  - evidence: `source_vocab`
  - matched by: `term:Infuus`
  - raw label: `Pat_Ontslag_Infuusbeleid`
  - raw value: `Ja, was reeds in orde`

match 20:
  - decision: `reject`
  - decision reason: `Vitamin C -- a medication where crystalloid is just the diluent, same vehicle-vs-therapy issue as match 16/18.`
  - table: `drugitems`
  - itemid: `9021`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//9021`
  - row count: `8073`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Infuus`
  - raw label: `Ascorbinezuur (Vit C)`
  - raw value: `Infuus - Crystalloid`

### inf_rbc, Packed Red Blood Cells, treatment, not specified

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `genuine packed/filtered red blood cell transfusion record.`
  - table: `drugitems`
  - itemid: `8429`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8429`
  - row count: `20834`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Gefiltreerde Ery's`
  - raw value: `Infuus - Bloedproducten`

match 2:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `7367`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7367`
  - row count: `5989`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Fresh Frozen Plasma`
  - raw value: `Infuus - Bloedproducten`

match 3:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `7369`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7369`
  - row count: `3728`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Thrombocyten suspensie`
  - raw value: `Infuus - Bloedproducten`

match 4:
  - decision: `keep`
  - decision reason: `genuine packed/filtered red blood cell transfusion record.`
  - table: `drugitems`
  - itemid: `7366`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7366`
  - row count: `267`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Packed cells`
  - raw value: `Infuus - Bloedproducten`

match 5:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `8945`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8945`
  - row count: `28`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Prothrombine complex`
  - raw value: `Infuus - Bloedproducten`

match 6:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `8944`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8944`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Factor VIII`
  - raw value: `Infuus - Bloedproducten`

match 7:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `8946`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8946`
  - row count: `3`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Von Willebrandfactor`
  - raw value: `Infuus - Bloedproducten`

### ffp, Fresh Frozen Plasma, treatment, not specified

- Decision: `OTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `8429`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8429`
  - row count: `20834`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Gefiltreerde Ery's`
  - raw value: `Infuus - Bloedproducten`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7367`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7367`
  - row count: `5989`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Fresh Frozen Plasma`
  - raw label: `Fresh Frozen Plasma`
  - raw value: `Infuus - Bloedproducten`

match 3:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `7369`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7369`
  - row count: `3728`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Thrombocyten suspensie`
  - raw value: `Infuus - Bloedproducten`

match 4:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `7366`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7366`
  - row count: `267`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Packed cells`
  - raw value: `Infuus - Bloedproducten`

match 5:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `8945`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8945`
  - row count: `28`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Prothrombine complex`
  - raw value: `Infuus - Bloedproducten`

match 6:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `8944`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8944`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Factor VIII`
  - raw value: `Infuus - Bloedproducten`

match 7:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `drugitems`
  - itemid: `8946`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8946`
  - row count: `3`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Von Willebrandfactor`
  - raw value: `Infuus - Bloedproducten`

match 8:
  - decision: `reject`
  - decision reason: `wrong blood product -- swept in by the overly broad BLOOD_PRODUCT/CVVH matcher, not the feature's actual product.`
  - table: `listitems`
  - itemid: `16606`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//16606//2`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:FFP`
  - raw label: `Rotem Ondernomen actie`
  - raw value: `FFPs`

### plat, Platelets, treatment, not specified

- Decision: `OTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `wrong concept for a platelet-transfusion indicator -- either the plt lab-count duplicate (m1) or a different blood product entirely swept in by the BLOOD_PRODUCT matcher (m2,3,5,6,7,8).`
  - table: `numericitems`
  - itemid: `9964`
  - source token: `LAB//9964//10^9/l`
  - row count: `214452`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Platelets`
  - raw label: `Thrombo's (bloed)`
  - raw unit: `10^9/l`

match 2:
  - decision: `reject`
  - decision reason: `wrong concept for a platelet-transfusion indicator -- either the plt lab-count duplicate (m1) or a different blood product entirely swept in by the BLOOD_PRODUCT matcher (m2,3,5,6,7,8).`
  - table: `drugitems`
  - itemid: `8429`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8429`
  - row count: `20834`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Gefiltreerde Ery's`
  - raw value: `Infuus - Bloedproducten`

match 3:
  - decision: `reject`
  - decision reason: `wrong concept for a platelet-transfusion indicator -- either the plt lab-count duplicate (m1) or a different blood product entirely swept in by the BLOOD_PRODUCT matcher (m2,3,5,6,7,8).`
  - table: `drugitems`
  - itemid: `7367`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7367`
  - row count: `5989`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Fresh Frozen Plasma`
  - raw value: `Infuus - Bloedproducten`

match 4:
  - decision: `keep`
  - decision reason: `Thrombocyten suspensie -- the only genuine platelet transfusion record.`
  - table: `drugitems`
  - itemid: `7369`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7369`
  - row count: `3728`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Thrombocyten suspensie`
  - raw value: `Infuus - Bloedproducten`

match 5:
  - decision: `reject`
  - decision reason: `wrong concept for a platelet-transfusion indicator -- either the plt lab-count duplicate (m1) or a different blood product entirely swept in by the BLOOD_PRODUCT matcher (m2,3,5,6,7,8).`
  - table: `drugitems`
  - itemid: `7366`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//7366`
  - row count: `267`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Packed cells`
  - raw value: `Infuus - Bloedproducten`

match 6:
  - decision: `reject`
  - decision reason: `wrong concept for a platelet-transfusion indicator -- either the plt lab-count duplicate (m1) or a different blood product entirely swept in by the BLOOD_PRODUCT matcher (m2,3,5,6,7,8).`
  - table: `drugitems`
  - itemid: `8945`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8945`
  - row count: `28`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Prothrombine complex`
  - raw value: `Infuus - Bloedproducten`

match 7:
  - decision: `reject`
  - decision reason: `wrong concept for a platelet-transfusion indicator -- either the plt lab-count duplicate (m1) or a different blood product entirely swept in by the BLOOD_PRODUCT matcher (m2,3,5,6,7,8).`
  - table: `drugitems`
  - itemid: `8944`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8944`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Factor VIII`
  - raw value: `Infuus - Bloedproducten`

match 8:
  - decision: `reject`
  - decision reason: `wrong concept for a platelet-transfusion indicator -- either the plt lab-count duplicate (m1) or a different blood product entirely swept in by the BLOOD_PRODUCT matcher (m2,3,5,6,7,8).`
  - table: `drugitems`
  - itemid: `8946`
  - ordercategoryid: `61.0`
  - source token: `DRUG//START//61//8946`
  - row count: `3`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:BLOOD_PRODUCT`
  - raw label: `Von Willebrandfactor`
  - raw value: `Infuus - Bloedproducten`

### inf_alb, Albumin Infusion, treatment, not specified

- Decision: `OTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `blood/CSF/urine/dialysate albumin concentration lab test, not an albumin infusion administration.`
  - table: `numericitems`
  - itemid: `9937`
  - source token: `LAB//9937//g/l`
  - row count: `104004`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Albumin`
  - raw label: `Alb.Chem (bloed)`
  - raw unit: `g/l`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `8933`
  - ordercategoryid: `17.0`
  - source token: `DRUG//START//17//8933`
  - row count: `3238`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Albumine`
  - raw label: `Albumine 20%`
  - raw value: `Infuus - Colloid`

match 3:
  - decision: `reject`
  - decision reason: `blood/CSF/urine/dialysate albumin concentration lab test, not an albumin infusion administration.`
  - table: `numericitems`
  - itemid: `6801`
  - source token: `LAB//6801//g/l`
  - row count: `3064`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Albumine`
  - raw label: `Albumine chemisch`
  - raw unit: `g/l`

match 4:
  - decision: `reject`
  - decision reason: `blood/CSF/urine/dialysate albumin concentration lab test, not an albumin infusion administration.`
  - table: `numericitems`
  - itemid: `10116`
  - source token: `LAB//10116//mg/l`
  - row count: `329`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Albumine`
  - raw label: `Albumine (imm.) (liquor)`
  - raw unit: `mg/l`

match 5:
  - decision: `reject`
  - decision reason: `blood/CSF/urine/dialysate albumin concentration lab test, not an albumin infusion administration.`
  - table: `numericitems`
  - itemid: `10382`
  - source token: `LAB//10382//mg/l`
  - row count: `216`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Albumine`
  - raw label: `Micro-albumine (urine)`
  - raw unit: `mg/l`

match 6:
  - decision: `reject`
  - decision reason: `blood/CSF/urine/dialysate albumin concentration lab test, not an albumin infusion administration.`
  - table: `numericitems`
  - itemid: `9975`
  - source token: `LAB//9975//g/l`
  - row count: `77`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Albumine`
  - raw label: `Albumine (imm.) (bloed)`
  - raw unit: `g/l`

match 7:
  - decision: `reject`
  - decision reason: `blood/CSF/urine/dialysate albumin concentration lab test, not an albumin infusion administration.`
  - table: `numericitems`
  - itemid: `12241`
  - source token: `LAB//12241//mg/24uur`
  - row count: `30`
  - evidence: `source_vocab`
  - matched by: `term:Albumine`
  - raw label: `Micro-albumine (verz. urine)`
  - raw unit: `mg/24uur`

match 8:
  - decision: `reject`
  - decision reason: `blood/CSF/urine/dialysate albumin concentration lab test, not an albumin infusion administration.`
  - table: `numericitems`
  - itemid: `10384`
  - source token: `LAB//10384//mg/l`
  - row count: `8`
  - evidence: `source_vocab`
  - matched by: `term:Albumine`
  - raw label: `Micro-albumine dialysaat (overig)`
  - raw unit: `mg/l`

### anti_delir, Anti Deliriant, treatment, neuro

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7097`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7097`
  - row count: `35980`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Haloperidol`
  - raw label: `Haloperidol (Haldol)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7097`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7097`
  - row count: `15061`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Haloperidol`
  - raw label: `Haloperidol (Haldol)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `13012`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//13012`
  - row count: `1632`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Olanzapine`
  - raw label: `Olanzapine (Zyprexa)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `16360`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//16360`
  - row count: `1534`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Quetiapine`
  - raw label: `Quetiapine (Seroquel)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 5:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7097`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7097`
  - row count: `17`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Haloperidol`
  - raw label: `Haloperidol (Haldol)`
  - raw value: `2. Spuitpompen`

match 6:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `14221`
  - source token: `LAB//14221//µg/l`
  - row count: `13`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Olanzapine`
  - raw label: `Olanzapine (bloed)`
  - raw unit: `µg/l`

match 7:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `14250`
  - source token: `LAB//14250//µg/l`
  - row count: `12`
  - evidence: `source_vocab`
  - matched by: `term:Quetiapine`
  - raw label: `Quetiapine (bloed)`
  - raw unit: `µg/l`

match 8:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9744`
  - source token: `LAB//9744//µg/l`
  - row count: `4`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Haloperidol`
  - raw label: `Haloperidol (bloed)`
  - raw unit: `µg/l`

### oth_diur, Other Diuretics, treatment, metabolic_renal

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `Furosemide -- a loop diuretic, duplicate of loop_diur match 2, not an 'other' diuretic.`
  - table: `drugitems`
  - itemid: `7244`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7244`
  - row count: `16612`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Furosemide (Lasix)`
  - raw value: `Injecties Circulatie/Diuretica`

match 2:
  - decision: `keep`
  - decision reason: `Hydrochlorothiazide -- genuine thiazide diuretic.`
  - table: `drugitems`
  - itemid: `9062`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//9062`
  - row count: `6026`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Hydrochloorthiazide`
  - raw label: `Hydrochloorthiazide (Esidrex)`
  - raw value: `Niet iv Circulatie/Diurese`

match 3:
  - decision: `keep`
  - decision reason: `Spironolactone -- genuine potassium-sparing diuretic.`
  - table: `drugitems`
  - itemid: `7011`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//7011`
  - row count: `4875`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Spironolacton`
  - raw label: `Spironolacton (Aldactone)`
  - raw value: `Niet iv Circulatie/Diurese`

match 4:
  - decision: `reject`
  - decision reason: `Digoxin -- wrong drug class, swept in by the ordercategory-24 term:Diuretic false positive.`
  - table: `drugitems`
  - itemid: `7173`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7173`
  - row count: `4203`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Digoxine (Lanoxin)`
  - raw value: `Injecties Circulatie/Diuretica`

match 5:
  - decision: `keep`
  - decision reason: `Acetazolamide -- genuine carbonic-anhydrase-inhibitor diuretic.`
  - table: `drugitems`
  - itemid: `6804`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6804`
  - row count: `3910`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Acetazolamide (Diamox)`
  - raw value: `Injecties Circulatie/Diuretica`

match 6:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `6818`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6818`
  - row count: `520`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Adrenaline (Epinefrine)`
  - raw value: `Injecties Circulatie/Diuretica`

match 7:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `7006`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7006`
  - row count: `449`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Sotalol (Sotacor)`
  - raw value: `Injecties Circulatie/Diuretica`

match 8:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `16113`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//16113`
  - row count: `411`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Amiodaron`
  - raw value: `Injecties Circulatie/Diuretica`

match 9:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `6864`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6864`
  - row count: `323`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Atropine sulfaat`
  - raw value: `Injecties Circulatie/Diuretica`

match 10:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `7184`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7184`
  - row count: `229`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Metoprolol (Selokeen )`
  - raw value: `Injecties Circulatie/Diuretica`

match 11:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `6816`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6816`
  - row count: `217`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Adenosine`
  - raw value: `Injecties Circulatie/Diuretica`

match 12:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `6862`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6862`
  - row count: `213`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Atenolol  (Tenormin)`
  - raw value: `Injecties Circulatie/Diuretica`

match 13:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `9015`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//9015`
  - row count: `211`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Amiodaron Onderhoudsdosis`
  - raw value: `Injecties Circulatie/Diuretica`

match 14:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `7504`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7504`
  - row count: `207`
  - evidence: `source_vocab`
  - matched by: `term:Diuretic`
  - raw label: `X nader te bepalen`
  - raw value: `Injecties Circulatie/Diuretica`

match 15:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `7188`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7188`
  - row count: `187`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Efedrine`
  - raw value: `Injecties Circulatie/Diuretica`

match 16:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `12438`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//12438`
  - row count: `98`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Acetylsalicylzuur (Aspegic)`
  - raw value: `Injecties Circulatie/Diuretica`

match 17:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `7213`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7213`
  - row count: `86`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Esmolol (Brevibloc)`
  - raw value: `Injecties Circulatie/Diuretica`

match 18:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `12467`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//12467`
  - row count: `69`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Terlipressine (Glypressin)`
  - raw value: `Injecties Circulatie/Diuretica`

match 19:
  - decision: `reject`
  - decision reason: `Bumetanide -- a loop diuretic, duplicate of loop_diur match 5, not an 'other' diuretic.`
  - table: `drugitems`
  - itemid: `6882`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6882`
  - row count: `59`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Bumetanide (Burinex)`
  - raw value: `Injecties Circulatie/Diuretica`

match 20:
  - decision: `reject`
  - decision reason: `wrong drug class -- swept in by the ordercategory-24 term:Diuretic false positive, not an actual diuretic.`
  - table: `drugitems`
  - itemid: `7224`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7224`
  - row count: `46`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diuretic`
  - raw label: `Flecaïnide (Tambocor)`
  - raw value: `Injecties Circulatie/Diuretica`

### anti_coag, Other Anticoagulants, treatment, circulatory

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7625`
  - ordercategoryid: `25.0`
  - source token: `DRUG//START//25//7625`
  - row count: `65281`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Nadroparine`
  - raw label: `Nadroparine (Fraxiparine)`
  - raw value: `Injecties Haematologisch`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7930`
  - row count: `52658`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `2. Spuitpompen`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `25.0`
  - source token: `DRUG//START//25//7930`
  - row count: `2281`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `Injecties Haematologisch`

match 4:
  - decision: `reject`
  - decision reason: `categorical protocol-selection flag, not an administration event.`
  - table: `listitems`
  - itemid: `20536`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//20536//2`
  - row count: `41`
  - evidence: `source_vocab`
  - matched by: `term:Heparine`
  - raw label: `CVVH behandel afspraken Antistolling`
  - raw value: `Heparine`

match 5:
  - decision: `reject`
  - decision reason: `categorical protocol-selection flag, not an administration event.`
  - table: `listitems`
  - itemid: `20536`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//20536//4`
  - row count: `23`
  - evidence: `source_vocab`
  - matched by: `term:Heparine`
  - raw label: `CVVH behandel afspraken Antistolling`
  - raw value: `Citraat en Heparine`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `8943`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//8943`
  - row count: `13`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Drukzak Heparine`
  - raw value: `Infuus - Crystalloid`

match 7:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7930`
  - row count: `11`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `Infuus - Crystalloid`

### vasod, Antihypertensive And Vasodilators, treatment, circulatory

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7218`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7218`
  - row count: `22430`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Nicardipine`
  - raw label: `Nicardipine (Cardene)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7478`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7478`
  - row count: `11834`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Nitroglycerine`
  - raw label: `Nitroglycerine (Nitro-pohl)`
  - raw value: `2. Spuitpompen`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `8154`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//8154`
  - row count: `10124`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amlodipine`
  - raw label: `Amlodipine (Norvasc)`
  - raw value: `Niet iv Circulatie/Diurese`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `9006`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//9006`
  - row count: `3328`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Nitroprusside`
  - raw label: `Nitroprusside (Nipride)`
  - raw value: `2. Spuitpompen`

match 5:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `9113`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//9113`
  - row count: `28`
  - evidence: `source_vocab`
  - matched by: `term:Nitroglycerine`
  - raw label: `Nitrobaat (Nitroglycerine)`
  - raw value: `Niet iv Circulatie/Diurese`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `20169`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//20169`
  - row count: `21`
  - evidence: `source_vocab`
  - matched by: `term:Nitroglycerine`
  - raw label: `Nitroglycerine Spray`
  - raw value: `Niet iv Circulatie/Diurese`

### anti_arrhythm, Antiarrhythmic, treatment, circulatory

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9015`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//9015`
  - row count: `15927`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Amiodaron Onderhoudsdosis`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7006`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//7006`
  - row count: `5457`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Sotalol`
  - raw label: `Sotalol (Sotacor)`
  - raw value: `Niet iv Circulatie/Diurese`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `6844`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//6844`
  - row count: `3450`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Amiodaron Oplaaddosis`
  - raw value: `2. Spuitpompen`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `16113`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//16113`
  - row count: `1317`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Amiodaron`
  - raw value: `Niet iv Circulatie/Diurese`

match 5:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9015`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//9015`
  - row count: `1147`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Amiodaron Onderhoudsdosis`
  - raw value: `Niet iv Circulatie/Diurese`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7006`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7006`
  - row count: `449`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Sotalol`
  - raw label: `Sotalol (Sotacor)`
  - raw value: `Injecties Circulatie/Diuretica`

match 7:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `16113`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//16113`
  - row count: `411`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Amiodaron`
  - raw value: `Injecties Circulatie/Diuretica`

match 8:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7224`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//7224`
  - row count: `294`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Flecainide`
  - raw label: `Flecaïnide (Tambocor)`
  - raw value: `Niet iv Circulatie/Diurese`

match 9:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9015`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//9015`
  - row count: `211`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Amiodaron Onderhoudsdosis`
  - raw value: `Injecties Circulatie/Diuretica`

match 10:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `6927`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//6927`
  - row count: `97`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Procainamide`
  - raw label: `Procainamide (Pronestyl)`
  - raw value: `2. Spuitpompen`

match 11:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7224`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7224`
  - row count: `46`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Flecainide`
  - raw label: `Flecaïnide (Tambocor)`
  - raw value: `Injecties Circulatie/Diuretica`

match 12:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7224`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7224`
  - row count: `41`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Flecainide`
  - raw label: `Flecaïnide (Tambocor)`
  - raw value: `2. Spuitpompen`

match 13:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9696`
  - source token: `LAB//9696//mg/l`
  - row count: `26`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Amiodaron (bloed)`
  - raw unit: `mg/l`

match 14:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9697`
  - source token: `LAB//9697//mg/l`
  - row count: `26`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Amiodaron, desethyl (bloed)`
  - raw unit: `mg/l`

match 15:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `6927`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6927`
  - row count: `22`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Procainamide`
  - raw label: `Procainamide (Pronestyl)`
  - raw value: `Injecties Circulatie/Diuretica`

match 16:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `18558`
  - source token: `LAB//18558//mg/l`
  - row count: `10`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Amiodaron`
  - raw label: `Tot.Amiodaron + Amiodaron desethyl (bloed)`
  - raw unit: `mg/l`

### dobu_ind, Dobutamine Indicator, treatment, circulatory

- Decision: `OTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `single candidate, row count 9168 >= 10 -- sufficient volume, no competing matches.`
  - table: `drugitems`
  - itemid: `7178`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7178`
  - row count: `9168`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Dobutamine`
  - raw label: `Dobutamine (Dobutrex)`
  - raw value: `2. Spuitpompen`

### levo_ind, Levosimendan Indicator, treatment, circulatory

- Decision: `[MTO/OTO]`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `no_source_candidates`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals. Verified genuinely absent from AmsterdamUMCdb: no drugitems row for Levosimendan (Simdax) in supplied_vocab.csv, the official AmsterdamUMCdb OMOP dictionary_map.csv, or the raw amsterdamumcdb/dictionary/dictionary.csv (checked brand names and INN synonyms too).`

No source-candidate matches recorded.

### norepi_ind, Norepinephrine Indicator, treatment, circulatory

- Decision: `OTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals. Same two source rows apply to both norepi and norepi_ind (identical pattern to epi/epi_ind, dopa/dopa_ind). NB: itemid 7229 (Noradrenaline) is *also* currently listed under the epi/epi_ind (Epinephrine) sections -- apparent term-matcher cross-contamination ("Nor-ADRENALINE" contains "adrenaline"); recommend rejecting those rows from epi/epi_ind during stage 2.`

match 1:
  - decision: `keep`
  - decision reason: `genuine Noradrenaline syringe-pump infusion, dominant channel.`
  - table: `drugitems`
  - itemid: `7229`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7229`
  - row count: `261506`
  - evidence: `supplied_vocab`
  - matched by: `term:Noradrenaline`
  - raw label: `Noradrenaline (Norepinefrine)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `n=1, ordercategory 'Niet iv CZS/Sedatie/Analgetica' is clinically implausible for a vasopressor -- likely miscoded; not trusted as a real administration record.`
  - table: `drugitems`
  - itemid: `7229`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7229`
  - row count: `1`
  - evidence: `supplied_vocab`
  - matched by: `term:Noradrenaline`
  - raw label: `Noradrenaline (Norepinefrine)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica -- likely miscoded (non-IV route for a vasopressor is clinically implausible)`


### epi_ind, Epinephrine Indicator, treatment, circulatory

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `reject`
  - decision reason: `Noradrenaline, not epinephrine -- term-matcher cross-contamination ('Nor-ADRENALINE' contains 'adrenaline'); this drug is norepi's, not epi's.`
  - table: `drugitems`
  - itemid: `7229`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7229`
  - row count: `261506`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Noradrenaline (Norepinefrine)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `genuine epinephrine (Adrenaline) administration record.`
  - table: `drugitems`
  - itemid: `6818`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//6818`
  - row count: `2195`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Adrenaline (Epinefrine)`
  - raw value: `2. Spuitpompen`

match 3:
  - decision: `keep`
  - decision reason: `genuine epinephrine (Adrenaline) administration record.`
  - table: `drugitems`
  - itemid: `6818`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6818`
  - row count: `520`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Adrenaline (Epinefrine)`
  - raw value: `Injecties Circulatie/Diuretica`

match 4:
  - decision: `reject`
  - decision reason: `blood concentration lab test, not an administration record. (Noradrenaline serum level.)`
  - table: `numericitems`
  - itemid: `10196`
  - source token: `LAB//10196//nmol/l`
  - row count: `26`
  - evidence: `source_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Noradrenaline (serum)`
  - raw unit: `nmol/l`

match 5:
  - decision: `reject`
  - decision reason: `blood concentration lab test, not an administration record. (Adrenaline blood level.)`
  - table: `numericitems`
  - itemid: `10197`
  - source token: `LAB//10197//nmol/l`
  - row count: `26`
  - evidence: `source_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Adrenaline  (bloed)`
  - raw unit: `nmol/l`

match 6:
  - decision: `reject`
  - decision reason: `Noradrenaline, not epinephrine -- term-matcher cross-contamination ('Nor-ADRENALINE' contains 'adrenaline'); this drug is norepi's, not epi's.`
  - table: `drugitems`
  - itemid: `7229`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7229`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Noradrenaline (Norepinefrine)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 7:
  - decision: `reject`
  - decision reason: `blood concentration lab test, not an administration record. (Noradrenaline plasma level.)`
  - table: `numericitems`
  - itemid: `10198`
  - source token: `LAB//10198//nmol/l`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Noradrenaline (plasma)`
  - raw unit: `nmol/l`

match 8:
  - decision: `reject`
  - decision reason: `blood concentration lab test, not an administration record. (Adrenaline blood level.)`
  - table: `numericitems`
  - itemid: `10199`
  - source token: `LAB//10199//nmol/l`
  - row count: `1`
  - evidence: `source_vocab`
  - matched by: `term:Adrenaline`
  - raw label: `Adrenaline (bloed)`
  - raw unit: `nmol/l`

### milrin_ind, Milrinone Indicator, treatment, circulatory

- Decision: `[MTO/OTO]`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `no_source_candidates`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals. Verified genuinely absent from AmsterdamUMCdb: no drugitems row for Milrinone (Corotrop) in supplied_vocab.csv, the official AmsterdamUMCdb OMOP dictionary_map.csv, or the raw amsterdamumcdb/dictionary/dictionary.csv (checked brand names and INN synonyms too).`

No source-candidate matches recorded.

### teophyllin_ind, Theophylline Indicator, treatment, circulatory

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `13000`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//13000`
  - row count: `138`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Theofylline`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9143`
  - ordercategoryid: `70.0`
  - source token: `DRUG//START//70//9143`
  - row count: `101`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Theolair retard (Theofylline)`
  - raw value: `Niet iv Tractus Respiratorius`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7023`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7023`
  - row count: `59`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Aminofylline (Theofylline)`
  - raw value: `2. Spuitpompen`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `9144`
  - ordercategoryid: `70.0`
  - source token: `DRUG//START//70//9144`
  - row count: `42`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Theolin retard (Theofylline)`
  - raw value: `Niet iv Tractus Respiratorius`

match 5:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9808`
  - source token: `LAB//9808//mg/l`
  - row count: `20`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Theofylline (bloed)`
  - raw unit: `mg/l`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7023`
  - ordercategoryid: `70.0`
  - source token: `DRUG//START//70//7023`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Theofylline`
  - raw label: `Aminofylline (Theofylline)`
  - raw value: `Niet iv Tractus Respiratorius`

### dopa_ind, Dopamine Indicator, treatment, circulatory

- Decision: `OTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7179`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7179`
  - row count: `31443`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Dopamine`
  - raw label: `Dopamine (Inotropin)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `15640`
  - source token: `LAB//15640//nmol/l`
  - row count: `11`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Dopamine`
  - raw label: `Dopamine (bloed)`
  - raw unit: `nmol/l`

### adh_ind, Vasopressin Indicator, treatment, circulatory

- Decision: `[MTO/OTO]`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `no_source_candidates`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals. Verified genuinely absent from AmsterdamUMCdb: no drugitems row for Vasopressin (argipressine/Pitressin) in supplied_vocab.csv, the official AmsterdamUMCdb OMOP dictionary_map.csv, or the raw amsterdamumcdb/dictionary/dictionary.csv (checked brand names and INN synonyms too). Two related-but-distinct drugs ARE present and should NOT be substituted: Desmopressine (Minrin, itemid 6992, a different indication/ATC H01BA02) and Terlipressine (Glypressin, itemid 12467, ATC H01BA04, used for variceal bleeding/hepatorenal syndrome, not septic-shock vasopressor support).`

No source-candidate matches recorded.

### hep_ind, Heparin Indicator, treatment, circulatory

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `Heparine/Spuitpompen -- genuine infusion.`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7930`
  - row count: `52658`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `Heparine/injection -- bolus is still a real administration event for a presence-only indicator.`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `25.0`
  - source token: `DRUG//START//25//7930`
  - row count: `2281`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `Injecties Haematologisch`

match 3:
  - decision: `reject`
  - decision reason: `Heparinoiden (Hirudoid)/topical -- 'Lik' application count, not heparin at all.`
  - table: `drugitems`
  - itemid: `9079`
  - ordercategoryid: `69.0`
  - source token: `DRUG//START//69//9079`
  - row count: `47`
  - evidence: `source_vocab`
  - matched by: `term:Heparin`
  - raw label: `Heparinoïden (Hirudoid)`
  - raw value: `Niet iv Zalven/Crèmes/Druppels`

match 4:
  - decision: `reject`
  - decision reason: `CVVH anticoag. protocol flag, not an administration event.`
  - table: `listitems`
  - itemid: `20536`
  - valueid: `2.0`
  - source token: `MEASUREMENT_CATEGORICAL//20536//2`
  - row count: `41`
  - evidence: `source_vocab`
  - matched by: `term:Heparine`
  - raw label: `CVVH behandel afspraken Antistolling`
  - raw value: `Heparine`

match 5:
  - decision: `reject`
  - decision reason: `CVVH anticoag. protocol flag, not an administration event.`
  - table: `listitems`
  - itemid: `20536`
  - valueid: `4.0`
  - source token: `MEASUREMENT_CATEGORICAL//20536//4`
  - row count: `23`
  - evidence: `source_vocab`
  - matched by: `term:Heparine`
  - raw label: `CVVH behandel afspraken Antistolling`
  - raw value: `Citraat en Heparine`

match 6:
  - decision: `reject`
  - decision reason: `Drukzak/pressure bag -- volume-only, heparin content unrecoverable.`
  - table: `drugitems`
  - itemid: `8943`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//8943`
  - row count: `13`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Drukzak Heparine`
  - raw value: `Infuus - Crystalloid`

match 7:
  - decision: `keep`
  - decision reason: `Heparine/Infuus-Crystalloid -- real heparin amount regardless of vehicle route, fine for presence-only.`
  - table: `drugitems`
  - itemid: `7930`
  - ordercategoryid: `55.0`
  - source token: `DRUG//START//55//7930`
  - row count: `11`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Heparine`
  - raw label: `Heparine`
  - raw value: `Infuus - Crystalloid`

### prop_ind, Propofol Indicator, treatment, neuro

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7480`
  - row count: `152707`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7480`
  - row count: `825`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7480`
  - ordercategoryid: `17.0`
  - source token: `DRUG//START//17//7480`
  - row count: `1`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Propofol`
  - raw label: `Propofol (Diprivan)`
  - raw value: `Infuus - Colloid`

### benzdia_ind, Benzodiazepine Indicator, treatment, neuro

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7194`
  - row count: `132665`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `6883`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//6883`
  - row count: `33358`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Oxazepam`
  - raw label: `Oxazepam (Seresta)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7165`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7165`
  - row count: `12197`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lorazepam`
  - raw label: `Lorazepam (Temesta)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7165`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7165`
  - row count: `8116`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lorazepam`
  - raw label: `Lorazepam (Temesta)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 5:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7165`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7165`
  - row count: `1913`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lorazepam`
  - raw label: `Lorazepam (Temesta)`
  - raw value: `2. Spuitpompen`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7194`
  - row count: `1681`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 7:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7170`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7170`
  - row count: `867`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Diazepam (Valium)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 8:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7194`
  - ordercategoryid: `29.0`
  - source token: `DRUG//START//29//7194`
  - row count: `339`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (Dormicum)`
  - raw value: `Niet iv CZS/Sedatie/Analgetica`

match 9:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7170`
  - ordercategoryid: `23.0`
  - source token: `DRUG//START//23//7170`
  - row count: `226`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Diazepam (Valium)`
  - raw value: `Injecties CZS/Sedatie/Analgetica`

match 10:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `18671`
  - valueid: `140.0`
  - source token: `MEASUREMENT_CATEGORICAL//18671//140`
  - row count: `111`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Benzodiazepine`
  - raw label: `NICE APACHEIV diagnosen`
  - raw value: `Non-operative neurologic - Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 11:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `17004`
  - valueid: `23.0`
  - source token: `MEASUREMENT_CATEGORICAL//17004//23`
  - row count: `84`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Benzodiazepine`
  - raw label: `APACHEIV Non-operative neurologic`
  - raw value: `Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 12:
  - decision: `reject`
  - decision reason: `blinded research-trial arm -- per-row drug identity unknown, may be placebo.`
  - table: `drugitems`
  - itemid: `14648`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//14648`
  - row count: `81`
  - evidence: `source_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Research  Midazolam/Placebo`
  - raw value: `2. Spuitpompen`

match 13:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `17025`
  - valueid: `51.0`
  - source token: `MEASUREMENT_CATEGORICAL//17025//51`
  - row count: `9`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Benzodiazepine`
  - raw label: `SEC_APACHEIV Non-operative neurologic`
  - raw value: `Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 14:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9766`
  - source token: `LAB//9766//µg/l`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Midazolam`
  - raw label: `Midazolam (bloed)`
  - raw unit: `µg/l`

match 15:
  - decision: `reject`
  - decision reason: `APACHE IV admission-diagnosis-category code ('Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines') -- a diagnosis label the term-matcher caught via the word 'sedative', not a treatment event.`
  - table: `listitems`
  - itemid: `18673`
  - valueid: `592.0`
  - source token: `MEASUREMENT_CATEGORICAL//18673//592`
  - row count: `8`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Benzodiazepine`
  - raw label: `NICE SEC APACHEIV diagnosen`
  - raw value: `Non-operative neurologic - Overdose, sedatives, hypnotics, antipsychotics, benzodiazepines`

match 16:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `12164`
  - source token: `LAB//12164//µg/l`
  - row count: `6`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Diazepam (bloed)`
  - raw unit: `µg/l`

match 17:
  - decision: `keep`
  - decision reason: `binary indicator: genuine administration record, presence-only so route/dose/potency don't matter.`
  - table: `drugitems`
  - itemid: `7170`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7170`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Diazepam (Valium)`
  - raw value: `2. Spuitpompen`

match 18:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9718`
  - source token: `LAB//9718//mg/l`
  - row count: `5`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Oxazepam`
  - raw label: `Oxazepam (bloed)`
  - raw unit: `mg/l`

match 19:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9717`
  - source token: `LAB//9717//µg/l`
  - row count: `4`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Diazepam`
  - raw label: `Nordiazepam (bloed)`
  - raw unit: `µg/l`

match 20:
  - decision: `reject`
  - decision reason: `blood/lab concentration measurement, not an administration event -- measures drug presence after the fact, doesn't confirm active dosing.`
  - table: `numericitems`
  - itemid: `9754`
  - source token: `LAB//9754//µg/l`
  - row count: `2`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Lorazepam`
  - raw label: `Lorazepam (bloed)`
  - raw unit: `µg/l`

### loop_diur_ind, Loop Diuretic Indicator, treatment, metabolic_renal

- Decision: `MTO`
- Target unit: `indicator`
- Reconstruction type: `treatment_indicator`
- Mapping status: `source_candidates_found`
- Notes: `Treatment rate/indicator construction is handled in grid_build_dataset from raw drug/process intervals.`

match 1:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7244`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//7244`
  - row count: `29079`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Furosemide`
  - raw label: `Furosemide (Lasix)`
  - raw value: `2. Spuitpompen`

match 2:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7244`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//7244`
  - row count: `16612`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Furosemide`
  - raw label: `Furosemide (Lasix)`
  - raw value: `Injecties Circulatie/Diuretica`

match 3:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `7244`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//7244`
  - row count: `2449`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Furosemide`
  - raw label: `Furosemide (Lasix)`
  - raw value: `Niet iv Circulatie/Diurese`

match 4:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `6882`
  - ordercategoryid: `30.0`
  - source token: `DRUG//START//30//6882`
  - row count: `595`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Bumetanide`
  - raw label: `Bumetanide (Burinex)`
  - raw value: `Niet iv Circulatie/Diurese`

match 5:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `6882`
  - ordercategoryid: `24.0`
  - source token: `DRUG//START//24//6882`
  - row count: `59`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Bumetanide`
  - raw label: `Bumetanide (Burinex)`
  - raw value: `Injecties Circulatie/Diuretica`

match 6:
  - decision: `keep`
  - decision reason: `binary indicator: presence-only, route/dose/potency don't matter -- confirmed via diagnostic plot review.`
  - table: `drugitems`
  - itemid: `6882`
  - ordercategoryid: `65.0`
  - source token: `DRUG//START//65//6882`
  - row count: `39`
  - evidence: `source_vocab|supplied_vocab`
  - matched by: `term:Bumetanide`
  - raw label: `Bumetanide (Burinex)`
  - raw value: `2. Spuitpompen`
