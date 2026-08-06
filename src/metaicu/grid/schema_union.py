"""Cross-cohort schema union for joint multi-dataset grid builds.

Shared by both aumcdb and mimiciv grid pipelines' matches dicts (tag -> {reconstruction_type,
target_unit, keep_matches, n_keep, structural_zero, ...}, from each pipeline's own
manifest_parser.parse_manifest()). A joint run must expose the exact same tag set/shape from
every cohort ("data-content invariant schema") regardless of which cohort's raw data actually
supports a given tag -- these functions build that union and pad each cohort's own matches dict
to match it, reusing grid.build.impute.materialize_structural_zero_columns's existing per-cohort
structural_zero convention rather than inventing a new missingness mechanism. Callers must pad
`matches` itself (not only a derived-targets-merged copy) before anything downstream consumes it,
and must never feed a padded/foreign-cohort dict into extraction -- keep_matches entries carry
raw itemids that are meaningless (and can collide) across datasets' own numbering spaces.
"""


def compute_union_matches(matches_by_cohort):
    """matches_by_cohort: {cohort_name: matches}, one dict per selected dataset, from that
    dataset's own parse_manifest(). Returns {tag: {reconstruction_type, target_unit}} covering
    every tag present in ANY cohort. Hard-fails (not a silent pick-one) if the same tag has a
    different reconstruction_type or target_unit across cohorts -- that mismatch is exactly the
    "data-content invariant schema" contract this function exists to enforce."""
    registry = {}
    for cohort, matches in matches_by_cohort.items():
        for tag, info in matches.items():
            entry = {"reconstruction_type": info["reconstruction_type"], "target_unit": info["target_unit"]}
            if tag in registry and registry[tag] != entry:
                raise ValueError(
                    f"tag {tag!r} disagrees across cohorts: {registry[tag]} (seen before {cohort!r}) "
                    f"vs {entry} ({cohort!r}) -- schema must be data-content invariant"
                )
            registry[tag] = entry
    return registry


def pad_matches_for_cohort(own_matches, union_registry):
    """own_matches: one cohort's own matches dict (never mutated). union_registry: from
    compute_union_matches. Returns a NEW dict with every tag in union_registry that this cohort
    doesn't itself have, added as structural_zero/n_keep=0/empty keep_matches -- the same shape
    grid.build.impute.materialize_structural_zero_columns already fills with nulls/zeros for a
    cohort lacking real data, and the same shape manifest_parser's own STRUCTURAL_ZERO_TAGS
    entries already use for e.g. AUMC's adh/milrin/pt."""
    padded = dict(own_matches)
    for tag, info in union_registry.items():
        if tag not in padded:
            padded[tag] = {**info, "keep_matches": [], "n_keep": 0, "structural_zero": True}
    return padded


def compute_union_categorical_vocab(vocab_by_cohort):
    """vocab_by_cohort: {cohort_name: {tag: [categories]}}, one dict per selected dataset, from
    that dataset's own grid.build.encode.get_categorical_vocab(matches). Returns {tag: sorted
    union of categories across every cohort that has this tag}. Categorical vocab is driven by
    keep_matches' standardized_label values, not tag presence, so it needs this explicit union
    rather than compute_union_matches/pad_matches_for_cohort (which only track
    reconstruction_type/target_unit) -- two cohorts' vocabularies for a shared tag agreeing today
    is a coincidence of two independently-maintained definitions, not something a caller should
    rely on without this."""
    union = {}
    for vocab in vocab_by_cohort.values():
        for tag, categories in vocab.items():
            union.setdefault(tag, set()).update(categories)
    return {tag: sorted(categories) for tag, categories in union.items()}
