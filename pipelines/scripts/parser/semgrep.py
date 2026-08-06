"""Parser for Semgrep JSON output.

Input: ``semgrep.json`` written by ``semgrep --json --output``.
Schema: ``{ "results": [ { "check_id", "path", "start": {"line"},
"extra": {"message", "severity", "metadata"} } ] }``

The SARIF file (``semgrep.sarif``) is not parsed here - the JSON format is
richer and used as the source of truth. The SARIF copy is kept for consumers
that need SARIF.
"""

import json
from typing import List

from shared.models import Finding

#: Semgrep severity values -> normalized severity.
_SEVERITY_MAP = {
    "ERROR": "high",
    "WARNING": "medium",
    "INFO": "info",
}


def _normalize_severity(severity: str) -> str:
    return _SEVERITY_MAP.get(str(severity).upper(), str(severity).lower())


def parse(path: str) -> List[Finding]:
    """Parse a Semgrep JSON report into :class:`Finding` objects."""
    # utf-8-sig tolerates the UTF-8 BOM that .NET's Encoding.UTF8 writes.
    with open(path, "r", encoding="utf-8-sig") as handle:
        data = json.load(handle)

    findings: List[Finding] = []
    for result in data.get("results", []):
        extra = result.get("extra", {})
        metadata = extra.get("metadata", {})

        message = extra.get("message", "") or ""
        title = message.splitlines()[0] if message.splitlines() else result.get("check_id", "")

        category = metadata.get("category") or metadata.get("subcategory") or "static analysis"

        remediation = metadata.get("fix") or ""
        if not remediation and metadata.get("fix_regex"):
            remediation = f"Apply fix_regex: {metadata['fix_regex']}"

        findings.append(
            Finding(
                tool="semgrep",
                category=str(category),
                severity=_normalize_severity(extra.get("severity") or "info"),
                rule=result.get("check_id", ""),
                title=title,
                file=result.get("path", ""),
                line=result.get("start", {}).get("line", 0) or 0,
                message=message,
                remediation=str(remediation),
            )
        )
    return findings
