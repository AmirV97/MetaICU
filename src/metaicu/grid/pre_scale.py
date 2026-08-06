"""Shared intermediate result type for splitting each grid pipeline's build_workflow at the seam
between extraction/assembly (metaicu.{aumcdb,mimiciv}.grid.build.build_workflow.build_pre_scale_grid)
and scale/impute/one-hot/write (...finish_grid_dataset). Both pipelines return this same type so a
future joint-dataset dispatcher can hold {cohort_name: PreScaleGrid} uniformly, e.g. to compute
pooled scalers (metaicu.grid.pool_scale) across cohorts before each cohort finishes its own build.

A single-dataset build_pre_scale_grid()+finish_grid_dataset(external_scalers=None) call pair
reproduces write_grid_dataset_outputs's pre-split output exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl


@dataclass
class PreScaleGrid:
    """grid: assembled wide DataFrame, post materialize_structural_zero_columns/capture_presence_mask,
    pre scale/impute/one-hot. matches: native (unpadded) tag -> feature info dict from this cohort's
    own parse_manifest(). matches_with_derived: matches merged with derived_target_matches -- what
    scale_grid/impute_grid/one_hot_encode_categorical actually consume. admissions: split-assigned,
    joined with raw (unscaled) static features. train_admission_ids: this cohort's own train-split
    admissionids. demo_source/static_categorical_encoding/next_categorical_pos: sex/adm/ethnic,
    already one-hot encoded if config.one_hot. presence_mask_cols: f"{tag}__observed" columns
    materialized onto grid. manifest_report/raw_shard_summary/admissions_before_inclusion: carried
    through unchanged for finish_grid_dataset's own summary JSON."""

    grid: pl.DataFrame
    matches: dict
    matches_with_derived: dict
    derived_target_matches: dict
    admissions: pl.DataFrame
    train_admission_ids: list[int]
    demo_source: pl.DataFrame
    static_categorical_encoding: list[dict]
    next_categorical_pos: int
    presence_mask_cols: list[str]
    manifest_report: dict
    raw_shard_summary: dict
    admissions_before_inclusion: int
