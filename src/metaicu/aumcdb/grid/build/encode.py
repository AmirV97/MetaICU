"""
A.4.2 categorical one-hot encoding (icarefm_preprocessing_reference.md): "Categorical: one-hot
encoded, with a dedicated class per variable for missing information." Runs AFTER grid.impute
(forward-fill has already resolved every hour with a prior real observation; whatever null
remains at that point is a genuine pre-first-observation gap -- exactly what the dedicated
missing class represents, not a value to fabricate).

Category vocabulary per feature is taken from the MANIFEST's declared standardized_label set
(grid.build.manifest_parser.parse_manifest()'s keep_matches), not empirically observed values in this
particular run -- ties the one-hot schema to the documented feature definition and guarantees
every declared category gets a column even if it never happens to appear in a given
train/val/test split (a rare category with an all-zero column is expected, not a bug).

Each categorical column `tag` (e.g. "rass") is REPLACED by len(vocab)+1 binary (Int8) columns:
one per declared category (alphabetically ordered, for determinism) plus one dedicated
f"{tag}__missing" column for null. Column naming: f"{tag}__{sanitized_category}". Exactly one
of a feature's one-hot columns is 1 per row (mutually exclusive, exhaustive) -- see
verify_one_hot_exclusive for the check.
"""
import logging
import re

import polars as pl

log = logging.getLogger(__name__)

MISSING_CATEGORY_LABEL = "(missing)"


def _sanitize(label):
    """Column-name-safe version of a category label, e.g. 'No artificial airway (low-flow O2)'
    -> 'No_artificial_airway_low_flow_O2'."""
    return re.sub(r"[^0-9a-zA-Z]+", "_", label).strip("_")


def get_categorical_vocab(matches):
    """matches: tag -> feature info dict from grid.build.manifest_parser.parse_manifest(). Returns
    {tag: sorted_list_of_declared_standardized_labels} for every categorical feature -- the
    dedicated missing class is NOT included here, it's added separately in
    one_hot_encode_categorical (every categorical feature gets one, not just ones with a
    declared "missing" match)."""
    vocab = {}
    for tag, info in matches.items():
        if info["reconstruction_type"] != "categorical":
            continue
        labels = sorted({m["standardized_label"] for m in info["keep_matches"] if m["standardized_label"]})
        vocab[tag] = labels
    return vocab


def one_hot_encode_categorical(grid, matches):
    """grid: wide DataFrame from grid.impute.impute_grid (categorical columns still single
    string-label columns; real nulls = pre-first-observation gaps). matches: tag -> info dict
    from grid.build.manifest_parser.parse_manifest().

    Returns (grid, encoding_schema): grid has each categorical tag column REPLACED by its
    one-hot expansion; encoding_schema is a list of row-dicts (feature, category, column_name,
    position_in_feature, position_global) -- one row per one-hot column produced, in the exact
    order the columns were added -- see save_categorical_encoding for how this is persisted."""
    vocab = get_categorical_vocab(matches)
    encoding_schema = []
    global_pos = 0

    for tag, categories in vocab.items():
        if tag not in grid.columns:
            continue
        col_names = [f"{tag}__{_sanitize(cat)}" for cat in categories]
        if len(set(col_names)) != len(col_names):
            raise ValueError(
                f"{tag}: sanitized category names collide ({col_names}) -- two distinct "
                f"standardized_labels produced the same one-hot column name, would silently "
                f"overwrite each other. Fix the manifest labels or _sanitize() before proceeding."
            )
        new_cols = []
        for i, (cat, col_name) in enumerate(zip(categories, col_names)):
            # fill_null(False): pl.col(tag) == cat is NULL (not False) when the row is null --
            # every category column must be a clean 0 for a missing row, only the dedicated
            # missing column below should be 1 there.
            new_cols.append((pl.col(tag) == cat).fill_null(False).cast(pl.Int8).alias(col_name))
            encoding_schema.append({
                "feature": tag, "category": cat, "column_name": col_name,
                "position_in_feature": i, "position_global": global_pos,
            })
            global_pos += 1

        missing_col_name = f"{tag}__missing"
        new_cols.append(pl.col(tag).is_null().cast(pl.Int8).alias(missing_col_name))
        encoding_schema.append({
            "feature": tag, "category": MISSING_CATEGORY_LABEL, "column_name": missing_col_name,
            "position_in_feature": len(categories), "position_global": global_pos,
        })
        global_pos += 1

        grid = grid.with_columns(new_cols).drop(tag)
        log.info(f"{tag}: one-hot encoded into {len(categories) + 1} columns "
                 f"({len(categories)} categories + missing)")

    return grid, encoding_schema


def save_categorical_encoding(encoding_schema, output_path):
    """encoding_schema: list of row-dicts from one_hot_encode_categorical. Writes a plain CSV
    (feature, category, column_name, position_in_feature, position_global) -- the requested
    record of which physical column each (feature, category) pair maps to and where it sits in
    the one-hot vector, both within its own feature's block and across all categorical
    features' columns concatenated in encoding order."""
    pl.DataFrame(encoding_schema).write_csv(output_path)
    log.info(f"Wrote {output_path} ({len(encoding_schema)} one-hot columns)")


def verify_one_hot_exclusive(grid, encoding_schema):
    """Sanity check (not called by default in the CLI -- available for QA/tests): for every
    feature, exactly one of its one-hot columns should be 1 per row. Returns a dict
    {feature: n_bad_rows} for any feature that fails (empty dict if all pass)."""
    by_feature = {}
    for row in encoding_schema:
        by_feature.setdefault(row["feature"], []).append(row["column_name"])
    bad = {}
    for feature, cols in by_feature.items():
        row_sums = grid.select(pl.sum_horizontal(cols).alias("s"))["s"]
        n_bad = int((row_sums != 1).sum())
        if n_bad:
            bad[feature] = n_bad
    return bad
