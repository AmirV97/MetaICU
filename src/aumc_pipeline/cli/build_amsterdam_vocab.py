"""Hydra CLI for AmsterdamUMCdb vocabulary preparation.

The CLI is intentionally thin. It reads configuration, dispatches one public
pipeline step, and leaves all data logic in ``aumc_pipeline.vocab_pipeline``
modules. The supplied vocabulary is consumed as a stable artifact rather than
rebuilt through historical validation steps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from aumc_pipeline.vocab_pipeline.build_workflow import BuildVocabConfig, write_build_vocab_outputs
from aumc_pipeline.vocab_pipeline.candidate_map import CandidateMapConfig, write_candidate_map_outputs
from aumc_pipeline.vocab_pipeline.evidence_normalization import EvidenceConfig, write_mapping_evidence
from aumc_pipeline.vocab_pipeline.resources import write_resource_inventory
from aumc_pipeline.vocab_pipeline.source_vocab import SourceVocabConfig, write_source_vocab_outputs


VALID_STEPS = {
    "source_vocab",
    "external_inventory",
    "normalize_evidence",
    "candidate_map",
    "build_vocab",
}


def _path(value: Any) -> Path:
    return Path(str(value)).expanduser()


def _optional_path(value: Any) -> Path | None:
    if value in (None, "", "null", "None"):
        return None
    return _path(value)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _project_path(value: Any) -> Path:
    path = _path(value)
    if path.is_absolute():
        return path
    return _project_root() / path


def _default_audit_dir(output_vocab: Path) -> Path:
    return output_vocab.parent / "audits"


def _path_from_parent(parent_dir: Path | None, child: str) -> Path | None:
    if parent_dir is None:
        return None
    return parent_dir / child


def _configured_or_parent(cfg: DictConfig, key: str, parent_dir: Path | None, child: str) -> Path:
    value = _optional_path(OmegaConf.select(cfg, f"paths.{key}"))
    if value is not None:
        return value
    parent_value = _path_from_parent(parent_dir, child)
    if parent_value is None:
        raise ValueError(f"paths.{key} is required unless paths.parent_dir is set")
    return parent_value


def run_source_vocab(cfg: DictConfig) -> dict[str, Path]:
    """Run source-vocabulary extraction from raw CSVs or internal pre-MEDS parquet."""

    config = SourceVocabConfig(
        pre_meds_dir=_optional_path(OmegaConf.select(cfg, "paths.pre_meds_dir")),
        audit_dir=_path(cfg.paths.audit_dir),
        max_rows_per_table=cfg.source_vocab.max_rows_per_table,
        reference_vocab=_optional_path(OmegaConf.select(cfg, "paths.reference_vocab")),
        dataset=str(cfg.source_vocab.dataset),
        input_format=str(cfg.source_vocab.input_format),
        raw_data_dir=_optional_path(OmegaConf.select(cfg, "paths.raw_data_dir")),
    )
    return write_source_vocab_outputs(config)


def run_external_inventory(cfg: DictConfig) -> dict[str, Path]:
    """Inventory external files and write required/missing/schema metadata."""

    return write_resource_inventory(
        external_root=_path(cfg.paths.external_root),
        omop_vocab_dir=_path(cfg.paths.omop_vocab_dir),
        audit_dir=_path(cfg.paths.audit_dir),
    )


def run_normalize_evidence(cfg: DictConfig) -> dict[str, Path]:
    """Inventory resources and normalize mapping/context evidence."""

    outputs = run_external_inventory(cfg)
    evidence_config = EvidenceConfig(
        external_root=_path(cfg.paths.external_root),
        omop_vocab_dir=_path(cfg.paths.omop_vocab_dir),
        audit_dir=_path(cfg.paths.audit_dir),
    )
    outputs.update(write_mapping_evidence(evidence_config))
    return outputs


def run_candidate_map(cfg: DictConfig) -> dict[str, Path]:
    """Join source tokens to normalized evidence candidates."""

    config = CandidateMapConfig(
        source_vocab=_path(cfg.paths.source_vocab),
        mapping_evidence=_path(cfg.paths.mapping_evidence),
        audit_dir=_path(cfg.paths.audit_dir),
    )
    return write_candidate_map_outputs(config)


def run_build_vocab(cfg: DictConfig) -> dict[str, Path]:
    """Run the public one-command vocabulary workflow."""

    parent_dir = _optional_path(OmegaConf.select(cfg, "paths.parent_dir"))
    output_vocab = _optional_path(OmegaConf.select(cfg, "paths.output_vocab")) or _configured_or_parent(
        cfg, "output_vocab", parent_dir, "outputs/aumc_supplied_vocab.csv"
    )
    audit_dir = _optional_path(OmegaConf.select(cfg, "paths.audit_dir")) or _default_audit_dir(output_vocab)
    config = BuildVocabConfig(
        raw_data_dir=_configured_or_parent(cfg, "raw_data_dir", parent_dir, "AUMC_raw"),
        external_root=_configured_or_parent(cfg, "external_root", parent_dir, "externals"),
        omop_vocab_dir=_configured_or_parent(cfg, "omop_vocab_dir", parent_dir, "externals/omop_vocab"),
        audit_dir=audit_dir,
        supplied_vocab=_project_path(cfg.paths.supplied_vocab),
        output_vocab=output_vocab,
        dataset=str(cfg.source_vocab.dataset),
        max_rows_per_table=cfg.source_vocab.max_rows_per_table,
    )
    return write_build_vocab_outputs(config)


@hydra.main(version_base=None, config_path="../configs", config_name="vocab")
def main(cfg: DictConfig) -> None:
    """Dispatch the configured vocabulary-pipeline step."""

    OmegaConf.resolve(cfg)
    step = str(cfg.step)
    if step not in VALID_STEPS:
        raise ValueError(f"Unsupported step {step!r}. Expected one of {sorted(VALID_STEPS)}")
    if step == "build_vocab":
        outputs = run_build_vocab(cfg)
    elif step == "source_vocab":
        outputs = run_source_vocab(cfg)
    elif step == "external_inventory":
        outputs = run_external_inventory(cfg)
    elif step == "normalize_evidence":
        outputs = run_normalize_evidence(cfg)
    else:
        outputs = run_candidate_map(cfg)
    print(json.dumps({name: str(path) for name, path in outputs.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
