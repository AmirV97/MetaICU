"""Cross-cohort pooled statistics for a joint multi-dataset grid build.

Standalone, dataset-agnostic functions -- a future joint dispatcher (grid_build_joint_dataset)
calls these once it has each cohort's own PreScaleGrid (metaicu.grid.pre_scale) in hand, then feeds
the results into scale_grid/scale_static_features's `external_scalers` param
(metaicu.{aumcdb,mimiciv}.grid.build.scale) so pooled statistics are applied instead of each
cohort fitting its own train split independently. Not wired into either build_workflow.py yet.

compute_cohort_weights returns each cohort's total MASS for pooling, not the training repo's
PER-ADMISSION loss weight. iCareFM_replicate/HANDOFF.md ("Cohort weighting -- the sqrt(n) rule")
gives each admission a per-admission weight w_c = 1/sqrt(n_cohort); a cohort's total mass is then
n_cohort * w_c = n_cohort / sqrt(n_cohort) = sqrt(n_cohort) -- e.g. AUMC 22,774 / MIMIC 87,513 is a
33.8%/66.2% split (HANDOFF.md's own worked example), NOT the ~66%/34% you'd get by normalizing
1/sqrt(n) directly, which was this function's bug before 2026-08-06 -- it returned the
per-admission weight where every caller (pooled_mean_std, pooled_fit_treatment) actually needed
the cohort-level mass to combine two cohorts' statistics correctly (larger cohort's own fit is
more reliable and should dominate the pooled fit, not be diluted by it).

pooled_mean_std uses the proper two-term pooled-variance formula (weighted average of the
per-cohort variances PLUS the weighted average of each cohort's squared deviation from the pooled
mean), not a naive average of the two SDs, which understates true pooled variance whenever the
cohorts' means differ.

pooled_fit_treatment can't use sample_weight -- sklearn's QuantileTransformer.fit() has none
(confirmed directly against its signature) -- so it instead builds a pooled sample via exact,
deterministic per-cohort replication (np.tile, not random resampling) chosen to approximate each
cohort's target weight. Replication (rather than a random weighted draw) means concatenating two
cohorts with identical distributions and equal weights reproduces fitting on either cohort alone
exactly -- no resampling noise -- matching the reproducibility convention the per-cohort fits in
scale.py already follow via a fixed random_state.
"""

from __future__ import annotations

import logging
import math

import numpy as np
from sklearn.preprocessing import QuantileTransformer

log = logging.getLogger(__name__)

MIN_TRAIN_VALUES = 10  # mirrors each pipeline's own scale.py::MIN_TRAIN_VALUES, applied here to
                        # the POOLED total rather than any single cohort's count -- a tag real in
                        # only one cohort must still get a valid pooled fit from that cohort alone.


def compute_cohort_weights(n_train_admissions_by_cohort):
    """n_train_admissions_by_cohort: {cohort: n_train_admissions}. Returns {cohort: weight},
    weight = sqrt(n) normalized to sum to 1 -- a cohort's total MASS (see module docstring), so
    the larger cohort's own fit dominates the pooled result, proportionally to sqrt(n)."""
    sqrt_n = {cohort: math.sqrt(n) for cohort, n in n_train_admissions_by_cohort.items()}
    total = sum(sqrt_n.values())
    return {cohort: s / total for cohort, s in sqrt_n.items()}


def pooled_mean_std(per_cohort, weights):
    """per_cohort: {cohort: {"mean": float, "std": float, "n": int}} for cohorts that actually
    have a real (non-structural-zero) fit for this tag. weights: cohort -> weight, e.g. the full
    run-wide dict from compute_cohort_weights -- may contain cohorts outside per_cohort (a cohort
    with no real data for this specific tag); renormalized here over just per_cohort's own keys,
    so a tag real in only one cohort reproduces that cohort's own mean/std exactly rather than a
    fit diluted by a weight computed for the full cohort set.

    Returns (pooled_mean, pooled_std) via the two-term pooled-variance formula."""
    cohorts = list(per_cohort)
    total_weight = sum(weights[c] for c in cohorts)
    w = {c: weights[c] / total_weight for c in cohorts}
    pooled_mean = sum(w[c] * per_cohort[c]["mean"] for c in cohorts)
    within_var = sum(w[c] * per_cohort[c]["std"] ** 2 for c in cohorts)
    between_var = sum(w[c] * (per_cohort[c]["mean"] - pooled_mean) ** 2 for c in cohorts)
    return pooled_mean, math.sqrt(within_var + between_var)


def _replication_counts(sizes, weights):
    """sizes: {cohort: n}, weights: {cohort: w} (already renormalized to sum to 1 over the same
    keys as sizes). Returns {cohort: k}, a positive integer replication count per cohort chosen
    so that k_c / n_c is proportional to w_c across cohorts, scaled so the smallest ratio gets
    k=1 -- collapses to k=1 for every cohort whenever natural (unweighted) proportions already
    match the target weights (equal per-cohort sizes with equal weights, or a single contributing
    cohort), which is exactly what the pooling invariant tests rely on."""
    per_unit = {c: weights[c] / sizes[c] for c in sizes}
    scale = 1.0 / min(per_unit.values())
    return {c: max(1, round(scale * per_unit[c])) for c in sizes}


def pooled_fit_treatment(train_values_by_cohort, weights, tag, random_seed=42):
    """train_values_by_cohort: {cohort: 1D numpy array of raw, non-null TRAIN-split values for
    this tag}. weights: cohort -> weight (e.g. the full run-wide dict from
    compute_cohort_weights); renormalized here over whichever cohorts actually have strictly-
    positive values for this tag, same rationale as pooled_mean_std. random_seed: passed to
    QuantileTransformer -- see scale.py::_fit_treatment_scaler's own docstring for why this must
    be fixed rather than left at sklearn's default.

    Returns a QuantileTransformer fit on a pooled sample built by replicating each contributing
    cohort's own strictly-positive values (see _replication_counts) and concatenating -- or None
    if the pooled strictly-positive total is below MIN_TRAIN_VALUES (mirrors
    scale.py::_fit_treatment_scaler's per-cohort guard, applied to the pooled total instead)."""
    positive_by_cohort = {c: v[v > 0] for c, v in train_values_by_cohort.items()}
    positive_by_cohort = {c: v for c, v in positive_by_cohort.items() if len(v) > 0}
    total_positive = sum(len(v) for v in positive_by_cohort.values())
    if total_positive < MIN_TRAIN_VALUES:
        log.warning(f"{tag}: fewer than {MIN_TRAIN_VALUES} pooled positive training values "
                    f"({total_positive}) -- pooled quantile transform not fit")
        return None

    cohorts = list(positive_by_cohort)
    total_weight = sum(weights[c] for c in cohorts)
    w = {c: weights[c] / total_weight for c in cohorts}
    sizes = {c: len(positive_by_cohort[c]) for c in cohorts}
    counts = _replication_counts(sizes, w)

    pooled_values = np.concatenate(
        [np.tile(positive_by_cohort[c], counts[c]) for c in cohorts]
    )
    # random_state fixed, matching scale.py::_fit_treatment_scaler's own convention -- the pooled
    # sample is built deterministically above, but QuantileTransformer itself still subsamples
    # internally above its own `subsample` threshold and needs a fixed seed to be reproducible.
    qt = QuantileTransformer(output_distribution="uniform",
                              n_quantiles=min(1000, len(pooled_values)), random_state=random_seed)
    qt.fit(pooled_values.reshape(-1, 1))
    return qt
