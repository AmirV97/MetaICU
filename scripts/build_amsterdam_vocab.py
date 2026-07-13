#!/usr/bin/env python3
"""Wrapper for the Hydra-configured AmsterdamUMCdb vocabulary CLI."""

from __future__ import annotations

import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.aumcdb.tokenized.cli.build_amsterdam_vocab import main  # noqa: E402


if __name__ == "__main__":
    main()
