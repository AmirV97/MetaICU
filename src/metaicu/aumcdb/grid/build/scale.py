"""
A.4.2 scaling (icarefm_preprocessing_reference.md), applied to the sparse wide grid from
grid.assemble -- must run BEFORE grid.impute, since impute's "fill remaining nulls with 0" step
for observations (A.4.3) is only valid once 0 has a defined meaning in scaled space (population
mean, per the paper's own justification). Fit parameters (log decision + mean/std for
observations; quantile-transform boundaries for treatments) are always fit on the TRAIN split's
non-null raw values only, then applied unchanged to every split -- avoids val/test leaking into
the scaling parameters.

Per A.4.2:
  - Continuous observations (direct_numeric, derived_output_rate): log1p/signed-log1p first if
    the tag is in LOG_TRANSFORM_TAGS (the 2026-07-14 consensus decisions in
    audits/grid_dataset_v1/plots_v2/outlier_methods/decisions.md), then standardized
    ((x - mean) / std, computed post-log on the train split's non-null values).
  - Continuous treatments (treatment_rate): quantile-transformed to [0, 1] via sklearn's
    QuantileTransformer, fit on the train split's non-null, STRICTLY POSITIVE raw values only.
    Zero (real or later-imputed "no medication") is hard-mapped to exactly 0, bypassing the
    fitted transform -- a transform fit on the full zero-inflated distribution would NOT map 0
    to 0 (70-99.9% of the training mass sits at 0 for these features), so the paper's explicit
    "0 = no medication" rule has to be enforced directly, not learned.
  - Treatment indicators: already binary {0,1} from grid.extract_indicator -- untouched here.
  - Categorical / admission_context: one-hot encoding (with a dedicated missing class) is a
    separate follow-up, NOT implemented in this module yet.

The iCareFM supplement requires removal of physiologically implausible values before hourly
aggregation, but does not prescribe an IQR/MAD/percentile rule. This implementation currently
uses the explicit broad clinical bounds in ``plausibility_bounds`` upstream of extraction.
The separate IQR/MAD/percentile comparison remains diagnostic context; it is not applied here.
"""
import logging
import pickle

import numpy as np
import polars as pl
from sklearn.preprocessing import QuantileTransformer

log = logging.getLogger(__name__)

MIN_TRAIN_VALUES = 10  # below this, log a warning and leave the tag unscaled rather than fit noise

# per-tag log-transform decision, transcribed from decisions.md's 2026-07-14 consensus table.
# "log1p" for non-negative features; "signed_log1p" for features with a real negative range.
# Absent tag = no log transform (standardize the raw value directly).
LOG_TRANSFORM_TAGS = {
    "po2": "log1p", "pco2": "log1p", "lact": "log1p",
    "crea": "log1p", "bun": "log1p", "glu": "log1p", "mg": "log1p", "phos": "log1p",
    "urine_rate": "log1p",
    "plt": "log1p", "wbc": "log1p", "ptt": "log1p", "inr_pt": "log1p",
    "alp": "log1p", "alt": "log1p", "ast": "log1p", "bili": "log1p", "ck": "log1p",
    "ckmb": "log1p", "tnt": "log1p", "tri": "log1p", "amyl": "log1p", "lip": "log1p",
    "ygt": "log1p", "amm": "log1p",
    "crp": "log1p", "hbco": "log1p", "methb": "log1p", "bnd": "log1p", "lymph": "log1p",
    "eos": "log1p",
    "icp": "signed_log1p",
    "cout": "log1p",
    "peep": "log1p",
    # derived TTE targets (grid.build.derive_targets) -- non-negative ratios, same physiologically
    # skewed shape as their raw constituents po2/urine_rate above.
    "pf_ratio": "log1p", "urine_rate_per_weight": "log1p",
}


def _apply_log(values, kind):
    if kind == "log1p":
        return np.log1p(values)
    if kind == "signed_log1p":
        return np.sign(values) * np.log1p(np.abs(values))
    return values


def _fit_observation_scaler(train_values, tag):
    """train_values: 1D numpy array, non-null raw values from the TRAIN split only. Returns
    (log_kind, mean, std); std is floored at 1.0 for a degenerate (constant) training column to
    avoid divide-by-zero -- the standardized value is then 0 everywhere, which is correct for a
    feature with no observed variance in training."""
    log_kind = LOG_TRANSFORM_TAGS.get(tag)
    transformed = _apply_log(train_values, log_kind)
    mean = float(np.mean(transformed))
    std = float(np.std(transformed))
    if std == 0.0:
        log.warning(f"{tag}: zero training-split variance (post-log) -- std floored at 1.0")
        std = 1.0
    return log_kind, mean, std


def _apply_observation_scaler(col, log_kind, mean, std):
    """col.to_numpy() silently turns polars nulls into NaN (no null bitmap in a plain numpy
    array) -- fill_nan(None) at the end converts them back to real polars nulls, otherwise
    they'd leak through as NaN and be indistinguishable from a real (if degenerate) value."""
    values = col.to_numpy()
    mask = ~np.isnan(values)
    out = values.astype(np.float64, copy=True)
    out[mask] = (_apply_log(values[mask], log_kind) - mean) / std
    return pl.Series(col.name, out).fill_nan(None)


def _fit_treatment_scaler(train_values, tag):
    """train_values: 1D numpy array, non-null raw values from the TRAIN split only. Returns a
    QuantileTransformer fit on the strictly-positive subset, or None if there are too few
    positive training values to fit meaningfully (tag left as raw 0/1 pass-through)."""
    positive = train_values[train_values > 0]
    if len(positive) < MIN_TRAIN_VALUES:
        log.warning(f"{tag}: fewer than {MIN_TRAIN_VALUES} positive training values "
                    f"({len(positive)}) -- quantile transform not fit, values left as raw")
        return None
    # random_state fixed (not sklearn's default None): QuantileTransformer subsamples up to
    # `subsample` points (default 10000) when fitting on more data than that, so leaving the
    # seed unset makes two fits on the IDENTICAL data disagree -- confirmed 2026-07-14 (hep has
    # 324k+ nonzero training rows, well above the subsample threshold). Fixing the seed makes
    # the fit reproducible across pipeline re-runs; it does not affect train/test leakage
    # (train_values passed in here is already train-only, see scale_grid).
    qt = QuantileTransformer(output_distribution="uniform",
                              n_quantiles=min(1000, len(positive)), random_state=42)
    qt.fit(positive.reshape(-1, 1))
    return qt


def _apply_treatment_scaler(col, qt):
    """See _apply_observation_scaler's docstring re: the NaN/null round-trip through numpy."""
    values = col.to_numpy()
    mask = ~np.isnan(values)
    out = values.astype(np.float64, copy=True)
    if qt is not None:
        pos_mask = mask & (values > 0)
        if pos_mask.any():
            out[pos_mask] = qt.transform(values[pos_mask].reshape(-1, 1)).flatten()
    out[mask & (values <= 0)] = 0.0  # explicit 0 = no medication, exact per iCareFM A.4.2
    return pl.Series(col.name, out).fill_nan(None)


def scale_grid(grid, matches, train_admission_ids):
    """grid: wide DataFrame from grid.assemble_grid (pre-imputation -- still has true nulls
    where a hour was never observed). matches: tag -> feature info dict from
    grid.build.manifest_parser.parse_manifest(). train_admission_ids: iterable of admissionids in the train
    split -- scaling parameters are fit on these rows' non-null values only.

    Returns (grid, scalers): grid with every direct_numeric/derived_output_rate/treatment_rate
    column transformed in place (nulls left as null, for grid.impute to resolve next); scalers
    is {tag: {"type": ..., ...fit params...}} -- observation entries are plain
    JSON-serializable dicts, treatment entries additionally hold the fitted QuantileTransformer
    object under "transformer" (not JSON-serializable -- see save_scalers)."""
    train_ids = set(train_admission_ids)
    train_mask = pl.col("admissionid").is_in(list(train_ids))
    scalers = {}

    for tag, info in matches.items():
        if tag not in grid.columns:
            continue
        rt = info["reconstruction_type"]
        if rt not in ("direct_numeric", "derived_output_rate", "treatment_rate"):
            continue

        col = grid[tag]
        train_values = grid.filter(train_mask)[tag].drop_nulls().to_numpy()

        if rt in ("direct_numeric", "derived_output_rate"):
            if len(train_values) < MIN_TRAIN_VALUES:
                log.warning(f"{tag}: fewer than {MIN_TRAIN_VALUES} non-null training values "
                            f"({len(train_values)}) -- not scaled")
                continue
            log_kind, mean, std = _fit_observation_scaler(train_values, tag)
            grid = grid.with_columns(_apply_observation_scaler(col, log_kind, mean, std))
            scalers[tag] = {"type": "observation", "log": log_kind, "mean": mean, "std": std}
            log.info(f"{tag}: observation scaler (log={log_kind}, mean={mean:.4g}, std={std:.4g})")

        elif rt == "treatment_rate":
            qt = _fit_treatment_scaler(train_values, tag)
            grid = grid.with_columns(_apply_treatment_scaler(col, qt))
            scalers[tag] = {"type": "treatment", "transformer": qt}
            log.info(f"{tag}: treatment quantile-transform ({'fit' if qt is not None else 'NOT fit -- too few positive values'})")

    return grid, scalers


STATIC_NUMERIC_TAGS = ["age", "weight", "height"]


def scale_static_features(admissions, train_admission_ids):
    """admissions: DataFrame already carrying age/weight/height (from
    grid.extract_static.extract_static_features, joined onto the main admissions frame).
    train_admission_ids: iterable of admissionids in the train split.

    Adds f"{tag}_scaled" columns (nulls preserved -- these are the same real, un-imputed nulls
    extract_static_features leaves behind, see its docstring) alongside the existing raw
    age/weight/height columns rather than replacing them, so metadata.csv stays usable for raw
    filtering/interpretability (e.g. "age > 65") while also carrying the standardized version a
    model would consume. No log transform -- age/weight/height are bin-median reconstructions
    (already coarse/capped, e.g. weight's "110+" bin), not raw continuous measurements, and
    aren't skewed enough to warrant it (unlike the observation features in decisions.md).

    Returns (admissions, scalers) -- scalers entries are shaped like scale_grid's observation
    entries (`{"type": "static", "log": None, "mean": ..., "std": ...}`), for a single combined
    scalers.pkl covering the whole pipeline."""
    train_ids = set(train_admission_ids)
    train_mask = pl.col("admissionid").is_in(list(train_ids))
    scalers = {}

    for tag in STATIC_NUMERIC_TAGS:
        if tag not in admissions.columns:
            continue
        train_values = admissions.filter(train_mask)[tag].drop_nulls().to_numpy()
        if len(train_values) < MIN_TRAIN_VALUES:
            log.warning(f"{tag} (static): fewer than {MIN_TRAIN_VALUES} non-null training "
                        f"values ({len(train_values)}) -- not scaled")
            continue
        mean = float(np.mean(train_values))
        std = float(np.std(train_values))
        if std == 0.0:
            log.warning(f"{tag} (static): zero training-split variance -- std floored at 1.0")
            std = 1.0
        scaled_col = _apply_observation_scaler(admissions[tag], None, mean, std).rename(f"{tag}_scaled")
        admissions = admissions.with_columns(scaled_col)
        scalers[tag] = {"type": "static", "log": None, "mean": mean, "std": std}
        log.info(f"{tag} (static): mean={mean:.4g}, std={std:.4g}")

    return admissions, scalers


def save_scalers(scalers, output_path):
    """Pickles the full scalers dict (including the non-JSON-serializable QuantileTransformer
    objects) to output_path, plus writes a human-readable JSON summary alongside it (transformer
    objects replaced with a boolean "fitted" flag) for quick inspection without unpickling."""
    with open(output_path, "wb") as f:
        pickle.dump(scalers, f)

    import json
    summary = {}
    for tag, s in scalers.items():
        if s["type"] in ("observation", "static"):
            summary[tag] = {"type": s["type"], "log": s["log"], "mean": s["mean"], "std": s["std"]}
        else:
            summary[tag] = {"type": "treatment", "fitted": s["transformer"] is not None}
    json_path = output_path.with_suffix(".summary.json")
    json.dump(summary, open(json_path, "w"), indent=2)
    log.info(f"Wrote {output_path} and {json_path}")
