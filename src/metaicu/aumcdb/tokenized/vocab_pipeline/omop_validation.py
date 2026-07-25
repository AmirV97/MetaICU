"""Local Athena OMOP vocabulary lookups used by vocabulary-construction policy layers.

CONCEPT.csv is large (hundreds of MB); always scan it lazily with a filter pushdown before
collecting, never read the whole file. ``quote_char=None`` is required because some
``concept_name`` values contain an unescaped literal ``"``. ``infer_schema_length=0`` loads
every column as a string so mixed/junk values can't break numeric type inference; callers cast
after collecting the already-filtered subset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import polars as pl


def scan_concept(omop_vocab_dir: Path) -> pl.LazyFrame:
    return pl.scan_csv(
        omop_vocab_dir / "CONCEPT.csv",
        separator="\t",
        infer_schema_length=0,
        quote_char=None,
    )


def lookup_concept_vocabulary(concept_ids: Sequence[int], omop_vocab_dir: Path) -> dict[int, str]:
    """Return {concept_id: vocabulary_id} for concept_ids present in the local Athena export.

    Concept_ids absent from the export are omitted from the result (callers must decide how to
    handle an unresolved lookup; this module never guesses).
    """

    if not concept_ids:
        return {}
    concepts = (
        scan_concept(omop_vocab_dir)
        .filter(pl.col("concept_id").cast(pl.Int64, strict=False).is_in(list(concept_ids)))
        .select("concept_id", "vocabulary_id")
        .collect()
        .with_columns(pl.col("concept_id").cast(pl.Int64))
    )
    return dict(zip(concepts["concept_id"].to_list(), concepts["vocabulary_id"].to_list()))
