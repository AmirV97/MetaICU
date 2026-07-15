"""Hydra CLI for raw AmsterdamUMCdb to iCareFM-style hourly grid construction."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from metaicu.aumcdb.grid.build_workflow import GridDatasetConfig, write_grid_dataset_outputs
from metaicu.aumcdb.grid.manifest_parser import DEFAULT_REVIEWED_MANIFEST


def _optional_path(value: Any) -> Path | None:
    if value in (None, "", "null", "None"):
        return None
    return Path(str(value)).expanduser()


def _resolve_path(cfg: DictConfig, key: str, parent_dir: Path | None, default_child: str) -> Path:
    explicit = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if explicit is not None:
        return explicit
    if parent_dir is None:
        raise ValueError(f"paths.{key} is required unless paths.parent_dir is set")
    return parent_dir / default_child


def _optional_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, "", "null", "None"):
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(entry) for entry in value)


def _build_config(cfg: DictConfig) -> GridDatasetConfig:
    parent_dir = _optional_path(OmegaConf.select(cfg, "paths.parent_dir"))
    return GridDatasetConfig(
        raw_data_dir=_resolve_path(cfg, "raw_data_dir", parent_dir, "data/raw"),
        raw_shards_dir=_resolve_path(cfg, "raw_shards_dir", parent_dir, "data/raw_shards"),
        output_dir=_resolve_path(cfg, "output_dir", parent_dir, "data/grid"),
        audit_dir=_resolve_path(cfg, "audit_dir", parent_dir, "audits/grid_dataset"),
        build_raw_shards=bool(OmegaConf.select(cfg, "run.build_raw_shards", default=True)),
        rebuild_raw_shards=bool(OmegaConf.select(cfg, "run.rebuild_raw_shards", default=False)),
        raw_shard_rows=int(OmegaConf.select(cfg, "run.raw_shard_rows", default=5_000_000)),
        manifest_path=_optional_path(OmegaConf.select(cfg, "paths.manifest_path")) or DEFAULT_REVIEWED_MANIFEST,
        admission_ids_file=_optional_path(OmegaConf.select(cfg, "paths.admission_ids_file")),
        sample_size=OmegaConf.select(cfg, "run.sample_size"),
        patients_per_file=int(OmegaConf.select(cfg, "run.patients_per_file", default=1_000)),
        seed=int(OmegaConf.select(cfg, "run.seed", default=42)),
        unit_of_analysis=str(OmegaConf.select(cfg, "split.unit_of_analysis", default="admission")),
        train_frac=float(OmegaConf.select(cfg, "split.train_frac", default=0.8)),
        val_frac=float(OmegaConf.select(cfg, "split.val_frac", default=0.1)),
        test_frac=float(OmegaConf.select(cfg, "split.test_frac", default=0.1)),
        split_seed=int(OmegaConf.select(cfg, "split.seed", default=42)),
        features=_optional_tuple(OmegaConf.select(cfg, "run.features")),
        reconstruction_types=_optional_tuple(OmegaConf.select(cfg, "run.reconstruction_types")),
        apply_inclusion_criteria=bool(OmegaConf.select(cfg, "run.apply_inclusion_criteria", default=True)),
        scale=bool(OmegaConf.select(cfg, "run.scale", default=True)),
        impute=bool(OmegaConf.select(cfg, "run.impute", default=True)),
        one_hot=bool(OmegaConf.select(cfg, "run.one_hot", default=True)),
    )


@hydra.main(version_base=None, config_path="../configs", config_name="grid_dataset")
def main(cfg: DictConfig) -> None:
    """Build a split-aware iCareFM-style hourly grid from raw AUMCdb CSVs."""

    OmegaConf.resolve(cfg)
    config = _build_config(cfg)
    config.audit_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=str(OmegaConf.select(cfg, "run.log_level", default="INFO")),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(config.audit_dir / "grid_build_dataset.log", mode="w"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    outputs = write_grid_dataset_outputs(config)
    print(json.dumps({name: str(path) for name, path in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
