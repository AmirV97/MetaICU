"""
Train/val/test split assignment. Always splits by subject_id, regardless of --unit-of-analysis
(which only controls sampling/dataset-row granularity, not split assignment) -- keeps all of one
patient's stays in the same split, avoiding cross-split leakage for patients with multiple ICU
admissions. Uses random.Random(seed), matching grid/sampling.py's RNG choice. Mirrors
AUMC_grid_pipeline/grid/split.py's split-always-by-patient convention (dataset-agnostic; MIMIC's
column is subject_id where AUMC's is patientid).
"""
import logging
import random

import polars as pl

log = logging.getLogger(__name__)


def assign_splits(admissions, train_frac, val_frac, test_frac, seed):
    """admissions: DataFrame with at least admissionid + subject_id. Returns a
    (admissionid, split) DataFrame, split in {"train","val","test"}."""
    assert abs(train_frac + val_frac + test_frac - 1.0) < 1e-6, \
        f"train/val/test fracs must sum to 1.0, got {train_frac}+{val_frac}+{test_frac}"

    subject_ids = sorted(admissions["subject_id"].unique().to_list())
    rng = random.Random(seed)
    rng.shuffle(subject_ids)

    n = len(subject_ids)
    n_train = round(n * train_frac)
    n_val = round(n * val_frac)
    split_of = {
        sid: ("train" if i < n_train else "val" if i < n_train + n_val else "test")
        for i, sid in enumerate(subject_ids)
    }
    log.info(f"split by subject ({n} unique subject_ids, seed={seed}): "
             f"train={n_train}, val={n_val}, test={n - n_train - n_val}")

    split_df = pl.DataFrame({"subject_id": list(split_of.keys()), "split": list(split_of.values())})
    return admissions.select(["admissionid", "subject_id"]).join(split_df, on="subject_id").select(["admissionid", "split"])
