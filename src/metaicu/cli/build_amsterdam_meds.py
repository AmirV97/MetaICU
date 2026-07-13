"""Hydra CLI for AmsterdamUMCdb MEDS conversion.

Consumes pre-MEDS parquet and aumc_supplied_vocab.csv; emits MEDS-like event
parquet and audit outputs. Split-aware mode fits numeric quantile boundaries
on train and applies them to train/val/test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from metaicu.meds.build_workflow import MEDSConfig, SplitMEDSConfig, write_meds_outputs, write_split_meds_outputs


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


def _optional_bool(value: Any) -> bool | None:
    if value in (None, "", "null", "None"):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _resolve_path(cfg: DictConfig, key: str, parent_dir: Path | None, default_child: str) -> Path:
    """Return paths.<key> if set, else parent_dir/default_child, else raise."""
    explicit = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if explicit is not None:
        return explicit
    if parent_dir is not None:
        return parent_dir / default_child
    raise ValueError(f"paths.{key} is required unless paths.parent_dir is set")


def _include_phases(cfg: DictConfig) -> tuple[str, ...]:
    return tuple(OmegaConf.to_container(cfg.meds.include_temporal_phases, resolve=True))


def _splits(cfg: DictConfig) -> tuple[str, ...]:
    return tuple(OmegaConf.to_container(cfg.run.splits, resolve=True))


def _should_run_split_outputs(cfg: DictConfig, pre_meds_dir: Path) -> bool:
    explicit = _optional_bool(OmegaConf.select(cfg, "run.split_outputs"))
    if explicit is not None:
        return explicit
    splits = _splits(cfg)
    return bool(splits) and all((pre_meds_dir / split).is_dir() for split in splits)


def _base_paths(cfg: DictConfig) -> tuple[Path, Path, Path, Path, Path]:
    parent_dir = _optional_path(OmegaConf.select(cfg, "paths.parent_dir"))
    pre_meds_dir = _resolve_path(cfg, "pre_meds_dir", parent_dir, "data/pre-MEDS")
    vocab_path = _resolve_path(cfg, "vocab_path", parent_dir, "vocab/aumc_supplied_vocab.csv")
    output_dir = _resolve_path(cfg, "output_dir", parent_dir, "data/MEDS")
    audit_dir = _resolve_path(cfg, "audit_dir", parent_dir, "audits/MEDS")
    metadata_dir = _resolve_path(cfg, "metadata_dir", parent_dir, "data/metadata")
    return pre_meds_dir, vocab_path, output_dir, audit_dir, metadata_dir


def _build_single_config(cfg: DictConfig) -> MEDSConfig:
    pre_meds_dir, vocab_path, output_dir, audit_dir, _ = _base_paths(cfg)
    return MEDSConfig(
        pre_meds_dir=pre_meds_dir,
        vocab_path=vocab_path,
        output_dir=output_dir,
        audit_dir=audit_dir,
        mode=str(cfg.run.mode),
        num_patients=_optional_int(OmegaConf.select(cfg, "run.num_patients")),
        seed=int(cfg.run.seed),
        max_rows=_optional_int(OmegaConf.select(cfg, "run.max_rows")),
        include_temporal_phases=_include_phases(cfg),
        quantile_bins=int(cfg.meds.quantile_bins),
        write_debug=bool(cfg.run.write_debug),
        overwrite=bool(cfg.run.overwrite),
    )


def _build_split_config(cfg: DictConfig) -> SplitMEDSConfig:
    pre_meds_dir, vocab_path, output_dir, audit_dir, metadata_dir = _base_paths(cfg)
    return SplitMEDSConfig(
        pre_meds_dir=pre_meds_dir,
        vocab_path=vocab_path,
        output_dir=output_dir,
        audit_dir=audit_dir,
        metadata_dir=metadata_dir,
        splits=_splits(cfg),
        mode=str(cfg.run.mode),
        num_patients=_optional_int(OmegaConf.select(cfg, "run.num_patients")),
        seed=int(cfg.run.seed),
        max_rows=_optional_int(OmegaConf.select(cfg, "run.max_rows")),
        include_temporal_phases=_include_phases(cfg),
        quantile_bins=int(cfg.meds.quantile_bins),
        write_debug=bool(cfg.run.write_debug),
        overwrite=bool(cfg.run.overwrite),
    )


@hydra.main(version_base=None, config_path="../configs", config_name="meds")
def main(cfg: DictConfig) -> None:
    """Convert Amsterdam pre-MEDS parquet to MEDS event parquet."""
    OmegaConf.resolve(cfg)
    pre_meds_dir, _, _, _, _ = _base_paths(cfg)
    if _should_run_split_outputs(cfg, pre_meds_dir):
        outputs = write_split_meds_outputs(_build_split_config(cfg))
    else:
        outputs = write_meds_outputs(_build_single_config(cfg))
    print(json.dumps({name: str(path) for name, path in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
