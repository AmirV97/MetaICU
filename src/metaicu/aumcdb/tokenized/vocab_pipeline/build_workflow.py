"""One-command user-facing vocabulary build workflow.

This module orchestrates the public vocabulary-preparation steps. It validates
that the user-provided raw Amsterdam data and external resources can be read,
writes audit artifacts, and copies the packaged supplied vocabulary to the
configured output location.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metaicu.aumcdb.tokenized.vocab_pipeline.candidate_map import CandidateMapConfig, write_candidate_map_outputs
from metaicu.aumcdb.tokenized.vocab_pipeline.evidence_normalization import EvidenceConfig, write_mapping_evidence
from metaicu.aumcdb.tokenized.vocab_pipeline.resources import inventory_resources, summarize_inventory
from metaicu.aumcdb.tokenized.vocab_pipeline.source_vocab import SourceVocabConfig, write_source_vocab_outputs


REQUIRED_RAW_TABLES = [
    "numericitems.csv",
    "listitems.csv",
    "drugitems.csv",
    "freetextitems.csv",
    "processitems.csv",
    "procedureorderitems.csv",
]


@dataclass(frozen=True)
class BuildVocabConfig:
    """Inputs and outputs for the public one-command vocabulary workflow."""

    raw_data_dir: Path
    external_root: Path
    omop_vocab_dir: Path
    audit_dir: Path
    supplied_vocab: Path
    output_vocab: Path
    dataset: str = "AmsterdamUMCdb"
    max_rows_per_table: int | None = None
    overwrite: bool = False


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _log(message: str) -> None:
    print(f"[build_vocab] {message}", flush=True)


def _elapsed(start: float) -> str:
    return f"{time.perf_counter() - start:.1f}s"


def _git_commit(path: Path) -> str:
    """Return the current git commit for ``path`` when it is in a git checkout."""

    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def _preflight(config: BuildVocabConfig) -> dict[str, Any]:
    """Validate user inputs before expensive scans begin."""

    errors: list[str] = []
    if not config.raw_data_dir.is_dir():
        errors.append(f"Raw Amsterdam data directory does not exist: {config.raw_data_dir}")
    else:
        missing_raw = [name for name in REQUIRED_RAW_TABLES if not (config.raw_data_dir / name).exists()]
        if missing_raw:
            errors.append(f"Missing raw Amsterdam CSV files in {config.raw_data_dir}: {missing_raw}")

    if not config.external_root.is_dir():
        errors.append(f"External resource directory does not exist: {config.external_root}")
    if not config.omop_vocab_dir.is_dir():
        errors.append(f"OMOP/Athena vocabulary directory does not exist: {config.omop_vocab_dir}")
    if not config.supplied_vocab.exists():
        errors.append(f"Packaged supplied vocabulary not found: {config.supplied_vocab}")
    if config.output_vocab.exists() and not config.overwrite:
        errors.append(
            f"Output vocabulary already exists: {config.output_vocab}. "
            "Set run.overwrite=true to replace it."
        )

    if errors:
        raise FileNotFoundError("\n".join(errors))

    inventory = inventory_resources(config.external_root, config.omop_vocab_dir)
    inventory_summary = summarize_inventory(inventory)
    if inventory_summary["missing_required_resources"]:
        raise FileNotFoundError(
            "Missing required external resources:\n"
            + "\n".join(inventory_summary["missing_required_paths"])
        )
    return inventory_summary


def _write_run_config(config: BuildVocabConfig, inventory_summary: dict[str, Any]) -> Path:
    """Snapshot the effective user-facing build configuration."""

    path = config.audit_dir / "run_config.json"
    payload = {
        "dataset": config.dataset,
        "raw_data_dir": str(config.raw_data_dir),
        "external_root": str(config.external_root),
        "omop_vocab_dir": str(config.omop_vocab_dir),
        "audit_dir": str(config.audit_dir),
        "supplied_vocab": str(config.supplied_vocab),
        "output_vocab": str(config.output_vocab),
        "max_rows_per_table": config.max_rows_per_table,
        "overwrite": config.overwrite,
        "package_git_commit": _git_commit(Path(__file__).resolve().parents[3]),
        "inventory_summary": inventory_summary,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def write_build_vocab_outputs(config: BuildVocabConfig) -> dict[str, Path]:
    """Run source-vocab, evidence, and candidate-map checks, then write vocab artifact."""

    total_start = time.perf_counter()
    config.audit_dir.mkdir(parents=True, exist_ok=True)

    step_start = time.perf_counter()
    _log("preflight validating raw data, external resources, OMOP vocab, and output policy")
    inventory_summary = _preflight(config)
    run_config_path = _write_run_config(config, inventory_summary)
    _log(f"preflight finished in {_elapsed(step_start)} -> {run_config_path}")

    step_start = time.perf_counter()
    _log(f"1/4 extracting source vocabulary from raw CSVs: {config.raw_data_dir}")
    source_outputs = write_source_vocab_outputs(
        SourceVocabConfig(
            pre_meds_dir=None,
            raw_data_dir=config.raw_data_dir,
            input_format="raw",
            audit_dir=config.audit_dir,
            max_rows_per_table=config.max_rows_per_table,
            dataset=config.dataset,
        )
    )
    _log(f"1/4 source vocabulary finished in {_elapsed(step_start)} -> {source_outputs['source_vocab']}")

    step_start = time.perf_counter()
    _log(f"2/4 normalizing external evidence from {config.external_root} and {config.omop_vocab_dir}")
    evidence_outputs = write_mapping_evidence(
        EvidenceConfig(
            external_root=config.external_root,
            omop_vocab_dir=config.omop_vocab_dir,
            audit_dir=config.audit_dir,
        )
    )
    _log(f"2/4 evidence normalization finished in {_elapsed(step_start)} -> {evidence_outputs['mapping_evidence']}")

    step_start = time.perf_counter()
    _log("3/4 constructing source-token candidate map")
    candidate_outputs = write_candidate_map_outputs(
        CandidateMapConfig(
            source_vocab=source_outputs["source_vocab"],
            mapping_evidence=evidence_outputs["mapping_evidence"],
            audit_dir=config.audit_dir,
        )
    )
    _log(f"3/4 candidate map finished in {_elapsed(step_start)} -> {candidate_outputs['candidates']}")

    step_start = time.perf_counter()
    _log(f"4/4 installing packaged supplied vocabulary artifact: {config.output_vocab}")
    _log(f"4/4 using packaged supplied vocabulary: {config.supplied_vocab}")
    config.output_vocab.parent.mkdir(parents=True, exist_ok=True)
    # The public workflow installs the curated supplied vocab; policy replay remains internal provenance.
    shutil.copy2(config.supplied_vocab, config.output_vocab)
    _log(f"4/4 supplied vocabulary installed in {_elapsed(step_start)}")

    summary_path = config.audit_dir / "build_vocab_summary.json"
    summary = {
        "raw_data_dir": str(config.raw_data_dir),
        "external_root": str(config.external_root),
        "omop_vocab_dir": str(config.omop_vocab_dir),
        "supplied_vocab_source": str(config.supplied_vocab),
        "output_vocab": str(config.output_vocab),
        "run_config": str(run_config_path),
        "overwrite": config.overwrite,
        "source_vocab_summary": _read_json(source_outputs["summary"]),
        "mapping_evidence_summary": _read_json(evidence_outputs["mapping_evidence_summary"]),
        "candidate_summary": _read_json(candidate_outputs["candidate_summary"]),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    _log(f"done in {_elapsed(total_start)}; summary -> {summary_path}")

    outputs: dict[str, Path] = {
        "output_vocab": config.output_vocab,
        "build_summary": summary_path,
        "run_config": run_config_path,
    }
    outputs.update({f"source_{key}": value for key, value in source_outputs.items()})
    outputs.update({f"evidence_{key}": value for key, value in evidence_outputs.items()})
    outputs.update({f"candidate_{key}": value for key, value in candidate_outputs.items()})
    return outputs
