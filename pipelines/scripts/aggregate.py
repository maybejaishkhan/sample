#!/usr/bin/env python3
"""Aggregate every scanner's raw output into one normalized report.

Scans the raw reports directory, parses each well-known file via
``shared.dispatch``, and writes a single ``combined.json``.

Usage:
    python3 aggregate.py \
        --raw reports/raw \
        --output reports/summary/combined.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.dispatch import PARSERS, parse_file  # noqa: E402
from shared.models import Finding  # noqa: E402


def aggregate(raw_dir: str) -> List[Finding]:
    """Parse every known report file found in ``raw_dir``."""
    findings: List[Finding] = []
    for file_name in sorted(os.listdir(raw_dir)):
        if file_name not in PARSERS:
            continue
        path = os.path.join(raw_dir, file_name)
        try:
            parsed = parse_file(path)
            findings.extend(parsed)
            print(f"Parsed {file_name}: {len(parsed)} findings")
        except Exception as exc:  # noqa: BLE001 - one bad file must not lose all reports
            print(f"ERROR parsing {file_name}: {exc}", file=sys.stderr)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, help="Directory containing raw scanner reports")
    parser.add_argument("--output", required=True, help="Path to write combined.json")
    args = parser.parse_args()

    findings = aggregate(args.raw)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tools": sorted({f.tool for f in findings}),
        "total_findings": len(findings),
        "findings": [f.to_dict() for f in findings],
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    print(f"Wrote {len(findings)} findings to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
