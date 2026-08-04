#!/usr/bin/env python3
"""Generate a summary of aggregated findings.

Reads ``combined.json`` (produced by aggregate.py) and writes:

  * summary.json - machine-readable counts (by severity, by tool)
  * summary.md   - human-readable Markdown report

Usage:
    python3 security_summary.py \
        --combined reports/summary/combined.json \
        --json reports/summary/summary.json \
        --markdown reports/summary/summary.md
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.models import SEVERITY_ORDER  # noqa: E402


def _empty_counts() -> Dict[str, int]:
    return {severity: 0 for severity in SEVERITY_ORDER}


def build_summary(combined: dict) -> dict:
    findings = combined.get("findings", [])

    by_severity: Dict[str, int] = _empty_counts()
    by_tool: Dict[str, dict] = {}

    for finding in findings:
        severity = finding.get("severity", "info")
        if severity not in by_severity:
            severity = "info"
        by_severity[severity] += 1

        tool = finding.get("tool", "unknown")
        tool_entry = by_tool.setdefault(tool, {"total": 0, "by_severity": _empty_counts()})
        tool_entry["total"] += 1
        tool_entry["by_severity"][severity] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_findings": len(findings),
        "by_severity": by_severity,
        "by_tool": {
            tool: {"total": entry["total"], "by_severity": entry["by_severity"]}
            for tool, entry in sorted(by_tool.items())
        },
        "tools": sorted(by_tool),
    }


def render_markdown(summary: dict) -> str:
    lines: List[str] = [
        "# Security scan summary",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Total findings: {summary['total_findings']}",
        "",
        "## By severity",
        "",
        "| Severity | Count |",
        "| --- | ---: |",
    ]
    for severity in SEVERITY_ORDER:
        count = summary["by_severity"][severity]
        lines.append(f"| {severity.capitalize()} | {count} |")

    lines += ["", "## By tool", ""]
    for tool, entry in summary["by_tool"].items():
        lines.append(f"### {tool}")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("| --- | ---: |")
        for severity in SEVERITY_ORDER:
            lines.append(f"| {severity.capitalize()} | {entry['by_severity'][severity]} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined", required=True, help="Path to combined.json")
    parser.add_argument("--json", dest="json_out", help="Output path for summary.json")
    parser.add_argument("--markdown", help="Output path for summary.md")
    args = parser.parse_args()

    with open(args.combined, "r", encoding="utf-8") as handle:
        combined = json.load(handle)

    summary = build_summary(combined)

    os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    if args.markdown:
        os.makedirs(os.path.dirname(os.path.abspath(args.markdown)), exist_ok=True)
        with open(args.markdown, "w", encoding="utf-8") as handle:
            handle.write(render_markdown(summary))

    print(f"Summary written: {summary['total_findings']} findings "
          f"(critical={summary['by_severity']['critical']}, "
          f"high={summary['by_severity']['high']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
