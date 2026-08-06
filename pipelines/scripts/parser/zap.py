"""Parser for OWASP ZAP JSON reports.

Input: ``zap.json`` produced by the ZAP daemon API (``jsonreport`` endpoint).
Schema: ``{ "site": [ { "alerts": [ { "riskcode": 0-3, "alert", "desc",
"uri", "param", "solution", "cweid", "wascid", ... } ] } ] }``
"""

import json
from typing import List

from shared.models import Finding

#: ZAP risk codes -> normalized severity.
_RISK_TO_SEVERITY = {
    0: "info",
    1: "low",
    2: "medium",
    3: "high",
}


def parse(path: str) -> List[Finding]:
    """Parse a ZAP JSON report into :class:`Finding` objects."""
    # utf-8-sig tolerates the UTF-8 BOM that .NET's Encoding.UTF8 writes.
    with open(path, "r", encoding="utf-8-sig") as handle:
        data = json.load(handle)

    findings: List[Finding] = []
    for site in data.get("site", []):
        for alert in site.get("alerts", []):
            risk_code = alert.get("riskcode")
            try:
                severity = _RISK_TO_SEVERITY.get(int(risk_code), "info")
            except (TypeError, ValueError):
                severity = "info"

            cwe_id = alert.get("cweid")
            rule = f"CWE-{cwe_id}" if cwe_id else str(alert.get("wascid") or "")

            message_parts = [p for p in (alert.get("desc") or "").splitlines() if p.strip()]
            message = message_parts[0] if message_parts else alert.get("alert", "")

            findings.append(
                Finding(
                    tool="zap",
                    category="active",
                    severity=severity,
                    rule=rule,
                    title=alert.get("alert", ""),
                    file=alert.get("uri", ""),
                    line=0,
                    message=message,
                    remediation=alert.get("solution", ""),
                )
            )
    return findings
