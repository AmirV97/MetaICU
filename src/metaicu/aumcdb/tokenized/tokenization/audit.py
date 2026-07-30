"""Full-output integrity audit for AUMC tokenized safetensors."""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import polars as pl
import torch
from safetensors.torch import load_file

from metaicu.aumcdb.tokenized.tokenization.build_workflow import (
    CORE_INPUT_COLUMNS,
    DEFAULT_TIME_INTERVALS_SPEC,
    QUANTILE_TOKENS,
    TIMELINE_END,
    TokenizationConfig,
    _expand_events,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


REQUIRED_TENSORS = {
    "tokens",
    "times",
    "patient_ids",
    "patient_offsets",
    "hadm_id",
    "icustay_id",
}


@dataclass(frozen=True)
class TokenizedAuditConfig:
    """Paths and sampling policy for a tokenized-cohort audit."""

    parent_dir: Path
    samples_per_split: int = 5
    seed: int = 20260618
    fail_on_error: bool = True

    @property
    def tokenized_dir(self) -> Path:
        return self.parent_dir / "data/tokenized"

    @property
    def meds_dir(self) -> Path:
        return self.parent_dir / "data/MEDS"

    @property
    def audit_dir(self) -> Path:
        return self.parent_dir / "audits/tokenization"

    @property
    def output_dir(self) -> Path:
        return self.audit_dir / "full_integrity"

    @property
    def timeline_index_path(self) -> Path:
        return self.tokenized_dir / "metadata/timeline_index.parquet"

    @property
    def summary_path(self) -> Path:
        return self.audit_dir / "tokenization_summary.json"


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _checks_frame(checks: list[dict[str, Any]]) -> pl.DataFrame:
    """Serialize heterogeneous check details into a stable CSV schema."""
    return pl.DataFrame(
        {
            "category": [str(row["category"]) for row in checks],
            "check": [str(row["check"]) for row in checks],
            "passed": [bool(row["passed"]) for row in checks],
            "observed": [
                json.dumps(row["observed"], sort_keys=True, default=_json_default)
                for row in checks
            ],
            "expected": [
                json.dumps(row["expected"], sort_keys=True, default=_json_default)
                for row in checks
            ],
            "detail": [str(row.get("detail", "")) for row in checks],
        },
        schema={
            "category": pl.String,
            "check": pl.String,
            "passed": pl.Boolean,
            "observed": pl.String,
            "expected": pl.String,
            "detail": pl.String,
        },
    )


def _load_vocab(path: Path) -> list[str]:
    with path.open() as handle:
        return [line.rstrip("\n") for line in handle if line.rstrip("\n")]


def _find_vocab_path(tokenized_dir: Path, train_split: str) -> Path:
    candidates = sorted((tokenized_dir / train_split).glob("vocab_t*.csv"))
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one train vocabulary under {tokenized_dir / train_split}, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _plot_histograms(metrics: pl.DataFrame, output_dir: Path) -> list[Path]:
    """Write split-overlaid log-scale token-count and duration histograms."""
    output_paths: list[Path] = []
    specs = [
        ("token_count", "Tokens per ICU stay", "sequence_length_histogram.png"),
        ("duration_days", "Days from first to last token", "timeline_duration_histogram.png"),
    ]
    colors = {"train": "#4C72B0", "val": "#55A868", "test": "#C44E52"}
    for column, xlabel, filename in specs:
        values = metrics.filter(pl.col(column) > 0)[column].to_numpy()
        if values.size == 0:
            continue
        lower = max(float(values.min()), 1e-6)
        upper = max(float(values.max()), lower * 1.01)
        if math.isclose(lower, upper):
            bins = [lower * 0.9, upper * 1.1]
        else:
            import numpy as np

            bins = np.logspace(math.log10(lower), math.log10(upper), 70)
        fig, ax = plt.subplots(figsize=(11, 6))
        for split in ("train", "val", "test"):
            split_values = (
                metrics.filter((pl.col("split") == split) & (pl.col(column) > 0))[
                    column
                ].to_numpy()
            )
            if split_values.size:
                ax.hist(
                    split_values,
                    bins=bins,
                    alpha=0.45,
                    label=f"{split} (n={split_values.size:,})",
                    color=colors[split],
                )
        ax.set_xscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Number of stays")
        ax.grid(alpha=0.2)
        ax.legend()
        fig.tight_layout()
        path = output_dir / filename
        fig.savefig(path, dpi=160)
        plt.close(fig)
        output_paths.append(path)
    return output_paths


class FullTokenizedAudit:
    """Validate vocabulary, tensors, timeline ordering, counts, and tracebacks."""

    def __init__(self, config: TokenizedAuditConfig):
        self.config = config
        self.checks: list[dict[str, Any]] = []

    def _check(
        self,
        category: str,
        name: str,
        passed: bool,
        observed: Any,
        expected: Any,
        detail: str = "",
    ) -> None:
        self.checks.append(
            {
                "category": category,
                "check": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
                "detail": detail,
            }
        )

    def _preflight(self) -> tuple[dict[str, Any], pl.DataFrame, Path, list[str]]:
        for path in (
            self.config.tokenized_dir,
            self.config.meds_dir,
            self.config.timeline_index_path,
            self.config.summary_path,
        ):
            if not path.exists():
                raise FileNotFoundError(path)
        summary = json.loads(self.config.summary_path.read_text())
        timeline_index = pl.read_parquet(self.config.timeline_index_path)
        vocab_path = _find_vocab_path(
            self.config.tokenized_dir, str(summary["train_split"])
        )
        vocab = _load_vocab(vocab_path)
        return summary, timeline_index, vocab_path, vocab

    def _audit_vocab(self, vocab_path: Path, vocab: list[str]) -> None:
        match = re.search(r"_t(\d+)\.csv$", vocab_path.name)
        declared_size = int(match.group(1)) if match else -1
        self._check(
            "vocabulary",
            "filename_size_matches_rows",
            declared_size == len(vocab),
            len(vocab),
            declared_size,
        )
        self._check(
            "vocabulary",
            "tokens_are_unique",
            len(vocab) == len(set(vocab)),
            len(set(vocab)),
            len(vocab),
        )
        required = set(QUANTILE_TOKENS) | {"UNK", TIMELINE_END}
        missing = sorted(required - set(vocab))
        self._check(
            "vocabulary",
            "required_shared_tokens_present",
            not missing,
            missing,
            [],
        )
        fused = [
            code
            for code in vocab
            if "//" in code and code.rsplit("//", 1)[-1] in QUANTILE_TOKENS
        ]
        self._check(
            "vocabulary",
            "no_fused_quantile_tokens",
            not fused,
            len(fused),
            0,
        )

    def _audit_shards(
        self,
        summary: dict[str, Any],
        timeline_index: pl.DataFrame,
        vocab: list[str],
    ) -> tuple[pl.DataFrame, dict[str, Counter[str]]]:
        summary_by_split = {
            row["split"]: row for row in summary["split_summaries"]
        }
        code_counts: dict[str, Counter[str]] = {}
        metric_frames: list[pl.DataFrame] = []
        vocab_size = len(vocab)
        end_id = vocab.index(TIMELINE_END)
        quantile_ids = torch.tensor(
            [
                vocab.index(code)
                for code in sorted(QUANTILE_TOKENS)
                if code in vocab
            ],
            dtype=torch.int64,
        )

        for split in summary["splits"]:
            split_index = timeline_index.filter(pl.col("split") == split)
            shards = sorted(
                (self.config.tokenized_dir / split).glob("*.safetensors"),
                key=lambda path: int(path.stem),
            )
            aggregate = torch.zeros(vocab_size, dtype=torch.int64)
            total_tokens = 0
            total_timelines = 0
            split_failures = Counter()

            for shard_path in shards:
                shard_id = int(shard_path.stem)
                tensors = load_file(str(shard_path), device="cpu")
                missing = REQUIRED_TENSORS - set(tensors)
                if missing:
                    split_failures["missing_tensors"] += len(missing)
                    continue
                tokens = tensors["tokens"].to(torch.int64)
                times = tensors["times"].to(torch.int64)
                hadm = tensors["hadm_id"].to(torch.int64)
                icustay = tensors["icustay_id"].to(torch.int64)
                patient_ids = tensors["patient_ids"].to(torch.int64)
                offsets = tensors["patient_offsets"].to(torch.int64)
                n_tokens = int(tokens.numel())
                n_timelines = int(patient_ids.numel())
                total_tokens += n_tokens
                total_timelines += n_timelines

                for tensor in (times, hadm, icustay):
                    if tensor.numel() != n_tokens:
                        split_failures["token_aligned_shape"] += 1
                if offsets.numel() != n_timelines:
                    split_failures["offset_shape"] += 1
                    continue
                if n_tokens:
                    split_failures["token_id_range"] += int(
                        ((tokens < 0) | (tokens >= vocab_size)).sum().item()
                    )
                    aggregate += torch.bincount(tokens, minlength=vocab_size)

                shard_index = split_index.filter(
                    pl.col("shard") == shard_id
                ).sort("token_start")
                expected_offsets = torch.tensor(
                    shard_index["token_start"].to_list(), dtype=torch.int64
                )
                expected_ends = shard_index["token_end"].to_list()
                expected_subjects = torch.tensor(
                    shard_index["subject_id"].to_list(), dtype=torch.int64
                )
                if shard_index.height != n_timelines:
                    split_failures["timeline_index_count"] += abs(
                        shard_index.height - n_timelines
                    )
                    continue
                split_failures["offset_values"] += int(
                    (offsets != expected_offsets).sum().item()
                )
                split_failures["patient_ids"] += int(
                    (patient_ids != expected_subjects).sum().item()
                )
                if expected_ends and int(expected_ends[-1]) != n_tokens:
                    split_failures["final_token_end"] += 1

                if n_tokens:
                    boundaries = torch.zeros(n_tokens, dtype=torch.bool)
                    boundaries[offsets] = True
                    decreasing = (times[1:] < times[:-1]) & ~boundaries[1:]
                    split_failures["timestamp_order"] += int(decreasing.sum().item())

                    q_mask = (
                        torch.isin(tokens, quantile_ids)
                        if quantile_ids.numel()
                        else torch.zeros(n_tokens, dtype=torch.bool)
                    )
                    bad_q_start = int(q_mask[0].item())
                    bad_q_time = int(
                        (q_mask[1:] & (times[1:] != times[:-1])).sum().item()
                    )
                    bad_q_predecessor = int(
                        (q_mask[1:] & torch.isin(tokens[:-1], quantile_ids)).sum().item()
                    )
                    split_failures["quantile_adjacency"] += (
                        bad_q_start + bad_q_time + bad_q_predecessor
                    )

                for row in shard_index.iter_rows(named=True):
                    start = int(row["token_start"])
                    end = int(row["token_end"])
                    if end <= start or end > n_tokens:
                        split_failures["timeline_bounds"] += 1
                        continue
                    if int(tokens[end - 1]) != end_id:
                        split_failures["timeline_end"] += 1
                    if summary["analysis_unit"] == "stay":
                        split_failures["hadm_identity"] += int(
                            (hadm[start:end] != int(row["hadm_id"])).sum().item()
                        )
                        split_failures["icustay_identity"] += int(
                            (
                                icustay[start:end]
                                != int(row["icustay_id"])
                            ).sum().item()
                        )

            nonzero_failures = {
                name: count
                for name, count in split_failures.items()
                if count
            }
            observed = {
                "tokens": total_tokens,
                "timelines": total_timelines,
                **nonzero_failures,
            }
            expected = {
                "tokens": int(summary_by_split[split]["kept_rows"]),
                "timelines": int(summary_by_split[split]["timelines"]),
            }
            self._check(
                "safetensors",
                f"{split}_tensor_integrity",
                total_tokens == expected["tokens"]
                and total_timelines == expected["timelines"]
                and not nonzero_failures,
                observed,
                expected,
            )
            code_counts[split] = Counter(
                {
                    vocab[index]: int(count)
                    for index, count in enumerate(aggregate.tolist())
                    if count
                }
            )
            metrics = split_index.with_columns(
                [
                    (pl.col("token_end") - pl.col("token_start"))
                    .cast(pl.Int64)
                    .alias("token_count"),
                    (
                        (
                            pl.col("end_time").cast(pl.Int64)
                            - pl.col("start_time").cast(pl.Int64)
                        )
                        / 86_400_000_000
                    ).alias("duration_days"),
                ]
            )
            metric_frames.append(metrics)

        return pl.concat(metric_frames, how="vertical_relaxed"), code_counts

    def _audit_code_counts(
        self,
        summary: dict[str, Any],
        actual_counts: dict[str, Counter[str]],
    ) -> None:
        path = self.config.audit_dir / "tokenization_code_counts_by_split.csv"
        recorded = pl.read_csv(path)
        for split in summary["splits"]:
            expected = Counter(
                {
                    str(row["code"]): int(row["count"])
                    for row in recorded.filter(
                        pl.col("split") == split
                    ).iter_rows(named=True)
                }
            )
            mismatched = sum(
                1
                for code in set(expected) | set(actual_counts[split])
                if expected[code] != actual_counts[split][code]
            )
            self._check(
                "counts",
                f"{split}_code_counts_match_tensors",
                mismatched == 0,
                mismatched,
                0,
            )

    def _sample_tracebacks(
        self,
        summary: dict[str, Any],
        timeline_index: pl.DataFrame,
        vocab: list[str],
    ) -> list[dict[str, Any]]:
        stoi = {code: index for index, code in enumerate(vocab)}
        unknown_id = stoi["UNK"]
        trace_rows: list[dict[str, Any]] = []
        tok_config = TokenizationConfig(
            meds_dir=self.config.meds_dir,
            output_dir=self.config.tokenized_dir,
            audit_dir=self.config.audit_dir,
            metadata_dir=self.config.tokenized_dir / "metadata",
            analysis_unit=str(summary["analysis_unit"]),
            medication_atc_depth=str(summary["medication_atc_depth"]),
            unknown_token="UNK",
            time_intervals_spec=DEFAULT_TIME_INTERVALS_SPEC.copy(),
        )

        for split_index, split in enumerate(summary["splits"]):
            candidates = timeline_index.filter(pl.col("split") == split)
            n = min(self.config.samples_per_split, candidates.height)
            selected = candidates.sample(
                n=n,
                seed=self.config.seed + split_index,
                shuffle=True,
            ).sort(["shard", "token_start"])
            if not n:
                continue

            meds_files = sorted(
                (self.config.meds_dir / split / "data").glob("*.parquet")
            )
            scan = pl.scan_parquet(meds_files).select(CORE_INPUT_COLUMNS)
            if summary["analysis_unit"] == "stay":
                scan = scan.filter(
                    pl.col("hadm_id").is_in(selected["hadm_id"].to_list())
                )
            else:
                scan = scan.filter(
                    pl.col("subject_id").is_in(selected["subject_id"].to_list())
                )
            meds = scan.collect(engine="streaming")

            for shard_id, shard_rows in selected.partition_by(
                "shard", as_dict=True, maintain_order=True
            ).items():
                shard_number = int(
                    shard_id[0] if isinstance(shard_id, tuple) else shard_id
                )
                tensors = load_file(
                    str(
                        self.config.tokenized_dir
                        / split
                        / f"{shard_number}.safetensors"
                    ),
                    device="cpu",
                )
                for row in shard_rows.iter_rows(named=True):
                    if summary["analysis_unit"] == "stay":
                        source = meds.filter(
                            (pl.col("subject_id") == int(row["subject_id"]))
                            & (pl.col("hadm_id") == int(row["hadm_id"]))
                        )
                    else:
                        source = meds.filter(
                            pl.col("subject_id") == int(row["subject_id"])
                        )
                    expanded = _expand_events(source, tok_config).df
                    expected_codes = expanded["code"].to_list()
                    expected_ids = [
                        stoi.get(str(code), unknown_id) for code in expected_codes
                    ]
                    expected_times = expanded["time"].cast(pl.Int64).to_list()
                    start = int(row["token_start"])
                    end = int(row["token_end"])
                    actual_ids = tensors["tokens"][start:end].tolist()
                    actual_times = tensors["times"][start:end].tolist()
                    mismatch_index = next(
                        (
                            index
                            for index, pair in enumerate(
                                zip(expected_ids, actual_ids)
                            )
                            if pair[0] != pair[1]
                        ),
                        None,
                    )
                    if mismatch_index is None and len(expected_ids) != len(actual_ids):
                        mismatch_index = min(len(expected_ids), len(actual_ids))
                    time_match = expected_times == actual_times
                    token_match = expected_ids == actual_ids
                    trace_rows.append(
                        {
                            "split": split,
                            "shard": shard_number,
                            "timeline_idx": int(row["timeline_idx"]),
                            "subject_id": int(row["subject_id"]),
                            "hadm_id": int(row["hadm_id"]),
                            "expected_tokens": len(expected_ids),
                            "actual_tokens": len(actual_ids),
                            "tokens_match": token_match,
                            "times_match": time_match,
                            "mismatch_index": mismatch_index,
                            "expected_code_at_mismatch": (
                                expected_codes[mismatch_index]
                                if mismatch_index is not None
                                and mismatch_index < len(expected_codes)
                                else None
                            ),
                            "actual_code_at_mismatch": (
                                vocab[actual_ids[mismatch_index]]
                                if mismatch_index is not None
                                and mismatch_index < len(actual_ids)
                                else None
                            ),
                        }
                    )

        failures = [
            row
            for row in trace_rows
            if not row["tokens_match"] or not row["times_match"]
        ]
        self._check(
            "traceback",
            "sampled_meds_to_tensor_tracebacks",
            not failures,
            len(failures),
            0,
            f"{len(trace_rows)} deterministic timelines checked",
        )
        return trace_rows

    def run(self) -> dict[str, Any]:
        """Run the full audit and write machine-readable and visual outputs."""
        start = time.perf_counter()
        summary, timeline_index, vocab_path, vocab = self._preflight()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self._audit_vocab(vocab_path, vocab)
        metrics, actual_counts = self._audit_shards(
            summary, timeline_index, vocab
        )
        self._audit_code_counts(summary, actual_counts)
        tracebacks = self._sample_tracebacks(summary, timeline_index, vocab)

        metrics.select(
            [
                "split",
                "analysis_unit",
                "shard",
                "timeline_idx",
                "subject_id",
                "hadm_id",
                "token_count",
                "duration_days",
            ]
        ).write_csv(self.config.output_dir / "timeline_metrics.csv")
        pl.DataFrame(tracebacks).write_csv(
            self.config.output_dir / "sampled_meds_token_tracebacks.csv"
        )
        plot_paths = _plot_histograms(metrics, self.config.output_dir)

        failures = [row for row in self.checks if not row["passed"]]
        result = {
            "passed": not failures,
            "check_count": len(self.checks),
            "failure_count": len(failures),
            "vocab_path": str(vocab_path),
            "vocab_size": len(vocab),
            "timelines": metrics.height,
            "samples_checked": len(tracebacks),
            "plots": [str(path) for path in plot_paths],
            "elapsed_seconds": round(time.perf_counter() - start, 1),
            "checks": self.checks,
        }
        (self.config.output_dir / "full_integrity_summary.json").write_text(
            json.dumps(
                result, indent=2, sort_keys=True, default=_json_default
            )
            + "\n"
        )
        _checks_frame(self.checks).write_csv(
            self.config.output_dir / "full_integrity_checks.csv"
        )
        _checks_frame(failures).write_csv(
            self.config.output_dir / "full_integrity_failures.csv"
        )
        if failures and self.config.fail_on_error:
            raise RuntimeError(
                f"Full tokenized integrity audit failed "
                f"{len(failures)}/{len(self.checks)} checks"
            )
        return result
