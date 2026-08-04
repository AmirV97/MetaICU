"""Fast structural tests for the installable MIMIC-IV hourly-grid pipeline. Mirrors
tests/integration/grid/test_grid_dataset_structure.py, adapted for two real differences: no
unit_of_analysis (M4_grid's split is unconditionally by subject_id, its shard/metadata output
unconditionally admission-grain -- see GridDatasetConfig's own docstring), and a dedicated
regression test for the Stage 0 split-by-subject fix (grid.build.split.assign_splits used to
accept a `unit` parameter that could split by admission instead, a real cross-split leakage
risk for multi-admission patients -- never triggered in practice, but removed entirely rather
than left as a footgun)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import polars as pl
from omegaconf import OmegaConf


from metaicu.mimiciv.grid.build.build_workflow import GridDatasetConfig
from metaicu.mimiciv.grid.build.encode import (
    get_categorical_vocab,
    one_hot_encode_categorical,
    one_hot_encode_columns,
)
from metaicu.mimiciv.grid.build.extract_static import (
    ETHNIC_CATEGORIES,
    HEIGHT_ITEMID,
    RACE_GROUP_BY_SOURCE_LABEL,
    WEIGHT_ITEMID,
    _filter_plausible_weight_height,
)
from metaicu.mimiciv.grid.build.extract_rate import _apply_rate_unit_conversions
from metaicu.mimiciv.grid.build.extract_indicator import _prescription_on_hours
from metaicu.mimiciv.grid.build.split import assign_splits
from metaicu.mimiciv.grid.cli.grid_build_dataset import _build_config
from metaicu.mimiciv.grid.build.manifest_parser import DEFAULT_REVIEWED_MANIFEST, parse_manifest


class GridDatasetStructureTests(unittest.TestCase):
    def test_static_weight_height_reject_implausible_raw_values_before_median(self) -> None:
        rows = pl.DataFrame({
            "admissionid": list(range(10)),
            "itemid": [WEIGHT_ITEMID] * 5 + [HEIGHT_ITEMID] * 5,
            "valuenum": [29.9, 30.0, 300.0, 300.1, None, 99.9, 100.0, 250.0, 250.1, None],
        })

        filtered = _filter_plausible_weight_height(rows)

        self.assertEqual(rows.shape, (10, 3))
        self.assertEqual(filtered.shape, (4, 3))
        self.assertEqual(filtered.schema, rows.schema)
        self.assertEqual(filtered["admissionid"].to_list(), [1, 2, 6, 7])
        self.assertEqual(filtered["valuenum"].to_list(), [30.0, 300.0, 100.0, 250.0])

    def test_race_mapping_is_exhaustive_and_emits_six_class_schema(self) -> None:
        source = pl.DataFrame({"race": list(RACE_GROUP_BY_SOURCE_LABEL)})
        collapsed = source.select(
            pl.col("race").replace_strict(
                RACE_GROUP_BY_SOURCE_LABEL, return_dtype=pl.String
            ).alias("ethnic")
        )
        encoded, schema, _ = one_hot_encode_columns(
            collapsed, {"ethnic": ETHNIC_CATEGORIES}
        )
        columns = [row["column_name"] for row in schema]

        self.assertEqual(len(RACE_GROUP_BY_SOURCE_LABEL) - 1, 33)
        self.assertEqual(
            columns,
            [
                "ethnic__ASIAN",
                "ethnic__BLACK",
                "ethnic__HISPANIC_LATINO",
                "ethnic__OTHER",
                "ethnic__WHITE",
                "ethnic__missing",
            ],
        )
        self.assertEqual(
            set(collapsed["ethnic"].drop_nulls().unique()),
            set(ETHNIC_CATEGORIES),
        )
        self.assertEqual(encoded.select(pl.sum_horizontal(columns)).to_series().unique().to_list(), [1])

        mapped = dict(zip(source["race"].to_list(), collapsed["ethnic"].to_list()))
        self.assertIsNone(mapped["UNKNOWN"])
        self.assertIsNone(mapped["UNABLE TO OBTAIN"])
        self.assertIsNone(mapped["PATIENT DECLINED TO ANSWER"])
        self.assertEqual(mapped["WHITE - RUSSIAN"], "WHITE")
        self.assertEqual(mapped["BLACK/CAPE VERDEAN"], "BLACK")
        self.assertEqual(mapped["HISPANIC/LATINO - PUERTO RICAN"], "HISPANIC_LATINO")
        self.assertEqual(mapped["ASIAN - CHINESE"], "ASIAN")
        self.assertEqual(mapped["MULTIPLE RACE/ETHNICITY"], "OTHER")

    def test_rass_preserves_full_manifest_detail_but_emits_aumc_schema(self) -> None:
        matches, _ = parse_manifest()
        raw_labels = {
            match["standardized_label"]
            for match in matches["rass"]["keep_matches"]
            if match["standardized_label"]
        }
        source = pl.DataFrame({
            "admissionid": [1, 2, 3, 4],
            "rass": ["+2 Agitated", "+3 Very agitated", "+4 Combative", None],
        })

        encoded, _ = one_hot_encode_categorical(source, matches)
        output_vocab = get_categorical_vocab(matches)["rass"]

        self.assertIn("+3 Very agitated", raw_labels)
        self.assertIn("+4 Combative", raw_labels)
        self.assertNotIn("+3 Very agitated", output_vocab)
        self.assertNotIn("+4 Combative", output_vocab)
        self.assertEqual(len(output_vocab), 8)
        self.assertEqual(encoded["rass__2_Agitated"].to_list(), [1, 1, 1, 0])
        self.assertEqual(encoded["rass__missing"].to_list(), [0, 0, 0, 1])

    def test_recoverable_icu_medication_sources_are_in_manifest(self) -> None:
        matches, _ = parse_manifest()

        self.assertEqual(
            {(m["table"], m["itemid"]) for m in matches["inf_alb"]["keep_matches"]},
            {("inputevents", "220862"), ("inputevents", "220864")},
        )
        self.assertIn(
            ("inputevents", "221342"),
            {(m["table"], m["itemid"]) for m in matches["teophyllin"]["keep_matches"]},
        )
        self.assertIn(
            ("inputevents", "221342"),
            {(m["table"], m["itemid"]) for m in matches["teophyllin_ind"]["keep_matches"]},
        )
        self.assertEqual(
            {(m["table"], m["itemid"]) for m in matches["supp_o2_vent"]["keep_matches"]},
            {("chartevents", "223835"), ("chartevents", "229280"), ("chartevents", "229841")},
        )
        oth_diur = matches["oth_diur"]["keep_matches"]
        self.assertEqual(len(oth_diur), 1)
        self.assertEqual(oth_diur[0]["table"], "prescriptions")
        self.assertEqual(len(oth_diur[0]["ndc_codes"]), 29)

    def test_prescription_intervals_reject_reverse_and_treat_null_stop_as_point(self) -> None:
        rows = pl.DataFrame({
            "admissionid": [1, 1, 1, 1],
            "ndc": ["A", "A", "A", "A"],
            "start_admission_relative_ms": [-1_000, 7_200_000, 8_000_000, 18_000_000],
            "stop_admission_relative_ms": [5_400_000, 3_600_000, None, 19_000_000],
            "los_ms": [14_400_000] * 4,
        })
        with patch(
            "metaicu.mimiciv.grid.build.extract_indicator.load_prescription_intervals",
            return_value=rows,
        ):
            result = _prescription_on_hours(Path("/unused"), [("oth_diur", "A")], pl.DataFrame(), None)

        self.assertEqual(rows.shape, (4, 5))
        self.assertEqual(result.sort("hour")["hour"].to_list(), [0, 1, 2])

    def test_aminophylline_rate_converts_from_mg_per_kg_hour_to_mg_per_min(self) -> None:
        rows = pl.DataFrame({
            "tag": ["teophyllin", "milrin"],
            "itemid": [221342, 221986],
            "rate": [0.6, 0.5],
            "rateuom": ["mg/kg/hour", "mcg/kg/min"],
            "patientweight": [100.0, 80.0],
        })

        converted = _apply_rate_unit_conversions(rows)

        self.assertAlmostEqual(converted["rate"][0], 1.0)
        self.assertAlmostEqual(converted["rate"][1], 40.0)

    def test_packaged_reviewed_manifest_parses_without_workspace_paths(self) -> None:
        self.assertTrue(DEFAULT_REVIEWED_MANIFEST.exists())
        matches, report = parse_manifest()
        self.assertGreater(len(matches), 0)
        self.assertIn("map", matches)
        self.assertGreater(report["n_total_blocks"], len(matches))
        self.assertEqual(report["structural_zero"], ["tri"])
        self.assertTrue(matches["tri"]["structural_zero"])

    def test_hydra_config_resolves_parent_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent_dir = Path(tmp) / "workspace"
            config = _build_config(OmegaConf.create({
                "paths": {
                    "parent_dir": str(parent_dir),
                    "raw_data_dir": None,
                    "raw_shards_dir": None,
                    "output_dir": None,
                    "audit_dir": None,
                    "manifest_path": None,
                    "admission_ids_file": None,
                },
                "split": {"train_frac": 0.8, "val_frac": 0.1, "test_frac": 0.1, "seed": 7},
                "run": {
                    "build_raw_shards": True,
                    "rebuild_raw_shards": False,
                    "raw_shard_rows": 1000,
                    "sample_size": 20,
                    "patients_per_file": 10,
                    "seed": 3,
                    "features": ["map", "lact"],
                    "reconstruction_types": ["direct_numeric"],
                    "apply_inclusion_criteria": True,
                    "scale": True,
                    "impute": True,
                    "one_hot": True,
                },
            }))
        self.assertEqual(config.raw_data_dir, parent_dir / "data/raw")
        self.assertEqual(config.raw_shards_dir, parent_dir / "data/raw_shards")
        self.assertEqual(config.output_dir, parent_dir / "data/grid")
        self.assertEqual(config.audit_dir, parent_dir / "audits/grid_dataset")
        self.assertEqual(config.manifest_path, DEFAULT_REVIEWED_MANIFEST)
        self.assertEqual(config.features, ("map", "lact"))

    def test_grid_config_is_package_local_and_path_explicit(self) -> None:
        config = GridDatasetConfig(
            raw_data_dir=Path("/data/raw"),
            output_dir=Path("/data/grid"),
            audit_dir=Path("/data/audits"),
            manifest_path=Path("/data/manifest.md"),
        )
        self.assertEqual(config.patients_per_file, 1_000)
        self.assertTrue(config.apply_inclusion_criteria)
        self.assertTrue(config.build_raw_shards)
        self.assertEqual(config.raw_shard_rows, 5_000_000)

    def test_split_always_groups_by_subject_id_even_when_leakage_would_otherwise_occur(self) -> None:
        # subject 100 has two admissions; if splitting ever fell back to admission-level (the
        # Stage 0 bug this guards against), a 50/50-ish train/test split could easily place
        # admission 1 in train and admission 2 in test for the SAME patient -- real leakage.
        # Run many seeds: every one must keep both of subject 100's admissions in the same split.
        admissions = pl.DataFrame({
            "admissionid": [1, 2, 3, 4, 5, 6],
            "subject_id": [100, 100, 200, 300, 400, 500],
        })
        for seed in range(20):
            assignments = assign_splits(admissions, train_frac=0.5, val_frac=0.25, test_frac=0.25, seed=seed)
            by_admission = dict(zip(assignments["admissionid"].to_list(), assignments["split"].to_list()))
            self.assertEqual(
                by_admission[1], by_admission[2],
                f"seed={seed}: subject 100's two admissions landed in different splits "
                f"({by_admission[1]!r} vs {by_admission[2]!r}) -- cross-split patient leakage",
            )

    def test_split_has_no_admission_level_fallback_parameter(self) -> None:
        # assign_splits must not accept a unit-of-analysis-style parameter at all -- the Stage 0
        # fix removed it entirely rather than defaulting it to "subject", so there is no
        # remaining code path that could ever select admission-level splitting.
        import inspect
        params = list(inspect.signature(assign_splits).parameters)
        self.assertEqual(params, ["admissions", "train_frac", "val_frac", "test_frac", "seed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
