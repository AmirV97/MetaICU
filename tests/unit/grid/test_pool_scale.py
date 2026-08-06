"""Unit tests for metaicu.grid.pool_scale -- the cross-cohort pooled-statistics helpers used to
fit dataset scalers on weighted, pooled train-split data instead of each cohort independently."""

from __future__ import annotations

import math
import unittest

import numpy as np
from sklearn.preprocessing import QuantileTransformer

from metaicu.grid.pool_scale import (
    MIN_TRAIN_VALUES,
    _replication_counts,
    compute_cohort_weights,
    pooled_fit_treatment,
    pooled_mean_std,
)


class ComputeCohortWeightsTests(unittest.TestCase):
    def test_weights_are_sqrt_normalized_to_one_larger_cohort_dominates(self) -> None:
        weights = compute_cohort_weights({"a": 100, "b": 400})
        self.assertAlmostEqual(weights["a"], 1 / 3)
        self.assertAlmostEqual(weights["b"], 2 / 3)
        self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_equal_n_gives_equal_weights(self) -> None:
        weights = compute_cohort_weights({"a": 50, "b": 50})
        self.assertAlmostEqual(weights["a"], 0.5)
        self.assertAlmostEqual(weights["b"], 0.5)


class PooledMeanStdTests(unittest.TestCase):
    def test_matches_hand_computed_two_term_formula(self) -> None:
        # Deliberately different per-cohort means -- a naive average of the two SDs ((2+4)/2=3)
        # would be very wrong here; the correct pooled SD also accounts for the between-cohort
        # spread of means (10 vs 20), giving sqrt(35) ~= 5.916, nearly double the naive answer.
        per_cohort = {
            "a": {"mean": 10.0, "std": 2.0, "n": 100},
            "b": {"mean": 20.0, "std": 4.0, "n": 100},
        }
        mean, std = pooled_mean_std(per_cohort, {"a": 0.5, "b": 0.5})
        self.assertAlmostEqual(mean, 15.0)
        self.assertAlmostEqual(std, math.sqrt(35.0))

    def test_single_contributor_reproduces_its_own_fit_exactly(self) -> None:
        per_cohort = {"b": {"mean": 20.0, "std": 4.0, "n": 50}}
        # weights carries an "a" entry the tag has no real data for (e.g. structural_zero) --
        # must be ignored via renormalization over per_cohort's own keys, not treated as a
        # missing-key error and not diluting b's fit.
        mean, std = pooled_mean_std(per_cohort, {"a": 0.7, "b": 0.3})
        self.assertAlmostEqual(mean, 20.0)
        self.assertAlmostEqual(std, 4.0)


class ReplicationCountsTests(unittest.TestCase):
    def test_equal_sizes_equal_weights_gives_count_one_each(self) -> None:
        counts = _replication_counts({"a": 50, "b": 50}, {"a": 0.5, "b": 0.5})
        self.assertEqual(counts, {"a": 1, "b": 1})

    def test_single_cohort_gives_count_one(self) -> None:
        counts = _replication_counts({"a": 37}, {"a": 1.0})
        self.assertEqual(counts, {"a": 1})

    def test_skewed_weight_biases_replication_toward_higher_weight_cohort(self) -> None:
        counts = _replication_counts({"a": 100, "b": 100}, {"a": 0.8, "b": 0.2})
        self.assertEqual(counts, {"a": 4, "b": 1})


class PooledFitTreatmentTests(unittest.TestCase):
    def test_returns_none_below_min_train_values_pooled_total(self) -> None:
        train_values_by_cohort = {"a": np.array([1.0, 2.0, 3.0]), "b": np.array([1.0, 2.0])}
        self.assertLess(sum(len(v) for v in train_values_by_cohort.values()), MIN_TRAIN_VALUES)
        qt = pooled_fit_treatment(train_values_by_cohort, {"a": 0.5, "b": 0.5}, "test_tag")
        self.assertIsNone(qt)

    def test_single_contributing_cohort_reproduces_solo_fit_exactly(self) -> None:
        # "aumcdb" has zero real values for this tag (e.g. pt, structural_zero on AUMC) -- the
        # pooled fit must be 100% derived from "mimic_iv", not diluted or altered by the empty
        # cohort's presence in the input dict.
        own_values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0])
        train_values_by_cohort = {"aumcdb": np.array([]), "mimic_iv": own_values}
        qt_pooled = pooled_fit_treatment(train_values_by_cohort, {"aumcdb": 0.7, "mimic_iv": 0.3}, "pt")
        qt_reference = QuantileTransformer(
            output_distribution="uniform", n_quantiles=min(1000, len(own_values)), random_state=42
        ).fit(own_values.reshape(-1, 1))
        np.testing.assert_array_equal(qt_pooled.quantiles_, qt_reference.quantiles_)
        np.testing.assert_array_equal(qt_pooled.references_, qt_reference.references_)

    def test_structural_zero_cohort_is_excluded_like_a_missing_key(self) -> None:
        # A cohort with only zero/negative values (e.g. real "no medication" rows, not missing
        # data) must be excluded from the pooled fit exactly like the previous test's empty
        # array -- scale.py's own "0 = no medication" convention means 0 carries no fit-relevant
        # information (see _apply_treatment_scaler, which hard-maps <=0 to 0 regardless of fit).
        own_values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0])
        train_values_by_cohort = {"aumcdb": np.zeros(20), "mimic_iv": own_values}
        qt_pooled = pooled_fit_treatment(train_values_by_cohort, {"aumcdb": 0.7, "mimic_iv": 0.3}, "pt")
        qt_reference = QuantileTransformer(
            output_distribution="uniform", n_quantiles=min(1000, len(own_values)), random_state=42
        ).fit(own_values.reshape(-1, 1))
        np.testing.assert_array_equal(qt_pooled.quantiles_, qt_reference.quantiles_)


if __name__ == "__main__":
    unittest.main(verbosity=2)
