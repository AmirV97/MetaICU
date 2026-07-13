#!/usr/bin/env python3
"""Wrapper for retrieving MetaICU external resources."""

from __future__ import annotations

import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PIPELINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metaicu.cli.retrieve_externals import main  # noqa: E402


if __name__ == "__main__":
    main()
