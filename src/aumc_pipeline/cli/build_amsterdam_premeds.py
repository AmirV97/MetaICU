"""Hydra CLI for AmsterdamUMCdb pre-MEDS extraction.

Thin dispatcher: reads Hydra config, resolves paths, and calls
``write_premeds_outputs``. All data logic lives in ``aumc_pipeline.pre_meds``.

Usage examples:

  # Full extraction using a workspace root:
  build-aumc-premeds paths.parent_dir=/path/to/workspace

  # Bounded test (1000 patients, all tables):
  build-aumc-premeds paths.parent_dir=/path/to/workspace run.num_patients=1000

  # Debug smoke with explicit paths and 50 k-row cap per table:
  build-aumc-premeds \\
      paths.raw_data_dir=/data/AmsterdamUMCdb \\
      paths.pre_meds_dir=/workspace/data/pre-MEDS \\
      paths.audit_dir=/workspace/audits/pre-MEDS \\
      run.max_rows=50000
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from aumc_pipeline.pre_meds.build_workflow import PreMedsConfig, write_premeds_outputs


def _path(value: Any) -> Path:
    return Path(str(value)).expanduser()


def _optional_path(value: Any) -> Path | None:
    if value in (None, "", "null", "None"):
        return None
    return _path(value)


def _optional_int(value: Any) -> int | None:
    if value in (None, "", "null", "None"):
        return None
    return int(value)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, "", "null", "None"):
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def _resolve_path(
    cfg: DictConfig,
    key: str,
    parent_dir: Path | None,
    default_child: str,
) -> Path:
    """Return paths.<key> if set, else parent_dir/default_child, else raise."""
    explicit = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if explicit is not None:
        return explicit
    if parent_dir is not None:
        return parent_dir / default_child
    raise ValueError(
        f"paths.{key} is required unless paths.parent_dir is set"
    )


def _build_config(cfg: DictConfig) -> PreMedsConfig:
    parent_dir = _optional_path(OmegaConf.select(cfg, "paths.parent_dir"))
    raw_data_dir = _resolve_path(cfg, "raw_data_dir", parent_dir, "data/raw")
    raw_shards_dir = _resolve_path(cfg, "raw_shards_dir", parent_dir, "data/raw_shards")
    pre_meds_dir = _resolve_path(cfg, "pre_meds_dir", parent_dir, "data/pre-MEDS")
    audit_dir = _resolve_path(cfg, "audit_dir", parent_dir, "audits/pre-MEDS")
    vocab_path = _resolve_path(cfg, "vocab_path", parent_dir, "vocab/aumc_supplied_vocab.csv")
    metadata_dir = _resolve_path(cfg, "metadata_dir", parent_dir, "data/metadata")
    split_outputs = bool(OmegaConf.select(cfg, "run.split_outputs", default=False))
    split_path = (
        _resolve_path(cfg, "split_path", parent_dir, "data/metadata/subject_splits.parquet")
        if split_outputs
        else _optional_path(OmegaConf.select(cfg, "paths.split_path"))
    )

    epoch_map = dict(OmegaConf.to_container(cfg.pre_meds.epoch_map, resolve=True))

    return PreMedsConfig(
        raw_data_dir=raw_data_dir,
        pre_meds_dir=pre_meds_dir,
        audit_dir=audit_dir,
        epoch_map=epoch_map,
        dataset=str(cfg.pre_meds.dataset),
        partition_rows=int(cfg.run.partition_rows),
        max_rows=_optional_int(OmegaConf.select(cfg, "run.max_rows")),
        num_patients=_optional_int(OmegaConf.select(cfg, "run.num_patients")),
        raw_shards_dir=raw_shards_dir,
        build_raw_shards=bool(OmegaConf.select(cfg, "run.build_raw_shards", default=True)),
        rebuild_raw_shards=bool(OmegaConf.select(cfg, "run.rebuild_raw_shards", default=False)),
        raw_shard_rows=_optional_int(OmegaConf.select(cfg, "run.raw_shard_rows")),
        split_path=split_path,
        split_outputs=split_outputs,
        split_train_frac=float(OmegaConf.select(cfg, "split.train_frac", default=0.8)),
        split_val_frac=float(OmegaConf.select(cfg, "split.val_frac", default=0.1)),
        split_test_frac=float(OmegaConf.select(cfg, "split.test_frac", default=0.1)),
        split_seed=int(OmegaConf.select(cfg, "split.seed", default=20260618)),
        vocab_path=vocab_path,
        build_hf_inventory=bool(OmegaConf.select(cfg, "run.build_hf_inventory", default=True)),
        build_binned_numericitems=bool(OmegaConf.select(cfg, "run.build_binned_numericitems", default=True)),
        hf_inventory_metadata_dir=metadata_dir,
        hf_highres_threshold_minutes=float(OmegaConf.select(cfg, "hf_inventory.highres_threshold_minutes", default=45.0)),
        hf_confidence_level=float(OmegaConf.select(cfg, "hf_inventory.confidence_level", default=0.99)),
        hf_min_groups=int(OmegaConf.select(cfg, "hf_inventory.min_groups", default=30)),
        hf_rare_dense_min_groups=int(OmegaConf.select(cfg, "hf_inventory.rare_dense_min_groups", default=2)),
        hf_rare_dense_min_row_count=int(OmegaConf.select(cfg, "hf_inventory.rare_dense_min_row_count", default=500_000)),
        hf_patient_batch_size=int(OmegaConf.select(cfg, "hf_inventory.patient_batch_size", default=500)),
        hf_candidate_limit=int(OmegaConf.select(cfg, "hf_inventory.candidate_limit", default=0)),
        hf_seed=int(OmegaConf.select(cfg, "hf_inventory.seed", default=20260601)),
        binning_window_minutes=int(OmegaConf.select(cfg, "binning.window_minutes", default=60)),
        listitems_state_change_dedup_labels=_string_tuple(
            OmegaConf.select(cfg, "listitems.state_change_dedup_labels", default=())
        ),
        overwrite=bool(OmegaConf.select(cfg, "run.overwrite", default=False)),
    )


@hydra.main(version_base=None, config_path="../configs", config_name="pre_meds")
def main(cfg: DictConfig) -> None:
    """Extract Amsterdam raw CSVs to pre-MEDS parquet."""
    OmegaConf.resolve(cfg)
    config = _build_config(cfg)
    outputs = write_premeds_outputs(config)
    print(
        json.dumps(
            {name: str(path) for name, path in outputs.items()},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
