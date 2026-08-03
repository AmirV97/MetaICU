"""Dataset-dispatching Hydra CLI for the iCareFM-style grid feature manifest. See
grid_build_dataset.py's module docstring for the dispatch mechanism."""

from __future__ import annotations

import json

import hydra
from omegaconf import DictConfig, OmegaConf

from metaicu.aumcdb.grid.cli.grid_build_manifest import _build_config as _build_aumcdb_config
from metaicu.aumcdb.grid.manifest import write_grid_manifest_outputs as _write_aumcdb_outputs
from metaicu.mimiciv.grid.cli.grid_build_manifest import _build_config as _build_mimiciv_config
from metaicu.mimiciv.grid.manifest import write_grid_manifest_outputs as _write_mimiciv_outputs

_DATASETS = {
    "aumcdb": (_build_aumcdb_config, _write_aumcdb_outputs),
    "mimic_iv": (_build_mimiciv_config, _write_mimiciv_outputs),
}


@hydra.main(version_base=None, config_path="../configs", config_name="grid_manifest")
def main(cfg: DictConfig) -> None:
    """Build the grid feature manifest and audit files for whichever dataset= is selected."""

    OmegaConf.resolve(cfg)
    dataset_name = str(OmegaConf.select(cfg, "dataset_name"))
    if dataset_name not in _DATASETS:
        raise ValueError(f"Unknown dataset_name={dataset_name!r}, expected one of {sorted(_DATASETS)}")
    build_config, write_outputs = _DATASETS[dataset_name]

    outputs = write_outputs(build_config(cfg))
    print(json.dumps({name: str(path) for name, path in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
