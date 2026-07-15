#!/usr/bin/env python3
"""
QA visualization for the v1 grid output: one heatmap per patient (features x hours), so the
whole generated multivariate record for a handful of admissions can be eyeballed at once.
Reads an already-extracted dataset dir (run_extraction.py's output: {train,val,test}/*.parquet
+ metadata.csv + feature_schema.json) only, no raw-table access -- safe to run directly, no
sbatch needed.

Design:
- Rows = every feature in the grid, grouped into 4 blocks (direct_numeric+derived_output_rate,
  categorical, treatment_indicator, treatment_rate) with a thin separator line between blocks
  -- individual per-row labels aren't legible at 114 rows, so only blocks are labeled.
- Columns = hour since admission.
- Color = per-feature normalized value: numeric columns clipped to the population's 1st-99th
  percentile (computed across all admissions in the sample, not just the 5 plotted) then
  min-max scaled to [0,1]; categorical (string-valued) columns factorized to integer category
  codes then min-max scaled. Null cells (missing/pre-first-observation, see grid/impute.py's
  docstring) are masked and rendered as light gray, distinct from the viridis colormap.
- Red markers: a vertical line at hour=0 (admission start) and one at the last recorded hour,
  annotated with mortality status (admissions.parquet's dateofdeath field -- note this may
  reflect eventual death, not necessarily death during this specific ICU stay; labeled
  "Death recorded" rather than "Died in ICU" to not overclaim what the field captures).
"""
import argparse
from pathlib import Path

import json
import matplotlib
import numpy as np
import polars as pl

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Patch

BLOCK_ORDER = ["direct_numeric", "derived_output_rate", "categorical", "treatment_indicator", "treatment_rate"]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-dir", type=Path, required=True,
                        help="grid output dir: {train,val,test}/*.parquet + metadata.csv")
    parser.add_argument("--admission-ids", type=int, nargs="+", default=None,
                         help="explicit list of admissionids to plot; default = auto-pick 5")
    parser.add_argument("--n-patients", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None,
                         help="default: {dataset-dir}/plots/patient_grid_heatmaps.png")
    return parser.parse_args()


def pick_admission_ids(metadata, n):
    """Spread picks evenly across the LOS distribution (>=24h floor so the plot isn't
    dominated by near-empty short stays) -- sorting by LOS descending and taking the first n
    (the previous approach) always grabs the longest stays clustered near the top of any
    filter window, not a representative spread; evenly-spaced rank positions fix that."""
    sub = metadata.filter(pl.col("los_hours") >= 24).sort("los_hours")
    if sub.height <= n:
        return sub["admissionid"].to_list()
    positions = np.linspace(0, sub.height - 1, n).round().astype(int)
    return [sub["admissionid"][int(i)] for i in positions]


def load_admission_frame(dataset_dir, metadata, admid, feature_order):
    """metadata's shard_file is split-relative (e.g. "train/3.parquet") -- see
    run_extraction.py's write_metadata/write_shards."""
    shard_file = metadata.filter(pl.col("admissionid") == admid)["shard_file"][0]
    shard = pl.read_parquet(dataset_dir / shard_file)
    return shard.filter(pl.col("admissionid") == admid).select(["hour"] + feature_order)


def normalize_columns(combined, feature_order):
    """Returns {feature: (kind, transform)} where kind is 'numeric' or 'categorical' and
    transform is either (lo, hi) clip bounds or a {label: code} mapping."""
    norm = {}
    for feat in feature_order:
        col = combined[feat]
        if col.dtype == pl.Utf8:
            cats = sorted(col.drop_nulls().unique().to_list())
            norm[feat] = ("categorical", {c: i for i, c in enumerate(cats)})
        else:
            vals = col.drop_nulls()
            if vals.len() == 0:
                norm[feat] = ("numeric", (0.0, 1.0))
                continue
            lo, hi = vals.quantile(0.01), vals.quantile(0.99)
            if lo == hi:
                hi = lo + 1.0
            norm[feat] = ("numeric", (lo, hi))
    return norm


def build_matrix(df, feature_order, norm):
    n_hours = int(df["hour"].max()) + 1
    mat = np.full((len(feature_order), n_hours), np.nan)
    hours = df["hour"].to_numpy().astype(int)
    for i, feat in enumerate(feature_order):
        kind, transform = norm[feat]
        col = df[feat]
        if kind == "categorical":
            codes = col.replace_strict(transform, default=None, return_dtype=pl.Int64).to_numpy().astype(float)
            n_cats = max(len(transform) - 1, 1)
            scaled = codes / n_cats
        else:
            lo, hi = transform
            vals = col.to_numpy().astype(float)
            scaled = np.clip((vals - lo) / (hi - lo), 0, 1)
        mat[i, hours] = scaled
    return mat


def main():
    args = parse_args()
    out_path = args.out or (args.dataset_dir / "plots" / "patient_grid_heatmaps.png")
    schema = json.load(open(args.dataset_dir / "feature_schema.json"))
    metadata = pl.read_csv(args.dataset_dir / "metadata.csv")

    admission_ids = args.admission_ids or pick_admission_ids(metadata, args.n_patients)
    print(f"Plotting admissions: {admission_ids}")

    # schema.json lists every resolved feature; figure out the actual per-shard column set
    # from one real shard file (pivot only creates a column for tags with >=1 row in-sample --
    # rare features like hba1c can be entirely absent from a bounded sample's grid).
    any_shard = pl.read_parquet(args.dataset_dir / metadata["shard_file"][0])
    grid_columns = set(any_shard.columns) - {"hour"}
    feature_order = [tag for rt in BLOCK_ORDER for tag, info in schema.items()
                     if info["reconstruction_type"] == rt and tag in grid_columns]
    dropped = (set(schema) & {t for t in schema if schema[t]["reconstruction_type"] in BLOCK_ORDER}) - set(feature_order)
    if dropped:
        print(f"Note: {len(dropped)} resolved features absent from this dataset's grid entirely "
              f"(0 rows in all {metadata.height} admissions): {sorted(dropped)}")
    block_sizes = [sum(1 for tag in feature_order if schema[tag]["reconstruction_type"] == rt) for rt in BLOCK_ORDER]

    frames = {a: load_admission_frame(args.dataset_dir, metadata, a, feature_order) for a in admission_ids}

    combined = pl.concat([f.select(feature_order) for f in frames.values()], how="vertical_relaxed")
    norm = normalize_columns(combined, feature_order)

    fig, axes = plt.subplots(len(admission_ids), 1, figsize=(22, 5 * len(admission_ids)), squeeze=False)
    for row, admid in enumerate(admission_ids):
        ax = axes[row, 0]
        df = frames[admid]
        mat = build_matrix(df, feature_order, norm)

        masked = np.ma.masked_invalid(mat)
        cmap = matplotlib.colormaps["viridis"].copy()
        cmap.set_bad("lightgray")
        im = ax.imshow(masked, aspect="auto", cmap=cmap, norm=Normalize(0, 1), interpolation="nearest",
                        extent=(0, mat.shape[1], len(feature_order), 0))

        cum = 0
        for size, rt in zip(block_sizes, BLOCK_ORDER):
            if size == 0:
                continue
            ax.axhline(cum, color="white", lw=1.5)
            ax.text(-mat.shape[1] * 0.012, cum + size / 2, rt, ha="right", va="center", fontsize=8)
            cum += size

        died = metadata.filter(pl.col("admissionid") == admid)["outcome"][0] == "died"
        outcome = "Death recorded" if died else "Discharged alive"
        ax.axvline(0, color="red", lw=2)
        ax.axvline(mat.shape[1] - 1, color="red", lw=2)
        ax.text(0, -1.5, "t=0", color="red", fontsize=9, ha="center")
        ax.text(mat.shape[1] - 1, -1.5, outcome, color="red", fontsize=9, ha="center")

        ax.set_title(f"admission {admid} -- LOS {mat.shape[1]}h -- {outcome}", fontsize=11)
        ax.set_xlabel("hour since admission")
        ax.set_yticks([])
        ax.set_xlim(0, mat.shape[1])

    legend_patches = [Patch(facecolor="lightgray", label="missing / no data")]
    fig.legend(handles=legend_patches, loc="upper right", fontsize=9)
    fig.colorbar(im, ax=axes.ravel().tolist(), label="per-feature normalized value (1st-99th pct clip, min-max)",
                 fraction=0.01, pad=0.01)
    fig.suptitle("v1 grid output -- per-patient feature heatmaps (rows grouped by reconstruction type)", fontsize=14)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
