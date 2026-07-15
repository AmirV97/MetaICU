#!/usr/bin/env python3
"""
v2 outlier-detection method comparison: for every continuous feature, a 3x4 grid --
rows = {IQR, MAD/robust-z, percentile}, columns = {raw, log-transformed} x {linear y, log y}.
Each subplot shows the value histogram, vertical threshold lines at that method's lower/upper
cutoff, and the row count (+ %) that method would exclude at that scale. Purpose: compare how
much each method excludes, and whether log-transforming first changes that, before committing
to any single outlier-handling strategy. Train split only (same convention as
analyze_features_v1.py).

Log transform: log1p for non-negative features (handles exact zeros natively, unlike plain
log). For the small set of features with a legitimately negative plausible range (icp, cvp,
mpap, dpap, spap, pcwp, be), sign(x)*log1p(|x|) (signed log1p) instead -- a real data
transform, well-defined for all values, compresses both tails symmetrically around zero.

Reads from a user-supplied unscaled grid dataset. Point it at a pre-scaling snapshot when
comparing raw-unit outlier policies; plotting already transformed values as raw units would be
misleading. By default, outputs go to ``{dataset_dir}/plots_v2/outlier_methods``.

Title color: blue if the feature is in grid.scale.LOG_TRANSFORM_TAGS (the finalized log-
transform decision), black otherwise -- so the log/no-log call is visible at a glance across
all 82 plots without cross-referencing decisions.md.

Output: {output_dir}/<feature>.png
"""
import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from metaicu.aumcdb.grid.scale import LOG_TRANSFORM_TAGS

CONTINUOUS_TYPES = {"direct_numeric", "derived_output_rate", "treatment_rate"}
LOG_FLAGGED_TITLE_COLOR = "tab:blue"

IQR_K = 3.0
MAD_THRESH = 3.5
PERCENTILE_P = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def load_train_df(dataset_dir: Path) -> pl.DataFrame:
    train_files = sorted((dataset_dir / "train").glob("*.parquet"))
    return pl.concat([pl.read_parquet(f) for f in train_files])


def iqr_bounds(x, k=IQR_K):
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


def mad_bounds(x, thresh=MAD_THRESH):
    """Modified z-score (Iglewicz-Hoaglin): 0.6745*(x-median)/MAD. Returns (nan, nan) when
    MAD=0 (common for zero-inflated treatment_rate features where >50% of values are
    identical) -- the method is degenerate there, not silently wrong."""
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    if mad == 0:
        return np.nan, np.nan
    delta = thresh * mad / 0.6745
    return med - delta, med + delta


def percentile_bounds(x, p=PERCENTILE_P):
    return tuple(np.percentile(x, [p, 100 - p]))


def log_transform(values):
    """Returns (transformed_values, is_signed). log1p for non-negative features; signed
    log1p (sign(x)*log1p(|x|)) for features with real negative values."""
    if (values >= 0).all():
        return np.log1p(values), False
    return np.sign(values) * np.log1p(np.abs(values)), True


def compute_all_bounds(values):
    return {
        f"IQR (k={IQR_K:g})": iqr_bounds(values),
        f"MAD (z={MAD_THRESH:g})": mad_bounds(values),
        f"Percentile ({PERCENTILE_P:g}/{100 - PERCENTILE_P:g})": percentile_bounds(values),
    }


def plot_outlier_methods(values, feature, unit, out_path, log_flagged):
    """4 columns per method row: {raw, log-transformed-x} x {linear y, log y} -- the y-axis
    log columns are the same data/bounds as the first two, just with counts on a log scale
    (reveals small excluded tails that a linear y-axis compresses into invisibility)."""
    log_values, is_signed = log_transform(values)
    log_label = "signed-log1p" if is_signed else "log1p"
    raw_bounds = compute_all_bounds(values)
    log_bounds = compute_all_bounds(log_values)
    n_total = len(values)

    fig, axes = plt.subplots(3, 4, figsize=(20, 11))
    for i, method in enumerate(raw_bounds):
        panels = [
            (values, raw_bounds[method], "raw", "steelblue", "linear"),
            (log_values, log_bounds[method], log_label, "darkorange", "linear"),
            (values, raw_bounds[method], "raw", "steelblue", "log"),
            (log_values, log_bounds[method], log_label, "darkorange", "log"),
        ]
        for col, (data, bounds, scale_label, color, yscale) in enumerate(panels):
            ax = axes[i, col]
            ax.hist(data, bins=80, color=color)
            ax.set_yscale(yscale)
            lo, hi = bounds
            if np.isnan(lo):
                excluded_str = "N/A (MAD=0, degenerate)"
            else:
                n_excl = int(((data < lo) | (data > hi)).sum())
                excluded_str = f"{n_excl} ({100 * n_excl / n_total:.2f}%)"
                for v in (lo, hi):
                    ax.axvline(v, color="red", ls="--", lw=1)
            y_tag = "log-y" if yscale == "log" else "lin-y"
            ax.set_title(f"{method} ({scale_label}, {y_tag}) -- excl. {excluded_str}", fontsize=7.5)
            ax.tick_params(labelsize=6.5)

    title_color = LOG_FLAGGED_TITLE_COLOR if log_flagged else "black"
    fig.suptitle(f"{feature} ({unit}) -- outlier-detection method comparison", fontsize=13, color=title_color)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main():
    args = parse_args()
    dataset_dir = args.dataset_dir
    out_dir = args.output_dir or dataset_dir / "plots_v2" / "outlier_methods"
    schema = json.loads((dataset_dir / "feature_schema.json").read_text())
    df = load_train_df(dataset_dir)
    print(f"train: {df.height} rows, {df['admissionid'].n_unique()} admissions")

    out_dir.mkdir(parents=True, exist_ok=True)

    n_log_flagged = 0
    for feature, info in schema.items():
        rtype = info["reconstruction_type"]
        if rtype not in CONTINUOUS_TYPES:
            continue
        unit = info["target_unit"]
        values = df[feature].drop_nulls().to_numpy()
        if len(values) == 0:
            print(f"  {feature}: no non-null values, skipping")
            continue
        log_flagged = feature in LOG_TRANSFORM_TAGS
        n_log_flagged += log_flagged
        plot_outlier_methods(values, feature, unit, out_dir / f"{feature}.png", log_flagged)
        print(f"  {feature} ({rtype}): n={len(values)}{' [log-flagged]' if log_flagged else ''}")

    print(f"done. {n_log_flagged} features title-colored blue (log-flagged).")


if __name__ == "__main__":
    main()
