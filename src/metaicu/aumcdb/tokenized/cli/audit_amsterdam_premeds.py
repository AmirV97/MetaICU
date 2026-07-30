"""CLI for the full Amsterdam pre-MEDS integrity audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metaicu.aumcdb.tokenized.pre_meds.audit import (
    FullPreMedsAudit,
    PreMedsAuditConfig,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-dir", type=Path, required=True)
    parser.add_argument("--no-fail", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = FullPreMedsAudit(
        PreMedsAuditConfig(
            parent_dir=args.parent_dir.expanduser(),
            fail_on_error=not args.no_fail,
        )
    ).run()
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "check_count": result["check_count"],
                "failure_count": result["failure_count"],
                "elapsed_seconds": result["elapsed_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
