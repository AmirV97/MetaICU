"""CLI for the full AUMC tokenized-output integrity audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metaicu.aumcdb.tokenized.tokenization.audit import (
    FullTokenizedAudit,
    TokenizedAuditConfig,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-dir", type=Path, required=True)
    parser.add_argument("--samples-per-split", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--no-fail", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = FullTokenizedAudit(
        TokenizedAuditConfig(
            parent_dir=args.parent_dir.expanduser(),
            samples_per_split=args.samples_per_split,
            seed=args.seed,
            fail_on_error=not args.no_fail,
        )
    ).run()
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "check_count": result["check_count"],
                "failure_count": result["failure_count"],
                "timelines": result["timelines"],
                "samples_checked": result["samples_checked"],
                "elapsed_seconds": result["elapsed_seconds"],
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
