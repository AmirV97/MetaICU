"""Hydra CLI for AmsterdamUMCdb MEDS -> tokenized safetensors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from aumc_pipeline.tokenization.build_workflow import TokenizationConfig, write_tokenized_outputs


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
    explicit = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if explicit is not None:
        return explicit
    if parent_dir is not None:
        return parent_dir / default_child
    raise ValueError(f"paths.{key} is required unless paths.parent_dir is set")


def _build_config(cfg: DictConfig) -> TokenizationConfig:
    parent_dir = _optional_path(OmegaConf.select(cfg, "paths.parent_dir"))
    meds_dir = _resolve_path(cfg, "meds_dir", parent_dir, "data/MEDS")
    output_dir = _resolve_path(cfg, "output_dir", parent_dir, "data/tokenized")
    audit_dir = _resolve_path(cfg, "audit_dir", parent_dir, "audits/tokenization")
    metadata_dir = _resolve_path(cfg, "metadata_dir", parent_dir, "data/tokenized/metadata")
    splits = tuple(OmegaConf.to_container(cfg.run.splits, resolve=True))
    time_intervals_spec = dict(OmegaConf.to_container(cfg.time_intervals_spec, resolve=True))
    return TokenizationConfig(
        meds_dir=meds_dir,
        output_dir=output_dir,
        audit_dir=audit_dir,
        metadata_dir=metadata_dir,
        splits=splits,
        train_split=str(cfg.run.train_split),
        max_rows=_optional_int(OmegaConf.select(cfg, "run.max_rows")),
        max_timelines_per_shard=int(cfg.run.max_timelines_per_shard),
        medication_atc_depth=str(cfg.run.medication_atc_depth),
        unknown_token=str(cfg.run.unknown_token),
        overwrite=bool(cfg.run.overwrite),
        time_intervals_spec=time_intervals_spec,
    )


@hydra.main(version_base=None, config_path="../configs", config_name="tokenization")
def main(cfg: DictConfig) -> None:
    """Tokenize split-aware AUMC MEDS parquet into safetensors."""

    OmegaConf.resolve(cfg)
    outputs = write_tokenized_outputs(_build_config(cfg))
    print(json.dumps({name: str(path) for name, path in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
