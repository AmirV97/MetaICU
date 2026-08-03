"""Post-write integrity checks shared by AUMCdb and MIMIC-IV hourly grids."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl


def audit_grid_dataset(
    output_dir: Path,
    audit_dir: Path,
    expected_columns: list[str],
    subject_column: str,
) -> Path:
    """Validate written shards and sidecars, write a JSON audit, and fail on violations."""
    metadata = pl.read_csv(output_dir / "metadata.csv")
    schema = json.loads((output_dir / "feature_schema.json").read_text())
    tte = json.loads((output_dir / "tte_targets.json").read_text())
    encoding_path = output_dir / "categorical_encoding.csv"
    encoding = pl.read_csv(encoding_path) if encoding_path.exists() else None
    failures: list[str] = []
    shard_paths = sorted(output_dir.glob("*/*.parquet"))
    if not shard_paths:
        failures.append("no parquet shards written")

    actual_relative = {str(path.relative_to(output_dir)) for path in shard_paths}
    referenced = set(metadata["shard_file"].drop_nulls().to_list())
    if actual_relative != referenced:
        failures.append(
            f"metadata/shard-file mismatch: unreferenced={sorted(actual_relative - referenced)}, "
            f"missing={sorted(referenced - actual_relative)}"
        )

    split_subjects = {
        split: set(metadata.filter(pl.col("split") == split)[subject_column].to_list())
        for split in ("train", "val", "test")
    }
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap = split_subjects[left] & split_subjects[right]
        if overlap:
            failures.append(f"{left}/{right} subject overlap: {len(overlap)}")

    one_hot_groups: dict[str, list[str]] = {}
    if encoding is not None:
        for row in encoding.iter_rows(named=True):
            one_hot_groups.setdefault(row["feature"], []).append(row["column_name"])

    observed_counts: dict[int, int] = {}
    total_rows = 0
    for split in ("train", "val", "test"):
        split_paths = sorted((output_dir / split).glob("*.parquet"), key=lambda path: int(path.stem))
        expected_names = [f"{index}.parquet" for index in range(len(split_paths))]
        if [path.name for path in split_paths] != expected_names:
            failures.append(f"{split} shard numbering is not contiguous from zero")
        for path in split_paths:
            frame = pl.read_parquet(path)
            total_rows += frame.height
            if frame.columns != expected_columns:
                failures.append(f"{path.relative_to(output_dir)} column order differs from canonical schema")
                continue
            keys = frame.select(["admissionid", "hour"])
            if keys.n_unique() != frame.height:
                failures.append(f"{path.relative_to(output_dir)} has duplicate (admissionid,hour) keys")
            per_admission = frame.group_by("admissionid").agg(
                pl.len().alias("rows"),
                pl.col("hour").n_unique().alias("unique_hours"),
                pl.col("hour").min().alias("min_hour"),
                pl.col("hour").max().alias("max_hour"),
            )
            bad_hours = per_admission.filter(
                (pl.col("rows") != pl.col("unique_hours"))
                | (pl.col("min_hour") != 0)
                | (pl.col("max_hour") != pl.col("rows") - 1)
            )
            if bad_hours.height:
                failures.append(f"{path.relative_to(output_dir)} has {bad_hours.height} non-dense admission timelines")
            observed_counts.update(dict(zip(per_admission["admissionid"].to_list(), per_admission["rows"].to_list())))
            for column in (name for name in frame.columns if name.endswith("__observed")):
                values = frame[column].drop_nulls()
                invalid = len(values.filter(~values.is_in([0, 1])))
                if invalid:
                    failures.append(f"{path.relative_to(output_dir)}:{column} has {invalid} non-binary values")
            for feature, columns in one_hot_groups.items():
                present = [column for column in columns if column in frame.columns]
                if present and frame.select(pl.sum_horizontal(present).ne(1).sum()).item():
                    failures.append(f"{path.relative_to(output_dir)}:{feature} one-hot rows are not exclusive")
            for column, dtype in frame.schema.items():
                if dtype.is_float() and (~frame[column].drop_nulls().is_finite()).sum():
                    failures.append(f"{path.relative_to(output_dir)}:{column} contains non-finite values")

    expected_counts = dict(zip(metadata["admissionid"].to_list(), metadata["n_rows"].to_list()))
    if observed_counts != expected_counts:
        failures.append("metadata admission IDs or n_rows differ from parquet shards")

    available = set(expected_columns)
    for tag, info in schema.items():
        physical = info.get("physical_columns")
        if physical is None:
            failures.append(f"feature schema lacks physical_columns for {tag}")
        elif not set(physical).issubset(available):
            failures.append(f"feature schema points to absent columns for {tag}: {physical}")
    missing_tte = set(tte.get("missing", []))
    for tag in tte.get("targets", []):
        if tag not in missing_tte and not schema.get(tag, {}).get("physical_columns"):
            failures.append(f"TTE target {tag} is declared available but has no physical column")

    summary = {
        "passed": not failures,
        "failures": failures,
        "shards": len(shard_paths),
        "rows": total_rows,
        "admissions": len(observed_counts),
        "subjects": metadata[subject_column].n_unique(),
        "columns": len(expected_columns),
    }
    audit_dir.mkdir(parents=True, exist_ok=True)
    output_path = audit_dir / "grid_integrity_summary.json"
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    if failures:
        raise ValueError(f"Grid integrity audit failed; see {output_path}: {failures}")
    return output_path
