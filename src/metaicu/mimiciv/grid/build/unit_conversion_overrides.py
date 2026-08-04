"""
Per-itemid unit-conversion overrides for direct_numeric/derived_output_rate/treatment_rate
features -- the v1 gap flagged in grid/extract_numeric.py's and grid/extract_rate.py's own
docstrings ("No unit conversion yet"). Mirrors
AUMC_grid_pipeline/unit_conversion_overrides.py's CONDITIONAL_PERCENT_ITEMIDS pattern (same fix
shape: AUMC's hct itemids mix fraction-scale (0-1) and percent-scale (0-100) rows under the same
itemid, a flat per-itemid factor is wrong either way) -- found here for fio2 during the 2026-07-31
AUMC-vs-M4 distribution-diff audit: the extracted grid showed 0.14% of fio2's non-null values as
raw fractions (0.21, 0.35, 0.5, ...) never converted to percent, a well-documented MIMIC-IV
charting inconsistency.

scripts_review/check_fio2_fraction_source.py (job 543476) broke this down per itemid, confirming
it is NOT uniform across fio2's 3 kept itemids:
  - 223835 "Inspired O2 Fraction" (main source, n=1,144,289): 1392 rows (0.122%) <=1.5
  - 229280 "FiO2 (ECMO)" (n=26,636): 78 rows (0.293%) <=1.5
  - 229841 "FiO2 (CH)" (n=4,201): 0 rows <=1.5 -- NOT affected, deliberately excluded below
Scoped to the two confirmed-affected itemids only, not a blanket per-tag fix (see AUMC's own hct
CONDITIONAL_PERCENT_ITEMIDS note on why a flat per-tag factor is wrong when only some itemids are
affected). A value <=1.5 is essentially unambiguous here regardless: a genuine raw-percent FiO2
reading below ~21% (room air) is not just implausible but physiologically impossible for a
supplemental-O2 delivery device, so any such row is a fraction-scale encoding, not a real low
reading.

Keys are (tag, itemid) int/str pairs. Rule: value <= threshold -> multiply by 100 (it's a
fraction); value > threshold -> leave as-is (it's already %). Applied in
grid/extract_numeric.py's _build_numeric_for_table, after the itemid->tag join, before the
plausibility-bounds filter (bounds are defined in the target unit, i.e. post-conversion).
"""

CONDITIONAL_PERCENT_ITEMIDS = {("fio2", 223835), ("fio2", 229280)}
CONDITIONAL_PERCENT_THRESHOLD = 1.5

# Per-kg-of-bodyweight treatment_rate rows -- first found for norepi during the 2026-08-03
# rank-11-20 divergence audit (scripts_review/audit_next10_features.py, job 547303), then swept
# across every OTHER inputevents-sourced treatment_rate tag before committing to model training
# (scripts_review/audit_all_treatment_rate_units.py, job 547592) since the same MIMIC-IV charting
# habit (recording vasoactive-drug rate per kg of bodyweight) turned out to be systemic, not
# norepi-specific. MIMIC-IV's inputevents carries a native `rateuom` column (unlike AUMC's
# drugitems, which has one rate unit per drug) and it is NOT uniform per itemid. Every tag below
# is a vasopressor/inotrope whose dominant (or exclusive) rateuom is a per-kg mass rate, while the
# tag's target unit is an ABSOLUTE mcg/min (confirmed against AUMC's own treatment_rate_formulas.py:
# every one of these uses raw_rate with factor=1.0, i.e. AUMC's native drugitems rate is already
# absolute, no weight term in AUMC's own formula -- milrin/adh have no AUMC source data at all to
# compare against, but AUMC's manifest still records their target_unit as mcg/min / U/min
# respectively, from the same shared feature spec, so the "absolute, not per-kg" expectation
# still holds). Without this fix, grid/extract_rate.py was taking each raw per-kg value as if it
# were already absolute -- every affected "on" hour was silently under-scaled by roughly the
# patient's bodyweight (~80kg median across all of these):
#   dobu itemid 221653:  10,264/10,264   (100%)    mcg/kg/min
#   dopa itemid 221662:  18,085/18,085   (100%)    mcg/kg/min
#   epi  itemid 221289:  31,495/31,495   (100%)    mcg/kg/min
#   milrin itemid 221986: 10,668/10,668  (100%)    mcg/kg/min
#   norepi itemid 221906: 459,798/459,800 (99.9996%) mcg/kg/min (2 rows mg/kg/min, included below)
#   prop itemid 222168:  402,985/498,811 (80.8%)   mcg/kg/min (95,823 null -- filtered upstream by
#     the rate.is_not_null() check before this table is even consulted; 3 rows mg/hour -- a
#     different, TIME-basis mismatch, not mass/per-kg, and negligible enough (0.0006%) to leave
#     unconverted, same call as hep's negligible rows below)
#
# hep's two treatment_rate itemids (225152, 229597) were checked the same way and found NOT to
# need this fix: 225152 is 88,728/98,795 rows "units/hour" (matches U/h target) vs only 2 rows
# "units/kg/hour"; 229597 is 1,795/1,796 rows "units/hour" vs 1 row "units/min" -- both mismatched
# variants are single-digit-row noise, not a systematic scale error, so left unconverted (not
# worth the added complexity for a handful of rows that can't move any aggregate statistic).
# benzdia/loop_diur were also checked and found already correctly absolute (mg/hour, matching
# their mg/h target) with no per-kg variant at all.
#
# Keys are (tag, itemid) -> {rateuom: mass_scale_factor}, mass_scale_factor being the multiplier
# that brings that rateuom's mass unit to the tag's target mass unit (e.g. mg->mcg is 1000.0;
# mcg->mcg is 1.0, kept explicit rather than omitted so every per-kg rateuom variant for a covered
# itemid is accounted for). Applied in grid/extract_rate.py's _extract_inputevents_rate as
# `rate * mass_scale_factor * patientweight` (patientweight is a native inputevents column, no
# join needed), before the hourly explode/mean-aggregation step.
PER_KG_RATE_MASS_SCALE = {
    ("norepi", 221906): {"mcg/kg/min": 1.0, "mg/kg/min": 1000.0},
    ("dobu", 221653): {"mcg/kg/min": 1.0},
    ("dopa", 221662): {"mcg/kg/min": 1.0},
    ("epi", 221289): {"mcg/kg/min": 1.0},
    ("milrin", 221986): {"mcg/kg/min": 1.0},
    ("prop", 222168): {"mcg/kg/min": 1.0},
}

# Aminophylline is recorded per kg and per hour, while the shared theophylline target is an
# absolute mg/min rate. The factor combines hour->minute conversion with the weight expansion.
PER_KG_RATE_TIME_SCALE = {
    ("teophyllin", 221342): {"mg/kg/hour": 1.0 / 60.0},
}

# Wrong-time-base treatment_rate rows -- same 2026-08-03 sweep (job 547592). adh (Vasopressin,
# itemid 222315) is 37,160/37,163 rows (99.99%) "units/hour" against a target unit of U/min (per
# both this manifest and AUMC's own, though AUMC itself has zero Vasopressin source data to
# extract from -- verified absent from AmsterdamUMCdb entirely, so this is a pure target-spec
# check, not a cross-dataset value comparison); only 3 rows are already the correct "units/min".
# Unlike the per-kg cases above, this is a flat time-base conversion -- no patientweight term.
# Keys/semantics mirror PER_KG_RATE_MASS_SCALE but the factor folds in BOTH any mass-unit change
# and the time-base change (hour->min is /60) with no per-kg multiply; applied the same place in
# grid/extract_rate.py as `rate * scale_factor` (no patientweight).
RATE_TIME_SCALE = {
    ("adh", 222315): {"units/hour": 1.0 / 60.0},
}
