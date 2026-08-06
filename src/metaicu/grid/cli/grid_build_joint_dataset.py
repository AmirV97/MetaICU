"""Hydra CLI for a JOINT AUMCdb + MIMIC-IV (or single-dataset) grid build with pooled statistics.

Orchestrates, per selected dataset in cfg.datasets:
  1. build_pre_scale_grid (metaicu.{aumcdb,mimiciv}.grid.build.build_workflow, Phase 2) --
     extraction/assembly through presence-mask capture, using that pipeline's OWN native matches.
     Unchanged/unaware of the joint build; identical to what a standalone grid_build_dataset run
     does internally.
  2. Cross-cohort schema padding (metaicu.grid.schema_union, Phase 1) -- pads each cohort's
     matches to the union of every selected cohort's tags, then re-runs
     materialize_structural_zero_columns/capture_presence_mask (idempotent for a tag already
     materialized; additive for a newly-padded one) so a tag real in only one cohort still gets a
     real (if all-null/0) column and presence mask in every cohort's grid.
  3. Pooled statistics (metaicu.grid.pool_scale, Phase 3) -- only when more than one dataset is
     selected; a single-dataset run through this command still fits its own train split, same as
     grid_build_dataset.
  4. finish_grid_dataset (Phase 2) per cohort, given the SAME external_scalers dict, so a pooled
     tag's fit (same QuantileTransformer instance / mean+std) is identical across cohorts --
     writes each cohort's own per-cohort STAGING output (dataset_configs.<name>.paths.*).
  5. write_joint_outputs (metaicu.grid.joint_assemble, Phase 4) -- namespaces admissionid/
     subject_id (String, cohort-prefixed), concatenates same-named splits, and writes the final
     flat joint dataset under joint.output_dir/joint.audit_dir.

grid_build_dataset (and metaicu.{aumcdb,mimiciv}.grid.cli.grid_build_dataset) remain the commands
for an exactly byte-identical, Int64-ID, standalone single-dataset build; prefer them unless the
pooled-statistics / flat-namespaced-layout joint format is actually wanted. This command's own
datasets=[X] single-dataset mode is NOT byte-identical to grid_build_dataset's own output -- see
namespace_ids: admissionid/subject_id are always String-prefixed and a `source` column is always
added, regardless of how many datasets were selected, so a consumer of this command's output never
needs to special-case dataset count.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import hydra
import numpy as np
import polars as pl
from omegaconf import DictConfig, OmegaConf

from metaicu.aumcdb.grid.build.build_workflow import build_pre_scale_grid as _build_aumcdb_pre_scale_grid
from metaicu.aumcdb.grid.build.build_workflow import finish_grid_dataset as _finish_aumcdb_dataset
from metaicu.aumcdb.grid.build.impute import (
    capture_presence_mask as _aumcdb_capture_presence_mask,
    materialize_structural_zero_columns as _aumcdb_materialize_structural_zero,
)
from metaicu.aumcdb.grid.build.scale import LOG_TRANSFORM_TAGS, _apply_log
from metaicu.aumcdb.grid.cli.grid_build_dataset import _build_config as _build_aumcdb_config
from metaicu.mimiciv.grid.build.build_workflow import build_pre_scale_grid as _build_mimiciv_pre_scale_grid
from metaicu.mimiciv.grid.build.build_workflow import finish_grid_dataset as _finish_mimiciv_dataset
from metaicu.mimiciv.grid.build.impute import (
    capture_presence_mask as _mimiciv_capture_presence_mask,
    materialize_structural_zero_columns as _mimiciv_materialize_structural_zero,
)
from metaicu.mimiciv.grid.cli.grid_build_dataset import _build_config as _build_mimiciv_config
from metaicu.grid.joint_assemble import write_joint_outputs
from metaicu.grid.pool_scale import MIN_TRAIN_VALUES, compute_cohort_weights, pooled_fit_treatment, pooled_mean_std
from metaicu.grid.schema_union import compute_union_matches, pad_matches_for_cohort

log = logging.getLogger(__name__)

# (build_config, build_pre_scale_grid, finish_grid_dataset, materialize_structural_zero_columns,
# capture_presence_mask) per dataset token -- mirrors grid_build_dataset.py's own _DATASETS
# registry shape, extended with each pipeline's own (byte-identical) impute.py pair so the
# post-padding re-materialization step (below) uses each cohort's own copy.
_DATASETS = {
    "aumcdb": (
        _build_aumcdb_config, _build_aumcdb_pre_scale_grid, _finish_aumcdb_dataset,
        _aumcdb_materialize_structural_zero, _aumcdb_capture_presence_mask,
    ),
    "mimic_iv": (
        _build_mimiciv_config, _build_mimiciv_pre_scale_grid, _finish_mimiciv_dataset,
        _mimiciv_materialize_structural_zero, _mimiciv_capture_presence_mask,
    ),
}

STATIC_NUMERIC_TAGS = ("age", "weight", "height")


def _optional_path(value: Any) -> Path | None:
    if value in (None, "", "null", "None"):
        return None
    return Path(str(value)).expanduser()


def _pad_pre_scale_grid(name, pre_scale_grid, union_registry, materialize_fn, presence_fn):
    """Mutates pre_scale_grid in place: pads its native `matches` to union_registry, re-merges
    with its own derived_target_matches, and re-runs materialize_structural_zero_columns/
    capture_presence_mask on its (already-built) grid with the padded dict -- see this module's
    own docstring, step 2."""
    n_before = len(pre_scale_grid.matches)
    padded_matches = pad_matches_for_cohort(pre_scale_grid.matches, union_registry)
    padded_matches_with_derived = {**padded_matches, **pre_scale_grid.derived_target_matches}
    grid = materialize_fn(pre_scale_grid.grid, padded_matches_with_derived)
    grid, presence_mask_cols = presence_fn(grid, padded_matches_with_derived)
    pre_scale_grid.matches = padded_matches
    pre_scale_grid.matches_with_derived = padded_matches_with_derived
    pre_scale_grid.grid = grid
    pre_scale_grid.presence_mask_cols = presence_mask_cols
    log.info(f"{name}: padded to {len(union_registry)} union tags "
             f"({len(union_registry) - n_before} newly added)")


def _train_values(df, train_admission_ids, tag):
    if tag not in df.columns:
        return np.array([])
    mask = pl.col("admissionid").is_in(list(train_admission_ids))
    return df.filter(mask)[tag].drop_nulls().to_numpy()


def _pooled_observation_scaler(per_cohort_values, weights, log_kind=None):
    """per_cohort_values: {cohort: 1D raw non-null train values}, already restricted to
    contributing cohorts (non-empty, non-structural-zero). Returns a scaler entry shaped like
    scale.py's own observation entries, or None if the pooled total is below MIN_TRAIN_VALUES."""
    total = sum(len(v) for v in per_cohort_values.values())
    if total < MIN_TRAIN_VALUES:
        return None
    transformed = {c: _apply_log(v, log_kind) for c, v in per_cohort_values.items()}
    stats = {c: {"mean": float(np.mean(v)), "std": float(np.std(v)), "n": len(v)} for c, v in transformed.items()}
    mean, std = pooled_mean_std(stats, weights)
    return {"type": "observation", "log": log_kind, "mean": mean, "std": std if std != 0.0 else 1.0}


def _compute_pooled_scalers(pre_scale_by_cohort, weights):
    """Returns one external_scalers dict (tag -> scaler entry) covering static (age/weight/
    height) and grid (direct_numeric/derived_output_rate/treatment_rate) tags, pooled across
    every cohort with real (non-structural-zero) train-split values for that tag -- passed
    identically to every cohort's finish_grid_dataset call. Only called when len(datasets) > 1."""
    pooled = {}

    for tag in STATIC_NUMERIC_TAGS:
        per_cohort_values = {
            name: _train_values(psg.admissions, psg.train_admission_ids, tag)
            for name, psg in pre_scale_by_cohort.items()
        }
        per_cohort_values = {c: v for c, v in per_cohort_values.items() if len(v) > 0}
        if not per_cohort_values:
            continue
        entry = _pooled_observation_scaler(per_cohort_values, weights, log_kind=None)
        if entry is not None:
            pooled[tag] = {**entry, "type": "static"}

    # Every cohort's matches_with_derived is identical post-padding -- any one of them is the
    # full joint tag registry.
    joint_matches = next(iter(pre_scale_by_cohort.values())).matches_with_derived
    for tag, info in joint_matches.items():
        rt = info["reconstruction_type"]
        if rt not in ("direct_numeric", "derived_output_rate", "treatment_rate"):
            continue
        per_cohort_values = {
            name: _train_values(psg.grid, psg.train_admission_ids, tag)
            for name, psg in pre_scale_by_cohort.items()
            if not psg.matches_with_derived.get(tag, {}).get("structural_zero")
        }
        per_cohort_values = {c: v for c, v in per_cohort_values.items() if len(v) > 0}
        if not per_cohort_values:
            continue

        if rt == "treatment_rate":
            qt = pooled_fit_treatment(per_cohort_values, weights, tag)
            if qt is not None:
                pooled[tag] = {"type": "treatment", "transformer": qt}
        else:
            entry = _pooled_observation_scaler(per_cohort_values, weights, log_kind=LOG_TRANSFORM_TAGS.get(tag))
            if entry is not None:
                pooled[tag] = entry

    return pooled


@hydra.main(version_base=None, config_path="../configs", config_name="joint_grid_dataset")
def main(cfg: DictConfig) -> None:
    """Build a joint, pooled-statistics AUMCdb+MIMIC-IV (or single-dataset) hourly grid."""

    OmegaConf.resolve(cfg)
    datasets = list(OmegaConf.select(cfg, "datasets") or [])
    unknown = sorted(set(datasets) - set(_DATASETS))
    if not datasets or unknown:
        raise ValueError(f"datasets must be a non-empty list drawn from {sorted(_DATASETS)}, got {datasets!r}")

    joint_output_dir = _optional_path(OmegaConf.select(cfg, "joint.output_dir"))
    joint_audit_dir = _optional_path(OmegaConf.select(cfg, "joint.audit_dir"))
    if joint_output_dir is None or joint_audit_dir is None:
        raise ValueError("joint.output_dir and joint.audit_dir are required")
    patients_per_file = int(OmegaConf.select(cfg, "joint.patients_per_file", default=1_000))

    joint_audit_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=str(OmegaConf.select(cfg, "joint.log_level", default="INFO")),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(joint_audit_dir / "grid_build_joint_dataset.log", mode="w"),
            logging.StreamHandler(),
        ],
        force=True,
    )

    configs = {}
    for name in datasets:
        build_config_fn = _DATASETS[name][0]
        sub_cfg = OmegaConf.select(cfg, f"dataset_configs.{name}")
        if sub_cfg is None:
            raise ValueError(f"dataset_configs.{name} is required when datasets includes {name!r}")
        config = build_config_fn(sub_cfg)
        if name == "aumcdb" and config.unit_of_analysis != "admission":
            raise ValueError(
                "grid_build_joint_dataset only supports split.unit_of_analysis='admission' -- "
                "subject-grain concatenation across cohorts is not implemented"
            )
        config.audit_dir.mkdir(parents=True, exist_ok=True)
        configs[name] = config

    log.info(f"Building pre-scale grids for {datasets}")
    pre_scale_by_cohort = {name: _DATASETS[name][1](configs[name]) for name in datasets}

    union_registry = compute_union_matches({name: psg.matches for name, psg in pre_scale_by_cohort.items()})
    for name, psg in pre_scale_by_cohort.items():
        materialize_fn, presence_fn = _DATASETS[name][3], _DATASETS[name][4]
        _pad_pre_scale_grid(name, psg, union_registry, materialize_fn, presence_fn)

    n_train_admissions = {name: len(psg.train_admission_ids) for name, psg in pre_scale_by_cohort.items()}
    weights = compute_cohort_weights(n_train_admissions)
    log.info(f"Cohort weights (1/sqrt(n_train), normalized): {weights}")

    external_scalers = None
    if len(datasets) > 1:
        external_scalers = _compute_pooled_scalers(pre_scale_by_cohort, weights)
        log.info(f"Pooled statistics fit for {len(external_scalers)} tags")

    cohort_output_dirs = {}
    for name in datasets:
        finish_fn = _DATASETS[name][2]
        finish_fn(configs[name], pre_scale_by_cohort[name], external_scalers=external_scalers)
        cohort_output_dirs[name] = configs[name].output_dir

    outputs = write_joint_outputs(
        cohort_output_dirs=cohort_output_dirs,
        joint_output_dir=joint_output_dir,
        joint_audit_dir=joint_audit_dir,
        patients_per_file=patients_per_file,
        weights=weights,
        n_train_admissions_by_cohort=n_train_admissions,
    )
    print(json.dumps({name: str(path) for name, path in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
