#!/usr/bin/env python3
"""
v1 grid dataset feature diagnostics: per-feature missingness, rows-present-per-admission
distribution, and value histograms (raw + log1p) for continuous features. Train split only
(avoid val/test leakage into any outlier/transform decision this informs). Reads directly
from grid_dataset_v1/train/*.parquet -- dataset is small (53MB), safe on the login node.

Outputs (all under {dataset_dir}/plots/):
  summary_stats.csv              -- one row per feature: missingness, rows-present stats,
                                     and (for continuous features) value distribution stats
  missingness_by_feature.png     -- all 115 features, sorted, colored by reconstruction_type
  rows_per_admission/*.png       -- one grid figure per reconstruction_type
  value_histograms/<feature>.png -- one figure per continuous feature (raw + log1p panels)
  value_histograms_overview.png  -- small-multiples quick-scan of all continuous features
"""
import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
from scipy import stats

CONTINUOUS_TYPES = {"direct_numeric", "derived_output_rate", "treatment_rate"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def load_train_df(dataset_dir: Path) -> pl.DataFrame:
    train_files = sorted((dataset_dir / "train").glob("*.parquet"))
    return pl.concat([pl.read_parquet(f) for f in train_files])


def rows_present_per_admission(df, feature):
    """One count per admission: how many hours have a non-null value for this feature."""
    return (
        df.group_by("admissionid")
        .agg(pl.col(feature).is_not_null().sum().alias("n_present"))["n_present"]
        .to_numpy()
    )


def plot_missingness(summary, out_path):
    summary_sorted = summary.sort("missing_frac", descending=True)
    types = summary_sorted["reconstruction_type"].to_list()
    type_colors = {t: c for t, c in zip(sorted(set(types)), plt.cm.tab10.colors)}
    colors = [type_colors[t] for t in types]

    fig, ax = plt.subplots(figsize=(9, max(6, 0.16 * summary_sorted.height)))
    ax.barh(summary_sorted["feature"].to_list()[::-1], summary_sorted["missing_frac"].to_list()[::-1],
            color=colors[::-1])
    ax.set_xlabel("Fraction of (admission, hour) rows missing")
    ax.set_title("Missingness by feature (train split)")
    ax.tick_params(axis="y", labelsize=6)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in type_colors.values()]
    ax.legend(handles, type_colors.keys(), loc="lower right", fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_rows_per_admission_grid(df, features_of_type, rtype, out_path):
    n = len(features_of_type)
    ncols = min(6, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3 * ncols, 2.5 * nrows), squeeze=False)
    for i, feature in enumerate(features_of_type):
        ax = axes[i // ncols][i % ncols]
        counts = rows_present_per_admission(df, feature)
        ax.hist(counts, bins=30, color="steelblue")
        ax.set_title(feature, fontsize=8)
        ax.tick_params(labelsize=6)
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")
    fig.suptitle(f"Rows present per admission -- {rtype}", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def value_stats(values):
    return {
        "min": float(np.min(values)), "p1": float(np.percentile(values, 1)),
        "p5": float(np.percentile(values, 5)), "median": float(np.median(values)),
        "mean": float(np.mean(values)), "std": float(np.std(values)),
        "p95": float(np.percentile(values, 95)), "p99": float(np.percentile(values, 99)),
        "max": float(np.max(values)), "skew": float(stats.skew(values)),
    }


def symlog_bin_edges(values, linthresh, n=80):
    """Bin edges matching the symlog axis's own warping (log-spaced beyond +-linthresh, linear
    in between) -- plain linear bins across the full raw range would be dominated by a handful
    of extreme sentinel values (e.g. resp's -28691) and crush the real data near 0 into one bar."""
    lo, hi = float(values.min()), float(values.max())
    parts = [np.linspace(-linthresh, linthresh, max(n // 4, 5))]
    if lo < -linthresh:
        neg = np.logspace(np.log10(linthresh), np.log10(-lo), max(n // 3, 5))
        parts.insert(0, -neg[::-1])
    if hi > linthresh:
        pos = np.logspace(np.log10(linthresh), np.log10(hi), max(n // 3, 5))
        parts.append(pos)
    return np.unique(np.concatenate(parts))


def plot_value_histogram(values, feature, unit, out_path):
    """Left panel: raw values, linear x, log y. Right panel: log-scale x for non-negative
    features (excl. exact zeros, which log can't represent); symlog x (handles negatives and
    zero natively, linear near 0 beyond +-linthresh) for features with negative values. Both
    panels use log y throughout -- empty bins just don't render, standard for count histograms."""
    non_negative = np.min(values) >= 0
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].hist(values, bins=80, color="steelblue")
    axes[0].set_yscale("log")
    axes[0].set_title(f"{feature} ({unit}) -- raw, skew={stats.skew(values):.1f}")

    if non_negative:
        positive = values[values > 0]
        zero_frac = 1 - positive.size / values.size
        if positive.size > 0:
            bins = np.logspace(np.log10(positive.min()), np.log10(positive.max()), 80)
            axes[1].hist(positive, bins=bins, color="darkorange")
            axes[1].set_xscale("log")
        axes[1].set_title(f"log-scale x-axis (excl. {zero_frac:.0%} exact zeros)")
    else:
        nonzero_abs = np.abs(values[values != 0])
        linthresh = float(np.percentile(nonzero_abs, 1)) if nonzero_abs.size > 0 else 1.0
        axes[1].hist(values, bins=symlog_bin_edges(values, linthresh), color="darkorange")
        axes[1].set_xscale("symlog", linthresh=linthresh)
        axes[1].set_title(f"symlog x-axis (linthresh={linthresh:.3g}, handles negatives/zero)")
    axes[1].set_yscale("log")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_value_overview(df, features, schema, out_path):
    n = len(features)
    ncols = 8
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(2.6 * ncols, 2.2 * nrows), squeeze=False)
    for i, feature in enumerate(features):
        ax = axes[i // ncols][i % ncols]
        values = df[feature].drop_nulls().to_numpy()
        ax.hist(values, bins=40, color="steelblue")
        ax.set_title(feature, fontsize=7)
        ax.tick_params(labelsize=5)
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")
    fig.suptitle("Value histograms overview -- all continuous features (raw scale)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main():
    args = parse_args()
    dataset_dir = args.dataset_dir
    plots_dir = args.output_dir or dataset_dir / "plots"
    schema = json.loads((dataset_dir / "feature_schema.json").read_text())
    df = load_train_df(dataset_dir)
    print(f"train: {df.height} rows, {df['admissionid'].n_unique()} admissions")

    (plots_dir / "rows_per_admission").mkdir(parents=True, exist_ok=True)
    (plots_dir / "value_histograms").mkdir(parents=True, exist_ok=True)

    rows = []
    for feature, info in schema.items():
        rtype = info["reconstruction_type"]
        if rtype == "admission_context":
            continue  # per-admission static feature (metadata.csv), not a per-hour grid column
        unit = info["target_unit"]
        missing_frac = df[feature].is_null().mean()
        present_counts = rows_present_per_admission(df, feature)
        row = {
            "feature": feature, "reconstruction_type": rtype, "target_unit": unit,
            "missing_frac": missing_frac,
            "rows_present_median": float(np.median(present_counts)),
            "rows_present_mean": float(np.mean(present_counts)),
        }
        if rtype in CONTINUOUS_TYPES:
            values = df[feature].drop_nulls().to_numpy()
            row.update(value_stats(values))
            plot_value_histogram(values, feature, unit, plots_dir / "value_histograms" / f"{feature}.png")
        rows.append(row)
        print(f"  {feature} ({rtype}): missing={missing_frac:.2%}")

    summary = pl.DataFrame(rows)
    summary.write_csv(plots_dir / "summary_stats.csv")
    print(f"wrote summary_stats.csv ({summary.height} features)")

    plot_missingness(summary, plots_dir / "missingness_by_feature.png")

    schema_types = sorted({v["reconstruction_type"] for v in schema.values()} - {"admission_context"})
    for rtype in schema_types:
        features_of_type = [f for f, v in schema.items() if v["reconstruction_type"] == rtype]
        plot_rows_per_admission_grid(df, features_of_type, rtype, plots_dir / "rows_per_admission" / f"{rtype}.png")

    continuous_features = [f for f, v in schema.items() if v["reconstruction_type"] in CONTINUOUS_TYPES]
    plot_value_overview(df, continuous_features, schema, plots_dir / "value_histograms_overview.png")

    print("done.")


if __name__ == "__main__":
    main()
