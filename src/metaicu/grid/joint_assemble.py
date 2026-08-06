"""Cross-cohort output assembly for a joint multi-dataset grid build (Phase 4 of the joint
AUMCdb+MIMIC-IV grid plan). Consumes the PER-COHORT outputs already written by each pipeline's own
finish_grid_dataset (metaicu.{aumcdb,mimiciv}.grid.build.build_workflow) -- one already-complete
train/val/test + metadata.csv + feature_schema.json per cohort, scaled with pooled statistics
whenever a future CLI dispatcher supplies them (metaicu.grid.pool_scale) -- and rewrites them into
ONE flat train/val/test dataset with a `source` column recording each admission's origin cohort.

Not wired into any CLI/Hydra entry point yet (that orchestration -- selecting datasets, building
each cohort's config, running build_pre_scale_grid/finish_grid_dataset, then calling
write_joint_outputs here -- is a separate, later step). This module only needs already-written
per-cohort output directories, so it's testable directly against two real
write_grid_dataset_outputs() runs.

ID collisions are handled by unconditional cohort-prefixing (namespace_ids), never
conditional detect-then-suffix -- see the joint-pipeline plan's decision #3. Prefixing
deliberately changes admissionid/subject_id from Int64 to String; this is the intentional,
consumer-visible format every write_joint_outputs call commits to, not a bug.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import polars as pl

from metaicu.grid.integrity import audit_grid_dataset

log = logging.getLogger(__name__)

ID_COLUMNS = ("admissionid", "subject_id")


def namespace_ids(df, cohort, id_columns=ID_COLUMNS):
    """df: any DataFrame carrying one or more of id_columns. Returns a NEW DataFrame with each
    present id column cast to String and prefixed f"{cohort}_{value}"."""
    present = [c for c in id_columns if c in df.columns]
    return df.with_columns([
        (pl.lit(f"{cohort}_") + pl.col(c).cast(pl.Utf8)).alias(c) for c in present
    ])


def count_cross_cohort_id_collisions(raw_id_sets_by_cohort):
    """raw_id_sets_by_cohort: {cohort: set of raw (pre-namespacing) ID values}. Returns the total
    count of ID values shared by two or more cohorts -- purely diagnostic, reported in the joint
    summary for auditability. namespace_ids makes an actual collision structurally impossible
    regardless of this count (distinct cohort prefixes can never coincide)."""
    cohorts = list(raw_id_sets_by_cohort)
    collisions = set()
    for i, a in enumerate(cohorts):
        for b in cohorts[i + 1:]:
            collisions |= raw_id_sets_by_cohort[a] & raw_id_sets_by_cohort[b]
    return len(collisions)


def assert_globally_unique(df, column):
    """df: a DataFrame already carrying every cohort's rows (post namespace_ids). Raises
    ValueError if `column` has any duplicate value -- expected to never fire once IDs are
    namespaced, unless a single cohort's own output already had an internal duplicate (a bug
    upstream of this module, not a cross-cohort collision)."""
    n_total, n_unique = df.height, df[column].n_unique()
    if n_unique != n_total:
        raise ValueError(f"{column}: {n_total - n_unique} duplicate values found after namespacing")


def merge_tte_targets(tte_infos_by_cohort):
    """tte_infos_by_cohort: {cohort: tte_targets.json contents}. AUMCdb and MIMIC-IV's own TTE
    target lists are INTENTIONALLY different sizes (MIMIC's K35 = AUMC's K34 + bili_dir, since
    only MIMIC has direct bilirubin) -- not a bug to reconcile by picking one. Returns the union
    of every cohort's "targets" (a target real in only one cohort is still meaningful in the
    joint dataset, exactly like a structural_zero grid tag -- see the presence_mask_column for
    per-row availability), "missing" = tags absent from every cohort, and "derived" = the merged
    union of every cohort's own derived-target-source mapping."""
    all_targets = set()
    all_missing = None
    derived = {}
    for info in tte_infos_by_cohort.values():
        all_targets.update(info.get("targets", []))
        missing = set(info.get("missing", []))
        all_missing = missing if all_missing is None else (all_missing & missing)
        derived.update(info.get("derived", {}))
    return {
        "targets": sorted(all_targets),
        "missing": sorted(all_missing or set()),
        "derived": derived,
    }


def _read_cohort_outputs(cohort, output_dir):
    output_dir = Path(output_dir)
    grid_paths = sorted(output_dir.glob("*/*.parquet"))
    if not grid_paths:
        raise ValueError(f"{cohort}: no parquet shards found under {output_dir}")
    grid = pl.concat([pl.read_parquet(path) for path in grid_paths], how="vertical")

    metadata = pl.read_csv(output_dir / "metadata.csv")
    if "admissionid" not in metadata.columns:
        raise ValueError(
            f"{cohort}: metadata.csv has no admissionid column -- only admission-grain per-cohort "
            f"outputs (unit_of_analysis='admission') are supported for a joint build"
        )

    schema = json.loads((output_dir / "feature_schema.json").read_text())
    tte = json.loads((output_dir / "tte_targets.json").read_text())
    encoding_path = output_dir / "categorical_encoding.csv"
    encoding = pl.read_csv(encoding_path) if encoding_path.exists() else None
    return grid, metadata, schema, tte, encoding


def write_joint_outputs(
    cohort_output_dirs,
    joint_output_dir,
    joint_audit_dir,
    patients_per_file,
    weights,
    n_train_admissions_by_cohort,
):
    """cohort_output_dirs: {cohort: Path}, each already a complete write_grid_dataset_outputs
    (or finish_grid_dataset) output directory -- admission-grain, scaled with pooled statistics
    whenever the caller supplied them for a multi-cohort run. joint_output_dir/joint_audit_dir:
    where the flat joint train/val/test + sidecars are written. patients_per_file: joint re-shard
    size (independent of each cohort's own per-cohort shard size). weights/
    n_train_admissions_by_cohort: reported in the joint summary for auditability, not recomputed
    here.

    Namespaces every cohort's admissionid/subject_id (String, f"{cohort}_{id}") unconditionally --
    even for a single-cohort call -- so the joint output's shape never depends on how many cohorts
    were selected. Returns the same {"output_dir", "metadata", "feature_schema", "tte_targets",
    "summary", "integrity"} path dict shape as write_grid_dataset_outputs, plus "scalers" (the
    fitted normalizers -- z-score mean/std and QuantileTransformer objects -- needed to preprocess
    a future inference-time subject the same way; None if no cohort's staging dir had one)."""
    joint_output_dir = Path(joint_output_dir)
    joint_audit_dir = Path(joint_audit_dir)
    joint_output_dir.mkdir(parents=True, exist_ok=True)
    joint_audit_dir.mkdir(parents=True, exist_ok=True)

    grids, metadatas, schemas, ttes, encodings = {}, {}, {}, {}, {}
    raw_admissionid_sets, raw_subject_id_sets = {}, {}
    for cohort, output_dir in cohort_output_dirs.items():
        grid, metadata, schema, tte, encoding = _read_cohort_outputs(cohort, output_dir)
        raw_admissionid_sets[cohort] = set(metadata["admissionid"].to_list())
        if "subject_id" in metadata.columns:
            raw_subject_id_sets[cohort] = set(metadata["subject_id"].to_list())

        grids[cohort] = namespace_ids(grid, cohort, id_columns=("admissionid",))
        # `source` records which cohort's own extraction/labeling conventions produced this row --
        # notably, "outcome" is NOT the same underlying event across cohorts despite matching
        # values: AUMCdb's is patient-level any-time death, MIMIC-IV's is in-hospital-this-
        # admission death. A joint-dataset consumer must key off `source` before comparing outcome
        # semantics across rows, not assume a shared definition.
        #
        # native_admissionid/native_subject_id: the original per-cohort numeric ID, captured
        # BEFORE namespace_ids overwrites admissionid/subject_id with the String cohort-prefixed
        # value -- explicit, so tracing an admission back to its source system never depends on
        # a consumer correctly parsing the namespaced string. That parsing is a real trap: cohort
        # "mimic_iv" itself contains an underscore, so e.g. "mimic_iv_12345" naively split on the
        # first "_" wrongly yields ("mimic", "iv_12345") instead of the real raw ID 12345 --
        # correct manual recovery requires `admissionid.removeprefix(f"{source}_")`, not a blind
        # split. These columns make that unnecessary.
        metadata_with_native_ids = metadata.with_columns([
            pl.col(c).alias(f"native_{c}") for c in ("admissionid", "subject_id") if c in metadata.columns
        ])
        metadatas[cohort] = namespace_ids(metadata_with_native_ids, cohort).with_columns(
            pl.lit(cohort).alias("source")
        )
        schemas[cohort] = schema
        ttes[cohort] = tte
        encodings[cohort] = encoding

    id_collisions = {
        "admissionid": count_cross_cohort_id_collisions(raw_admissionid_sets),
        "subject_id": count_cross_cohort_id_collisions(raw_subject_id_sets),
    }

    schema_values = list(schemas.values())
    if any(s != schema_values[0] for s in schema_values[1:]):
        raise ValueError(
            "feature_schema.json differs across cohorts -- expected identical by construction "
            "(data-content invariant schema, see metaicu.grid.schema_union)"
        )
    joint_schema = schema_values[0]

    encoding_values = [e for e in encodings.values() if e is not None]
    if len(encoding_values) > 1 and any(not e.equals(encoding_values[0]) for e in encoding_values[1:]):
        raise ValueError(
            "categorical_encoding.csv differs across cohorts -- one-hot vocabularies must match "
            "for a joint build (see metaicu.grid.schema_union.compute_union_categorical_vocab)"
        )

    # "diagonal_relaxed" (not "vertical"): the feature_schema.json equality check above already
    # guarantees every cohort's grid has the same COLUMN SET (data-content invariant schema), but
    # not the same column ORDER -- schema_union.pad_matches_for_cohort appends newly-padded tags
    # at the end of each cohort's own matches dict, so a tag padded for one cohort but already
    # native (in a different position) for another leaves the two cohorts' canonical_column_order
    # results genuinely different, which "vertical" (exact order match required) rejects.
    joint_grid = pl.concat(list(grids.values()), how="diagonal_relaxed")
    joint_metadata = pl.concat(list(metadatas.values()), how="diagonal_relaxed")
    # admissionid: one row per admission, so this genuinely must be globally unique.
    # subject_id is NOT checked the same way -- metadata is admission-grain, and a real patient
    # with >1 admission legitimately repeats their own subject_id across rows; that is not a
    # collision. A real CROSS-COHORT subject_id collision is structurally impossible after
    # namespacing anyway (the cohort prefix always differs), and was already checked pre-
    # namespacing above via count_cross_cohort_id_collisions/raw_subject_id_sets.
    assert_globally_unique(joint_metadata, "admissionid")

    shard_info: dict[str, dict[str, int | str]] = {}
    split_counts = {}
    for split in ("train", "val", "test"):
        split_ids = sorted(joint_metadata.filter(pl.col("split") == split)["admissionid"].to_list())
        split_counts[split] = len(split_ids)
        if not split_ids:
            continue
        split_dir = joint_output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        for shard_index, start in enumerate(range(0, len(split_ids), patients_per_file)):
            batch_ids = split_ids[start:start + patients_per_file]
            shard = joint_grid.filter(pl.col("admissionid").is_in(batch_ids)).sort(["admissionid", "hour"])
            shard_file = f"{shard_index}.parquet"
            shard.write_parquet(split_dir / shard_file)
            counts = shard.group_by("admissionid").len()
            for admission_id, row_count in zip(counts["admissionid"].to_list(), counts["len"].to_list()):
                shard_info[admission_id] = {"shard_file": f"{split}/{shard_file}", "n_rows": row_count}
            log.info(f"wrote {split}/{shard_file}: {len(batch_ids)} admissions, {shard.height} rows")

    joint_metadata = joint_metadata.with_columns(
        pl.col("admissionid").replace_strict(
            {aid: info["shard_file"] for aid, info in shard_info.items()}, default=None
        ).alias("shard_file"),
        pl.col("admissionid").replace_strict(
            {aid: info["n_rows"] for aid, info in shard_info.items()}, default=0
        ).alias("n_rows"),
    )
    metadata_path = joint_output_dir / "metadata.csv"
    joint_metadata.write_csv(metadata_path)

    schema_path = joint_output_dir / "feature_schema.json"
    schema_path.write_text(json.dumps(joint_schema, indent=2, sort_keys=True))

    tte_targets_path = joint_output_dir / "tte_targets.json"
    tte_targets_path.write_text(json.dumps(merge_tte_targets(ttes), indent=2))

    if encoding_values:
        encoding_values[0].write_csv(joint_output_dir / "categorical_encoding.csv")

    # scalers.pkl/scalers.summary.json are written by each cohort's own finish_grid_dataset into
    # its per-cohort STAGING dir only -- copy the canonical (first, alphabetically) cohort's copy
    # into the joint output too, so a consumer that only keeps joint_output_dir around (the staging
    # dirs are documented as disposable intermediates) still has the exact fitted normalizers
    # (z-score mean/std, QuantileTransformer objects) needed to preprocess a future inference-time
    # subject consistently. With len(datasets) > 1 every pooled tag's scaler entry is the SAME
    # external_scalers dict applied to both cohorts (see _compute_pooled_scalers), so any one
    # cohort's copy is the joint one; picking alphabetically first just makes the choice deterministic.
    canonical_cohort = sorted(cohort_output_dirs)[0]
    canonical_scalers_dir = Path(cohort_output_dirs[canonical_cohort])
    scalers_path = canonical_scalers_dir / "scalers.pkl"
    scalers_summary_path = canonical_scalers_dir / "scalers.summary.json"
    if scalers_path.exists():
        shutil.copy2(scalers_path, joint_output_dir / "scalers.pkl")
    if scalers_summary_path.exists():
        shutil.copy2(scalers_summary_path, joint_output_dir / "scalers.summary.json")

    integrity_path = audit_grid_dataset(
        joint_output_dir, joint_audit_dir, joint_grid.columns, subject_column="subject_id"
    )

    summary_path = joint_audit_dir / "joint_grid_build_summary.json"
    summary_path.write_text(json.dumps({
        "cohorts": sorted(cohort_output_dirs),
        "cohort_admission_counts": {cohort: metadatas[cohort].height for cohort in cohort_output_dirs},
        "cohort_weights": weights,
        "n_train_admissions_by_cohort": n_train_admissions_by_cohort,
        "split_admission_counts": split_counts,
        "cross_cohort_id_collisions_pre_namespacing": id_collisions,
        "grid_rows": joint_grid.height,
    }, indent=2, sort_keys=True, default=str))

    return {
        "output_dir": joint_output_dir,
        "metadata": metadata_path,
        "feature_schema": schema_path,
        "tte_targets": tte_targets_path,
        "summary": summary_path,
        "integrity": integrity_path,
        "scalers": joint_output_dir / "scalers.pkl" if scalers_path.exists() else None,
    }
