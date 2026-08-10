"""Parser for TruffleHog JSON output.

Input: ``trufflehog.json`` written by ``trufflehog filesystem --json``.
Output is newline-delimited JSON (one object per line), but a single JSON
object or a JSON array are also tolerated for robustness.

TruffleHog v3 schema (per item):
    { "DetectorName", "Verified", "Redacted", "SourceMetadata": {
        "Data": { "Git": { "file", "line" } } }, "DetectorDescription", ... }
"""

import json
from typing import Any, List

from shared.models import Finding


def _load_items(path: str) -> List[dict]:
    # utf-8-sig tolerates the UTF-8 BOM that .NET's Encoding.UTF8 writes.
    with open(path, "r", encoding="utf-8-sig") as handle:
        content = handle.read().strip()
    if not content:
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Fall back to newline-delimited JSON objects.
        data = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                data.append(json.loads(line))

    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)]


def _severity(item: dict) -> str:
    explicit = item.get("Severity")
    if explicit:
        return str(explicit).lower()
    # Any detected secret fails the policy gate, verified or not. TruffleHog's
    # own --fail only exits non-zero for verified secrets, so we map unverified
    # ones to high as well; the message keeps the "(verified)" marker.
    return "high"


def parse(path: str) -> List[Finding]:
    """Parse a TruffleHog JSON report into :class:`Finding` objects."""
    findings: List[Finding] = []
    for item in _load_items(path):
        detector = item.get("DetectorName", "")
        git_meta: dict = item.get("SourceMetadata", {}).get("Data", {}).get("Git", {})

        message = f"Detected {detector or 'secret'}"
        if item.get("Verified"):
            message += " (verified)"
        redacted = item.get("Redacted")
        if redacted:
            message += f" - {redacted}"

        findings.append(
            Finding(
                tool="trufflehog",
                category="secrets",
                severity=_severity(item),
                rule=detector,
                title=detector or "TruffleHog secret",
                file=git_meta.get("file", ""),
                line=git_meta.get("line", 0) or 0,
                message=message,
                remediation="Rotate the exposed credential and remove it from "
                "source control and history.",
            )
        )
    return findings
