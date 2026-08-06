"""Reuse a previously-built grid dataset's numerical processing artifacts (scalers.pkl,
categorical_encoding.csv, feature_schema.json, metadata.csv's train-admission count) when
building a DIFFERENT dataset, pooling with that dataset's own fresh per-tag fit via the same
1/sqrt(n_train_admissions) weighting metaicu.grid.pool_scale already uses for joint builds.

A tag entirely absent from the external artifacts (a genuinely new feature the other dataset
never had) is simply left OUT of the returned external_scalers dict -- scale_grid/
scale_static_features's own existing external_scalers.get(tag) fallback already fits it solo on
this dataset's own train split, no special-casing needed here.

Treatment-rate (QuantileTransformer) tags can't be pooled from a fitted transformer object the
way pooled_fit_treatment pools two RAW value arrays -- there's no "raw values" left once a
transformer is fit. synthetic_treatment_values approximates them by inverse-transforming a dense
uniform quantile grid, standing in for "the external dataset's raw values" so the existing,
unmodified pooled_fit_treatment can run unchanged; _replication_counts' own k_c ~ w_c/n_c
proportionality (metaicu.grid.pool_scale) means the exact choice of how many synthetic points to
draw does not bias the resulting external-vs-own weight ratio, only how finely the external
dataset's shape is resolved.
"""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from metaicu.grid.pool_scale import pooled_fit_treatment, pooled_mean_std
from metaicu.grid.schema_union import compute_union_categorical_vocab

MISSING_CATEGORY_LABEL = "(missing)"
SYNTHETIC_TREATMENT_SAMPLES = 2000  # exceeds a fitted QuantileTransformer's own n_quantiles cap
                                     # (<=1000), so this isn't the resolution bottleneck


@dataclass
class ExternalArtifacts:
    scalers: dict
    schema_registry: dict
    categorical_vocab: dict
    n_train_admissions: int


def load_external_artifacts(artifacts_dir: Path) -> ExternalArtifacts:
    """artifacts_dir: a previously-completed single-dataset grid build's output_dir (has
    scalers.pkl, feature_schema.json, categorical_encoding.csv, metadata.csv)."""
    artifacts_dir = Path(artifacts_dir)
    with open(artifacts_dir / "scalers.pkl", "rb") as f:
        scalers = pickle.load(f)

    feature_schema = json.loads((artifacts_dir / "feature_schema.json").read_text())
    schema_registry = {
        tag: {"reconstruction_type": info["reconstruction_type"], "target_unit": info["target_unit"]}
        for tag, info in feature_schema.items()
    }

    encoding = pl.read_csv(artifacts_dir / "categorical_encoding.csv")
    categorical_vocab = {
        feature: group.sort("position_in_feature")["category"].to_list()
        for (feature,), group in encoding.filter(pl.col("category") != MISSING_CATEGORY_LABEL)
        .group_by(["feature"], maintain_order=True)
    }

    metadata = pl.read_csv(artifacts_dir / "metadata.csv")
    n_train_admissions = metadata.filter(pl.col("split") == "train").height

    return ExternalArtifacts(
        scalers=scalers, schema_registry=schema_registry,
        categorical_vocab=categorical_vocab, n_train_admissions=n_train_admissions,
    )


def synthetic_treatment_values(quantile_transformer, n_synthetic: int = SYNTHETIC_TREATMENT_SAMPLES) -> np.ndarray:
    """Draws n_synthetic values from quantile_transformer's own fitted inverse CDF, as a stand-in
    for the raw positive training values it was originally fit on (not retained on disk)."""
    quantiles = np.linspace(1e-4, 1 - 1e-4, n_synthetic).reshape(-1, 1)
    return quantile_transformer.inverse_transform(quantiles).ravel()


def train_values(df: pl.DataFrame, train_admission_ids, tag: str) -> np.ndarray:
    """df: any DataFrame carrying `tag` and `admissionid`. Returns this dataset's own non-null
    raw TRAIN-split values for tag, or an empty array if the tag isn't a column at all (e.g. a
    structural-zero tag for this cohort)."""
    if tag not in df.columns:
        return np.array([])
    mask = pl.col("admissionid").is_in(list(train_admission_ids))
    return df.filter(mask)[tag].drop_nulls().to_numpy()


def _apply_log(values: np.ndarray, kind: str | None) -> np.ndarray:
    """Mirrors {aumcdb,mimiciv}/grid/build/scale.py::_apply_log (byte-identical in both) -- kept
    as its own tiny copy here rather than importing a dataset-specific module from this
    dataset-agnostic one."""
    if kind == "log1p":
        return np.log1p(values)
    if kind == "signed_log1p":
        return np.sign(values) * np.log1p(np.abs(values))
    return values


def build_pooled_external_scalers(
    pre_scale_grid, external: ExternalArtifacts, weights: dict, random_seed: int = 42,
) -> dict:
    """pre_scale_grid: this dataset's OWN PreScaleGrid, already padded to
    external.schema_registry by the caller (metaicu.grid.schema_union.pad_matches_for_cohort).
    weights: {"external": ..., "own": ...} from metaicu.grid.pool_scale.compute_cohort_weights.
    random_seed: passed to pooled_fit_treatment's QuantileTransformer.

    Returns an external_scalers dict in the exact shape scale_grid/scale_static_features expect.
    Only covers tags external.scalers has an entry for -- a tag this dataset has that the
    external artifacts lack entirely is left out, so scale_grid's own solo-fit fallback handles
    it unchanged."""
    external_scalers = {}
    for tag, ext_entry in external.scalers.items():
        # scale_grid/scale_static_features skip a structural_zero tag unconditionally (own.py:
        # "if info.get('structural_zero'): continue"), regardless of external_scalers -- computing
        # a pooled entry for one here would just be discarded, matching how
        # grid_build_joint_dataset.py's own _compute_pooled_scalers filters these out too.
        if pre_scale_grid.matches_with_derived.get(tag, {}).get("structural_zero"):
            continue
        if ext_entry["type"] == "treatment":
            if ext_entry["transformer"] is None:
                continue
            values_by_side = {"external": synthetic_treatment_values(ext_entry["transformer"])}
            own_values = train_values(pre_scale_grid.grid, pre_scale_grid.train_admission_ids, tag)
            own_values = own_values[own_values > 0]
            if len(own_values) > 0:
                values_by_side["own"] = own_values
            qt = pooled_fit_treatment(values_by_side, weights, tag, random_seed=random_seed)
            if qt is not None:
                external_scalers[tag] = {"type": "treatment", "transformer": qt}
        else:
            source = pre_scale_grid.admissions if ext_entry["type"] == "static" else pre_scale_grid.grid
            own_raw = train_values(source, pre_scale_grid.train_admission_ids, tag)
            per_side = {"external": {"mean": ext_entry["mean"], "std": ext_entry["std"]}}
            if len(own_raw) > 0:
                # Use the EXTERNAL side's own log_kind for both sides' values -- pooling two
                # means/stds only makes sense if they're in the same transformed space.
                own_transformed = _apply_log(own_raw, ext_entry["log"])
                per_side["own"] = {"mean": float(np.mean(own_transformed)), "std": float(np.std(own_transformed))}
            mean, std = pooled_mean_std(per_side, weights)
            external_scalers[tag] = {**ext_entry, "mean": mean, "std": std if std != 0.0 else 1.0}
    return external_scalers


def build_external_vocab(external: ExternalArtifacts, own_vocab: dict) -> dict:
    """own_vocab: this dataset's own grid.build.encode.get_categorical_vocab(matches)."""
    return compute_union_categorical_vocab({"external": external.categorical_vocab, "own": own_vocab})
