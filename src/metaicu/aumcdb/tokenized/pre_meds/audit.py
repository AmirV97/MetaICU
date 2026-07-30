"""Full-data source-preservation and split-integrity audit for pre-MEDS.

The audit is read-only. It uses partition metadata for row reconciliation and
streaming, order-independent row fingerprints for content comparisons so the
full Amsterdam numeric table never needs to be materialized in memory.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from metaicu.aumcdb.common.parquet import parquet_exists, parquet_row_count, scan_parquet
from metaicu.aumcdb.common.raw_schema import LARGE_TABLE_RAW_SCHEMAS


SPLITS = ("train", "val", "test")
LARGE_TABLES = ("numericitems", "listitems", "drugitems")
SMALL_TABLES = ("freetextitems", "processitems", "procedureorderitems")
HASH_SEEDS = (20260618, 20260729)


@dataclass(frozen=True)
class PreMedsAuditConfig:
    """Paths for one full pre-MEDS integrity audit."""

    parent_dir: Path
    fail_on_error: bool = True

    @property
    def pre_meds_dir(self) -> Path:
        return self.parent_dir / "data/pre-MEDS"

    @property
    def raw_shards_dir(self) -> Path:
        return self.parent_dir / "data/raw_shards"

    @property
    def metadata_dir(self) -> Path:
        return self.parent_dir / "data/metadata"

    @property
    def build_summary_path(self) -> Path:
        return self.parent_dir / "audits/pre-MEDS/premeds_summary.json"

    @property
    def output_dir(self) -> Path:
        return self.parent_dir / "audits/pre-MEDS/full_integrity"


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _checks_frame(checks: list[dict[str, Any]]) -> pl.DataFrame:
    """Return audit checks with heterogeneous values serialized for CSV."""
    return pl.DataFrame(
        {
            "category": [str(check["category"]) for check in checks],
            "check": [str(check["check"]) for check in checks],
            "passed": [bool(check["passed"]) for check in checks],
            "observed": [
                json.dumps(check["observed"], sort_keys=True, default=_json_default)
                for check in checks
            ],
            "expected": [
                json.dumps(check["expected"], sort_keys=True, default=_json_default)
                for check in checks
            ],
            "detail": [str(check.get("detail", "")) for check in checks],
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


def _fingerprint(frame: pl.LazyFrame, columns: list[str]) -> dict[str, int]:
    """Return count plus two commutative 64-bit row-hash sums."""
    if not columns:
        raise ValueError("Cannot fingerprint an empty column set")
    schema_names = set(frame.collect_schema().names())
    missing = sorted(set(columns) - schema_names)
    if missing:
        raise ValueError(f"Fingerprint columns missing from frame: {missing}")
    expressions: list[pl.Expr] = [pl.len().alias("rows")]
    for index, seed in enumerate(HASH_SEEDS):
        expressions.append(
            pl.struct(columns)
            .hash(seed=seed, seed_1=seed + 1, seed_2=seed + 2, seed_3=seed + 3)
            .sum()
            .alias(f"hash_{index}")
        )
    row = frame.select(expressions).collect(engine="streaming").row(0, named=True)
    return {name: int(value or 0) for name, value in row.items()}


def _grouped_fingerprint(
    frame: pl.LazyFrame,
    columns: list[str],
    group_column: str,
) -> dict[str, dict[str, int]]:
    """Return row fingerprints grouped by one low-cardinality column."""
    expressions: list[pl.Expr] = [pl.len().alias("rows")]
    for index, seed in enumerate(HASH_SEEDS):
        expressions.append(
            pl.struct(columns)
            .hash(seed=seed, seed_1=seed + 1, seed_2=seed + 2, seed_3=seed + 3)
            .sum()
            .alias(f"hash_{index}")
        )
    result = (
        frame.group_by(group_column)
        .agg(expressions)
        .collect(engine="streaming")
        .sort(group_column)
    )
    return {
        str(row[group_column]): {
            name: int(row[name] or 0)
            for name in ("rows", "hash_0", "hash_1")
        }
        for row in result.iter_rows(named=True)
    }


class FullPreMedsAudit:
    """Run row, content, split, and causal-binning integrity checks."""

    def __init__(self, config: PreMedsAuditConfig):
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

    def _load_summary(self) -> dict[str, Any]:
        if not self.config.build_summary_path.is_file():
            raise FileNotFoundError(self.config.build_summary_path)
        return json.loads(self.config.build_summary_path.read_text())

    def _audit_manifest(self) -> None:
        manifest_path = self.config.metadata_dir / "subject_splits.parquet"
        manifest = pl.read_parquet(manifest_path).select(
            pl.col("subject_id").cast(pl.Int64),
            pl.col("split").cast(pl.String),
        )
        duplicate_subjects = (
            manifest.group_by("subject_id").len().filter(pl.col("len") != 1).height
        )
        invalid_splits = manifest.filter(~pl.col("split").is_in(SPLITS)).height
        split_counts = {
            row["split"]: int(row["len"])
            for row in manifest.group_by("split").len().iter_rows(named=True)
        }
        self._check("split_manifest", "unique_subject_assignment", duplicate_subjects == 0, duplicate_subjects, 0)
        self._check("split_manifest", "valid_split_names", invalid_splits == 0, invalid_splits, 0)
        self._check(
            "split_manifest",
            "all_expected_splits_present",
            set(split_counts) == set(SPLITS),
            sorted(split_counts),
            sorted(SPLITS),
        )

        admissions = pl.read_parquet(self.config.pre_meds_dir / "admissions.parquet")
        joined = admissions.select("subject_id", "split").join(
            manifest, on="subject_id", how="left", suffix="_manifest"
        )
        missing = joined.filter(pl.col("split_manifest").is_null()).height
        mismatched = joined.filter(
            pl.col("split_manifest").is_not_null()
            & (pl.col("split") != pl.col("split_manifest"))
        ).height
        self._check("split_manifest", "all_admissions_in_manifest", missing == 0, missing, 0)
        self._check("split_manifest", "admission_split_matches_manifest", mismatched == 0, mismatched, 0)

    def _expected_listitems(self, raw: pl.LazyFrame, labels: list[str]) -> pl.LazyFrame:
        """Apply the production listitems state-change policy to raw source rows."""
        row_order = "__audit_row_order"
        previous = "__audit_previous_valueid"
        is_target = pl.col("item").cast(pl.String).is_in(labels)
        return (
            raw.filter(pl.col("measuredat") != -1899)
            .with_row_index(row_order)
            .sort(["admissionid", "itemid", "measuredat", "valueid", row_order])
            .with_columns(
                pl.col("valueid")
                .shift(1)
                .over(["admissionid", "itemid"])
                .alias(previous)
            )
            .filter(
                ~is_target
                | pl.col(previous).is_null()
                | (pl.col("valueid") != pl.col(previous))
            )
            .sort(row_order)
            .drop([row_order, previous])
        )

    def _audit_large_source_preservation(self, summary: dict[str, Any]) -> None:
        for table in LARGE_TABLES:
            raw_path = self.config.raw_shards_dir / table
            output_path = self.config.pre_meds_dir / table
            raw = scan_parquet(raw_path)
            output = scan_parquet(output_path)
            source_columns = list(LARGE_TABLE_RAW_SCHEMAS[table])
            if table == "numericitems":
                expected = raw.filter(pl.col("measuredat") != -1899)
            elif table == "listitems":
                labels = summary["large_tables"]["listitems"]["state_change_dedup"]["labels"]
                expected = self._expected_listitems(raw, labels)
            else:
                expected = raw

            expected_fp = _fingerprint(expected, source_columns)
            output_fp = _fingerprint(output, source_columns)
            self._check(
                "source_preservation",
                f"{table}_source_columns_fingerprint",
                output_fp == expected_fp,
                output_fp,
                expected_fp,
            )

            recorded = summary["large_tables"][table]["row_counts"]
            self._check(
                "row_accounting",
                f"{table}_summary_matches_output",
                int(recorded["rows_emitted"]) == output_fp["rows"],
                output_fp["rows"],
                int(recorded["rows_emitted"]),
            )

    def _audit_small_row_accounting(self, summary: dict[str, Any]) -> None:
        for table in SMALL_TABLES:
            recorded = summary["small_tables"][table]
            output_path = self.config.pre_meds_dir / f"{table}.parquet"
            output_rows = parquet_row_count(output_path)
            expected_rows = (
                int(recorded["rows_after_patient_filter"])
                - int(recorded["rows_excluded_measuredat_minus_1899"])
                - int(recorded["missing_admission_join_rows"])
            )
            self._check(
                "row_accounting",
                f"{table}_documented_exclusions_reconcile",
                output_rows == expected_rows == int(recorded["rows_emitted"]),
                output_rows,
                expected_rows,
            )

    def _audit_split_outputs(self) -> None:
        tables = ("admissions", "patient") + SMALL_TABLES + LARGE_TABLES
        for table in tables:
            combined_path = (
                self.config.pre_meds_dir / f"{table}.parquet"
                if (self.config.pre_meds_dir / f"{table}.parquet").is_file()
                else self.config.pre_meds_dir / table
            )
            combined = scan_parquet(combined_path)
            schema = combined.collect_schema()
            if "split" not in schema.names():
                self._check("split_outputs", f"{table}_has_split_column", False, False, True)
                continue
            source_columns = [
                column
                for column in (
                    ["subject_id", "hadm_id", "stay_id"]
                    + list(LARGE_TABLE_RAW_SCHEMAS.get(table, {}))
                )
                if column in schema.names() and column != "split"
            ]
            if table in SMALL_TABLES:
                source_columns = [
                    column
                    for column in schema.names()
                    if column
                    not in {
                        "split",
                        "admittedattime",
                        "dischargedattime",
                        "measuredattime",
                        "registeredattime",
                        "updatedattime",
                        "starttime",
                        "stoptime",
                    }
                ]
            if table in {"admissions", "patient"}:
                source_columns = [column for column in schema.names() if column != "split"]

            combined_by_split = _grouped_fingerprint(combined, source_columns, "split")
            for split in SPLITS:
                split_path = (
                    self.config.pre_meds_dir / split / f"{table}.parquet"
                    if (self.config.pre_meds_dir / split / f"{table}.parquet").is_file()
                    else self.config.pre_meds_dir / split / table
                )
                split_fp = (
                    _fingerprint(scan_parquet(split_path), source_columns)
                    if parquet_exists(split_path)
                    else {"rows": 0, "hash_0": 0, "hash_1": 0}
                )
                expected_fp = combined_by_split.get(
                    split, {"rows": 0, "hash_0": 0, "hash_1": 0}
                )
                self._check(
                    "split_outputs",
                    f"{table}_{split}_matches_combined",
                    split_fp == expected_fp,
                    split_fp,
                    expected_fp,
                )

    def _audit_binning(self, summary: dict[str, Any]) -> None:
        inventory = pl.read_csv(self.config.metadata_dir / "hf_numeric_inventory.csv")
        highres_ids = (
            inventory.filter(
                pl.col("is_high_resolution")
                .cast(pl.Boolean, strict=False)
                .fill_null(False)
            )
            .select(pl.col("itemid").cast(pl.Int64))
            .drop_nulls()
            .to_series()
            .to_list()
        )
        self._check("binning", "high_resolution_inventory_size", len(highres_ids) == 117, len(highres_ids), 117)

        passthrough_columns = list(LARGE_TABLE_RAW_SCHEMAS["numericitems"])
        for split in SPLITS:
            raw = scan_parquet(self.config.pre_meds_dir / split / "numericitems")
            binned = scan_parquet(self.config.pre_meds_dir / split / "numericitems_binned")
            raw_passthrough = raw.filter(~pl.col("itemid").is_in(highres_ids))
            output_passthrough = binned.filter(pl.col("binning_method") == "raw_passthrough")
            raw_fp = _fingerprint(raw_passthrough, passthrough_columns)
            output_fp = _fingerprint(output_passthrough, passthrough_columns)
            self._check(
                "binning",
                f"{split}_raw_passthrough_preserved",
                output_fp == raw_fp,
                output_fp,
                raw_fp,
            )

            dense_invalid = int(
                binned.filter(pl.col("binning_method") == "causal_mean")
                .filter(
                    ~pl.col("itemid").is_in(highres_ids)
                    | pl.col("bin_start_ms").is_null()
                    | pl.col("bin_end_ms").is_null()
                    | (pl.col("bin_end_ms") - pl.col("bin_start_ms") != 3_600_000)
                    | (pl.col("admission_relative_ms") != pl.col("bin_end_ms"))
                    | (pl.col("raw_rows_in_bin") < 1)
                )
                .select(pl.len().alias("n"))
                .collect(engine="streaming")["n"][0]
            )
            self._check("binning", f"{split}_causal_bin_contract", dense_invalid == 0, dense_invalid, 0)

            recorded = summary["binned_numericitems"]["splits"][split]
            method_counts = {
                row["binning_method"]: int(row["len"])
                for row in (
                    binned.group_by("binning_method")
                    .len()
                    .collect(engine="streaming")
                    .iter_rows(named=True)
                )
            }
            observed = {
                "output_rows": sum(method_counts.values()),
                "high_resolution_binned_rows": method_counts.get("causal_mean", 0),
                "raw_passthrough_rows": method_counts.get("raw_passthrough", 0),
            }
            expected = {name: int(recorded[name]) for name in observed}
            self._check(
                "binning",
                f"{split}_summary_matches_output",
                observed == expected,
                observed,
                expected,
            )

    def run(self) -> dict[str, Any]:
        start = time.perf_counter()
        summary = self._load_summary()
        self._audit_manifest()
        self._audit_large_source_preservation(summary)
        self._audit_small_row_accounting(summary)
        self._audit_split_outputs()
        self._audit_binning(summary)

        failures = [check for check in self.checks if not check["passed"]]
        result = {
            "dataset": summary.get("dataset"),
            "parent_dir": str(self.config.parent_dir),
            "passed": not failures,
            "check_count": len(self.checks),
            "failure_count": len(failures),
            "elapsed_seconds": round(time.perf_counter() - start, 1),
            "checks": self.checks,
        }
        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "full_integrity_summary.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, default=_json_default) + "\n"
        )
        _checks_frame(self.checks).write_csv(output_dir / "full_integrity_checks.csv")
        _checks_frame(failures).write_csv(output_dir / "full_integrity_failures.csv")
        if failures and self.config.fail_on_error:
            raise RuntimeError(
                f"Full pre-MEDS integrity audit failed {len(failures)}/{len(self.checks)} checks"
            )
        return result
