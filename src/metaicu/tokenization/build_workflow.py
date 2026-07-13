"""Split-aware MEDS -> ETHOS-style tokenized timeline workflow.

The semantic vocabulary is already resolved before MEDS. This module builds the
model token vocabulary from train MEDS only, applies it unchanged to all splits,
and writes safetensors with one timeline per configured analysis unit.
"""

from __future__ import annotations

import json
import math
import shutil
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

import polars as pl
import torch
from safetensors.torch import save_file

from metaicu.tokenization.vocabulary import TokenVocabulary, build_lexicographic_vocab

TIMELINE_END = "TIMELINE_END"
DEFAULT_UNKNOWN_TOKEN = "UNK"
CORE_INPUT_COLUMNS = ["subject_id", "time", "code", "numeric_value", "text_value", "hadm_id", "icustay_id"]


DEFAULT_TIME_INTERVALS_SPEC: dict[str, dict[str, int]] = {
    "5m-15m": {"minutes": 5},
    "15m-45m": {"minutes": 15},
    "45m-1h15m": {"minutes": 45},
    "1h15m-2h": {"hours": 1, "minutes": 15},
    "2h-3h": {"hours": 2},
    "3h-5h": {"hours": 3},
    "5h-8h": {"hours": 5},
    "8h-12h": {"hours": 8},
    "12h-18h": {"hours": 12},
    "18h-1d": {"hours": 18},
    "1d-2d": {"days": 1},
    "2d-4d": {"days": 2},
    "4d-7d": {"days": 4},
    "7d-12d": {"days": 7},
    "12d-20d": {"days": 12},
    "20d-30d": {"days": 20},
    "30d-2mt": {"days": 30},
    "2mt-6mt": {"days": 60},
    "=6mt": {"days": 180},
}


@dataclass(frozen=True)
class TokenizationConfig:
    """Inputs, outputs, and runtime tokenization policy."""

    meds_dir: Path
    output_dir: Path
    audit_dir: Path
    metadata_dir: Path
    splits: tuple[str, ...] = ("train", "val", "test")
    train_split: str = "train"
    max_rows: int | None = None
    max_timelines_per_shard: int = 1000
    medication_atc_depth: str = "full"
    analysis_unit: str = "stay"
    unknown_token: str = DEFAULT_UNKNOWN_TOKEN
    overwrite: bool = False
    time_intervals_spec: dict[str, dict[str, int]] = field(default_factory=lambda: DEFAULT_TIME_INTERVALS_SPEC.copy())


@dataclass
class ExpandedEvents:
    """Expanded token stream plus enough metadata to write tensors and audits."""

    df: pl.DataFrame
    interval_durations_us: dict[str, list[int]]
    original_rows: int


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def _log(msg: str) -> None:
    print(f"[tokenization] {msg}", flush=True)


def _elapsed(start: float) -> str:
    return f"{time.perf_counter() - start:.1f}s"


def _parse_interval_spec(spec: dict[str, dict[str, int]]) -> dict[str, int]:
    return {label: int(timedelta(**kwargs).total_seconds() * 1_000_000) for label, kwargs in spec.items()}


def _meds_split_data_files(meds_dir: Path, split: str) -> list[Path]:
    data_dir = meds_dir / split / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"MEDS split data directory not found: {data_dir}")
    files = sorted(data_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No MEDS parquet files found in: {data_dir}")
    return files


def _timeline_group_columns(config: TokenizationConfig) -> list[str]:
    """Return the columns defining one tokenized timeline."""
    if config.analysis_unit == "stay":
        return ["subject_id", "hadm_id"]
    if config.analysis_unit == "subject":
        return ["subject_id"]
    raise ValueError("analysis_unit must be 'stay' or 'subject'")


def _event_sort_columns(config: TokenizationConfig) -> list[str]:
    """Return deterministic event ordering for the chosen analysis unit."""
    if config.analysis_unit == "stay":
        return ["subject_id", "hadm_id", "time", "code"]
    if config.analysis_unit == "subject":
        return ["subject_id", "time", "hadm_id", "code"]
    raise ValueError("analysis_unit must be 'stay' or 'subject'")


def _within_timeline_sort_columns(config: TokenizationConfig) -> list[str]:
    if config.analysis_unit == "stay":
        return ["time", "code"]
    return ["time", "hadm_id", "code"]


def _load_split_events(config: TokenizationConfig, split: str) -> pl.DataFrame:
    files = _meds_split_data_files(config.meds_dir, split)
    scan = pl.scan_parquet(files).select(CORE_INPUT_COLUMNS)
    if config.max_rows is not None:
        scan = scan.limit(config.max_rows)
    return (
        scan.drop_nulls(["subject_id", "hadm_id", "time", "code"])
        .with_columns([
            pl.col("subject_id").cast(pl.Int64),
            pl.col("hadm_id").cast(pl.Int64),
            pl.col("icustay_id").cast(pl.Int64, strict=False),
            pl.col("time").cast(pl.Datetime("us")),
            pl.col("code").cast(pl.String),
        ])
        .sort(_event_sort_columns(config))
        .collect(engine="streaming")
    )


def _transform_medication_code(code: str, medication_atc_depth: str) -> str:
    if not code.startswith("MEDICATION//"):
        return code
    if medication_atc_depth == "full":
        return code
    depth = int(medication_atc_depth)
    pieces = code.split("//")
    if len(pieces) <= 1:
        return code
    keep = min(len(pieces), 1 + depth)
    return "//".join(pieces[:keep])


def _interval_tokens_for_gap(gap_us: int, interval_bounds: dict[str, int]) -> tuple[list[str], list[int]]:
    """Return ETHOS-style interval token(s) for one positive time gap."""

    if gap_us <= 0:
        return [], []
    ordered = sorted(interval_bounds.items(), key=lambda kv: kv[1], reverse=True)
    largest_label, largest_us = ordered[0]
    if gap_us >= largest_us:
        repeats = max(1, int(round(gap_us / largest_us)))
        duration = max(1, int(round(gap_us / repeats)))
        return [largest_label] * repeats, [duration] * repeats
    for label, lower_us in ordered[1:]:
        if gap_us >= lower_us:
            return [label], [gap_us]
    return [], []


def _expand_events(df: pl.DataFrame, config: TokenizationConfig) -> ExpandedEvents:
    """Apply medication-depth policy and inject interval/end tokens per ICU stay."""

    if df.is_empty():
        schema = {
            "subject_id": pl.Int64,
            "hadm_id": pl.Int64,
            "icustay_id": pl.Int64,
            "time": pl.Datetime("us"),
            "code": pl.String,
        }
        return ExpandedEvents(pl.DataFrame(schema=schema), {}, 0)

    interval_bounds = _parse_interval_spec(config.time_intervals_spec)
    rows: list[dict[str, Any]] = []
    interval_durations: dict[str, list[int]] = defaultdict(list)

    group_cols = _timeline_group_columns(config)
    sort_cols = _within_timeline_sort_columns(config)
    for _, stay in df.partition_by(group_cols, as_dict=True, maintain_order=True).items():
        stay = stay.sort(sort_cols)
        previous_time_us: int | None = None
        stay_rows = stay.select(["subject_id", "hadm_id", "icustay_id", "time", "code"]).iter_rows(named=True)
        buffered = list(stay_rows)
        for idx, row in enumerate(buffered):
            time_us = int(row["time"].timestamp() * 1_000_000)
            if previous_time_us is not None:
                labels, durations = _interval_tokens_for_gap(time_us - previous_time_us, interval_bounds)
                for label, duration in zip(labels, durations):
                    interval_durations[label].append(duration)
                    rows.append({**row, "code": label})
            rows.append({
                **row,
                "code": _transform_medication_code(str(row["code"]), config.medication_atc_depth),
            })
            if idx == len(buffered) - 1:
                rows.append({**row, "code": TIMELINE_END})
            previous_time_us = time_us

    return ExpandedEvents(pl.DataFrame(rows), dict(interval_durations), df.height)


def _build_train_expanded(config: TokenizationConfig) -> tuple[ExpandedEvents, TokenVocabulary, Counter[str]]:
    train = _expand_events(_load_split_events(config, config.train_split), config)
    code_counts = Counter(train.df["code"].to_list()) if not train.df.is_empty() else Counter()
    vocab_codes = list(code_counts)
    if config.unknown_token:
        vocab_codes.append(config.unknown_token)
    vocab = build_lexicographic_vocab(vocab_codes)
    return train, vocab, code_counts


def _write_vocab_files(
    config: TokenizationConfig,
    vocab: TokenVocabulary,
    train_code_counts: Counter[str],
    interval_durations: dict[str, list[int]],
) -> dict[str, Path]:
    train_dir = config.output_dir / config.train_split
    vocab_path = vocab.dump(train_dir)
    pl.DataFrame(
        [{"code": code, "count": count} for code, count in train_code_counts.most_common()]
    ).write_csv(train_dir / "code_counts.csv")
    interval_stats = _interval_stats(interval_durations)
    interval_path = train_dir / "interval_estimates.json"
    interval_path.write_text(json.dumps(interval_stats, indent=2) + "\n")

    for split in config.splits:
        if split == config.train_split:
            continue
        split_dir = config.output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(vocab_path, split_dir / vocab_path.name)
        shutil.copy(train_dir / "vocab_decoded.csv", split_dir / "vocab_decoded.csv")
        shutil.copy(interval_path, split_dir / "interval_estimates.json")

    return {"vocab": vocab_path, "intervals": interval_path, "code_counts": train_dir / "code_counts.csv"}


def _quantile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return int(ordered[idx])


def _interval_stats(interval_durations: dict[str, list[int]]) -> dict[str, dict[str, int]]:
    stats = {"min": {}, "q1": {}, "mean": {}, "median": {}, "q3": {}, "max": {}}
    for code, durations in sorted(interval_durations.items()):
        if not durations:
            continue
        stats["min"][code] = int(min(durations))
        stats["q1"][code] = _quantile(durations, 0.25)
        stats["mean"][code] = int(round(sum(durations) / len(durations)))
        stats["median"][code] = _quantile(durations, 0.50)
        stats["q3"][code] = _quantile(durations, 0.75)
        stats["max"][code] = int(max(durations))
    return stats


def _prepare_outputs(config: TokenizationConfig) -> None:
    if config.output_dir.exists():
        if not config.overwrite:
            raise FileExistsError(f"Tokenized output exists: {config.output_dir}. Set run.overwrite=true.")
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.audit_dir.mkdir(parents=True, exist_ok=True)
    config.metadata_dir.mkdir(parents=True, exist_ok=True)


def _timeline_groups(df: pl.DataFrame, config: TokenizationConfig) -> Iterable[pl.DataFrame]:
    group_cols = _timeline_group_columns(config)
    sort_cols = _within_timeline_sort_columns(config)
    for _, group in df.partition_by(group_cols, as_dict=True, maintain_order=True).items():
        yield group.sort(sort_cols)


def _timeline_metadata(group: pl.DataFrame, split: str, shard_idx: int, timeline_idx: int, token_start: int, token_end: int, config: TokenizationConfig) -> dict[str, Any]:
    """Build one row of timeline metadata for stay- or subject-level outputs."""
    subject_id = int(group["subject_id"][0])
    hadm_ids = sorted({int(v) for v in group["hadm_id"].drop_nulls().to_list()})
    icustay_ids = sorted({int(v) for v in group["icustay_id"].drop_nulls().to_list()})
    if config.analysis_unit == "stay":
        hadm_id = hadm_ids[0] if hadm_ids else -1
        icustay_id = icustay_ids[0] if icustay_ids else -1
    else:
        hadm_id = -1
        icustay_id = -1
    return {
        "split": split,
        "analysis_unit": config.analysis_unit,
        "shard": shard_idx,
        "timeline_idx": timeline_idx,
        "subject_id": subject_id,
        "hadm_id": hadm_id,
        "icustay_id": icustay_id,
        "hadm_ids": hadm_ids,
        "icustay_ids": icustay_ids,
        "hadm_ids_text": ",".join(str(v) for v in hadm_ids),
        "icustay_ids_text": ",".join(str(v) for v in icustay_ids),
        "n_admissions": len(hadm_ids),
        "token_start": token_start,
        "token_end": token_end,
        "start_time": group["time"][0],
        "end_time": group["time"][-1],
    }


def _write_split_safetensors(
    split: str,
    expanded: ExpandedEvents,
    vocab: TokenVocabulary,
    config: TokenizationConfig,
) -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
    split_dir = config.output_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)
    stoi = vocab.stoi
    unknown = Counter(code for code in expanded.df["code"].to_list() if code not in stoi) if not expanded.df.is_empty() else Counter()
    if unknown:
        if not config.unknown_token or config.unknown_token not in stoi:
            raise ValueError("unknown_token must be present in the token vocabulary when unknown codes exist")
        kept = expanded.df.with_columns(
            pl.when(pl.col("code").is_in(list(stoi)))
            .then(pl.col("code"))
            .otherwise(pl.lit(config.unknown_token))
            .alias("code")
        )
    else:
        kept = expanded.df
    kept_counts = Counter(kept["code"].to_list()) if not kept.is_empty() else Counter()
    pl.DataFrame(
        [{"code": code, "count": count} for code, count in kept_counts.most_common()],
        schema={"code": pl.String, "count": pl.Int64},
    ).write_csv(split_dir / "code_counts.csv")

    timeline_records: list[dict[str, Any]] = []
    shard_idx = 0
    shard_groups: list[pl.DataFrame] = []

    def flush() -> None:
        nonlocal shard_idx, shard_groups, timeline_records
        if not shard_groups:
            return
        rows = []
        patient_ids = []
        offsets = []
        token_offset = 0
        for local_idx, group in enumerate(shard_groups):
            offsets.append(token_offset)
            subject_id = int(group["subject_id"][0])
            patient_ids.append(subject_id)
            token_start = token_offset
            for row in group.iter_rows(named=True):
                rows.append(row)
                token_offset += 1
            timeline_records.append(
                _timeline_metadata(
                    group=group,
                    split=split,
                    shard_idx=shard_idx,
                    timeline_idx=len(timeline_records),
                    token_start=token_start,
                    token_end=token_offset,
                    config=config,
                )
            )

        out_df = pl.DataFrame(rows)
        tensors = {
            "tokens": torch.tensor([stoi[code] for code in out_df["code"].to_list()], dtype=torch.int64),
            "times": torch.tensor(out_df["time"].cast(pl.Int64).to_list(), dtype=torch.int64),
            "patient_ids": torch.tensor(patient_ids, dtype=torch.int64),
            "patient_offsets": torch.tensor(offsets, dtype=torch.int64),
            "hadm_id": torch.tensor(out_df["hadm_id"].to_list(), dtype=torch.int64),
            "icustay_id": torch.tensor(out_df["icustay_id"].fill_null(-1).to_list(), dtype=torch.int64),
        }
        shard_path = split_dir / f"{shard_idx}.safetensors"
        shard_path.parent.mkdir(parents=True, exist_ok=True)
        save_file(tensors, str(shard_path))
        shard_idx += 1
        shard_groups = []

    for group in _timeline_groups(kept, config):
        shard_groups.append(group)
        if len(shard_groups) >= config.max_timelines_per_shard:
            flush()
    flush()

    return timeline_records, kept_counts, unknown


def _write_codes_metadata(config: TokenizationConfig, vocab: TokenVocabulary, train_counts: Counter[str]) -> Path:
    rows = [
        {
            "code": code,
            "description": code,
            "parent_codes": _parent_codes(code),
            "token_id": idx,
            "train_count": int(train_counts.get(code, 0)),
        }
        for idx, code in enumerate(vocab.codes)
    ]
    out = config.metadata_dir / "codes.parquet"
    pl.DataFrame(rows).write_parquet(out)
    return out


def _parent_codes(code: str) -> list[str]:
    parts = code.split("//")
    if len(parts) <= 2:
        return []
    return ["//".join(parts[:i]) for i in range(2, len(parts))]


def _write_audits(
    config: TokenizationConfig,
    split_summaries: list[dict[str, Any]],
    timeline_rows: list[dict[str, Any]],
    unknown_rows: list[dict[str, Any]],
    token_counts: list[dict[str, Any]],
) -> Path:
    audit = config.audit_dir
    timeline_df = pl.DataFrame(timeline_rows)
    timeline_df.write_parquet(config.metadata_dir / "timeline_index.parquet")
    timeline_df.drop(["hadm_ids", "icustay_ids"], strict=False).write_csv(audit / "tokenization_timeline_index.csv")
    pl.DataFrame(unknown_rows).write_csv(audit / "tokenization_unknown_codes.csv")
    pl.DataFrame(token_counts).write_csv(audit / "tokenization_code_counts_by_split.csv")

    seq_df = pl.DataFrame(timeline_rows)
    if not seq_df.is_empty():
        seq_df = seq_df.with_columns((pl.col("token_end") - pl.col("token_start")).alias("token_count"))
        seq_df.select(["split", "analysis_unit", "subject_id", "hadm_id", "n_admissions", "token_count"]).write_csv(
            audit / "tokenization_sequence_lengths.csv"
        )
    else:
        pl.DataFrame(
            schema={
                "split": pl.String,
                "analysis_unit": pl.String,
                "subject_id": pl.Int64,
                "hadm_id": pl.Int64,
                "n_admissions": pl.Int64,
                "token_count": pl.Int64,
            }
        ).write_csv(audit / "tokenization_sequence_lengths.csv")

    summary = {
        "splits": list(config.splits),
        "train_split": config.train_split,
        "output_dir": str(config.output_dir),
        "metadata_dir": str(config.metadata_dir),
        "meds_dir": str(config.meds_dir),
        "medication_atc_depth": config.medication_atc_depth,
        "analysis_unit": config.analysis_unit,
        "max_timelines_per_shard": config.max_timelines_per_shard,
        "split_summaries": split_summaries,
    }
    summary_path = audit / "tokenization_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, cls=_JsonEncoder) + "\n")
    return summary_path


def write_tokenized_outputs(config: TokenizationConfig) -> dict[str, Path]:
    """Build train-frozen token vocabulary and write split safetensors."""

    total_start = time.perf_counter()
    if config.train_split not in set(config.splits):
        raise ValueError("train_split must be included in splits")
    if config.medication_atc_depth != "full":
        depth = int(config.medication_atc_depth)
        if depth < 1:
            raise ValueError("medication_atc_depth must be 'full' or a positive integer")
    if config.max_timelines_per_shard < 1:
        raise ValueError("max_timelines_per_shard must be >= 1")
    if config.analysis_unit not in {"stay", "subject"}:
        raise ValueError("analysis_unit must be 'stay' or 'subject'")

    _prepare_outputs(config)
    _log("1/4 building train-frozen token vocabulary")
    train_expanded, vocab, train_counts = _build_train_expanded(config)
    vocab_paths = _write_vocab_files(config, vocab, train_counts, train_expanded.interval_durations_us)
    codes_metadata = _write_codes_metadata(config, vocab, train_counts)
    _log(f"  vocab size={len(vocab):,} -> {vocab_paths['vocab']}")

    split_summaries: list[dict[str, Any]] = []
    timeline_rows: list[dict[str, Any]] = []
    unknown_rows: list[dict[str, Any]] = []
    token_count_rows: list[dict[str, Any]] = []

    for split in config.splits:
        step = time.perf_counter()
        _log(f"2/4 tokenizing split={split}")
        expanded = train_expanded if split == config.train_split else _expand_events(_load_split_events(config, split), config)
        split_timeline_rows, kept_counts, unknown_counts = _write_split_safetensors(split, expanded, vocab, config)
        timeline_rows.extend(split_timeline_rows)
        unknown_rows.extend([
            {"split": split, "code": code, "mapped_to": config.unknown_token, "mapped_rows": count}
            for code, count in unknown_counts.most_common()
        ])
        token_count_rows.extend([
            {"split": split, "code": code, "count": count}
            for code, count in kept_counts.most_common()
        ])
        split_summaries.append({
            "split": split,
            "input_rows": int(expanded.original_rows),
            "expanded_rows": int(expanded.df.height),
            "kept_rows": int(sum(kept_counts.values())),
            "unknown_mapped_rows": int(sum(unknown_counts.values())),
            "unknown_dropped_rows": 0,
            "timelines": int(len(split_timeline_rows)),
            "safetensor_shards": int(math.ceil(len(split_timeline_rows) / config.max_timelines_per_shard)) if split_timeline_rows else 0,
            "elapsed_seconds": round(time.perf_counter() - step, 1),
        })
        _log(f"  {len(split_timeline_rows):,} timelines, {sum(kept_counts.values()):,} tokens [{_elapsed(step)}]")

    _log("3/4 writing metadata and audits")
    summary_path = _write_audits(config, split_summaries, timeline_rows, unknown_rows, token_count_rows)

    _log(f"4/4 done in {_elapsed(total_start)} -> {summary_path}")
    outputs = {
        "summary": summary_path,
        "vocab": vocab_paths["vocab"],
        "codes_metadata": codes_metadata,
        "timeline_index": config.metadata_dir / "timeline_index.parquet",
    }
    for split in config.splits:
        outputs[f"{split}_dir"] = config.output_dir / split
    return outputs
