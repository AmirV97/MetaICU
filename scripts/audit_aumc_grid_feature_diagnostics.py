#!/usr/bin/env python3
"""
Quantitative companion to analyze_features_v2.py's plots: for every continuous feature,
compute the numbers needed to make a log-transform / outlier-method decision without having
to eyeball all 82 PNGs by hand -- skew (raw vs log), zero-inflation, MAD-degeneracy, negative
values, exclusion % per method at raw vs log scale, and a simple "sentinel spike" check (an
exact repeated value sitting at the top of the range, which usually means a device/EHR cap
rather than a real biological outlier).

Output: audits/grid_dataset_v1/plots_v2/outlier_methods/feature_diagnostics.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import skew

CONTINUOUS_TYPES = {"direct_numeric", "derived_output_rate", "treatment_rate"}

IQR_K = 3.0
MAD_THRESH = 3.5
PERCENTILE_P = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def load_train_df(dataset_dir: Path) -> pl.DataFrame:
    train_files = sorted((dataset_dir / "train").glob("*.parquet"))
    return pl.concat([pl.read_parquet(f) for f in train_files])


def iqr_bounds(x, k=IQR_K):
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


def mad_bounds(x, thresh=MAD_THRESH):
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    if mad == 0:
        return np.nan, np.nan
    delta = thresh * mad / 0.6745
    return med - delta, med + delta


def percentile_bounds(x, p=PERCENTILE_P):
    return tuple(np.percentile(x, [p, 100 - p]))


def log_transform(values):
    if (values >= 0).all():
        return np.log1p(values), False
    return np.sign(values) * np.log1p(np.abs(values)), True


def excl_pct(data, bounds):
    lo, hi = bounds
    if np.isnan(lo):
        return None
    return float(100 * ((data < lo) | (data > hi)).mean())


def sentinel_spike(values, top_frac=0.001):
    """Flags a value that is both (a) at/near the max and (b) repeated far more often than
    its neighbors -- the signature of a device ceiling or EHR sentinel code, not real biology."""
    vmax = values.max()
    n_at_max = int((values == vmax).sum())
    if n_at_max < 5:
        return None
    frac_at_max = n_at_max / len(values)
    if frac_at_max >= top_frac:
        return {"value": float(vmax), "n": n_at_max, "frac_pct": round(100 * frac_at_max, 4)}
    return None


def main():
    args = parse_args()
    dataset_dir = args.dataset_dir
    out_path = args.output or dataset_dir / "plots_v2" / "outlier_methods" / "feature_diagnostics.json"
    schema = json.loads((dataset_dir / "feature_schema.json").read_text())
    df = load_train_df(dataset_dir)

    results = {}
    for feature, info in schema.items():
        rtype = info["reconstruction_type"]
        if rtype not in CONTINUOUS_TYPES:
            continue
        values = df[feature].drop_nulls().to_numpy()
        if len(values) == 0:
            continue
        log_values, is_signed = log_transform(values)

        raw_methods = {
            "iqr": iqr_bounds(values), "mad": mad_bounds(values), "pct": percentile_bounds(values),
        }
        log_methods = {
            "iqr": iqr_bounds(log_values), "mad": mad_bounds(log_values), "pct": percentile_bounds(log_values),
        }

        pct = np.percentile(values, [0, 1, 5, 25, 50, 75, 95, 99, 100])
        results[feature] = {
            "unit": info["target_unit"],
            "n": len(values),
            "pct_zero": round(float((values == 0).mean() * 100), 3),
            "pct_negative": round(float((values < 0).mean() * 100), 3),
            "is_signed_log": is_signed,
            "skew_raw": round(float(skew(values)), 3),
            "skew_log": round(float(skew(log_values)), 3),
            "percentiles_0_1_5_25_50_75_95_99_100": [round(float(v), 4) for v in pct],
            "excl_pct_raw": {m: (round(v, 3) if (v := excl_pct(values, b)) is not None else None)
                             for m, b in raw_methods.items()},
            "excl_pct_log": {m: (round(v, 3) if (v := excl_pct(log_values, b)) is not None else None)
                             for m, b in log_methods.items()},
            "sentinel_spike": sentinel_spike(values),
        }
        print(f"  {feature}: n={len(values)} skew_raw={results[feature]['skew_raw']} "
              f"skew_log={results[feature]['skew_log']} pct_zero={results[feature]['pct_zero']}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
