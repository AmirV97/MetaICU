"""Regenerate train-only and full-data AUMC token vocabularies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metaicu.aumcdb.tokenized.tokenization.vocab_inventory import (
    VocabInventoryConfig,
    write_scoped_vocabularies,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-meds-dir", type=Path, required=True)
    parser.add_argument("--supplied-vocab", type=Path, required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print("[vocab] scanning complete pre-MEDS cohort", flush=True)
    outputs = write_scoped_vocabularies(
        VocabInventoryConfig(
            pre_meds_dir=args.pre_meds_dir,
            supplied_vocab=args.supplied_vocab,
            split_manifest=args.split_manifest,
            output_dir=args.output_dir,
        )
    )
    print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2), flush=True)


if __name__ == "__main__":
    main()
