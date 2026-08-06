"""Parser for Microsoft Security DevOps SARIF output.

Input: ``msdo.sarif``. SARIF (JSON) schema, relevant parts:
    runs[].tool.driver.name
    runs[].results[].{ruleId, level, message.text,
                      locations[].physicalLocation.{artifactLocation.uri,
                                                    region.startLine}}

SARIF levels are mapped to normalized severities:
    error -> high, warning -> medium, note -> low.
"""

import json
from typing import List

from shared.models import Finding

_LEVEL_TO_SEVERITY = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "info",
}


def parse(path: str) -> List[Finding]:
    """Parse an MSDO SARIF report into :class:`Finding` objects."""
    # utf-8-sig tolerates the UTF-8 BOM that .NET's Encoding.UTF8 writes.
    with open(path, "r", encoding="utf-8-sig") as handle:
        data = json.load(handle)

    findings: List[Finding] = []
    for run in data.get("runs", []):
        driver = run.get("tool", {}).get("driver", {})
        tool_name = driver.get("name", "msdo")

        for result in run.get("results", []):
            location = result.get("locations", [{}])[0].get("physicalLocation", {}) if result.get("locations") else {}
            file_path = location.get("artifactLocation", {}).get("uri", "")
            line = location.get("region", {}).get("startLine", 0) or 0
            rule_id = result.get("ruleId", "") or ""
            message = result.get("message", {}).get("text", "") or ""
            title = message.splitlines()[0] if message.splitlines() else rule_id

            findings.append(
                Finding(
                    tool=tool_name,
                    category="sast",
                    severity=_LEVEL_TO_SEVERITY.get(result.get("level", "warning"), "medium"),
                    rule=rule_id,
                    title=title,
                    file=file_path,
                    line=line,
                    message=message,
                    remediation="",
                )
            )
    return findings
