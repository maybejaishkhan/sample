#!/usr/bin/env python3
"""Policy gate for a single scanner's raw output.

Fails the job when the report contains findings at a configured severity. Used
by the security jobs right after archiving results, so a crash in the scanner
(which usually means the report is missing) also fails the job instead of
silently passing.

Severity gates are taken from the ``FAIL_ON_CRITICAL`` / ``FAIL_ON_HIGH``
environment variables (set by the pipeline from the FailOnCritical / FailOnHigh
variables) or from ``--fail-on`` arguments. When both are present, either
source can trigger a failure.

Exit codes:
    0 - no findings above the threshold
    1 - findings above the threshold (gate violated)
    2 - report missing/corrupt and --allow-missing not set
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.dispatch import parse_file  # noqa: E402


def _env_gates() -> set:
    gates: set = set()
    if os.environ.get("FAIL_ON_CRITICAL", "").strip().lower() == "true":
        gates.add("critical")
    if os.environ.get("FAIL_ON_HIGH", "").strip().lower() == "true":
        gates.add("high")
    return gates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Raw scanner report to evaluate")
    parser.add_argument("--fail-on", action="append", default=[],
                        help="Severity that fails the gate (repeatable)")
    parser.add_argument("--allow-missing", action="store_true",
                        help="Do not fail when the report file is absent")
    args = parser.parse_args()

    gates = set(args.fail_on) | _env_gates()

    if not os.path.isfile(args.file):
        if args.allow_missing:
            print(f"Report {args.file} missing (allowed).")
            return 0
        print(f"ERROR: expected report {args.file} was not produced.", file=sys.stderr)
        return 2

    try:
        findings = parse_file(args.file)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not parse {args.file}: {exc}", file=sys.stderr)
        return 2

    counts = Counter(f.severity for f in findings)
    violations = {severity: counts[severity] for severity in gates if counts.get(severity)}

    print(f"{os.path.basename(args.file)}: {len(findings)} findings "
          f"{dict(counts)} gate={sorted(gates) or 'none'}")

    if violations:
        print("Policy gate violated:", file=sys.stderr)
        for severity, count in sorted(violations.items()):
            print(f"  - {severity}: {count}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
