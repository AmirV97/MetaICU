#!/usr/bin/env python3
"""
Categorical / treatment_indicator feature distribution plots: one bar chart per feature showing
label/state counts on a log-scale y-axis -- many categories and most treatment indicators are
heavily skewed toward one dominant state (e.g. "not intubated" / indicator=0), so a linear
y-axis would hide every minority category entirely. Uses the fully-processed train split
(post-impute), same convention as analyze_features_v1.py/v2.py -- categorical counts therefore
reflect the forward-filled state distribution actually seen by a downstream model, not raw
observation instances alone; treatment_indicator counts are the zero-filled any-per-hour flag.

Output: {dataset_dir}/plots_v2/categorical_indicator/<feature>.png
"""
import argparse
import json
from pathlib import Path

import polars as pl
import matplotlib.pyplot as plt

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def load_train_df(dataset_dir: Path) -> pl.DataFrame:
    train_files = sorted((dataset_dir / "train").glob("*.parquet"))
    return pl.concat([pl.read_parquet(f) for f in train_files])


def plot_categorical(df, feature, out_path):
    col = df[feature]
    n_total = len(col)
    n_null = col.null_count()
    counts = col.drop_nulls().value_counts().sort("count", descending=True)
    labels = [str(v) for v in counts[feature].to_list()]
    values = counts["count"].to_list()
    if n_null:
        labels.append("(missing)")
        values.append(n_null)

    fig, ax = plt.subplots(figsize=(max(6, 0.6 * len(labels)), 5))
    ax.bar(labels, values, color="steelblue")
    ax.set_yscale("log")
    ax.set_ylabel("count (log scale)")
    for tick in ax.get_xticklabels():
        tick.set_rotation(45)
        tick.set_ha("right")
    ax.set_title(f"{feature} (categorical) -- n={n_total}, {len(labels)} states shown")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_indicator(df, feature, out_path):
    col = df[feature]
    n_total = len(col)
    n_null = col.null_count()
    counts = col.drop_nulls().value_counts().sort(feature)
    labels = [str(int(v)) for v in counts[feature].to_list()]
    values = counts["count"].to_list()
    if n_null:
        labels.append("(missing)")
        values.append(n_null)

    n_on = int((col == 1).sum())
    pct_on = 100 * n_on / n_total if n_total else 0.0
    colors = ["darkorange" if l == "1" else "lightgray" if l == "0" else "gray" for l in labels]

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(labels, values, color=colors)
    ax.set_yscale("log")
    ax.set_ylabel("count (log scale)")
    ax.set_title(f"{feature} (treatment_indicator) -- n={n_total}, on={pct_on:.2f}%", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main():
    args = parse_args()
    dataset_dir = args.dataset_dir
    out_dir = args.output_dir or dataset_dir / "plots_v2" / "categorical_indicator"
    schema = json.loads((dataset_dir / "feature_schema.json").read_text())
    df = load_train_df(dataset_dir)
    print(f"train: {df.height} rows, {df['admissionid'].n_unique()} admissions")

    out_dir.mkdir(parents=True, exist_ok=True)

    n_cat, n_ind = 0, 0
    for feature, info in schema.items():
        rtype = info["reconstruction_type"]
        if feature not in df.columns:
            continue
        if rtype == "categorical":
            plot_categorical(df, feature, out_dir / f"{feature}.png")
            n_cat += 1
            print(f"  {feature} (categorical): plotted")
        elif rtype == "treatment_indicator":
            plot_indicator(df, feature, out_dir / f"{feature}.png")
            n_ind += 1
            print(f"  {feature} (treatment_indicator): plotted")

    print(f"done. {n_cat} categorical, {n_ind} treatment_indicator features plotted.")


if __name__ == "__main__":
    main()
