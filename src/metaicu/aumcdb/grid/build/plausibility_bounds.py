"""
Generous clinical-plausibility bounds for direct_numeric/derived_output_rate features,
applied to raw values (post-unit-conversion) before hourly aggregation -- per
icarefm_preprocessing_reference.md's A.4.1 step order (harmonization -> outlier removal ->
hourly binning). Values outside a feature's bound are dropped (treated as missing, not
zero-filled, not clipped to the boundary) before that hour's median is computed -- same
handling as any other unmeasured hour.

These are deliberately generous "clinically/physically impossible even in extreme ICU
illness" ceilings/floors, NOT normal-reference-range bounds -- calibrated 2026-07-13 against
(1) the actual train-split value distribution (every bound below was checked for how many
real rows it would drop, and what those dropped values looked like -- a bound that clipped a
smooth, dense, plausible-looking cluster was widened; one that only clipped a small, sharply
separated, physically-impossible tail was kept), and (2) a literature check for the features
flagged as uncertain (cai, ckmb, esr, ygt, ph) -- e.g. esr's 200 mm/hr ceiling is the physical
length of a manual Westergren tube (a hard instrument limit, not a guess); ph's 6.0 floor
leaves margin below the lowest well-documented survived case (pH 6.25); cai's 3.5 ceiling
leaves margin above a documented survived hypercalcemic-crisis ionized-calcium reading of 2.80
mmol/L.

icp's ceiling was revised 300 -> 150 on 2026-07-14: grid/_check_icp_cluster.py found a
~250-300 mmHg plateau confined to itemid 8835 (icp's dominant source), concentrated in 42/1002
admissions and sitting as a tight, sustained flat band within an admission (e.g. one 29-row
admission reading 315-321 throughout) rather than a noisy trend -- the signature of a
transducer zero-drift/calibration fault, not real deterioration. A literature check found the
highest ICP ever recorded in a dedicated brain-death study was 145 mmHg (median at brain death
103.5 mmHg); a live, monitored patient sustaining 250-300 mmHg across many consecutive hourly
readings is not physiologically possible (cerebral perfusion pressure would be catastrophically
negative long before that). 150 leaves a small margin above the 145 mmHg literature max while
dropping the artifact plateau.

Any feature whose target_unit is exactly "%" gets an automatic (0, 100) bound with no entry
needed here -- a percentage outside that range is impossible by definition, not a judgment
call.

`pt` is absent -- not because it's unbounded, but because it no longer resolves as an
in-scope feature at all. Its raw values (median ~1.3) never looked like seconds despite the
raw_unit metadata saying so; a raw-CSV check (grid/_check_pt_vs_inr.py) confirmed it's a
legacy duplicate of the INR channel (inr_pt) with a mislabeled unit, not a real PT-in-seconds
source, so its manifest match was rejected outright (2026-07-13) rather than given a bound.

Out of scope for this module: treatment_rate (has its own dedicated fix, not generic
clipping -- see treatment_rate_formulas.py), treatment_indicator (already binary),
categorical, admission_context.
"""

PERCENT_RANGE = (0.0, 100.0)

# value dropped (treated as missing) if outside [lo, hi]
PLAUSIBLE_RANGE = {
    # hemodynamics / vitals
    "hr": (0.0, 300.0), "sbp": (0.0, 300.0), "dbp": (0.0, 200.0), "map": (0.0, 250.0),
    "cvp": (-10.0, 40.0), "icp": (-40.0, 150.0), "mpap": (-10.0, 150.0), "dpap": (-10.0, 150.0),
    "spap": (-10.0, 150.0), "pcwp": (-10.0, 60.0), "cout": (0.0, 20.0), "resp": (0.0, 100.0),
    "temp": (20.0, 45.0), "etco2": (0.0, 100.0), "pco2": (0.0, 200.0), "po2": (0.0, 700.0),
    "ph": (6.0, 7.8),

    # ventilator mechanics
    # tv revised 3000 -> 1800 on 2026-07-14: full-population check (grid/_check_open_flags.py)
    # found itemid 8851 ("Tidal Volume (Set)") is bimodal -- a real ~0.5 L cluster (correctly
    # converts to ~500mL) and a separate ~2.0 cluster plus a single raw=2000 outlier that the
    # x1000 factor turns into 2000mL / 2,000,000mL, both of which silently passed the old 3000
    # bound. 1800 leaves generous margin above even historical high-volume ventilation (15
    # mL/kg x ~102kg predicted body weight for the largest realistic adult =~1530mL) while
    # dropping this itemid's artifact cluster.
    "tv": (0.0, 1800.0), "peak": (0.0, 80.0), "peep": (0.0, 80.0), "ps": (0.0, 80.0),
    "plateau": (0.0, 80.0), "urine_rate": (0.0, 2000.0),

    # electrolytes / renal
    "na": (90.0, 200.0), "k": (1.0, 15.0), "cl": (50.0, 200.0), "ca": (2.0, 20.0),
    "cai": (0.2, 3.5), "mg": (0.0, 15.0), "phos": (0.0, 20.0), "crea": (0.0, 40.0),
    "bun": (0.0, 300.0),

    # acid-base
    "be": (-40.0, 40.0), "bicar": (0.0, 60.0),

    # hematology
    "hgb": (0.0, 25.0), "wbc": (0.0, 500.0), "plt": (0.0, 3000.0), "rbc": (0.0, 10.0),
    "esr": (0.0, 200.0),

    # coagulation
    "ptt": (0.0, 300.0), "inr_pt": (0.0, 20.0),

    # liver / pancreas
    "alt": (0.0, 100000.0), "ast": (0.0, 100000.0), "alp": (0.0, 5000.0), "ygt": (0.0, 5000.0),
    "bili": (0.0, 80.0), "amyl": (0.0, 20000.0), "lip": (0.0, 20000.0), "alb": (0.0, 10.0),
    "fgn": (0.0, 2000.0),

    # other labs
    "amm": (0.0, 1000.0), "lact": (0.0, 30.0), "crp": (0.0, 1000.0), "glu": (0.0, 2000.0),
    "ckmb": (0.0, 1000.0), "ck": (0.0, 1000000.0), "tnt": (0.0, 150.0), "tri": (0.0, 150.0),
}


def resolve_bounds(matches):
    """matches: tag -> feature info dict from grid.build.manifest_parser.parse_manifest(). Returns
    {tag: (lo, hi)} for every direct_numeric/derived_output_rate feature that has a bound --
    a manual PLAUSIBLE_RANGE entry, or an automatic (0, 100) for any %-unit feature. Tags with
    neither (currently just `pt`) are absent from the result -- left unbounded."""
    bounds = {}
    for tag, info in matches.items():
        if info["reconstruction_type"] not in ("direct_numeric", "derived_output_rate"):
            continue
        if tag in PLAUSIBLE_RANGE:
            bounds[tag] = PLAUSIBLE_RANGE[tag]
        elif (info["target_unit"] or "").strip() == "%":
            bounds[tag] = PERCENT_RANGE
    return bounds
