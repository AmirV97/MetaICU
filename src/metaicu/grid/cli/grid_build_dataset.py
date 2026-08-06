"""Dataset-dispatching Hydra CLI for raw-source to iCareFM-style hourly grid construction.

Delegates to each dataset's own (_build_config, write_grid_dataset_outputs) pair based on
cfg.dataset_name (set by the composed dataset=<name> config group -- see configs/dataset/).
metaicu.aumcdb.grid.cli.grid_build_dataset and metaicu.mimiciv.grid.cli.grid_build_dataset
remain independently invocable and untouched; this module is the shared multi-dataset entry
point pyproject.toml's grid_build_dataset console script points at.

Prefer grid_build_joint_dataset (metaicu.grid.cli.grid_build_joint_dataset) for new work, even for
a single dataset -- this command stays exactly as-is (byte-identical, Int64 admissionid) for
callers that specifically need that legacy single-dataset output shape.
"""

from __future__ import annotations

import json
import logging

import hydra
from omegaconf import DictConfig, OmegaConf

from metaicu.aumcdb.grid.build.build_workflow import write_grid_dataset_outputs as _write_aumcdb_outputs
from metaicu.aumcdb.grid.cli.grid_build_dataset import _build_config as _build_aumcdb_config
from metaicu.mimiciv.grid.build.build_workflow import write_grid_dataset_outputs as _write_mimiciv_outputs
from metaicu.mimiciv.grid.cli.grid_build_dataset import _build_config as _build_mimiciv_config

_DATASETS = {
    "aumcdb": (_build_aumcdb_config, _write_aumcdb_outputs),
    "mimic_iv": (_build_mimiciv_config, _write_mimiciv_outputs),
}


@hydra.main(version_base=None, config_path="../configs", config_name="grid_dataset")
def main(cfg: DictConfig) -> None:
    """Build a split-aware iCareFM-style hourly grid for whichever dataset= is selected."""

    OmegaConf.resolve(cfg)
    dataset_name = str(OmegaConf.select(cfg, "dataset_name"))
    if dataset_name not in _DATASETS:
        raise ValueError(f"Unknown dataset_name={dataset_name!r}, expected one of {sorted(_DATASETS)}")
    build_config, write_outputs = _DATASETS[dataset_name]

    config = build_config(cfg)
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
    outputs = write_outputs(config)
    print(json.dumps({name: str(path) for name, path in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
