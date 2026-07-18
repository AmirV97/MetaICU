"""Reusable raw-AUMCdb to hourly-grid workflow.

The workflow consumes the reviewed feature manifest, extracts raw source rows, applies
feature-specific harmonization and plausibility filters, then writes split-specific hourly
grid parquet shards. The CLI only resolves Hydra settings and invokes this module.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from metaicu.aumcdb.common.raw_shards import build_raw_shards_for_tables
from metaicu.aumcdb.common.raw_tables import raw_table_input_mode

from .assemble import assemble_grid
from .derive_targets import K34_TTE_TARGETS, DERIVED_TARGET_SOURCES, add_derived_tte_targets
from .encode import one_hot_encode_categorical, one_hot_encode_columns, save_categorical_encoding
from .extract_indicator import extract_treatment_indicator
from .extract_numeric import extract_numeric_categorical
from .extract_rate import extract_treatment_rate
from .extract_static import STATIC_CATEGORICAL_VOCAB, extract_static_features
from .impute import capture_presence_mask, impute_grid
from .manifest_parser import ALL_RECONSTRUCTION_TYPES, parse_manifest
from .sampling import apply_inclusion_criteria, get_admission_ids, load_valid_admissions
from .scale import save_scalers, scale_grid, scale_static_features
from .split import assign_splits


log = logging.getLogger(__name__)
_LARGE_TABLES = ["numericitems", "listitems", "drugitems"]


@dataclass(frozen=True)
class GridDatasetConfig:
    """Resolved inputs and runtime settings for one grid-dataset build."""

    raw_data_dir: Path
    output_dir: Path
    audit_dir: Path
    raw_shards_dir: Path | None = None
    build_raw_shards: bool = True
    rebuild_raw_shards: bool = False
    raw_shard_rows: int = 5_000_000
    manifest_path: Path | None = None
    admission_ids_file: Path | None = None
    sample_size: int | None = None
    patients_per_file: int = 1_000
    seed: int = 42
    unit_of_analysis: str = "admission"
    train_frac: float = 0.8
    val_frac: float = 0.1
    test_frac: float = 0.1
    split_seed: int = 42
    features: tuple[str, ...] = ()
    reconstruction_types: tuple[str, ...] = ()
    apply_inclusion_criteria: bool = True
    scale: bool = True
    impute: bool = True
    one_hot: bool = True


def _write_shards(
    grid: pl.DataFrame,
    admissions: pl.DataFrame,
    admission_ids: list[int],
    output_dir: Path,
    units_per_file: int,
    unit_of_analysis: str,
) -> dict[int, dict[str, int | str]]:
    """Write numbered batches of samples and return per-admission metadata needed for the
    sidecar. unit_of_analysis="admission": one sample per admission. "subject": one sample
    per patient, its admissions concatenated in chronological (admittedat) order."""

    order = admissions.select(["admissionid", "patientid", "admittedat"]).filter(
        pl.col("admissionid").is_in(admission_ids)
    )
    unit_col = "patientid" if unit_of_analysis == "subject" else "admissionid"
    sort_cols = ["patientid", "admittedat", "hour"] if unit_of_analysis == "subject" else ["admissionid", "hour"]
    unit_ids = sorted(order[unit_col].unique().to_list())

    shard_info: dict[int, dict[str, int | str]] = {}
    for shard_index, start in enumerate(range(0, len(unit_ids), units_per_file)):
        batch_units = unit_ids[start : start + units_per_file]
        batch_admission_ids = order.filter(pl.col(unit_col).is_in(batch_units))["admissionid"].to_list()
        shard = (
            grid.filter(pl.col("admissionid").is_in(batch_admission_ids))
            .join(order, on="admissionid")
            .sort(sort_cols)
            .drop(["patientid", "admittedat"])
        )
        shard_name = f"{shard_index}.parquet"
        shard.write_parquet(output_dir / shard_name)
        counts = shard.group_by("admissionid").len()
        for admission_id, row_count in zip(counts["admissionid"].to_list(), counts["len"].to_list()):
            shard_info[int(admission_id)] = {"shard_file": shard_name, "n_rows": int(row_count)}
        log.info("Wrote %s: %d %ss, %d rows", shard_name, len(batch_units), unit_of_analysis, shard.height)
    return shard_info


def _write_metadata_by_admission(
    admissions: pl.DataFrame,
    shard_info: dict[int, dict[str, int | str]],
    output_path: Path,
) -> None:
    """Write one row per included ICU admission, each with its own static features."""

    scaled_columns = [column for column in ("age_scaled", "weight_scaled", "height_scaled") if column in admissions]
    records = []
    for row in admissions.iter_rows(named=True):
        admission_id = int(row["admissionid"])
        info = shard_info.get(admission_id, {"shard_file": None, "n_rows": 0})
        record = {
            "admissionid": admission_id,
            "patientid": row["patientid"],
            "split": row["split"],
            "shard_file": info["shard_file"],
            "los_hours": row["true_los_hours"],
            "outcome": "died" if row["dateofdeath"] is not None else "alive",
            "n_rows": info["n_rows"],
            "age": row["age"],
            "weight": row["weight"],
            "height": row["height"],
            "sex": row["sex"],
            "adm": row["adm"],
        }
        for column in scaled_columns:
            record[column] = row[column]
        records.append(record)
    pl.DataFrame(records).write_csv(output_path)
    log.info("Wrote %s (%d admissions)", output_path.name, len(records))


def _write_metadata_by_subject(
    admissions: pl.DataFrame,
    shard_info: dict[int, dict[str, int | str]],
    output_path: Path,
) -> None:
    """Write one row per patient: demographics from the earliest admission, outcome
    (died/alive) from the latest admission, admission-specific fields (adm, admission_ids)
    as chronologically ordered lists."""

    scaled_columns = [column for column in ("age_scaled", "weight_scaled", "height_scaled") if column in admissions]
    ordered = admissions.sort(["patientid", "admittedat"])
    records = []
    for (patientid,), group in ordered.group_by(["patientid"], maintain_order=True):
        first = group.row(0, named=True)
        last = group.row(-1, named=True)
        admission_ids = [int(a) for a in group["admissionid"].to_list()]
        n_rows = sum(shard_info.get(aid, {"n_rows": 0})["n_rows"] for aid in admission_ids)
        record = {
            "patientid": patientid,
            "split": first["split"],
            "admission_ids": ",".join(str(a) for a in admission_ids),
            "n_admissions": len(admission_ids),
            "shard_file": shard_info.get(admission_ids[0], {"shard_file": None})["shard_file"],
            "los_hours": group["true_los_hours"].sum(),
            "outcome": "died" if last["dateofdeath"] is not None else "alive",
            "n_rows": n_rows,
            "age": first["age"],
            "weight": first["weight"],
            "height": first["height"],
            "sex": first["sex"],
            "adm": ",".join(str(a) for a in group["adm"].to_list()),
        }
        for column in scaled_columns:
            record[column] = first[column]
        records.append(record)
    pl.DataFrame(records).write_csv(output_path)
    log.info("Wrote %s (%d subjects)", output_path.name, len(records))


def _select_matches(config: GridDatasetConfig) -> tuple[dict[str, dict], dict]:
    requested_types = config.reconstruction_types or tuple(ALL_RECONSTRUCTION_TYPES)
    matches, report = parse_manifest(config.manifest_path, reconstruction_types=requested_types)
    if not config.features:
        return matches, report

    requested_features = set(config.features)
    missing = requested_features - set(matches)
    if missing:
        log.warning("Requested feature tags not present in the resolved manifest: %s", sorted(missing))
    return {tag: info for tag, info in matches.items() if tag in requested_features}, report


def write_grid_dataset_outputs(config: GridDatasetConfig) -> dict[str, Path]:
    """Build a split-aware hourly grid and write data, metadata, and audit summaries."""

    if config.patients_per_file <= 0:
        raise ValueError("patients_per_file must be positive")
    if config.raw_shard_rows <= 0:
        raise ValueError("raw_shard_rows must be positive")
    if config.build_raw_shards and config.raw_shards_dir is None:
        raise ValueError("build_raw_shards=true requires raw_shards_dir")
    if config.one_hot and not config.impute:
        raise ValueError("one_hot requires impute so categorical missingness has its defined meaning")
    if config.unit_of_analysis not in ("admission", "subject"):
        raise ValueError(f"unit_of_analysis must be 'admission' or 'subject', got {config.unit_of_analysis!r}")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.audit_dir.mkdir(parents=True, exist_ok=True)

    matches, manifest_report = _select_matches(config)
    if not matches:
        raise ValueError("No resolved feature matches are in scope")
    log.info("Resolved %d grid features", len(matches))

    raw_shard_summary: dict[str, object] = {"skipped": "run.build_raw_shards=false"}
    if config.build_raw_shards:
        log.info("Building or reusing shared raw parquet shards")
        raw_shard_summary = build_raw_shards_for_tables(
            tables=_LARGE_TABLES,
            raw_dir=config.raw_data_dir,
            raw_shards_dir=config.raw_shards_dir,
            partition_rows=config.raw_shard_rows,
            max_rows=None,
            rebuild=config.rebuild_raw_shards,
        )
        log.info(
            "Raw shard cache ready: %s",
            {
                table: summary["action"]
                for table, summary in raw_shard_summary.items()
                if isinstance(summary, dict)
            },
        )

    admission_ids = get_admission_ids(
        config.raw_data_dir,
        sample_size=config.sample_size,
        seed=config.seed,
        admission_ids_file=config.admission_ids_file,
    )
    admissions = load_valid_admissions(config.raw_data_dir)
    if admission_ids is not None:
        admissions = admissions.filter(pl.col("admissionid").is_in(list(admission_ids)))
    admissions_before_inclusion = admissions.height

    numeric_long, categorical_long = extract_numeric_categorical(
        matches,
        config.raw_data_dir,
        admissions,
        admission_ids,
        config.raw_shards_dir,
    )
    if numeric_long is None:
        raise ValueError("Grid construction requires at least one resolved numeric feature")

    if config.apply_inclusion_criteria:
        admissions = apply_inclusion_criteria(admissions, numeric_long, matches)
        included_ids = set(admissions["admissionid"].to_list())
        numeric_long = numeric_long.filter(pl.col("admissionid").is_in(list(included_ids)))
        if categorical_long is not None:
            categorical_long = categorical_long.filter(pl.col("admissionid").is_in(list(included_ids)))
    else:
        included_ids = set(admissions["admissionid"].to_list())

    assignments = assign_splits(
        admissions,
        config.train_frac,
        config.val_frac,
        config.test_frac,
        config.split_seed,
    )
    admissions = admissions.join(assignments, on="admissionid")
    admissions = admissions.join(extract_static_features(admissions), on="admissionid")
    train_ids = admissions.filter(pl.col("split") == "train")["admissionid"].to_list()

    scalers = {}
    if config.scale:
        admissions, static_scalers = scale_static_features(admissions, train_ids)
        scalers.update(static_scalers)

    # sex/adm one-hot encoded on a side copy (demo_source), never on `admissions` itself --
    # metadata.csv (via _write_metadata_by_admission/_write_metadata_by_subject) still needs the
    # original human-readable sex/adm values.
    demo_source = admissions.select(["admissionid", "sex", "adm"])
    static_categorical_encoding: list[dict] = []
    next_categorical_pos = 0
    if config.one_hot:
        demo_source, static_categorical_encoding, next_categorical_pos = one_hot_encode_columns(
            demo_source, STATIC_CATEGORICAL_VOCAB
        )

    indicator_on_hours = extract_treatment_indicator(
        matches,
        config.raw_data_dir,
        admissions,
        included_ids,
        config.raw_shards_dir,
    )
    rate_tags = [tag for tag, info in matches.items() if info["reconstruction_type"] == "treatment_rate"]
    rate_long = extract_treatment_rate(
        config.raw_data_dir,
        admissions,
        included_ids,
        tags=rate_tags,
        raw_shards_dir=config.raw_shards_dir,
    ) if rate_tags else None

    grid = assemble_grid(admissions, numeric_long, categorical_long, indicator_on_hours, rate_long)
    grid, derived_target_matches = add_derived_tte_targets(grid, admissions)
    matches_with_derived = {**matches, **derived_target_matches}
    grid, presence_mask_cols = capture_presence_mask(grid, matches_with_derived)
    if config.scale:
        grid, grid_scalers = scale_grid(grid, matches_with_derived, train_ids)
        scalers.update(grid_scalers)
        save_scalers(scalers, config.output_dir / "scalers.pkl")
    if config.impute:
        grid = impute_grid(grid, matches_with_derived, scaled=config.scale)
    if config.one_hot:
        grid, grid_encoding, _ = one_hot_encode_categorical(grid, matches, start_pos=next_categorical_pos)
        save_categorical_encoding(
            static_categorical_encoding + grid_encoding, config.output_dir / "categorical_encoding.csv"
        )

    # Prepend the 5 available static/demographic features (age, weight, height, sex, adm --
    # `ethnic` has no AmsterdamUMCdb source, see extract_static.py) onto every hourly row of
    # their admission, so each per-timestep sample carries patient context directly rather than
    # only living in metadata.csv. Numeric columns 0-fill remaining nulls when scaled (0 =
    # population mean post-standardization, same A.4.3 convention as the rest of the grid);
    # unscaled, real nulls are left as-is.
    numeric_static_cols = [f"{tag}_scaled" if config.scale else tag for tag in ("age", "weight", "height")]
    categorical_static_cols = (
        [row["column_name"] for row in static_categorical_encoding] if config.one_hot else ["sex", "adm"]
    )
    demo_numeric = admissions.select(
        ["admissionid"]
        + [(pl.col(c).fill_null(0.0) if config.scale else pl.col(c)) for c in numeric_static_cols]
    )
    demo_frame = demo_numeric.join(demo_source, on="admissionid")
    demo_cols = numeric_static_cols + categorical_static_cols

    grid = grid.join(demo_frame, on="admissionid")
    other_cols = [c for c in grid.columns if c not in demo_cols and c not in ("admissionid", "hour")]
    grid = grid.select(["admissionid", "hour"] + demo_cols + other_cols)

    shard_info: dict[int, dict[str, int | str]] = {}
    split_counts = {}
    for split in ("train", "val", "test"):
        split_ids = sorted(admissions.filter(pl.col("split") == split)["admissionid"].to_list())
        split_counts[split] = len(split_ids)
        if not split_ids:
            continue
        split_dir = config.output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        for admission_id, info in _write_shards(
            grid, admissions, split_ids, split_dir, config.patients_per_file, config.unit_of_analysis
        ).items():
            shard_info[admission_id] = {
                "shard_file": f"{split}/{info['shard_file']}",
                "n_rows": info["n_rows"],
            }

    metadata_path = config.output_dir / "metadata.csv"
    if config.unit_of_analysis == "subject":
        _write_metadata_by_subject(admissions, shard_info, metadata_path)
    else:
        _write_metadata_by_admission(admissions, shard_info, metadata_path)
    schema_path = config.output_dir / "feature_schema.json"
    schema = {
        tag: {"reconstruction_type": info["reconstruction_type"], "target_unit": info["target_unit"]}
        for tag, info in matches.items()
    }
    for tag, info in derived_target_matches.items():
        schema[tag] = {"reconstruction_type": "derived_tte_target", "target_unit": info["target_unit"],
                       "derived_from": DERIVED_TARGET_SOURCES[tag]}
    for tag in schema:
        if f"{tag}__observed" in presence_mask_cols:
            schema[tag]["presence_mask_column"] = f"{tag}__observed"
    schema.update({
        "age": {"reconstruction_type": "static_numeric", "target_unit": "years"},
        "weight": {"reconstruction_type": "static_numeric", "target_unit": "kg"},
        "height": {"reconstruction_type": "static_numeric", "target_unit": "cm"},
        "sex": {"reconstruction_type": "static_categorical", "target_unit": "categorical"},
        "adm": {"reconstruction_type": "static_categorical", "target_unit": "categorical"},
    })
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True))

    # K=34 TTE pretraining target manifest (see derive_targets.K34_TTE_TARGETS) -- lets a Dataset
    # class read the canonical target list/order and each target's presence_mask_column directly
    # from the dataset artifacts, rather than hardcoding or re-deriving it from context.md.
    available_targets = [tag for tag in K34_TTE_TARGETS if tag in schema]
    missing_targets = [tag for tag in K34_TTE_TARGETS if tag not in schema]
    if missing_targets:
        log.warning(f"TTE targets not resolved in this build (feature-restricted run?): {missing_targets}")
    tte_targets_path = config.output_dir / "tte_targets.json"
    tte_targets_path.write_text(json.dumps({
        "targets": available_targets,
        "missing": missing_targets,
        "derived": DERIVED_TARGET_SOURCES,
        "excluded": {"bili_dir": "not present in AmsterdamUMCdb (context.md Q3)"},
    }, indent=2))

    summary_path = config.audit_dir / "grid_build_summary.json"
    summary_path.write_text(json.dumps({
        "admissions_before_inclusion": admissions_before_inclusion,
        "admissions_after_inclusion": admissions.height,
        "grid_rows": grid.height,
        "features": sorted(matches),
        "split_admission_counts": split_counts,
        "unit_of_analysis": config.unit_of_analysis,
        "scaled": config.scale,
        "imputed": config.impute,
        "one_hot_encoded": config.one_hot,
        "raw_shards": raw_shard_summary,
        "large_table_input_modes": {
            table: raw_table_input_mode(table, config.raw_shards_dir)
            for table in _LARGE_TABLES
        },
        "manifest_report": manifest_report,
    }, indent=2, sort_keys=True, default=str))

    return {
        "output_dir": config.output_dir,
        "metadata": metadata_path,
        "feature_schema": schema_path,
        "tte_targets": tte_targets_path,
        "summary": summary_path,
    }
