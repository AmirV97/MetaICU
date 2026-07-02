"""Hydra CLI for deterministic AmsterdamUMCdb subject splits.

Usage examples:

  build-aumc-split paths.parent_dir=/path/to/workspace

  build-aumc-split \
      paths.parent_dir=/path/to/workspace \
      run.train_frac=0.8 run.val_frac=0.0 run.test_frac=0.2
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from aumc_pipeline.splits.build_splits import SplitConfig, write_subject_splits


def _path(value: Any) -> Path:
    return Path(str(value)).expanduser()


def _optional_path(value: Any) -> Path | None:
    if value in (None, "", "null", "None"):
        return None
    return _path(value)


def _resolve_path(cfg: DictConfig, key: str, parent_dir: Path | None, default_child: str) -> Path:
    explicit = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if explicit is not None:
        return explicit
    if parent_dir is not None:
        return parent_dir / default_child
    raise ValueError(f"paths.{key} is required unless paths.parent_dir is set")


def _build_config(cfg: DictConfig) -> SplitConfig:
    parent_dir = _optional_path(OmegaConf.select(cfg, "paths.parent_dir"))
    raw_data_dir = _resolve_path(cfg, "raw_data_dir", parent_dir, "data/raw")
    metadata_dir = _resolve_path(cfg, "metadata_dir", parent_dir, "data/metadata")
    split_path = _resolve_path(
        cfg,
        "split_path",
        parent_dir,
        "data/metadata/subject_splits.parquet",
    )

    return SplitConfig(
        raw_data_dir=raw_data_dir,
        metadata_dir=metadata_dir,
        split_path=split_path,
        train_frac=float(cfg.run.train_frac),
        val_frac=float(cfg.run.val_frac),
        test_frac=float(cfg.run.test_frac),
        seed=int(cfg.run.seed),
        train_name=str(cfg.run.split_names.train),
        val_name=str(cfg.run.split_names.val),
        test_name=str(cfg.run.split_names.test),
        overwrite=bool(cfg.run.overwrite),
    )


@hydra.main(version_base=None, config_path="../configs", config_name="split")
def main(cfg: DictConfig) -> None:
    """Write subject_splits.parquet/csv from raw admissions.csv."""
    OmegaConf.resolve(cfg)
    outputs = write_subject_splits(_build_config(cfg))
    print(json.dumps({k: str(v) for k, v in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
