#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from combined findings.

Reads ``combined.json`` (produced by aggregate.py) and writes a single
``index.html`` with no external dependencies (embedded CSS/JS).

The dashboard shows:
  * summary cards (total, per-severity, per-tool)
  * findings grouped by severity
  * findings grouped by scanner
  * clickable file paths when a finding has one

Usage:
    python3 generate_html.py \
        --combined reports/summary/combined.json \
        --output reports/html/index.html
"""

import argparse
import html
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.models import SEVERITY_ORDER  # noqa: E402

_SEVERITY_COLORS = {
    "critical": "#d64545",
    "high": "#e67e22",
    "medium": "#e5c83d",
    "low": "#4aa3df",
    "info": "#95a5a6",
}

_CSS = """
:root { --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8;
        --border:#334155; --accent:#38bdf8; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text);
       font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
header { padding: 24px 32px; border-bottom: 1px solid var(--border);
         display:flex; align-items:baseline; gap:16px; flex-wrap:wrap; }
header h1 { margin:0; font-size:20px; }
header .meta { color:var(--muted); font-size:13px; }
main { padding: 24px 32px; max-width: 1100px; margin: 0 auto; }
.cards { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap:12px; margin-bottom:28px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; }
.card .value { font-size:28px; font-weight:700; }
.card .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }
h2 { font-size:15px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted);
     margin:28px 0 12px; }
table { width:100%; border-collapse:collapse; background:var(--card);
        border:1px solid var(--border); border-radius:10px; overflow:hidden; font-size:13px; }
th,td { text-align:left; padding:8px 12px; border-bottom:1px solid var(--border); }
th { background:rgba(255,255,255,.04); color:var(--muted); font-size:11px;
     text-transform:uppercase; letter-spacing:.05em; }
tr:last-child td { border-bottom:none; }
.pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px;
        font-weight:700; color:#fff; }
a.file { color:var(--accent); text-decoration:none; font-family:ui-monospace,monospace; font-size:12px; }
a.file:hover { text-decoration:underline; }
.code { font-family:ui-monospace, monospace; font-size:12px; word-break:break-all; }
.muted { color:var(--muted); }
.filters { margin:12px 0; display:flex; gap:8px; flex-wrap:wrap; }
.filters button { background:var(--card); color:var(--text); border:1px solid var(--border);
                  border-radius:999px; padding:6px 14px; cursor:pointer; font-size:12px; }
.filters button.active { border-color:var(--accent); color:var(--accent); }
"""


def _pill(severity: str) -> str:
    color = _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS["info"])
    return f'<span class="pill" style="background:{color}">{html.escape(severity)}</span>'


def _finding_rows(findings: List[dict], prefix: str) -> str:
    rows = []
    for idx, finding in enumerate(findings):
        tool = finding.get("tool", "unknown")
        file_path = finding.get("file") or ""
        if file_path:
            location = f'<a class="file" href="{html.escape(file_path)}" title="{html.escape(file_path)}">{html.escape(file_path)}</a>'
        else:
            location = '<span class="muted">n/a</span>'
        if finding.get("line"):
            location += f':{finding["line"]}'
        rule = html.escape(finding.get("rule") or "")
        message = html.escape(finding.get("message") or "")
        rows.append(
            f"<tr id=\"{prefix}-{idx}\">"
            f"<td>{_pill(finding.get('severity', 'info'))}</td>"
            f"<td>{html.escape(finding.get('title') or finding.get('rule') or '')}</td>"
            f"<td>{location}</td>"
            f"<td>{rule}</td>"
            f"<td>{message}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def render(combined: dict) -> str:
    findings = combined.get("findings", [])
    generated = combined.get("generated_at") or datetime.now(timezone.utc).isoformat()

    by_severity = Counter(f.get("severity", "info") for f in findings)
    by_tool: Dict[str, List[dict]] = defaultdict(list)
    for finding in findings:
        by_tool[finding.get("tool", "unknown")].append(finding)

    cards = [("Total findings", len(findings))]
    for severity in SEVERITY_ORDER:
        cards.append((severity, by_severity.get(severity, 0)))
    cards.append(("Tools", len(by_tool)))
    cards_html = "".join(
        f'<div class="card"><div class="value" style="color:{_SEVERITY_COLORS.get(label, "#fff")}">'
        f'{value}</div><div class="label">{html.escape(label)}</div></div>'
        for label, value in cards
    )

    # Grouped by severity (most severe first).
    by_severity_groups: Dict[str, List[dict]] = defaultdict(list)
    for finding in findings:
        by_severity_groups[finding.get("severity", "info")].append(finding)

    severity_sections = []
    for severity in SEVERITY_ORDER:
        group = by_severity_groups.get(severity)
        if not group:
            continue
        severity_sections.append(
            f"<h2>By severity: {severity}</h2>"
            f"<table><thead><tr><th>Severity</th><th>Title</th><th>File</th>"
            f"<th>Rule</th><th>Message</th></tr></thead><tbody>"
            f"{_finding_rows(group, 'sev-' + severity)}</tbody></table>"
        )

    tool_sections = []
    for tool in sorted(by_tool):
        group = by_tool[tool]
        tool_sections.append(
            f"<h2>By scanner: {html.escape(tool)} ({len(group)})</h2>"
            f"<table><thead><tr><th>Severity</th><th>Title</th><th>File</th>"
            f"<th>Rule</th><th>Message</th></tr></thead><tbody>"
            f"{_finding_rows(group, 'tool-' + tool)}</tbody></table>"
        )

    # TODO: In production, wire the file links below to a code host (e.g.
    # https://dev.azure.com/.../_git/.../blob/main/{file}#L{line}). The href
    # currently points at the repo-relative path.

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Security scan dashboard</title>
<style>{_CSS}</style>
</head>
<body>
<header>
  <h1>Security scan dashboard</h1>
  <span class="meta">Generated {html.escape(generated)}</span>
</header>
<main>
  <div class="cards">{cards_html}</div>
  {''.join(severity_sections)}
  {''.join(tool_sections)}
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined", required=True, help="Path to combined.json")
    parser.add_argument("--output", required=True, help="Path to write index.html")
    args = parser.parse_args()

    with open(args.combined, "r", encoding="utf-8") as handle:
        combined = json.load(handle)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(render(combined))

    print(f"Wrote dashboard ({combined.get('total_findings', 0)} findings) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
