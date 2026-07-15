# Sepsis-3 label construction (planned, not yet implemented)

Downstream task label built on top of the grid features `samp` and `abx` (both already
resolved in `aumc_grid_feature_manifest_review_claude.md`), following the standard Singer/
Seymour et al. Sepsis-3 "suspected infection" criteria as implemented by ricu's `susp_inf`/
`sep3` (`amsterdam_external/ricu/R/callback-sep3.R`), not the iCareFM paper's stated "detected
bacterial growth" wording -- see chat history for why: AmsterdamUMCdb has no systematic
growth/positivity signal (confirmed via dictionary/vocab/OMOP cross-check, ricu's own
concept-dict.json showing its aumc `samp` is also just an order flag, and independent
literature -- van Doorn et al. PLOS ONE 2024, Fleuren et al. -- both using antibiotics+order
or antibiotic-escalation instead of growth for this exact dataset). A sweep of candidate
policies against the paper's reported AmsterdamUMCdb Sepsis-3 count (5,357/22,893 = 23.4%)
confirmed the windowed antibiotics+order combination (P2b below) lands closest (25.3%,
5,841/23,103), while true growth (7 admissions, 0.03%) is off by three orders of magnitude
and can be ruled out.

## Step 1: suspected infection (`susp_inf`), P2b definition

For each admission, build two event-hour sets:
- **A** = every hour an antibiotic administration started (`abx` feature, drugitems).
- **S** = every hour a `samp` order fired (`samp` feature, as redefined -- 14-itemid
  procedureorderitems whitelist, see the manifest's `samp` section).

`susp_inf = TRUE` iff either:
- ∃ a∈A, s∈S with **a ≤ s ≤ a + 24h** ("antibiotics, then a culture ordered within a day"), OR
- ∃ s∈S, a∈A with **s ≤ a ≤ s + 72h** ("culture ordered, then antibiotics within three days")

Whichever of the two qualifying events happens first is the **SI time** for that admission.
(`abx_win = 24h`, `samp_win = 72h` are ricu's defaults, matching Singer et al.)

## Step 2: suspected-infection window

`SI window = [SI_time − 48h, SI_time + 24h]` (ricu's `si_lwr`/`si_upr` defaults, per Seymour
et al.'s supplemental material).

## Step 3: organ-dysfunction filter -- NOT YET IMPLEMENTED

Real Sepsis-3 requires the full 6-organ SOFA score (respiratory, coagulation, liver,
cardiovascular, CNS, renal) to increase by **≥2 points** somewhere within the SI window,
relative to a baseline. This has not been built. The candidate-policy sweep (`P6` in chat)
used a crude 1-organ placeholder instead -- "ever received a vasopressor" (cardiovascular
only, no baseline/delta logic, no window restriction) -- which landed at 25.9% (5,987/23,103),
close to but not a substitute for the real filter. Building the true SOFA-delta computation
is the next step before this label should be used for anything beyond a plausibility check.

## Step 4: final label

`sep3 = susp_inf AND (SOFA increased ≥2 within the SI window)`

## Reference numbers (from `check_sepsis3_candidate_policies.py`, full population, 23,103 valid-LOS admissions)

| Policy | Definition | N | % |
|---|---|---|---|
| P1 | ricu `samp` (20-itemid list), pure order flag, unwindowed | 7,691 | 33.3% |
| P4 | Our 14-itemid samp list, pure order flag, unwindowed | 6,232 | 27.0% |
| P5 | Antibiotics ever (no culture requirement) | 17,140 | 74.2% |
| P3 | abx OR samp, unwindowed | 17,488 | 75.7% |
| P2 | susp_inf windowed, ricu's 20-itemid samp list | 7,296 | 31.6% |
| **P2b** | **susp_inf windowed, our 14-itemid samp list -- adopted for `samp`** | **5,841** | **25.3%** |
| P6 | P2 ∩ ever-vasopressor (crude 1-organ SOFA-cv proxy) | 5,987 | 25.9% |
| — | **iCareFM reported (target)** | **5,357** | **23.4%** |
