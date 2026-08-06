"""Fast structural tests for the installable AUMC hourly-grid pipeline."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl
from omegaconf import OmegaConf



from metaicu.aumcdb.grid.build.build_workflow import (
    GridDatasetConfig,
    _write_metadata_by_subject,
    _write_shards,
)
from metaicu.aumcdb.grid.build.encode import one_hot_encode_columns
from metaicu.aumcdb.grid.build.extract_static import (
    ADM_CATEGORIES,
    ORIGIN_TOP4,
    STATIC_CATEGORICAL_VOCAB,
    extract_static_features,
)
from metaicu.aumcdb.grid.build.extract_numeric import _derive_direct_bilirubin
from metaicu.mimiciv.grid.build.extract_static import (
    ADM_CATEGORIES as MIMIC_ADM_CATEGORIES,
    ORIGIN_COLLAPSED as MIMIC_ORIGIN_COLLAPSED,
)
from metaicu.aumcdb.grid.cli.grid_build_dataset import _build_config
from metaicu.aumcdb.grid.build.manifest_parser import DEFAULT_REVIEWED_MANIFEST, parse_manifest


class GridDatasetStructureTests(unittest.TestCase):
    def test_adm_uses_shared_union_schema_without_merging_ward_and_transfer(self) -> None:
        expected = sorted(
            f"{urgency}_{origin}"
            for urgency in ("elective", "emergency")
            for origin in ("ed", "icu_ccu", "missing", "other", "transfer", "ward_same_hospital")
        )
        self.assertEqual(ADM_CATEGORIES, expected)
        self.assertEqual(MIMIC_ADM_CATEGORIES, expected)
        self.assertEqual(ORIGIN_TOP4["Eerste Hulp afdeling zelfde ziekenhuis"], "ed")
        self.assertEqual(ORIGIN_TOP4["CCU/IC zelfde ziekenhuis"], "icu_ccu")
        self.assertEqual(
            ORIGIN_TOP4["Verpleegafdeling zelfde ziekenhuis"], "ward_same_hospital"
        )
        self.assertEqual(MIMIC_ORIGIN_COLLAPSED["TRANSFER FROM HOSPITAL"], "transfer")
        self.assertEqual(MIMIC_ORIGIN_COLLAPSED["PACU"], "icu_ccu")

        admissions = pl.DataFrame({
            "admissionid": [1, 2, 3],
            "agegroup": ["18-39"] * 3,
            "weightgroup": ["70-79"] * 3,
            "heightgroup": ["170-179"] * 3,
            "gender": ["Man"] * 3,
            "urgency": [0, 1, 1],
            "origin": [
                "Eerste Hulp afdeling zelfde ziekenhuis",
                "CCU/IC zelfde ziekenhuis",
                "Verpleegafdeling zelfde ziekenhuis",
            ],
        })
        static = extract_static_features(admissions)
        encoded, schema, _ = one_hot_encode_columns(
            static.select(["admissionid", "adm"]), {"adm": ADM_CATEGORIES}
        )
        columns = [row["column_name"] for row in schema]

        self.assertEqual(
            static["adm"].to_list(),
            ["elective_ed", "emergency_icu_ccu", "emergency_ward_same_hospital"],
        )
        self.assertEqual(columns, [f"adm__{category}" for category in expected] + ["adm__missing"])
        self.assertEqual(
            encoded.select(pl.sum_horizontal(columns).alias("sum"))["sum"].to_list(),
            [1, 1, 1],
        )
        self.assertEqual(encoded["adm__elective_transfer"].to_list(), [0, 0, 0])
        self.assertEqual(encoded["adm__emergency_transfer"].to_list(), [0, 0, 0])

        mimic_adm = pl.DataFrame({
            "admissionid": [10, 11],
            "adm": ["emergency_transfer", "elective_icu_ccu"],
        })
        mimic_encoded, mimic_schema, _ = one_hot_encode_columns(
            mimic_adm, {"adm": MIMIC_ADM_CATEGORIES}
        )
        self.assertEqual(
            [row["column_name"] for row in mimic_schema],
            columns,
        )
        self.assertEqual(mimic_encoded["adm__elective_ward_same_hospital"].to_list(), [0, 0])
        self.assertEqual(mimic_encoded["adm__emergency_ward_same_hospital"].to_list(), [0, 0])

    def test_aumc_sex_is_normalized_to_shared_f_m_schema(self) -> None:
        admissions = pl.DataFrame({
            "admissionid": [1, 2, 3],
            "agegroup": ["18-39"] * 3,
            "weightgroup": ["70-79"] * 3,
            "heightgroup": ["170-179"] * 3,
            "gender": ["Man", "Vrouw", ""],
            "urgency": [1, 0, 1],
            "origin": pl.Series([None, None, None], dtype=pl.String),
        })

        static = extract_static_features(admissions)
        encoded, schema, _ = one_hot_encode_columns(
            static.select(["admissionid", "sex"]),
            {"sex": STATIC_CATEGORICAL_VOCAB["sex"]},
        )

        self.assertEqual(static["sex"].to_list(), ["M", "F", None])
        self.assertEqual(
            [row["column_name"] for row in schema],
            ["sex__F", "sex__M", "sex__missing"],
        )
        self.assertNotIn("sex__Man", encoded.columns)
        self.assertNotIn("sex__Vrouw", encoded.columns)
        self.assertEqual(
            encoded.select(["sex__F", "sex__M", "sex__missing"]).rows(),
            [(0, 1, 0), (1, 0, 0), (0, 0, 1)],
        )

    def test_aumc_ethnic_is_structurally_missing(self) -> None:
        admissions = pl.DataFrame({
            "admissionid": [1, 2],
            "agegroup": ["18-39", "40-49"],
            "weightgroup": ["70-79", "80-89"],
            "heightgroup": ["170-179", "180-189"],
            "gender": ["Man", "Vrouw"],
            "urgency": [1, 0],
            "origin": pl.Series([None, None], dtype=pl.String),
        })

        static = extract_static_features(admissions)
        encoded, schema, _ = one_hot_encode_columns(
            static.select(["admissionid", "ethnic"]),
            {"ethnic": STATIC_CATEGORICAL_VOCAB["ethnic"]},
        )

        self.assertEqual(static.schema["ethnic"], pl.String)
        self.assertEqual(static["ethnic"].to_list(), [None, None])
        self.assertEqual(
            [row["column_name"] for row in schema],
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
            encoded.select([row["column_name"] for row in schema]).rows(),
            [(0, 0, 0, 0, 0, 1), (0, 0, 0, 0, 0, 1)],
        )
        self.assertEqual(encoded["ethnic__missing"].to_list(), [1, 1])

    def test_packaged_reviewed_manifest_parses_without_workspace_paths(self) -> None:
        self.assertTrue(DEFAULT_REVIEWED_MANIFEST.exists())
        matches, report = parse_manifest()
        self.assertGreater(len(matches), 0)
        self.assertIn("map", matches)
        self.assertGreater(report["n_total_blocks"], len(matches))

    def test_direct_bilirubin_is_derived_and_unavailable_features_are_structural(self) -> None:
        matches, report = parse_manifest()
        self.assertEqual(
            report["structural_zero"],
            ["tri", "pt", "milrin", "adh", "milrin_ind", "adh_ind"],
        )
        self.assertEqual(matches["bili_dir"]["keep_matches"][0]["itemid"], "12079")

        raw = pl.DataFrame({
            "admissionid": [1, 1, 1, 1, 2, 2],
            "itemid": [12079, 9945, 12079, 9945, 12079, 6813],
            "value": [0.5, 34.2, 1.2, 17.1, 0.25, 68.4],
            "admission_relative_ms": [0, 0, 3_600_000, 3_600_000, 0, 0],
        })
        derived = _derive_direct_bilirubin(raw).sort("admissionid")

        self.assertEqual(raw.shape, (6, 4))
        self.assertEqual(derived.shape, (2, 4))
        self.assertEqual(derived["converted_value"].to_list(), [1.0, 1.0])

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
                "split": {"unit_of_analysis": "subject", "train_frac": 0.8, "val_frac": 0.1, "test_frac": 0.1, "seed": 7},
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
        self.assertEqual(config.unit_of_analysis, "subject")
        self.assertEqual(config.features, ("map", "lact"))

    def test_grid_config_is_package_local_and_path_explicit(self) -> None:
        config = GridDatasetConfig(
            raw_data_dir=Path("/data/raw"),
            output_dir=Path("/data/grid"),
            audit_dir=Path("/data/audits"),
        )
        self.assertEqual(config.patients_per_file, 1_000)
        self.assertEqual(config.unit_of_analysis, "admission")
        self.assertTrue(config.apply_inclusion_criteria)

    def test_subject_level_shards_concatenate_admissions_in_chronological_order(self) -> None:
        # Patient 100 has two admissions (out of chronological order in the input),
        # patient 200 has one. Demographics differ between patient 100's two admissions.
        admissions = pl.DataFrame({
            "admissionid": [2, 1, 3],
            "patientid": [100, 100, 200],
            "admittedat": [100, 0, 0],
            "true_los_hours": [3.0, 5.0, 10.0],
            "dateofdeath": [12345.0, None, None],
            "age": [55.5, 44.5, 64.5],
            "weight": [70.0, 60.0, 80.0],
            "height": [170.0, 160.0, 180.0],
            "sex": ["Man", "Vrouw", "Man"],
            "adm": ["emergency", "elective", "elective"],
            "ethnic": pl.Series([None, None, None], dtype=pl.String),
            "split": ["train", "train", "val"],
        })
        grid = pl.DataFrame({
            "admissionid": [1, 1, 2, 3],
            "hour": [0, 1, 0, 0],
            "val": [10.0, 11.0, 20.0, 30.0],
        })

        with tempfile.TemporaryDirectory() as tmp:
            split_dir = Path(tmp)
            shard_info = _write_shards(
                grid, admissions, [1, 2, 3], split_dir, units_per_file=10, unit_of_analysis="subject"
            )
            shard = pl.read_parquet(split_dir / "0.parquet")
            metadata_path = split_dir / "metadata.csv"
            _write_metadata_by_subject(admissions, shard_info, metadata_path)
            metadata = pl.read_csv(metadata_path)

        # both patients land in one shard (units_per_file=10); admission 1 (earlier)
        # precedes admission 2 (later) for patient 100.
        patient_100_rows = shard.filter(pl.col("admissionid").is_in([1, 2]))
        self.assertEqual(patient_100_rows["admissionid"].to_list(), [1, 1, 2])

        row_100 = metadata.filter(pl.col("subject_id") == 100).row(0, named=True)
        self.assertEqual(row_100["admission_ids"], "1,2")
        self.assertEqual(row_100["n_admissions"], 2)
        self.assertEqual(row_100["outcome"], "died")  # from admission 2, the later one
        self.assertEqual(row_100["age"], 44.5)  # from admission 1, the earlier one
        self.assertEqual(row_100["weight"], 60.0)
        self.assertAlmostEqual(row_100["los_hours"], 8.0)
        self.assertEqual(row_100["n_rows"], 3)

        row_200 = metadata.filter(pl.col("subject_id") == 200).row(0, named=True)
        self.assertEqual(row_200["admission_ids"], "3")
        self.assertEqual(row_200["n_admissions"], 1)
        self.assertEqual(row_200["outcome"], "alive")


if __name__ == "__main__":
    unittest.main(verbosity=2)
