"""
Per-match unit-conversion overrides for direct_numeric/derived_output_rate/categorical
features, transcribed directly from the already-written `decision reason` text in
aumc_grid_feature_manifest_review_claude.md. Originally built by exhaustively grepping every
in-scope kept match's decision reason for convert/factor/formula/scale language, then checking
every feature with >1 distinct raw unit among its kept matches -- that grep-based pass missed
some real conversions (e.g. bun's decision reason literally says "x 2.8" and still wasn't
caught), and some are invisible to any text/raw-unit-string check at all (sao2's raw_unit says
"Geen", this dataset's usual harmless-dimensionless label, but the actual values are a 0-1
fraction, not %). The 2026-07-13 additions below were found via a systematic sweep comparing
every in-scope feature's target unit against its kept matches' raw units AND actual value
percentiles (see chat), not text-grepping alone.

Default (no entry here) = pool raw value as-is (same unit family, or a labeling-only
difference confirmed harmless, e.g. E/l vs IE/l, or µmol/l vs µmol, or ng/ml vs µg/l which are
numerically identical).

Keys are (tag, itemid) strings, matching feature_matches.json's string-typed fields.
"""

# value_target = value_raw * FACTOR
UNIT_FACTOR = {
    ("po2", "21214"): 7.50062,      # kPa -> mmHg
    ("pco2", "21213"): 7.50062,     # kPa -> mmHg
    ("bili", "9945"): 1 / 17.1,     # umol/L -> mg/dL
    ("bili", "6813"): 1 / 17.1,     # umol -> mg/dL
    ("phos", "9935"): 3.097,        # mmol/L -> mg/dL (phosphorus)
    ("phos", "6828"): 3.097,
    ("peep", "8862"): 1.0197,       # mbar -> cmH2O
    ("peep", "8879"): 1.0197,
    ("peep", "9666"): 1.0197,
    ("peak", "8877"): 1.0197,
    ("ps", "8865"): 1.0197,
    ("tv", "8851"): 1000.0,         # mislabeled 'ml' but actually L-scale

    # Found 2026-07-13 via the systematic target-unit-vs-raw-unit-vs-value-scale sweep
    # described above -- see chat for the full per-feature evidence (bulk percentiles landing
    # on the raw unit's scale, not the target's).
    ("ca", "9933"): 40.078 / 10,       # mmol/L -> mg/dL (calcium, atomic weight 40.078)
    ("ca", "6817"): 40.078 / 10,
    ("crea", "9941"): 113.12 / 10000,  # umol/L -> mg/dL (creatinine, MW 113.12)
    ("crea", "6836"): 113.12 / 10000,
    ("glu", "9947"): 180.156 / 10,     # mmol/L -> mg/dL (glucose, MW 180.156)
    ("glu", "9557"): 180.156 / 10,
    ("glu", "6833"): 180.156 / 10,
    ("mg", "9952"): 24.305 / 10,       # mmol/L -> mg/dL (magnesium, atomic weight 24.305)
    ("mg", "6839"): 24.305 / 10,
    ("mg", "9953"): 24.305 / 10,
    ("hgb", "10286"): 1.6114,          # mmol/L -> g/dL (hemoglobin, standard clinical factor)
    ("hgb", "9960"): 1.6114,
    ("hgb", "9553"): 1.6114,
    ("hgb", "6778"): 1.6114,
    ("hgb", "19703"): 1.6114,
    ("fgn", "10175"): 100.0,           # g/L -> mg/dL (dimensional, exact)
    ("fgn", "9989"): 100.0,
    ("fgn", "6776"): 100.0,
    ("alb", "9937"): 0.1,              # g/L -> g/dL (dimensional, exact)
    ("alb", "6801"): 0.1,
    ("alb", "14349"): 0.1,
    ("bun", "9943"): 2.8,              # mmol/L urea -> mg/dL BUN, the manifest's own literal
    ("bun", "6850"): 2.8,              # decided factor (kept as-is, not re-derived)
    ("sao2", "12311"): 100.0,          # sole sao2 source reports a 0-1 fraction, not % --
                                        # invisible to a raw-unit-string check (see docstring)
    ("plateau", "8878"): 1.0197,       # mbar -> cmH2O, matching its peep/peak/ps siblings
}

# value_target = value_raw * AFFINE[tag,itemid][0] + AFFINE[tag,itemid][1]
UNIT_AFFINE = {
    ("hba1c", "16166"): (0.09148, 2.152),  # mmol/mol (IFCC) -> % (NGSP)
}

# Some raw itemids mix fraction-scale (0-1) and percent-scale (0-100) rows for the SAME
# analyte under the SAME itemid -- a flat per-itemid UNIT_FACTOR entry is wrong either way
# (x100 on every row inflates the already-% minority; leaving it alone keeps the fraction-scale
# majority wrong). Found 2026-07-13 for hct: all 3 kept itemids (11545, 11423, 6777) show
# ~93-99.99% of rows in [0,1.2] (fraction-scale) and a small remainder already >1.2 up to ~47
# (percent-scale) -- confirmed via a direct raw-value check (grid/_check_hct_scale.py), not
# assumed from the 'Geen' unit label (which is NOT a reliable already-% signal here, unlike
# fio2/svo2). Rule: value <= threshold -> multiply by 100 (it's a fraction); value > threshold
# -> leave as-is (it's already %). Threshold sits in the clean gap between the two clusters
# (fraction rows top out ~1.0 by physical definition; percent rows start ~20 in practice).
CONDITIONAL_PERCENT_ITEMIDS = {("hct", "11545"), ("hct", "11423"), ("hct", "6777")}
CONDITIONAL_PERCENT_THRESHOLD = 1.5

# listitems rows where the categorical valueid stands in for a fixed numeric constant
# (keys are (tag, itemid, valueid))
CATEGORICAL_CONSTANT = {
    ("peep", "15142", "1"): 7.5,
    ("peep", "15142", "2"): 10.0,
}

# kept matches that are dimensionally incompatible with the feature's target unit and are
# therefore EXCLUDED from pooling here (flagged, not silently averaged in) -- (tag, itemid)
EXCLUDE_FROM_POOLING = {
    ("neut", "14254"),  # 10^9/l absolute count, target unit is % (relative fraction)
}

# raw sentinel/error-code values that must be dropped (treated as missing) before any unit
# conversion or aggregation -- same "missing, not clipped" convention as the plausibility
# filter, just applied earlier (pre-conversion) since these are device codes, not out-of-range
# physiology. Found 2026-07-14 (grid/_check_open_flags.py): mpap/spap/dpap raw readings never
# go below -1 (no -2, -3, ... -- a hard floor, not a smooth tail), a strong signal that -1 is
# AmsterdamUMCdb's disconnection/zeroing code for these itemids (6644/6645/6646), not real
# pulmonary artery pressure. Only ~0.044% of raw rows, but forward-fill persistence after the
# PA catheter is removed (typically within a few days) inflated this to ~15% of grid-hours
# pre-fix -- a rare raw sentinel, amplified by imputation. icp's own ~0.6% share of exact -1.0
# readings was checked too and deliberately NOT added here: unlike mpap/spap/dpap, icp shows a
# real continuum of small negative values (-1, -2, -3 all genuinely occur), consistent with
# real post-craniectomy readings -- no clean way to separate a sentinel from real data there.
SENTINEL_VALUES = {
    ("mpap", "6645"): {-1.0},
    ("spap", "6644"): {-1.0},
    ("dpap", "6646"): {-1.0},
}
