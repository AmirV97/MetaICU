"""Reusable raw-MIMIC-IV to hourly-grid workflow.

The workflow consumes the reviewed feature manifest, extracts raw source rows, applies
feature-specific harmonization and plausibility filters, then writes split-specific hourly
grid parquet shards. The CLI only resolves Hydra settings and invokes this module. Mirrors
metaicu.aumcdb.grid.build.build_workflow's shape; differs where M4_grid's own pipeline differs
from aumcdb's (no unit_of_analysis -- see GridDatasetConfig's docstring).
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from metaicu.mimiciv.common.raw_shards import build_raw_shards_for_tables
from metaicu.mimiciv.common.raw_tables import TABLE_FILES as LARGE_TABLE_FILES, raw_table_input_mode
from metaicu.grid.external_artifacts import build_external_vocab, build_pooled_external_scalers, load_external_artifacts
from metaicu.grid.integrity import audit_grid_dataset
from metaicu.grid.pool_scale import compute_cohort_weights
from metaicu.grid.pre_scale import PreScaleGrid
from metaicu.grid.schema_union import compute_union_matches, pad_matches_for_cohort

from .assemble import assemble_grid, canonical_column_order
from .derive_targets import MIMIC_K35_TTE_TARGETS, DERIVED_TARGET_SOURCES, add_derived_tte_targets
from .encode import get_categorical_vocab, one_hot_encode_categorical, one_hot_encode_columns, save_categorical_encoding
from .extract_indicator import extract_treatment_indicator
from .extract_numeric import extract_numeric_categorical
from .extract_rate import extract_treatment_rate
from .extract_static import STATIC_CATEGORICAL_VOCAB, extract_static_features
from .impute import capture_presence_mask, impute_grid, materialize_structural_zero_columns
from .manifest_parser import ALL_RECONSTRUCTION_TYPES, parse_manifest
from .sampling import apply_inclusion_criteria, get_admission_ids, load_valid_admissions
from .scale import save_scalers, scale_grid, scale_static_features
from .split import assign_splits

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GridDatasetConfig:
    """Resolved inputs and runtime settings for one MIMIC-IV grid-dataset build. No
    unit_of_analysis -- M4_grid's split is unconditionally by subject_id
    (grid.build.split.assign_splits) and its shard/metadata output is unconditionally
    admission-grain; unlike aumcdb, M4_grid never had a subject-grain output mode, so there's
    nothing for this field to select between."""

    raw_data_dir: Path
    output_dir: Path
    audit_dir: Path
    manifest_path: Path
    raw_shards_dir: Path | None = None
    build_raw_shards: bool = True
    rebuild_raw_shards: bool = False
    raw_shard_rows: int = 5_000_000
    admission_ids_file: Path | None = None
    external_artifacts_dir: Path | None = None
    sample_size: int | None = None
    patients_per_file: int = 1_000
    train_frac: float = 0.8
    val_frac: float = 0.1
    test_frac: float = 0.1
    random_seed: int = 42  # drives admission subsampling, split assignment, and treatment
                            # (QuantileTransformer) scaler fitting -- one knob for every random
                            # component in this pipeline
    features: tuple[str, ...] = ()
    reconstruction_types: tuple[str, ...] = ()
    apply_inclusion_criteria: bool = True
    scale: bool = True
    impute: bool = True
    one_hot: bool = True
    overwrite: bool = False


_GENERATED_FILES = {
    "metadata.csv", "feature_schema.json", "tte_targets.json", "scalers.pkl",
    "scalers.summary.json", "categorical_encoding.csv",
}


def _prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    generated = [output_dir / split for split in ("train", "val", "test") if (output_dir / split).exists()]
    generated += [output_dir / name for name in _GENERATED_FILES if (output_dir / name).exists()]
    if generated and not overwrite:
        raise FileExistsError(f"Grid output already contains generated artifacts: {output_dir}; set run.overwrite=true")
    for path in generated:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)


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


def _write_shards(
    grid: pl.DataFrame,
    admission_ids_sorted: list[int],
    output_dir: Path,
    patients_per_file: int,
) -> dict[int, dict[str, int | str]]:
    """Flat, numbered parquet shards (0.parquet, 1.parquet, ...) -- no per-admission subfolder,
    matching AUMC_pipeline's file-level convention. Returns {admissionid: {"shard_file": ...,
    "n_rows": ...}} for the metadata.csv sidecar."""
    shard_info: dict[int, dict[str, int | str]] = {}
    for shard_idx, start in enumerate(range(0, len(admission_ids_sorted), patients_per_file)):
        batch_ids = admission_ids_sorted[start : start + patients_per_file]
        shard = grid.filter(pl.col("admissionid").is_in(batch_ids)).sort(["admissionid", "hour"])
        shard_file = f"{shard_idx}.parquet"
        shard.write_parquet(output_dir / shard_file)
        counts = shard.group_by("admissionid").len()
        for admission_id, row_count in zip(counts["admissionid"].to_list(), counts["len"].to_list()):
            shard_info[admission_id] = {"shard_file": shard_file, "n_rows": row_count}
        log.info(f"wrote {shard_file}: {len(batch_ids)} admissions, {shard.height} rows")
    return shard_info


def _write_metadata(admissions: pl.DataFrame, shard_info: dict[int, dict[str, int | str]], output_path: Path) -> None:
    """age/weight/height are written in raw units (metadata.csv's whole point is human-readable
    filtering, e.g. "age > 65") plus, if grid.scale.scale_static_features ran (config.scale), a
    f"{tag}_scaled" column alongside each. outcome = hospital_expire_flag (died during THIS
    hospitalization) -- MIMIC's closest admission-scoped analog to AUMC's patient-level
    dateofdeath. ethnic is the reviewed five-group collapse of admissions.race plus missing."""
    scaled_cols = [c for c in ("age_scaled", "weight_scaled", "height_scaled") if c in admissions.columns]
    rows = []
    for row in admissions.iter_rows(named=True):
        admission_id = row["admissionid"]
        info = shard_info.get(admission_id, {"shard_file": None, "n_rows": 0})
        record = {
            "admissionid": admission_id,
            "subject_id": row["subject_id"],
            "split": row["split"],
            "shard_file": info["shard_file"],
            "los_hours": row["true_los_hours"],
            "outcome": "died" if row["hospital_expire_flag"] == 1 else "alive",
            "n_rows": info["n_rows"],
            "age": row["age"],
            "weight": row["weight"],
            "height": row["height"],
            "sex": row["sex"],
            "adm": row["adm"],
            "ethnic": row["ethnic"],
        }
        for column in scaled_cols:
            record[column] = row[column]
        rows.append(record)
    pl.DataFrame(rows).write_csv(output_path)
    log.info(f"Wrote metadata.csv ({len(rows)} admissions, scaled columns: {scaled_cols})")


def build_pre_scale_grid(config: GridDatasetConfig) -> PreScaleGrid:
    """Extraction and assembly through presence-mask capture -- everything write_grid_dataset_outputs
    always did up to (not including) scaling. Config validation stays here, unchanged, so a failing
    config still fails before any extraction runs, same as before this function existed.

    Static feature scaling (scale_static_features) is deliberately NOT done here even though it
    used to run before this point in the pre-split code -- nothing between its old call site and
    scale_grid's ever reads the `_scaled` columns or mutates the raw age/weight/height columns it's
    based on, so moving it into finish_grid_dataset (alongside scale_grid) is behavior-preserving
    and lets both static and grid scaling take the same external_scalers path uniformly."""
    if config.patients_per_file <= 0:
        raise ValueError("patients_per_file must be positive")
    if config.raw_shard_rows <= 0:
        raise ValueError("raw_shard_rows must be positive")
    if config.build_raw_shards and config.raw_shards_dir is None:
        raise ValueError("build_raw_shards=true requires raw_shards_dir")
    if config.one_hot and not config.impute:
        raise ValueError("one_hot requires impute so categorical missingness has its defined meaning")

    _prepare_output_dir(config.output_dir, config.overwrite)
    config.audit_dir.mkdir(parents=True, exist_ok=True)

    matches, manifest_report = _select_matches(config)
    if not matches:
        raise ValueError("No resolved feature matches are in scope")
    log.info("Resolved %d grid features", len(matches))

    raw_shard_summary: dict[str, object] = {"skipped": "build_raw_shards=false"}
    if config.build_raw_shards:
        log.info("Building or reusing shared raw parquet shards")
        raw_shard_summary = build_raw_shards_for_tables(
            tables=LARGE_TABLE_FILES,
            raw_data_dir=config.raw_data_dir,
            raw_shards_dir=config.raw_shards_dir,
            partition_rows=config.raw_shard_rows,
            max_rows=None,
            rebuild=config.rebuild_raw_shards,
        )
        log.info(
            "Raw shard cache ready: %s",
            {table: summary["action"] for table, summary in raw_shard_summary.items()},
        )

    admission_ids = get_admission_ids(
        config.raw_data_dir,
        sample_size=config.sample_size,
        seed=config.random_seed,
        admission_ids_file=config.admission_ids_file,
    )
    admissions = load_valid_admissions(config.raw_data_dir)
    if admission_ids is not None:
        admissions = admissions.filter(pl.col("admissionid").is_in(list(admission_ids)))
    admissions_before_inclusion = admissions.height

    numeric_long, categorical_long = extract_numeric_categorical(
        matches, config.raw_data_dir, admissions, admission_ids, config.raw_shards_dir
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

    assignments = assign_splits(admissions, config.train_frac, config.val_frac, config.test_frac, config.random_seed)
    admissions = admissions.join(assignments, on="admissionid")
    admissions = admissions.join(
        extract_static_features(config.raw_data_dir, admissions, admission_ids, config.raw_shards_dir),
        on="admissionid",
    )
    train_ids = admissions.filter(pl.col("split") == "train")["admissionid"].to_list()

    # sex/adm/ethnic one-hot encoded on a side copy (demo_source), never on `admissions` itself --
    # metadata.csv (via _write_metadata) still needs the human-readable collapsed values.
    demo_source = admissions.select(["admissionid", "sex", "adm", "ethnic"])
    static_categorical_encoding: list[dict] = []
    next_categorical_pos = 0
    if config.one_hot:
        demo_source, static_categorical_encoding, next_categorical_pos = one_hot_encode_columns(
            demo_source, STATIC_CATEGORICAL_VOCAB
        )

    indicator_on_hours = extract_treatment_indicator(
        matches, config.raw_data_dir, admissions, included_ids, config.raw_shards_dir
    )
    rate_long = extract_treatment_rate(matches, config.raw_data_dir, admissions, included_ids, config.raw_shards_dir)

    grid = assemble_grid(admissions, numeric_long, categorical_long, indicator_on_hours, rate_long)
    grid, derived_target_matches = add_derived_tte_targets(grid, admissions)
    matches_with_derived = {**matches, **derived_target_matches}
    grid = materialize_structural_zero_columns(grid, matches_with_derived)
    grid, presence_mask_cols = capture_presence_mask(grid, matches_with_derived)

    return PreScaleGrid(
        grid=grid,
        matches=matches,
        matches_with_derived=matches_with_derived,
        derived_target_matches=derived_target_matches,
        admissions=admissions,
        train_admission_ids=train_ids,
        demo_source=demo_source,
        static_categorical_encoding=static_categorical_encoding,
        next_categorical_pos=next_categorical_pos,
        presence_mask_cols=presence_mask_cols,
        manifest_report=manifest_report,
        raw_shard_summary=raw_shard_summary,
        admissions_before_inclusion=admissions_before_inclusion,
    )


def finish_grid_dataset(
    config: GridDatasetConfig, pre_scale_grid: PreScaleGrid,
    external_scalers: dict | None = None, external_vocab: dict | None = None,
) -> dict[str, Path]:
    """Scale (using external_scalers per tag when supplied -- e.g. a pooled cross-cohort fit from
    metaicu.grid.pool_scale -- instead of fitting on this cohort's own train split), impute,
    one-hot (using external_vocab in place of this cohort's own categorical vocab when supplied),
    and write every output artifact. external_scalers=None/external_vocab=None reproduces exactly
    what write_grid_dataset_outputs always did.

    config.output_dir is (re-)ensured here rather than assumed from build_pre_scale_grid's own
    _prepare_output_dir call -- callers may build a PreScaleGrid some other way (e.g. a hand-built
    one in a test) and call this function directly, without ever going through
    build_pre_scale_grid; mkdir with exist_ok=True is a no-op for the normal wrapper path, where
    the directory already exists by this point."""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    grid = pre_scale_grid.grid
    matches = pre_scale_grid.matches
    matches_with_derived = pre_scale_grid.matches_with_derived
    derived_target_matches = pre_scale_grid.derived_target_matches
    admissions = pre_scale_grid.admissions
    train_ids = pre_scale_grid.train_admission_ids
    demo_source = pre_scale_grid.demo_source
    static_categorical_encoding = list(pre_scale_grid.static_categorical_encoding)
    next_categorical_pos = pre_scale_grid.next_categorical_pos
    presence_mask_cols = pre_scale_grid.presence_mask_cols

    scalers = {}
    if config.scale:
        admissions, static_scalers = scale_static_features(admissions, train_ids, external_scalers=external_scalers)
        scalers.update(static_scalers)
        grid, grid_scalers = scale_grid(
            grid, matches_with_derived, train_ids, external_scalers=external_scalers, random_seed=config.random_seed
        )
        scalers.update(grid_scalers)
    if scalers:
        save_scalers(scalers, config.output_dir / "scalers.pkl")
    if config.impute:
        scaled_numeric_tags = {
            tag for tag, scaler in scalers.items() if scaler["type"] == "observation"
        }
        grid = impute_grid(grid, matches_with_derived, scaled_numeric_tags=scaled_numeric_tags)

    encoding_schema = list(static_categorical_encoding)
    if config.one_hot:
        grid, grid_encoding_schema = one_hot_encode_categorical(
            grid, matches_with_derived, start_pos=next_categorical_pos, external_vocab=external_vocab
        )
        encoding_schema += grid_encoding_schema
    if encoding_schema:
        save_categorical_encoding(encoding_schema, config.output_dir / "categorical_encoding.csv")

    # Prepend the static/demographic features onto every hourly row of their admission, so each
    # per-timestep sample carries patient context directly rather than only living in
    # metadata.csv. Numeric columns 0-fill remaining nulls when scaled (0 = population mean
    # post-standardization, same A.4.3 convention as the rest of the grid); unscaled, real nulls
    # are left as-is. A tag is only actually scaled if scale_static_features found >=
    # MIN_TRAIN_VALUES train values to fit on (see its own "not scaled" skip) -- checking scalers
    # itself, not just config.scale, avoids both a ColumnNotFoundError on the never-created
    # f"{tag}_scaled" column and 0-filling raw-unit nulls as if they were a population mean in
    # standardized space.
    numeric_static_cols = [
        f"{tag}_scaled" if config.scale and scalers.get(tag, {}).get("type") == "static" else tag
        for tag in ("age", "weight", "height")
    ]
    categorical_static_cols = (
        [row["column_name"] for row in static_categorical_encoding]
        if config.one_hot else ["sex", "adm", "ethnic"]
    )
    demo_numeric = admissions.select(
        ["admissionid"]
        + [(pl.col(c).fill_null(0.0) if c.endswith("_scaled") else pl.col(c)) for c in numeric_static_cols]
    )
    demo_frame = demo_numeric.join(demo_source, on="admissionid")
    demo_cols = numeric_static_cols + categorical_static_cols
    grid = grid.join(demo_frame, on="admissionid")
    column_order, tag_to_physical = canonical_column_order(
        grid.columns, matches_with_derived, encoding_schema, presence_mask_cols, demo_cols
    )
    grid = grid.select(column_order)

    shard_info: dict[int, dict[str, int | str]] = {}
    split_counts = {}
    for split in ("train", "val", "test"):
        split_ids = sorted(admissions.filter(pl.col("split") == split)["admissionid"].to_list())
        split_counts[split] = len(split_ids)
        if not split_ids:
            continue
        split_dir = config.output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        for admission_id, info in _write_shards(grid, split_ids, split_dir, config.patients_per_file).items():
            shard_info[admission_id] = {"shard_file": f"{split}/{info['shard_file']}", "n_rows": info["n_rows"]}

    metadata_path = config.output_dir / "metadata.csv"
    _write_metadata(admissions, shard_info, metadata_path)

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
        "ethnic": {"reconstruction_type": "static_categorical", "target_unit": "categorical"},
    })
    static_physical = dict(zip(("age", "weight", "height"), ([column] for column in numeric_static_cols)))
    for tag in ("sex", "adm", "ethnic"):
        static_physical[tag] = (
            [row["column_name"] for row in static_categorical_encoding if row["feature"] == tag]
            if config.one_hot else [tag]
        )
    for tag in schema:
        physical = static_physical.get(tag, tag_to_physical.get(tag, []))
        schema[tag]["physical_columns"] = [column for column in physical if column in grid.columns]
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True))

    # MIMIC's own K=35 TTE pretraining target manifest (grid.derive_targets.MIMIC_K35_TTE_TARGETS
    # -- AUMC's K=34 list plus bili_dir, which MIMIC-IV has and AUMCdb doesn't).
    tte_present = set(matches_with_derived) | {"age", "weight", "height", "sex", "adm", "ethnic"}
    tte_missing = [tag for tag in MIMIC_K35_TTE_TARGETS if tag not in tte_present or tag not in grid.columns]
    tte_targets_path = config.output_dir / "tte_targets.json"
    tte_targets_path.write_text(json.dumps({
        "targets": MIMIC_K35_TTE_TARGETS,
        "missing": tte_missing,
        "derived": {t: DERIVED_TARGET_SOURCES[t] for t in DERIVED_TARGET_SOURCES if t in MIMIC_K35_TTE_TARGETS},
    }, indent=2))

    integrity_path = audit_grid_dataset(
        config.output_dir, config.audit_dir, grid.columns, subject_column="subject_id"
    )

    summary_path = config.audit_dir / "grid_build_summary.json"
    summary_path.write_text(json.dumps({
        "admissions_before_inclusion": pre_scale_grid.admissions_before_inclusion,
        "admissions_after_inclusion": admissions.height,
        "grid_rows": grid.height,
        "features": sorted(matches),
        "split_admission_counts": split_counts,
        "scaled": config.scale,
        "imputed": config.impute,
        "one_hot_encoded": config.one_hot,
        "raw_shards": pre_scale_grid.raw_shard_summary,
        "large_table_input_modes": {
            table: raw_table_input_mode(table, config.raw_shards_dir) for table in LARGE_TABLE_FILES
        },
        "manifest_report": pre_scale_grid.manifest_report,
    }, indent=2, sort_keys=True, default=str))

    return {
        "output_dir": config.output_dir,
        "metadata": metadata_path,
        "feature_schema": schema_path,
        "tte_targets": tte_targets_path,
        "summary": summary_path,
        "integrity": integrity_path,
    }


def write_grid_dataset_outputs(config: GridDatasetConfig) -> dict[str, Path]:
    """Build a split-aware hourly MIMIC-IV grid and write data, metadata, and audit summaries.

    config.external_artifacts_dir=None reproduces exactly what this function always did. When
    set, it points at a PREVIOUSLY-completed single-dataset grid build's output_dir (own or
    another cohort's) -- this run's own per-tag statistics are pooled with that build's saved
    scalers.pkl/categorical_encoding.csv/feature_schema.json via the same 1/sqrt(n_train_admissions)
    weighting metaicu.grid.pool_scale uses for a joint build, rather than fitting solely on this
    run's own train split. Mirrors grid_build_joint_dataset.py's own pad-then-pool sequencing:
    pad this cohort's matches to the union of its own tags and the external schema's (re-running
    materialize_structural_zero_columns/capture_presence_mask on the padded dict, since the grid
    was already assembled from the UNPADDED dict), then pool statistics, then finish."""
    pre_scale_grid = build_pre_scale_grid(config)
    external_scalers = None
    external_vocab = None
    if config.external_artifacts_dir is not None:
        external = load_external_artifacts(config.external_artifacts_dir)
        union_registry = compute_union_matches({"external": external.schema_registry, "own": pre_scale_grid.matches})
        padded_matches = pad_matches_for_cohort(pre_scale_grid.matches, union_registry)
        padded_matches_with_derived = {**padded_matches, **pre_scale_grid.derived_target_matches}
        pre_scale_grid.grid = materialize_structural_zero_columns(pre_scale_grid.grid, padded_matches_with_derived)
        pre_scale_grid.grid, pre_scale_grid.presence_mask_cols = capture_presence_mask(
            pre_scale_grid.grid, padded_matches_with_derived
        )
        pre_scale_grid.matches = padded_matches
        pre_scale_grid.matches_with_derived = padded_matches_with_derived

        weights = compute_cohort_weights(
            {"external": external.n_train_admissions, "own": len(pre_scale_grid.train_admission_ids)}
        )
        external_scalers = build_pooled_external_scalers(pre_scale_grid, external, weights, random_seed=config.random_seed)
        external_vocab = build_external_vocab(external, get_categorical_vocab(pre_scale_grid.matches_with_derived))
        log.info(f"External artifacts from {config.external_artifacts_dir}: "
                 f"pooled {len(external_scalers)} scaler tags, weights={weights}")

    return finish_grid_dataset(config, pre_scale_grid, external_scalers=external_scalers, external_vocab=external_vocab)
