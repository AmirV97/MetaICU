"""
Train/val/test split assignment, at the granularity of --unit-of-analysis
(admissionid, or patientid to keep all of one patient's admissions in the same split and
avoid cross-split leakage). Uses random.Random(seed), matching grid/sampling.py's RNG choice.
"""
import logging
import random

import polars as pl

log = logging.getLogger(__name__)


def assign_splits(admissions, unit, train_frac, val_frac, test_frac, seed):
    """admissions: DataFrame with at least admissionid + (patientid if unit=="subject").
    unit: "admission" or "subject". Returns a (admissionid, split) DataFrame, split in
    {"train","val","test"}."""
    assert abs(train_frac + val_frac + test_frac - 1.0) < 1e-6, \
        f"train/val/test fracs must sum to 1.0, got {train_frac}+{val_frac}+{test_frac}"
    unit_col = "patientid" if unit == "subject" else "admissionid"

    unit_ids = sorted(admissions[unit_col].unique().to_list())
    rng = random.Random(seed)
    rng.shuffle(unit_ids)

    n = len(unit_ids)
    n_train = round(n * train_frac)
    n_val = round(n * val_frac)
    split_of = {
        uid: ("train" if i < n_train else "val" if i < n_train + n_val else "test")
        for i, uid in enumerate(unit_ids)
    }
    log.info(f"split by {unit} ({n} unique {unit_col}s, seed={seed}): "
             f"train={n_train}, val={n_val}, test={n - n_train - n_val}")

    split_df = pl.DataFrame({unit_col: list(split_of.keys()), "split": list(split_of.values())})
    cols = list(dict.fromkeys(["admissionid", unit_col]))
    return admissions.select(cols).join(split_df, on=unit_col).select(["admissionid", "split"])
