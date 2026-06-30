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
      paths.pre_meds_dir=/workspace/outputs/pre_meds \\
      paths.audit_dir=/workspace/outputs/audits \\
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
    raw_data_dir = _resolve_path(cfg, "raw_data_dir", parent_dir, "AUMC_raw")
    pre_meds_dir = _resolve_path(cfg, "pre_meds_dir", parent_dir, "outputs/pre_meds")
    audit_dir = _resolve_path(cfg, "audit_dir", parent_dir, "outputs/audits")

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
