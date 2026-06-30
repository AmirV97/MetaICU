"""Train-split high-frequency numeric signal inventory.

This transform selects dense numeric source variables that should later be
causal-mean binned before MEDS/tokenization. It is intentionally separate from
binning: inventory is a one-time train-derived artifact, while binning applies
that artifact to train/val/test.
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist
from typing import Any, Sequence

import polars as pl

from aumc_pipeline.utils.parquet_datasets import parquet_exists, scan_parquet


def _unique_preserving_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


@dataclass(frozen=True)
class HFInventoryConfig:
    """Configuration for high-frequency numeric inventory."""

    input_path: Path
    vocab_path: Path
    output_csv_path: Path
    output_json_path: Path
    summary_path: Path
    signal_column: str = "itemid"
    time_column: str = "admission_relative_ms"
    patient_column: str = "patientid"
    grouping_columns: Sequence[str] = field(default_factory=lambda: ("admissionid", "itemid"))
    source_table: str = "numericitems"
    source_table_column: str = "source_table"
    emit_column: str = "emit_as_model_token"
    row_count_column: str = "row_count"
    source_itemid_column: str = "source_itemid"
    source_token_column: str = "source_token"
    harmonized_token_column: str = "harmonized_token"
    source_label_column: str = "source_label"
    source_unit_column: str = "source_unit"
    highres_threshold_minutes: float = 45.0
    confidence_level: float = 0.99
    min_groups: int = 30
    patient_batch_size: int = 500
    candidate_limit: int = 0
    seed: int = 20260601


class RunningNormalCI:
    """Incremental mean/variance state for normal-approximation CIs."""

    def __init__(self) -> None:
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def update(self, value: float) -> None:
        if value is None or not math.isfinite(value):
            return
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def sd(self) -> float | None:
        if self.n < 2:
            return None
        return math.sqrt(self.m2 / (self.n - 1))

    def ci(self, z: float) -> tuple[float | None, float | None]:
        if self.n < 2:
            return None, None
        sd = self.sd or 0.0
        half_width = z * sd / math.sqrt(self.n)
        return self.mean - half_width, self.mean + half_width


class HFInventoryBuilder:
    """Build high-frequency variable inventory from train numericitems."""

    def __init__(self, config: HFInventoryConfig):
        self.config = config
        self.threshold_frequency = 1.0 / config.highres_threshold_minutes
        self.confidence_z = NormalDist().inv_cdf(0.5 + config.confidence_level / 2.0)

    def run(self) -> dict[str, Any]:
        total_start = time.perf_counter()
        cfg = self.config
        if not parquet_exists(cfg.input_path):
            raise FileNotFoundError(f"Missing numeric pre-MEDS input: {cfg.input_path}")
        if not cfg.vocab_path.is_file():
            raise FileNotFoundError(f"Missing supplied vocab: {cfg.vocab_path}")

        candidates = self._load_candidates()
        candidate_ids = [row[cfg.signal_column] for row in candidates]
        states = {signal_id: RunningNormalCI() for signal_id in candidate_ids}
        status = {signal_id: "pending" for signal_id in candidate_ids}
        reason = {signal_id: "" for signal_id in candidate_ids}
        decision_batches: dict[Any, int] = {}
        decision_patients: dict[Any, int] = {}

        batches_processed = 0
        patients_checked = 0
        for patient_batch in self._patient_batches():
            batches_processed += 1
            patients_checked += len(patient_batch)
            active_ids = [sid for sid in candidate_ids if status[sid] == "pending"]
            if not active_ids:
                break
            for signal_id, frequency in self._batch_group_frequencies(patient_batch, active_ids):
                states[signal_id].update(frequency)
            for signal_id in active_ids:
                previous = status[signal_id]
                self._update_status(signal_id, states[signal_id], status, reason)
                if previous == "pending" and status[signal_id] != "pending":
                    decision_batches[signal_id] = batches_processed
                    decision_patients[signal_id] = patients_checked

        for signal_id in candidate_ids:
            if status[signal_id] == "pending":
                status[signal_id] = "skipped_inconclusive"
                reason[signal_id] = "patient sampling ended before CI crossed threshold"
                decision_batches[signal_id] = batches_processed
                decision_patients[signal_id] = patients_checked

        rows = [
            self._result_row(row, states[row[cfg.signal_column]], status, reason, decision_batches, decision_patients)
            for row in candidates
        ]
        out = pl.DataFrame(rows).sort("row_count", descending=True)
        cfg.output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.output_json_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.summary_path.parent.mkdir(parents=True, exist_ok=True)
        out.write_csv(cfg.output_csv_path)
        highres_rows = out.filter(pl.col("is_high_resolution")).to_dicts()
        cfg.output_json_path.write_text(json.dumps(highres_rows, indent=2, default=_json_default) + "\n")

        highres_row_sum = out.filter(pl.col("is_high_resolution")).select(pl.col("row_count").sum()).item()
        summary = {
            "input_path": str(cfg.input_path),
            "vocab_path": str(cfg.vocab_path),
            "output_csv_path": str(cfg.output_csv_path),
            "output_json_path": str(cfg.output_json_path),
            "highres_threshold_minutes": cfg.highres_threshold_minutes,
            "threshold_frequency_1_per_min": self.threshold_frequency,
            "confidence_level": cfg.confidence_level,
            "confidence_z": self.confidence_z,
            "min_groups": cfg.min_groups,
            "patient_batch_size": cfg.patient_batch_size,
            "candidate_limit": cfg.candidate_limit,
            "patients_checked": patients_checked,
            "patient_batches_processed": batches_processed,
            "candidates_evaluated": len(rows),
            "high_resolution_signals": int(out.filter(pl.col("is_high_resolution")).height),
            "high_resolution_vocab_rows": int(highres_row_sum or 0),
            "status_counts": {
                str(r["status"]): int(r["count"])
                for r in out.group_by("status").len(name="count").iter_rows(named=True)
            },
            "top_high_resolution_signals": highres_rows[:25],
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }
        cfg.summary_path.write_text(json.dumps(summary, indent=2, default=_json_default) + "\n")
        return summary

    def _load_candidates(self) -> list[dict[str, Any]]:
        cfg = self.config
        vocab = pl.read_csv(cfg.vocab_path, infer_schema_length=10000)
        required = [
            cfg.source_itemid_column,
            cfg.row_count_column,
            cfg.source_token_column,
            cfg.harmonized_token_column,
        ]
        missing = [col for col in required if col not in vocab.columns]
        if missing:
            raise ValueError(f"Missing required vocab columns for HF inventory: {missing}")

        label_col = cfg.source_label_column if cfg.source_label_column in vocab.columns else cfg.source_token_column
        unit_col = cfg.source_unit_column if cfg.source_unit_column in vocab.columns else cfg.source_token_column
        emit_expr = pl.col(cfg.emit_column).cast(pl.String).str.to_lowercase().is_in(["true", "1", "yes"])
        table_expr = pl.col(cfg.source_table_column) == cfg.source_table

        candidates = (
            vocab.with_columns([
                pl.col(cfg.source_itemid_column).cast(pl.Int64, strict=False).alias(cfg.signal_column),
                pl.col(cfg.row_count_column).cast(pl.Int64, strict=False).fill_null(0).alias("row_count"),
                pl.col(label_col).cast(pl.String).alias("source_label"),
                pl.col(unit_col).cast(pl.String).alias("source_unit"),
            ])
            .filter(table_expr & emit_expr & pl.col(cfg.signal_column).is_not_null() & (pl.col("row_count") > 0))
            .sort("row_count", descending=True)
            .unique(subset=[cfg.signal_column], keep="first", maintain_order=True)
        )
        if cfg.candidate_limit and cfg.candidate_limit > 0:
            candidates = candidates.head(cfg.candidate_limit)
        return candidates.select([
            cfg.signal_column,
            "row_count",
            cfg.source_token_column,
            cfg.harmonized_token_column,
            "source_label",
            "source_unit",
        ]).to_dicts()

    def _patient_batches(self) -> list[list[Any]]:
        cfg = self.config
        patient_ids = (
            scan_parquet(cfg.input_path)
            .select(cfg.patient_column)
            .unique()
            .collect(engine="streaming")[cfg.patient_column]
            .to_list()
        )
        rng = random.Random(cfg.seed)
        rng.shuffle(patient_ids)
        return [patient_ids[i : i + cfg.patient_batch_size] for i in range(0, len(patient_ids), cfg.patient_batch_size)]

    def _batch_group_frequencies(self, patient_batch: list[Any], active_ids: list[Any]) -> list[tuple[Any, float]]:
        cfg = self.config
        group_cols = _unique_preserving_order(list(cfg.grouping_columns) or [cfg.patient_column, cfg.signal_column])
        if cfg.signal_column not in group_cols:
            group_cols.append(cfg.signal_column)
        select_cols = _unique_preserving_order(group_cols + [cfg.patient_column, cfg.time_column])
        df = (
            scan_parquet(cfg.input_path)
            .select(select_cols)
            .filter(pl.col(cfg.patient_column).is_in(patient_batch))
            .filter(pl.col(cfg.signal_column).is_in(active_ids))
            .filter(pl.col(cfg.time_column).is_not_null())
            .collect(engine="streaming")
        )
        if df.is_empty():
            return []
        freqs = (
            df.sort(group_cols + [cfg.time_column])
            .with_columns(pl.col(cfg.time_column).shift(1).over(group_cols).alias("_previous_time"))
            .filter(pl.col("_previous_time").is_not_null())
            .with_columns(
                ((pl.col(cfg.time_column).cast(pl.Float64) - pl.col("_previous_time").cast(pl.Float64)) / 60_000.0)
                .alias("adjacent_interval_minutes")
            )
            .filter(pl.col("adjacent_interval_minutes") > 0)
            .group_by(group_cols)
            .agg(pl.col("adjacent_interval_minutes").mean().alias("mean_interval_minutes"))
            .with_columns((1.0 / pl.col("mean_interval_minutes")).alias("frequency_1_per_min"))
            .select([cfg.signal_column, "frequency_1_per_min"])
        )
        return [(row[cfg.signal_column], float(row["frequency_1_per_min"])) for row in freqs.iter_rows(named=True)]

    def _update_status(
        self,
        signal_id: Any,
        state: RunningNormalCI,
        status: dict[Any, str],
        reason: dict[Any, str],
    ) -> None:
        cfg = self.config
        if status[signal_id] != "pending" or state.n < cfg.min_groups:
            return
        lower, upper = state.ci(self.confidence_z)
        if lower is not None and upper is not None and lower > self.threshold_frequency and upper > self.threshold_frequency:
            status[signal_id] = "high_resolution_confident"
            reason[signal_id] = "both CI bounds exceed 1/highres_threshold_minutes"
        elif lower is not None and upper is not None and lower < self.threshold_frequency and upper < self.threshold_frequency:
            status[signal_id] = "skipped_low_frequency_confident"
            reason[signal_id] = "both CI bounds are below 1/highres_threshold_minutes"

    def _result_row(
        self,
        candidate: dict[str, Any],
        state: RunningNormalCI,
        status: dict[Any, str],
        reason: dict[Any, str],
        decision_batches: dict[Any, int],
        decision_patients: dict[Any, int],
    ) -> dict[str, Any]:
        cfg = self.config
        signal_id = candidate[cfg.signal_column]
        lower, upper = state.ci(self.confidence_z)
        return {
            cfg.signal_column: signal_id,
            "row_count": int(candidate.get("row_count") or 0),
            "source_token": candidate.get(cfg.source_token_column, ""),
            "harmonized_token": candidate.get(cfg.harmonized_token_column, ""),
            "source_label": candidate.get("source_label", ""),
            "source_unit": candidate.get("source_unit", ""),
            "sampled_group_count": int(state.n),
            "patient_batches_until_decision": int(decision_batches.get(signal_id, 0)),
            "patients_checked_until_decision": int(decision_patients.get(signal_id, 0)),
            "mean_frequency_1_per_min": state.mean if state.n else None,
            "ci_lower_frequency_1_per_min": lower,
            "ci_upper_frequency_1_per_min": upper,
            "threshold_frequency_1_per_min": self.threshold_frequency,
            "is_high_resolution": status[signal_id].startswith("high_resolution"),
            "status": status[signal_id],
            "decision_reason": reason[signal_id],
        }
