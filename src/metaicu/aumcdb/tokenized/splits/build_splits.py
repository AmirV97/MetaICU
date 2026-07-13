"""Build deterministic subject-level train/val/test splits.

The split artifact is intentionally small and stable: one row per Amsterdam
``patientid`` with two columns, ``subject_id`` and ``split``. Downstream stages
join this manifest by subject_id/patientid and must never split admissions from
one patient across multiple cohorts.
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl


@dataclass(frozen=True)
class SplitConfig:
    """Configuration for one subject-split generation run."""

    raw_data_dir: Path
    metadata_dir: Path
    split_path: Path
    train_frac: float = 0.8
    val_frac: float = 0.1
    test_frac: float = 0.1
    seed: int = 20260618
    train_name: str = "train"
    val_name: str = "val"
    test_name: str = "test"
    overwrite: bool = False


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def _log(message: str) -> None:
    print(f"[build_split] {message}", flush=True)


def _elapsed(start: float) -> str:
    return f"{time.perf_counter() - start:.1f}s"


def _validate_fractions(train_frac: float, val_frac: float, test_frac: float) -> None:
    fracs = [train_frac, val_frac, test_frac]
    if any(frac < 0 for frac in fracs):
        raise ValueError("split fractions must be non-negative")
    total = sum(fracs)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(f"split fractions must sum to 1.0; got {total}")
    if total <= 0:
        raise ValueError("at least one split fraction must be > 0")


def _largest_remainder_counts(n: int, fractions: list[float]) -> list[int]:
    raw = [n * frac for frac in fractions]
    counts = [math.floor(value) for value in raw]
    remainder = n - sum(counts)
    order = sorted(
        range(len(fractions)),
        key=lambda idx: (raw[idx] - counts[idx], -idx),
        reverse=True,
    )
    for idx in order[:remainder]:
        counts[idx] += 1
    return counts


def read_subject_ids(raw_data_dir: Path) -> list[int]:
    """Read unique Amsterdam patient IDs from raw admissions.csv."""
    admissions_path = raw_data_dir / "admissions.csv"
    if not admissions_path.is_file():
        raise FileNotFoundError(f"Missing admissions.csv: {admissions_path}")
    raw = pd.read_csv(admissions_path, encoding="latin1", usecols=["patientid"])
    subject_ids = (
        pd.to_numeric(raw["patientid"], errors="coerce")
        .dropna()
        .astype("int64")
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    if not subject_ids:
        raise ValueError(f"No patientid values found in {admissions_path}")
    return subject_ids


def assign_subject_splits(
    subject_ids: list[int],
    train_frac: float,
    val_frac: float,
    test_frac: float,
    seed: int,
    train_name: str = "train",
    val_name: str = "val",
    test_name: str = "test",
) -> pd.DataFrame:
    """Return deterministic subject-level split assignments."""
    _validate_fractions(train_frac, val_frac, test_frac)
    names = [train_name, val_name, test_name]
    if len(set(names)) != 3:
        raise ValueError(f"split names must be unique; got {names}")

    shuffled = list(subject_ids)
    random.Random(seed).shuffle(shuffled)
    counts = _largest_remainder_counts(
        len(shuffled), [train_frac, val_frac, test_frac]
    )

    rows: list[dict[str, object]] = []
    start = 0
    for name, count in zip(names, counts):
        for subject_id in shuffled[start : start + count]:
            rows.append({"subject_id": int(subject_id), "split": name})
        start += count

    out = pd.DataFrame(rows, columns=["subject_id", "split"])
    return out.sort_values("subject_id").reset_index(drop=True)


def summarize_splits(
    split_df: pd.DataFrame,
    config: SplitConfig,
    elapsed_seconds: float,
) -> dict[str, Any]:
    counts = split_df["split"].value_counts().sort_index().to_dict()
    return {
        "raw_data_dir": str(config.raw_data_dir),
        "split_path": str(config.split_path),
        "seed": config.seed,
        "requested_fractions": {
            config.train_name: config.train_frac,
            config.val_name: config.val_frac,
            config.test_name: config.test_frac,
        },
        "subject_count": int(len(split_df)),
        "split_counts": {str(key): int(value) for key, value in counts.items()},
        "split_fractions_observed": {
            str(key): (float(value) / float(len(split_df)))
            for key, value in counts.items()
        },
        "elapsed_seconds": round(elapsed_seconds, 1),
    }


def write_subject_splits(config: SplitConfig) -> dict[str, Path]:
    """Build and write subject split parquet/csv plus a JSON summary."""
    total_start = time.perf_counter()
    _validate_fractions(config.train_frac, config.val_frac, config.test_frac)

    if config.split_path.exists() and not config.overwrite:
        raise FileExistsError(
            f"{config.split_path} already exists. Set run.overwrite=true to replace."
        )

    config.metadata_dir.mkdir(parents=True, exist_ok=True)
    config.split_path.parent.mkdir(parents=True, exist_ok=True)

    _log(f"reading subjects from {config.raw_data_dir / 'admissions.csv'}")
    subject_ids = read_subject_ids(config.raw_data_dir)
    _log(f"assigning {len(subject_ids):,} subjects with seed={config.seed}")
    split_df = assign_subject_splits(
        subject_ids=subject_ids,
        train_frac=config.train_frac,
        val_frac=config.val_frac,
        test_frac=config.test_frac,
        seed=config.seed,
        train_name=config.train_name,
        val_name=config.val_name,
        test_name=config.test_name,
    )

    pl.from_pandas(split_df).with_columns(
        pl.col("subject_id").cast(pl.Int64),
        pl.col("split").cast(pl.String),
    ).write_parquet(config.split_path)

    csv_path = config.split_path.with_suffix(".csv")
    split_df.to_csv(csv_path, index=False)

    summary_path = config.metadata_dir / "subject_splits_summary.json"
    summary = summarize_splits(split_df, config, time.perf_counter() - total_start)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, cls=_JsonEncoder) + "\n"
    )
    _log(f"done in {_elapsed(total_start)} -> {config.split_path}")

    return {
        "subject_splits": config.split_path,
        "subject_splits_csv": csv_path,
        "summary": summary_path,
    }
