"""Hydra CLI for the iCareFM-style AUMC grid feature manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from metaicu.grid.manifest import GridManifestConfig, write_grid_manifest_outputs


def _path(value: Any) -> Path:
    return Path(str(value)).expanduser()


def _optional_path(value: Any) -> Path | None:
    if value in (None, "", "null", "None"):
        return None
    return _path(value)


def _resolve_required(cfg: DictConfig, key: str, parent_dir: Path | None, default_child: str) -> Path:
    """Return an explicit path or parent-relative default for required outputs."""

    explicit = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if explicit is not None:
        return explicit
    if parent_dir is None:
        raise ValueError(f"paths.{key} is required unless paths.parent_dir is set")
    return parent_dir / default_child


def _resolve_optional(cfg: DictConfig, key: str, parent_dir: Path | None, default_child: str) -> Path | None:
    """Return an explicit path, parent-relative default, or None for optional inputs."""

    explicit = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if explicit is not None:
        return explicit
    if parent_dir is None:
        return None
    return parent_dir / default_child


def _build_config(cfg: DictConfig) -> GridManifestConfig:
    parent_dir = _optional_path(OmegaConf.select(cfg, "paths.parent_dir"))
    return GridManifestConfig(
        output_manifest=_resolve_required(cfg, "output_manifest", parent_dir, "grid/aumc_grid_feature_manifest.csv"),
        audit_dir=_resolve_required(cfg, "audit_dir", parent_dir, "audits/grid_manifest"),
        feature_list=_optional_path(OmegaConf.select(cfg, "paths.feature_list")),
        source_vocab=_resolve_optional(cfg, "source_vocab", parent_dir, "audits/vocab/vocab_pipeline_source_vocab.csv"),
        supplied_vocab=_resolve_optional(cfg, "supplied_vocab", parent_dir, "vocab/aumc_supplied_vocab.csv"),
        openicu_root=_resolve_optional(cfg, "openicu_root", parent_dir, "externals/OpenICU"),
    )


@hydra.main(version_base=None, config_path="../configs", config_name="grid_manifest")
def main(cfg: DictConfig) -> None:
    """Build the grid feature manifest and audit files."""

    OmegaConf.resolve(cfg)
    outputs = write_grid_manifest_outputs(_build_config(cfg))
    print(json.dumps({name: str(path) for name, path in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
