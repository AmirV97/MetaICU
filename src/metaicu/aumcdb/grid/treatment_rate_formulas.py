"""
Structured, executable version of the decided treatment_rate reconstruction formulas --
transcribed directly from each match's decision-reason text and each feature's Target unit
field in aumc_grid_feature_manifest_review_claude.md. v1: no outlier exclusion (per user
decision 2026-07-10 -- extract raw first, inspect, add outlier clipping in v2).

Each entry: (table, itemid, ordercategoryid_or_None, formula, factor).
formula is one of:
  "raw_rate"                 -- use drugitems.rate as-is (validated this session for the
                                 vasopressor family: raw_rate tracked dose/duration closely
                                 during continuous stretches but without dose/duration's
                                 spurious spikes)
  "dose_over_duration"       -- dose / (duration/60) with NO further unit multiplier
                                 (teophyllin's target unit is mg/min, and dose(mg)/
                                 duration(min) already lands in mg/min directly)
  "dose_over_duration_x60"   -- dose / (duration/60), for mg/h or U/h targets (hep,
                                 benzdia, loop_diur) where dose(mg or IE)/duration(min)*60
                                 converts to a per-hour rate
  "dose_over_duration_x1000" -- dose / (duration/60) * 1000, for prop (mg/min -> mcg/min)
  "raw_value_numericitems"   -- ufilt only: not a drugitems rate at all, just the raw
                                 numericitems value (median per hour, same mechanism as
                                 direct_numeric) -- table/ordercategoryid fields are
                                 repurposed (table="numericitems", ordercategoryid=None,
                                 a code_prefix filter is applied separately since itemid
                                 8805 also has an already-rejected dead MEASUREMENT_BEDSIDE
                                 route sharing the same itemid).
"""

TREATMENT_RATE_MATCHES = {
    "ufilt": [
        # RESOLVED (2026-07-10): switching to raw CSVs removes amsterdam_pipeline's derived
        # code_prefix column (SUBJECT_FLUID_OUTPUT vs the dead all-zero MEASUREMENT_BEDSIDE
        # route for itemid 8805). Checked three raw numericitems.csv columns directly
        # (fluidout, islabresult, tag) as candidate replacements for that split -- none of
        # them distinguish it: fluidout turned out to NOT be a 0/1 flag (622 distinct numeric
        # values, uniform across all 98383 rows for this itemid); islabresult is uniformly 0;
        # tag splits into an unrelated NUL/blank grouping (865/97518). The SUBJECT_FLUID_OUTPUT/
        # MEASUREMENT_BEDSIDE categorization isn't derivable from any raw per-row column --
        # it must come from an external vocabulary/lookup table amsterdam_pipeline consults,
        # which raw-CSV mode deliberately avoids depending on for just one feature.
        # Accepted tradeoff: pool all itemid-8805 rows unfiltered. The dead channel is a small
        # minority (6117/98383 = 6.2% zero-valued rows) and hour-level MEDIAN aggregation is
        # robust to that minority contamination -- confirmed the pooled median (110.0) matches
        # the already-validated real-signal-only median from earlier this session.
        {"table": "numericitems", "itemid": 8805, "formula": "raw_value_numericitems", "factor": 1.0},
    ],
    "dobu": [
        {"table": "drugitems", "itemid": 7178, "ordercategoryid": 65, "formula": "raw_rate", "factor": 1.0},
    ],
    "norepi": [
        {"table": "drugitems", "itemid": 7229, "ordercategoryid": 65, "formula": "raw_rate", "factor": 1.0},
    ],
    "epi": [
        {"table": "drugitems", "itemid": 6818, "ordercategoryid": 65, "formula": "raw_rate", "factor": 1.0},
    ],
    "dopa": [
        {"table": "drugitems", "itemid": 7179, "ordercategoryid": 65, "formula": "raw_rate", "factor": 1.0},
    ],
    "teophyllin": [
        {"table": "drugitems", "itemid": 13000, "ordercategoryid": 65, "formula": "dose_over_duration", "factor": 1.0},
        {"table": "drugitems", "itemid": 7023, "ordercategoryid": 65, "formula": "dose_over_duration", "factor": 0.8},
    ],
    "hep": [
        {"table": "drugitems", "itemid": 7930, "ordercategoryid": 65, "formula": "dose_over_duration_x60", "factor": 1.0},
    ],
    "prop": [
        {"table": "drugitems", "itemid": 7480, "ordercategoryid": 65, "formula": "dose_over_duration_x1000", "factor": 1.0},
    ],
    "benzdia": [
        {"table": "drugitems", "itemid": 7194, "ordercategoryid": 65, "formula": "dose_over_duration_x60", "factor": 1.0},
        # REMOVED 2026-07-13 (root cause 3 fix): itemid 7194 was also matched under
        # ordercategoryid 23 ("Injecties CZS/Sedatie/Analgetica") and 29 ("Niet iv
        # CZS/Sedatie/Analgetica") -- both are bolus-injection/non-IV categories, not
        # continuous infusion, and 100% of their rows have duration=1 (a fixed sentinel for
        # "instantaneous event", not real elapsed time). Feeding those through a continuous-
        # rate formula is a category-matching bug, not a numeric-threshold issue -- only
        # ordercategoryid 65 ("2. Spuitpompen" = syringe pump) is a genuine continuous
        # infusion, matching hep/prop/loop_diur below, which were never matched to 23/29.
        {"table": "drugitems", "itemid": 7165, "ordercategoryid": 65, "formula": "dose_over_duration_x60", "factor": 2.0},
        {"table": "drugitems", "itemid": 7170, "ordercategoryid": 65, "formula": "dose_over_duration_x60", "factor": 0.4},
    ],
    "loop_diur": [
        {"table": "drugitems", "itemid": 7244, "ordercategoryid": 65, "formula": "dose_over_duration_x60", "factor": 1.0},
        {"table": "drugitems", "itemid": 6882, "ordercategoryid": 65, "formula": "dose_over_duration_x60", "factor": 40.0},
    ],
}

TARGET_UNITS = {
    "ufilt": "ml", "dobu": "mcg/min", "norepi": "mcg/min", "epi": "mcg/min", "dopa": "mcg/min",
    "teophyllin": "mg/min", "hep": "U/h", "prop": "mcg/min", "benzdia": "mg/h", "loop_diur": "mg/h",
}

# Flagged 2026-07-10 after visualizing v1 on 10 subjects: these 4 features' dose_over_duration*
# formulas blow up whenever `duration` is corrupted (negative/zero -- stop logged before start,
# or a zero-width interval used as a divisor) or merely very short, producing inf/nonsensical
# rates that dominate the plot scale (benzdia max=inf, hep max=49.2M U/h, loop_diur(furosemide)
# max=2.16M mg/h, prop max=inf). teophyllin (also dose_over_duration) checked and is clean --
# no duration<=0 rows, not flagged. dobu/norepi/epi/dopa (raw_rate) and ufilt (raw value) have
# no division at all, not affected, not flagged.
#
# REVISED 2026-07-13 (root cause 3 fix): the original v1 duration<=0 filter only caught the
# most blatant corruption. A raw duration sweep (see chat) showed a much larger share of rows
# have short-but-positive durations that still amplify dose-quantization/rounding error into
# implausible rates -- and critically, the *median* computed rate itself kept shrinking as the
# minimum-duration threshold rose (not just the tail), meaning no single duration cutoff cleanly
# separates real infusions from amplified ones without discarding most of the data. Fix is
# two-part:
#   1. MIN_DURATION_SECONDS: a 60s floor drops only sub-minute logging-artifact segments (a
#      real, deliberately-set infusion rate order isn't meaningfully characterized in <60s).
#   2. RATE_CEILING (applied in grid/extract_rate.py on the computed rate, drop-as-missing not
#      clip -- same convention as grid/plausibility_bounds.py): a generous, literature-grounded
#      per-drug ceiling as the actual backstop, since the duration floor alone can't fully
#      remove the amplification without destroying real data. Sourced 2026-07-13:
#        benzdia (mg/h, midazolam-equivalent): high-dose refractory status epilepticus
#          protocols report a median max of 0.4 mg/kg/h (IQR 0.2-1.0); 150 leaves margin above
#          1.0 mg/kg/h even at an extreme 150kg body weight.
#        hep (U/h): standard weight-based infusion is 18 U/kg/h with no protocol-stated cap;
#          10000 leaves wide margin above 18 U/kg/h even at 250kg.
#        prop (mg/h): labeling caps maintenance at 70 mcg/kg/min ("never exceed" for propofol
#          infusion syndrome risk); 1000 leaves margin above that even at 150kg
#          (70 mcg/kg/min * 150kg * 60 = 630 mg/h).
#        loop_diur (mg/h, furosemide-equivalent): FDA labeling states a maximum furosemide
#          continuous-infusion rate of 4 mg/min = 240 mg/h -- used directly, not re-derived.
#
# EXTENDED 2026-07-14: dobu/norepi/epi/dopa/teophyllin were never covered by the 2026-07-13
# fix above -- checked now (grid/_check_rate_drugs.py) and found the identical signature: every
# extreme value traces to a duration=1s (occasionally a few seconds) sentinel row. teophyllin
# additionally still produces implausible rates at duration=60s (e.g. dose=400mg/duration=60s
# = 400 mg/min), so the duration floor alone isn't enough for it either -- same two-part fix.
# Ceilings sourced 2026-07-14 (see chat), each a generous max-labeled-dose x 150kg:
#   dobu (mcg/min): max labeled dose 40 mcg/kg/min; 6000 = 40*150.
#   norepi (mcg/min): no established hard cap; 0.4-1 mcg/kg/min is already the "high-dose
#     refractory shock" range associated with high mortality but real, administered doses;
#     750 = 5 mcg/kg/min*150kg leaves wide margin above that range.
#   epi (mcg/min): practical/labeled max ~2 mcg/kg/min; 300 = 2*150.
#   dopa (mcg/min): labeled max 50 mcg/kg/min, with >50 "safely used" in extremis per some
#     sources; 15000 = 100 mcg/kg/min*150kg leaves margin above even that off-label use.
#   teophyllin (mg/min): loading dose 6-7 mg/kg over 20-30 min -> ~45-52 mg/min at 150kg;
#     50 leaves margin at the very top of that range.
MIN_DURATION_SECONDS = {
    "benzdia": 60.0, "hep": 60.0, "loop_diur": 60.0, "prop": 60.0,
    "dobu": 60.0, "norepi": 60.0, "epi": 60.0, "dopa": 60.0, "teophyllin": 60.0,
}
RATE_CEILING = {
    "benzdia": 150.0, "hep": 10000.0, "prop": 1000.0, "loop_diur": 240.0,
    "dobu": 6000.0, "norepi": 750.0, "epi": 300.0, "dopa": 15000.0, "teophyllin": 50.0,
}
