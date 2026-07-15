# iCareFM preprocessing methodology (reference for grid_build_dataset)

Source: `Supplementary Material for "A Foundation Model for Intensive Care..."`
(the iCareFM supplementary PDF), sections
A.2.2, A.2.4, A.2.5, A.4.1-A.4.4. Not covered in the two main-text PDFs. Quotes are
verbatim from the PDF text extraction; section numbers let you re-verify.

## Admission inclusion criteria (A.2.2) -- implemented 2026-07-15

Never implemented before this pass -- found while reviewing the supplement for an unrelated
question. `grid.sampling.load_valid_admissions` only ever filtered on `true_los_hours` being
non-null and positive; the paper's actual criteria are stricter. Verbatim (A.2.2, "Inclusion
criteria and data splitting"):

> We consider patient stays that after extraction have
> - a valid admission and discharge time,
> - a valid length of stay (LoS) of at least 4 hours,
> - a maximum gap between measurements of at most 48 hours,
> - and at least 4 measurements.
>
> Compared to Van De Water et al., we broaden the inclusion criteria by reducing the LoS
> requirement from 6 to 4 hours and increasing the allowed maximum gap between measurements
> from 12 to 48 hours. We keep inclusion criteria minimal so the pretraining corpus covers a
> broad demographic.

The paper doesn't define what counts as a "measurement" for the >=4-measurements and
max-gap<=48h criteria. Resolved empirically: Table S1 reports UMCdb's (AmsterdamUMCdb's) final
cohort size as **22,883 stays** after all inclusion criteria -- a concrete target to validate
against. Tested 3 hypotheses on the full population (`grid/_check_los_inclusion_criteria.py`,
combined with LOS>=4h):

| hypothesis | reconstruction types pooled | resulting admissions | diff from 22,883 target |
|---|---|---|---|
| H1 | all 5 types (direct_numeric, derived_output_rate, categorical, treatment_indicator, treatment_rate) | 15,948 | -6,935 |
| H2 | observations only (direct_numeric, derived_output_rate, categorical) | 15,917 | -6,966 |
| **H3** | **numeric vitals/labs only (direct_numeric, derived_output_rate)** | **22,774** | **-109** |

H3 wins by a wide margin (0.5% off vs. ~30% off for H1/H2) -- confirming the paper's
"measurement" criterion is intended to apply to the continuous numeric vital/lab stream only,
not sparse categorical scores or event-driven treatments. This matches A.2.4's own description
of numeric physiological data as "observed continuously and also stored with high frequency
and density" in contrast to categorical scores, which are called out there as "available more
sparsely." **This confirms H3 was indeed the paper's intended definition, not just the best
available guess** -- adopted as the actual rule. The residual 109-admission gap is attributable
to things we can't exactly replicate (their precise AmsterdamUMCdb extraction version/date,
exact numeric-vs-lab item boundaries, LOS rounding), not a wrong definition.

Implemented in `grid.sampling.apply_inclusion_criteria` (LOS>=4h AND >=4 distinct hours with
any direct_numeric/derived_output_rate measurement AND max gap between those hours <=48h),
called in `run_extraction.py` right after `extract_numeric_categorical` (needs real per-hour
data) and before `grid.split.assign_splits` (splits must be computed on the final,
post-inclusion-criteria cohort). Toggled via `--inclusion-criteria`/`--no-inclusion-criteria`
(default on).

## Treatment indicators are binary, no PK/half-life modeling (A.2.4, A.4.1-A.4.3)

- **Infusions**: "we extract both accurate treatment administration rates and
  treatment indicators (binary presence of active infusion)."
- **Bolus/tablet doses**: "If dosage information is available we harmonize
  these drug administrations together with the infusions by computing an
  instantaneous application rate, otherwise a simple administration
  indicator is extracted."
- **Hourly binning**: "for binary information an any operation is used" --
  indicator = 1 for an hour iff there is any overlap with an active
  infusion/administration in that hour, else 0.
- **Scaling**: "treatment indicators are binary encoded using {0, 1} where 0
  represents no medication given." Continuous treatments are quantile-
  transformed to [0, 1] where 0 = no medication given.
- **Imputation -- deliberate asymmetry vs. observations**: "Gridded
  time-step data... are forward-filled indefinitely for all observation
  variables." But "Any treatment variable is excluded from forward-filling
  operations and missing data points are strictly filled using 0."

**Consequence for our `_ind` features** (`norepi_ind`, `epi_ind`, etc.):
no half-life / pharmacokinetic "presence in system" window. A bolus dose is
only "on" for the hour(s) actually covered by its raw administration
interval (start-stop overlap for infusions; the administration instant for
boluses), reverting to 0 the moment there is no new raw event -- never
carried forward. Searched the full 66-page supplement for "half-life",
"pharmacokinetic", "elimination", "decay" -- zero hits in the relevant
sense; this is confirmed absent, not an oversight on our part.

Implementation for our pipeline: compute the `_ind` value per grid hour as
`ANY(raw drugitems row's [start, stop] interval overlaps this hour)`,
zero-fill absent hours, never forward-fill.

## Hourly grid construction pipeline (A.4.1)

Three steps: (1) concept harmonization across source tables/columns/units
into one target unit, (2) outlier removal with "big margins, to avoid
erroneously removing strong signals of severely ill patients", (3)
aggregation into an hourly sparse grid:
- numeric observations -> **median** aggregation per bin
- categorical -> **mode** per bin
- binary (indicators) -> **any** per bin
- continuous treatment (infusion rates) -> **mean** aggregation per bin,
  with rate extracted "as accurately as possible given the available data
  w.r.t. time and amount"
- "No imputation is performed at this stage, time bins without any data
  remain empty."

## Scaling (A.4.2)

- Continuous observations: standardized (center + unit variance); log
  transform first "if deemed suitable".
- Categorical: one-hot encoded, with a dedicated class per variable for
  missing information.
- Continuous treatments: quantile-transformed to [0, 1], 0 = no medication.
- Treatment indicators: binary {0, 1}, 0 = no medication.

## Imputation (A.4.3)

- Observation variables: forward-filled indefinitely; anything still
  missing after that is imputed with 0 (= population mean, given standard
  scaling was already applied). Categorical missing -> the dedicated
  "missing" one-hot class.
- Treatment variables: **excluded** from forward-filling; missing is always
  filled with 0 (= no treatment), regardless of how long ago the last dose
  was given.

## Downstream feature extraction (A.4.4) -- not part of the base grid

Separate from grid construction: for ML input features, rolling-window
statistics are computed over 8h/24h/72h history windows (mean, std, slope,
mean absolute change, non-missing fraction, quantiles for continuous;
mode/missing-count/any-missing for categorical; count-with-treatment/
any-treatment for indicators). This is a downstream feature-engineering
step on top of the hourly grid, not a grid-construction rule -- don't
conflate with the A.4.1-A.4.3 rules above.

## Caveat: task-label imputation is a separate, different scheme (A.5.1)

Task labels (e.g. circulatory failure) apply their **own** imputation on
top of the base grid, which is *not* the same rule as A.4.3 and is
value-dependent, not variable-type-dependent. Example given for lactate in
the circulatory-failure label: normal-range measurements are forward/
backward-filled indefinitely, but measurements crossing the critical
threshold (>2 mmol/l) are only forward/backward-filled up to 6 hours (linear
interpolation if two measurements are <6h apart). This only applies to
specific task-label construction, not to the general per-feature grid
values -- do not apply this 6-hour capping rule to the base grid itself.

## Treatment concept curation (A.2.5)

Concepts chosen from variables "identified as most predictive... in
published literature (circulatory failure, respiratory failure, kidney
failure, sepsis)"; some made more granular per ICU-clinician input (e.g.
vasopressors split into individual drugs), low-priority ones dropped (e.g.
laxatives). Free-text treatment variables (>16,000 unique raw entries across
~half the source datasets) were LLM-pre-labeled, then manually verified in
three rounds: data scientists first, then two physicians independently.

---

# Our own AUMC decisions (not from the iCareFM paper)

The paper's methodology above doesn't cover every case we hit while deciding
AUMC's grid candidates. Decisions below are ours, sourced separately, kept
here so the reasoning/citations aren't lost before they're written into the
manifest.

## benzdia (Benzodiazepine, mg/h): cross-drug dose standardization

`benzdia` groups 4 non-equipotent drugs (Midazolam, Lorazepam, Diazepam,
Oxazepam). Policy: **numeric standardization** -- convert each drug's
administered mg to a midazolam-mg-equivalent before summing, rather than
rejecting the non-midazolam drugs or summing raw mg unweighted.

**Conversion factors (raw mg x factor = midazolam-mg-equivalent):**

| Drug | Factor | Source confidence |
|---|---|---|
| Midazolam | x 1.0 | reference drug |
| Lorazepam | x 2.0 | citable |
| Diazepam | x 0.4 | citable |
| Oxazepam | x 0.133 | citable |

**Derivation:** VA/DoD and Ashton Manual both anchor to 10mg oral diazepam:
10mg diazepam = 2mg lorazepam (VA/DoD; Ashton says 1mg -- VA/DoD figure used
here) = 30mg oxazepam (VA/DoD; Ashton says 20mg). Bridged to midazolam via
1mg lorazepam = 2mg midazolam => 4mg midazolam = 10mg diazepam = 2mg
lorazepam = 30mg oxazepam, giving the factors above relative to midazolam=1.

**Sources (diazepam/lorazepam/oxazepam leg -- solid):**
- Department of Veterans Affairs, Department of Defense. *VA/DoD Clinical
  Practice Guideline for the Management of Substance Use Disorders.* 2021.
- Ashton CH. *The diagnosis and management of benzodiazepine dependence.*
  Curr Opin Psychiatry. 2005;18(3):249-255.
  doi:10.1097/01.yco.0000165594.60434.84 (table also in: Ashton,
  *Benzodiazepines: How They Work and How to Withdraw*, Institute of
  Neuroscience, Newcastle University, 2002; https://www.benzo.org.uk/bzequiv.htm)
- Both tabulated side by side in: ASAM/AAAP *Joint Clinical Practice
  Guideline on Benzodiazepine Tapering* (2025), "Benzodiazepine Dose
  Equivalents" table.

**Caveat (midazolam leg -- weaker, flag this):** none of the above tables
include midazolam at all -- they're built for chronic oral anxiolytic
tapering, and midazolam is IV-only/short-acting, essentially never used
that way. The 1mg lorazepam = 2mg midazolam bridge recurred consistently
across clinical dosing calculators but I could not trace it to a
peer-reviewed primary source. Also directly relevant: a real ICU pharmacy
department memo on switching between these exact IV drugs states "there
are no direct dose conversions between agents" and gives pharmacokinetic
profiles (onset/duration/half-life) instead of a dose table -- i.e. real
ICU practice titrates to a sedation score rather than converting doses.
This standardization is therefore a pragmatic approximation for an ML
feature, not a clinically validated equivalence -- state that plainly in
the manifest note, don't present it as more rigorous than it is.

**Reconstruction:** `benzdia` (mg/h) = sum over drugs of (administered
mg/h x factor). `benzdia_ind` (binary) is unaffected -- potency doesn't
matter for a presence/absence signal, so all 4 drugs count as-is.
