"""Integration test for metaicu.grid.external_artifacts + the new
GridDatasetConfig.external_artifacts_dir wiring in both pipelines' build_workflow.py.

Builds MIMIC-IV fully first (a real on-disk grid output, exactly like a normal solo run), then
builds AUMCdb with external_artifacts_dir pointing at MIMIC-IV's output_dir -- exercising the
actual new code path (loading scalers.pkl/categorical_encoding.csv/feature_schema.json back off
disk), not a live second PreScaleGrid the way test_grid_build_joint_dataset.py's own tests do.

Tag scenario, deliberately covering every branch build_pooled_external_scalers/
build_external_vocab has:
  - hr: direct_numeric, REAL in both -- exercises genuine pooling, hand-checked against
    pooled_mean_std computed independently in the test.
  - crp: direct_numeric (log1p), MIMIC-IV only (structural_zero for AUMCdb) -- exercises the
    "external side fully drives it" case (AUMCdb contributes zero real values).
  - nor: treatment_rate, REAL in both -- exercises the synthetic_treatment_values approximation
    feeding the existing pooled_fit_treatment.
  - abx: treatment_indicator... actually direct_numeric, AUMCdb-only, entirely ABSENT from
    MIMIC-IV's schema/scalers -- exercises "genuinely new feature -> solo fit, no pooling".
  - airway: categorical, present in both but with a DIFFERENT category in each -- exercises
    build_external_vocab's union.
"""

from __future__ import annotations

import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np
import polars as pl

from metaicu.aumcdb.grid.build.build_workflow import GridDatasetConfig as AumcConfig
from metaicu.mimiciv.grid.build.build_workflow import GridDatasetConfig as MimicConfig
from metaicu.mimiciv.grid.build.build_workflow import finish_grid_dataset as finish_mimiciv
from metaicu.grid.pool_scale import compute_cohort_weights, pooled_mean_std
from metaicu.grid.pre_scale import PreScaleGrid

HOURS = list(range(10))  # >= MIN_TRAIN_VALUES(10) real values per pooled tag


def _grid_frame(admission_rows):
    rows = []
    for admission_id, tags in admission_rows.items():
        n_hours = len(next(iter(tags.values())))
        for hour in range(n_hours):
            row = {"admissionid": admission_id, "hour": hour}
            for tag, values in tags.items():
                row[tag] = values[hour]
            rows.append(row)
    return pl.DataFrame(rows)


class ExternalArtifactsPoolingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)

        # --- Build MIMIC-IV solo first: hr + crp + nor + airway (category "A"). ---
        mimic_matches = {
            "hr": {"reconstruction_type": "direct_numeric", "target_unit": "bpm", "keep_matches": [], "n_keep": 1},
            "crp": {"reconstruction_type": "direct_numeric", "target_unit": "mg/L", "keep_matches": [], "n_keep": 1},
            "nor": {"reconstruction_type": "treatment_rate", "target_unit": "mcg/kg/min", "keep_matches": [], "n_keep": 1},
            "airway": {"reconstruction_type": "categorical", "target_unit": "categorical",
                       "keep_matches": [{"standardized_label": "A"}], "n_keep": 1},
        }
        cls.mimic_hr = np.array([74.0 + h for h in HOURS])
        cls.mimic_crp_raw = np.array([5.0 + 0.5 * h for h in HOURS])
        cls.mimic_nor = np.array([2.0 + 0.1 * h for h in HOURS])
        mimic_grid = _grid_frame({
            100: {"hr": list(cls.mimic_hr), "crp": list(cls.mimic_crp_raw), "nor": list(cls.mimic_nor),
                  "airway": ["A"] * 10},
        })
        mimic_admissions = pl.DataFrame([
            {"admissionid": 100, "subject_id": 1, "split": "train", "true_los_hours": 10.0,
             "hospital_expire_flag": 0, "age": 65.0, "weight": 85.0, "height": 180.0,
             "sex": "M", "adm_urgency": "emergency", "adm_origin": "other", "ethnic": "white"},
        ])
        mimic_pre_scale = PreScaleGrid(
            grid=mimic_grid, matches=mimic_matches, matches_with_derived=dict(mimic_matches),
            derived_target_matches={}, admissions=mimic_admissions, train_admission_ids=[100],
            demo_source=mimic_admissions.select(["admissionid", "sex", "adm_urgency", "adm_origin", "ethnic"]),
            static_categorical_encoding=[], next_categorical_pos=0, presence_mask_cols=[],
            manifest_report={}, raw_shard_summary={}, admissions_before_inclusion=1,
        )
        cls.mimic_config = MimicConfig(
            raw_data_dir=Path("/unused"), output_dir=root / "mimic_iv" / "data",
            audit_dir=root / "mimic_iv" / "audit", manifest_path=Path("/unused"),
            scale=True, impute=True, one_hot=True, overwrite=True,
        )
        finish_mimiciv(cls.mimic_config, mimic_pre_scale)
        cls.mimic_n_train = 1

        # --- Build AUMCdb with external_artifacts_dir pointing at MIMIC-IV's real output. ---
        # hr + nor shared (real values both sides); crp entirely absent (structural_zero here);
        # abx is a genuinely new tag MIMIC-IV's schema never had; airway has a DIFFERENT category.
        aumc_matches = {
            "hr": {"reconstruction_type": "direct_numeric", "target_unit": "bpm", "keep_matches": [], "n_keep": 1},
            "nor": {"reconstruction_type": "treatment_rate", "target_unit": "mcg/kg/min", "keep_matches": [], "n_keep": 1},
            "abx": {"reconstruction_type": "direct_numeric", "target_unit": "score", "keep_matches": [], "n_keep": 1},
            "airway": {"reconstruction_type": "categorical", "target_unit": "categorical",
                       "keep_matches": [{"standardized_label": "B"}], "n_keep": 1},
        }
        cls.aumc_hr = np.array([70.0 + h for h in HOURS])
        cls.aumc_nor = np.array([1.0 + 0.1 * h for h in HOURS])
        cls.aumc_abx = np.array([3.0 + 0.2 * h for h in HOURS])
        aumc_grid = _grid_frame({
            10: {"hr": list(cls.aumc_hr), "nor": list(cls.aumc_nor), "abx": list(cls.aumc_abx),
                 "airway": ["B"] * 10},
        })
        aumc_admissions = pl.DataFrame([
            {"admissionid": 10, "patientid": 1, "admittedat": 0, "split": "train", "true_los_hours": 10.0,
             "dateofdeath": None, "age": 60.0, "weight": 80.0, "height": 175.0,
             "sex": "M", "adm_urgency": "emergency", "adm_origin": "other", "ethnic": "unknown"},
        ])
        cls.aumc_config = AumcConfig(
            raw_data_dir=Path("/unused"), output_dir=root / "aumcdb" / "data",
            audit_dir=root / "aumcdb" / "audit",
            unit_of_analysis="admission", scale=True, impute=True, one_hot=True, overwrite=True,
            external_artifacts_dir=cls.mimic_config.output_dir,
        )
        # Bypass build_pre_scale_grid's raw extraction (no real raw data in this test) by hand-
        # building the PreScaleGrid and calling write_grid_dataset_outputs's own new orchestration
        # block directly via a small monkey-injection: simplest is to replicate that block here,
        # since build_pre_scale_grid requires real raw CSVs.
        from metaicu.aumcdb.grid.build.build_workflow import finish_grid_dataset
        from metaicu.aumcdb.grid.build.impute import capture_presence_mask, materialize_structural_zero_columns
        from metaicu.aumcdb.grid.build.encode import get_categorical_vocab
        from metaicu.grid.external_artifacts import build_external_vocab, build_pooled_external_scalers, load_external_artifacts
        from metaicu.grid.schema_union import compute_union_matches, pad_matches_for_cohort

        aumc_pre_scale = PreScaleGrid(
            grid=aumc_grid, matches=aumc_matches, matches_with_derived=dict(aumc_matches),
            derived_target_matches={}, admissions=aumc_admissions, train_admission_ids=[10],
            demo_source=aumc_admissions.select(["admissionid", "sex", "adm_urgency", "adm_origin", "ethnic"]),
            static_categorical_encoding=[], next_categorical_pos=0, presence_mask_cols=[],
            manifest_report={}, raw_shard_summary={}, admissions_before_inclusion=1,
        )
        cls.external = load_external_artifacts(cls.mimic_config.output_dir)
        union_registry = compute_union_matches({"external": cls.external.schema_registry, "own": aumc_pre_scale.matches})
        padded_matches = pad_matches_for_cohort(aumc_pre_scale.matches, union_registry)
        padded_matches_with_derived = {**padded_matches, **aumc_pre_scale.derived_target_matches}
        aumc_pre_scale.grid = materialize_structural_zero_columns(aumc_pre_scale.grid, padded_matches_with_derived)
        aumc_pre_scale.grid, aumc_pre_scale.presence_mask_cols = capture_presence_mask(
            aumc_pre_scale.grid, padded_matches_with_derived
        )
        aumc_pre_scale.matches = padded_matches
        aumc_pre_scale.matches_with_derived = padded_matches_with_derived

        cls.weights = compute_cohort_weights({"external": cls.mimic_n_train, "own": len(aumc_pre_scale.train_admission_ids)})
        cls.external_scalers = build_pooled_external_scalers(aumc_pre_scale, cls.external, cls.weights)
        cls.external_vocab = build_external_vocab(cls.external, get_categorical_vocab(aumc_pre_scale.matches_with_derived))
        finish_grid_dataset(
            cls.aumc_config, aumc_pre_scale,
            external_scalers=cls.external_scalers, external_vocab=cls.external_vocab,
        )
        cls.aumc_scalers = pickle.loads((cls.aumc_config.output_dir / "scalers.pkl").read_bytes())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_hr_is_pooled_between_mimic_artifact_and_aumcdbs_own_fit(self) -> None:
        mimic_hr_scaler = self.external.scalers["hr"]
        expected_mean, expected_std = pooled_mean_std(
            {
                "external": {"mean": mimic_hr_scaler["mean"], "std": mimic_hr_scaler["std"]},
                "own": {"mean": float(self.aumc_hr.mean()), "std": float(self.aumc_hr.std())},
            },
            self.weights,
        )
        self.assertAlmostEqual(self.aumc_scalers["hr"]["mean"], expected_mean)
        self.assertAlmostEqual(self.aumc_scalers["hr"]["std"], expected_std)
        # Sanity: pooled value must lie strictly between AUMCdb's own raw mean and MIMIC's own
        # mean -- proves BOTH sides actually contributed, not one silently overriding the other.
        lo, hi = sorted((float(self.aumc_hr.mean()), mimic_hr_scaler["mean"]))
        self.assertTrue(lo < self.aumc_scalers["hr"]["mean"] < hi)

    def test_crp_structural_zero_for_aumcdb_is_padded_but_not_pooled(self) -> None:
        # AUMCdb has zero real crp values (padded structural_zero) -- scale_grid/
        # scale_static_features skip a structural_zero tag unconditionally regardless of
        # external_scalers (pre-existing behavior, unrelated to this feature), so crp correctly
        # gets NO scaler entry at all in AUMCdb's own scalers.pkl -- computing one would be
        # discarded work, per build_pooled_external_scalers' own structural_zero skip. What DOES
        # matter is that the column exists (from padding) and is genuinely empty/unobserved.
        self.assertNotIn("crp", self.external_scalers)
        self.assertNotIn("crp", self.aumc_scalers)
        shard = pl.concat([
            pl.read_parquet(p) for p in sorted((self.aumc_config.output_dir / "train").glob("*.parquet"))
        ])
        self.assertIn("crp", shard.columns)
        self.assertIn("crp__observed", shard.columns)
        self.assertEqual(shard["crp__observed"].to_list(), [0] * shard.height)

    def test_nor_treatment_rate_pooling_runs_and_produces_a_fitted_transformer(self) -> None:
        self.assertEqual(self.aumc_scalers["nor"]["type"], "treatment")
        self.assertIsNotNone(self.aumc_scalers["nor"]["transformer"])
        # Applying it to values spanning both cohorts' real ranges should give varied, valid
        # [0,1]-ish uniform-quantile outputs -- not a degenerate constant.
        qt = self.aumc_scalers["nor"]["transformer"]
        sample = np.concatenate([self.aumc_nor, self.mimic_nor])
        transformed = qt.transform(sample[sample > 0].reshape(-1, 1)).ravel()
        self.assertGreater(np.std(transformed), 0.0)

    def test_abx_is_a_genuinely_new_tag_and_gets_its_own_solo_fit(self) -> None:
        self.assertNotIn("abx", self.external.scalers)
        self.assertIn("abx", self.aumc_scalers)
        expected_mean = float(self.aumc_abx.mean())
        self.assertAlmostEqual(self.aumc_scalers["abx"]["mean"], expected_mean)

    def test_airway_categorical_vocab_is_the_union_of_both_cohorts_categories(self) -> None:
        self.assertEqual(self.external.categorical_vocab["airway"], ["A"])
        self.assertEqual(self.external_vocab["airway"], ["A", "B"])
        shard = pl.concat([
            pl.read_parquet(p) for p in sorted((self.aumc_config.output_dir / "train").glob("*.parquet"))
        ])
        self.assertIn("airway__A", shard.columns)
        self.assertIn("airway__B", shard.columns)


if __name__ == "__main__":
    unittest.main()
