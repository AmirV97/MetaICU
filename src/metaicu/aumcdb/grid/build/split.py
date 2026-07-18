"""
Train/val/test split assignment at the patient (subject) level, so all of one patient's
admissions land in the same split and repeat admissions never leak across splits.
Uses random.Random(seed), matching grid/sampling.py's RNG choice.
"""
import logging
import random

import polars as pl

log = logging.getLogger(__name__)


def assign_splits(admissions, train_frac, val_frac, test_frac, seed):
    """admissions: DataFrame with at least admissionid + patientid.
    Returns a (admissionid, split) DataFrame, split in {"train","val","test"}."""
    assert abs(train_frac + val_frac + test_frac - 1.0) < 1e-6, \
        f"train/val/test fracs must sum to 1.0, got {train_frac}+{val_frac}+{test_frac}"

    patient_ids = sorted(admissions["patientid"].unique().to_list())
    rng = random.Random(seed)
    rng.shuffle(patient_ids)

    n = len(patient_ids)
    n_train = round(n * train_frac)
    n_val = round(n * val_frac)
    split_of = {
        pid: ("train" if i < n_train else "val" if i < n_train + n_val else "test")
        for i, pid in enumerate(patient_ids)
    }
    log.info(f"split by subject ({n} unique patientids, seed={seed}): "
             f"train={n_train}, val={n_val}, test={n - n_train - n_val}")

    split_df = pl.DataFrame({"patientid": list(split_of.keys()), "split": list(split_of.values())})
    return admissions.select(["admissionid", "patientid"]).join(split_df, on="patientid").select(["admissionid", "split"])
