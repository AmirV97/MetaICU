"""Hydra CLI for AmsterdamUMCdb MEDS conversion.

Consumes pre-MEDS parquet and aumc_supplied_vocab.csv; emits a MEDS-like
event parquet and audit outputs.

Usage examples:

  # Full run using a workspace root (reads pre_meds/ from there):
  build-aumc-meds paths.parent_dir=/path/to/workspace

  # Bounded secondary sample within a 1000-patient pre-MEDS:
  build-aumc-meds paths.parent_dir=/path/to/workspace \\
      run.mode=bounded run.num_patients=100

  # Explicit paths (pre-MEDS already bounded):
  build-aumc-meds \\
      paths.pre_meds_dir=/path/to/pre_meds_1000 \\
      paths.vocab_path=/path/to/outputs/aumc_supplied_vocab.csv \\
      paths.output_dir=/path/to/outputs/meds_1000 \\
      paths.audit_dir=/path/to/outputs/audits
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from aumc_pipeline.meds.build_workflow import MEDSConfig, write_meds_outputs


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


def _resolve_path(cfg: DictConfig, key: str, parent_dir: Path | None, default_child: str) -> Path:
    """Return paths.<key> if set, else parent_dir/default_child, else raise."""
    explicit = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if explicit is not None:
        return explicit
    if parent_dir is not None:
        return parent_dir / default_child
    raise ValueError(f"paths.{key} is required unless paths.parent_dir is set")


def _build_config(cfg: DictConfig) -> MEDSConfig:
    parent_dir = _optional_path(OmegaConf.select(cfg, "paths.parent_dir"))
    pre_meds_dir = _resolve_path(cfg, "pre_meds_dir", parent_dir, "outputs/pre_meds")
    vocab_path = _resolve_path(cfg, "vocab_path", parent_dir, "outputs/aumc_supplied_vocab.csv")
    output_dir = _resolve_path(cfg, "output_dir", parent_dir, "outputs/meds")
    audit_dir = _resolve_path(cfg, "audit_dir", parent_dir, "outputs/audits")

    include_phases = tuple(OmegaConf.to_container(cfg.meds.include_temporal_phases, resolve=True))

    return MEDSConfig(
        pre_meds_dir=pre_meds_dir,
        vocab_path=vocab_path,
        output_dir=output_dir,
        audit_dir=audit_dir,
        mode=str(cfg.run.mode),
        num_patients=_optional_int(OmegaConf.select(cfg, "run.num_patients")),
        seed=int(cfg.run.seed),
        max_rows=_optional_int(OmegaConf.select(cfg, "run.max_rows")),
        include_temporal_phases=include_phases,
        quantile_bins=int(cfg.meds.quantile_bins),
        write_debug=bool(cfg.run.write_debug),
        overwrite=bool(cfg.run.overwrite),
    )


@hydra.main(version_base=None, config_path="../configs", config_name="meds")
def main(cfg: DictConfig) -> None:
    """Convert Amsterdam pre-MEDS parquet to MEDS event parquet."""
    OmegaConf.resolve(cfg)
    config = _build_config(cfg)
    outputs = write_meds_outputs(config)
    print(
        json.dumps(
            {name: str(path) for name, path in outputs.items()},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
