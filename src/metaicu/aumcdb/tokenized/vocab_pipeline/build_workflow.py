"""One-command user-facing vocabulary build workflow.

This module orchestrates the public vocabulary-preparation steps: it validates that the
user-provided raw Amsterdam data and external resources can be read, extracts the source
vocabulary and mapping evidence, resolves baseline targets, applies the fixed-order policy
layers (curated manifests + deterministic rules), validates the result against the
supplied-vocabulary contract, and writes the constructed vocabulary to the configured output
location. See docs/aumc_vocab_rebuild_handoff.md for the full design and target_resolution.py's
docstring for the one remaining known scope limit (baseline candidate ranking).
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import pandas as pd

from metaicu.aumcdb.tokenized.vocab_pipeline.candidate_map import CandidateMapConfig, write_candidate_map_outputs
from metaicu.aumcdb.tokenized.vocab_pipeline.evidence_normalization import EvidenceConfig, write_mapping_evidence
from metaicu.aumcdb.tokenized.vocab_pipeline.policies.engine import apply_policy_layers
from metaicu.aumcdb.tokenized.vocab_pipeline.resources import inventory_resources, summarize_inventory
from metaicu.aumcdb.tokenized.vocab_pipeline.schema import COMPACT_COLUMNS
from metaicu.aumcdb.tokenized.vocab_pipeline.source_vocab import SourceVocabConfig, write_source_vocab_outputs
from metaicu.aumcdb.tokenized.vocab_pipeline.target_resolution import (
    DEFAULT_BASELINE_RESOLUTION,
    load_baseline_resolution,
    resolve_baseline_targets,
)
from metaicu.aumcdb.tokenized.vocab_pipeline.validation import validate_supplied_vocab


REQUIRED_RAW_TABLES = [
    "numericitems.csv",
    "listitems.csv",
    "drugitems.csv",
    "freetextitems.csv",
    "processitems.csv",
    "procedureorderitems.csv",
]


def packaged_supplied_vocab() -> Path:
    """Return the supplied Amsterdam vocabulary bundled with MetaICU."""

    return Path(
        str(
            files("metaicu.aumcdb.tokenized").joinpath(
                "data/aumc_supplied_vocab.csv"
            )
        )
    )


@dataclass(frozen=True)
class BuildVocabConfig:
    """Inputs and outputs for the public one-command vocabulary workflow.

    ``supplied_vocab`` is no longer the source of the output vocabulary -- the build now
    resolves and validates the vocabulary from raw data, evidence, and packaged policy
    manifests (see ``target_resolution.py`` and ``policies/engine.py``). It is kept as an
    optional historical reference: if present, the build logs a diagnostic diff against it but
    never reads it as an input to construction.
    """

    raw_data_dir: Path
    external_root: Path
    omop_vocab_dir: Path
    audit_dir: Path
    supplied_vocab: Path
    output_vocab: Path
    dataset: str = "AmsterdamUMCdb"
    max_rows_per_table: int | None = None
    overwrite: bool = False
    allow_unresolved_source_tokens: bool = False


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
    """Extract source vocab/evidence/candidates, resolve targets, apply policy, write vocab."""

    total_start = time.perf_counter()
    config.audit_dir.mkdir(parents=True, exist_ok=True)

    step_start = time.perf_counter()
    _log("preflight validating raw data, external resources, OMOP vocab, and output policy")
    inventory_summary = _preflight(config)
    run_config_path = _write_run_config(config, inventory_summary)
    _log(f"preflight finished in {_elapsed(step_start)} -> {run_config_path}")

    step_start = time.perf_counter()
    _log(f"1/6 extracting source vocabulary from raw CSVs: {config.raw_data_dir}")
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
    _log(f"1/6 source vocabulary finished in {_elapsed(step_start)} -> {source_outputs['source_vocab']}")

    step_start = time.perf_counter()
    _log(f"2/6 normalizing external evidence from {config.external_root} and {config.omop_vocab_dir}")
    evidence_outputs = write_mapping_evidence(
        EvidenceConfig(
            external_root=config.external_root,
            omop_vocab_dir=config.omop_vocab_dir,
            audit_dir=config.audit_dir,
        )
    )
    _log(f"2/6 evidence normalization finished in {_elapsed(step_start)} -> {evidence_outputs['mapping_evidence']}")

    step_start = time.perf_counter()
    _log("3/6 constructing source-token candidate map")
    candidate_outputs = write_candidate_map_outputs(
        CandidateMapConfig(
            source_vocab=source_outputs["source_vocab"],
            mapping_evidence=evidence_outputs["mapping_evidence"],
            audit_dir=config.audit_dir,
        )
    )
    _log(f"3/6 candidate map finished in {_elapsed(step_start)} -> {candidate_outputs['candidates']}")

    step_start = time.perf_counter()
    _log("4/6 resolving baseline targets")
    source_vocab = pd.read_csv(source_outputs["source_vocab"], dtype=str, keep_default_na=False)
    baseline_resolution = load_baseline_resolution(DEFAULT_BASELINE_RESOLUTION)
    resolved = resolve_baseline_targets(
        source_vocab, baseline_resolution, allow_unresolved_source_tokens=config.allow_unresolved_source_tokens
    )
    _log(f"4/6 baseline target resolution finished in {_elapsed(step_start)}")

    step_start = time.perf_counter()
    _log("5/6 applying policy layers (curated manifests + deterministic rules)")
    final_vocab = apply_policy_layers(resolved, config.omop_vocab_dir)
    _log(f"5/6 policy layers finished in {_elapsed(step_start)}")

    step_start = time.perf_counter()
    _log("6/6 validating and writing supplied vocabulary")
    validation_report = validate_supplied_vocab(
        source_vocab, final_vocab, config.omop_vocab_dir, strict=not config.allow_unresolved_source_tokens
    )
    config.output_vocab.parent.mkdir(parents=True, exist_ok=True)
    final_vocab[COMPACT_COLUMNS].to_csv(config.output_vocab, index=False)
    validation_path = config.audit_dir / "final_vocab_validation.json"
    validation_path.write_text(json.dumps(validation_report, indent=2, sort_keys=True) + "\n")
    _log(f"6/6 supplied vocabulary written in {_elapsed(step_start)} -> {config.output_vocab}")

    reference_diff_path = None
    if config.supplied_vocab.exists():
        reference_diff_path = _write_reference_diff(config, final_vocab)
        _log(f"reference diff against historical supplied vocab -> {reference_diff_path}")

    summary_path = config.audit_dir / "build_vocab_summary.json"
    summary = {
        "raw_data_dir": str(config.raw_data_dir),
        "external_root": str(config.external_root),
        "omop_vocab_dir": str(config.omop_vocab_dir),
        "output_vocab": str(config.output_vocab),
        "run_config": str(run_config_path),
        "overwrite": config.overwrite,
        "allow_unresolved_source_tokens": config.allow_unresolved_source_tokens,
        "source_vocab_summary": _read_json(source_outputs["summary"]),
        "mapping_evidence_summary": _read_json(evidence_outputs["mapping_evidence_summary"]),
        "candidate_summary": _read_json(candidate_outputs["candidate_summary"]),
        "final_vocab_validation": validation_report,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    _log(f"done in {_elapsed(total_start)}; summary -> {summary_path}")

    outputs: dict[str, Path] = {
        "output_vocab": config.output_vocab,
        "build_summary": summary_path,
        "run_config": run_config_path,
        "final_vocab_validation": validation_path,
    }
    if reference_diff_path is not None:
        outputs["reference_diff"] = reference_diff_path
    outputs.update({f"source_{key}": value for key, value in source_outputs.items()})
    outputs.update({f"evidence_{key}": value for key, value in evidence_outputs.items()})
    outputs.update({f"candidate_{key}": value for key, value in candidate_outputs.items()})
    return outputs


def _write_reference_diff(config: BuildVocabConfig, final_vocab: pd.DataFrame) -> Path:
    """Diagnostic-only: compare the freshly constructed vocab to a historical reference file.

    Never used as a build input -- purely an audit aid for detecting unexpected drift.
    """

    from metaicu.aumcdb.tokenized.vocab_pipeline.schema import POLICY_FIELDS

    reference = pd.read_csv(config.supplied_vocab, dtype=str, keep_default_na=False)
    left = final_vocab.set_index("source_token")[POLICY_FIELDS]
    right = reference.set_index("source_token")[POLICY_FIELDS] if set(POLICY_FIELDS).issubset(reference.columns) else None

    rows: list[dict[str, Any]] = []
    if right is None:
        rows.append({"source_token": "", "diff_type": "reference_schema_incompatible"})
    else:
        common = left.index.intersection(right.index)
        for token in sorted(set(left.index) - set(right.index)):
            rows.append({"source_token": token, "diff_type": "extra_in_build"})
        for token in sorted(set(right.index) - set(left.index)):
            rows.append({"source_token": token, "diff_type": "missing_in_build"})
        mismatched_fields = (left.loc[common] != right.loc[common]).any(axis=1)
        for token in common[mismatched_fields]:
            changed = [f for f in POLICY_FIELDS if left.loc[token, f] != right.loc[token, f]]
            rows.append({"source_token": token, "diff_type": "field_mismatch", "mismatched_fields": ";".join(changed)})

    diff_path = config.audit_dir / "final_vocab_reference_diff.csv"
    pd.DataFrame(rows, columns=["source_token", "diff_type", "mismatched_fields"]).to_csv(diff_path, index=False)
    return diff_path
