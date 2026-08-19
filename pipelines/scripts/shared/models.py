"""Shared data model used by every scanner parser.

Every parser in ``parser/`` understands exactly one scanner and returns a list
of :class:`Finding`. The aggregator then merges all of them into a single,
tool-agnostic representation.

Severity strings are always lowercase: ``critical``, ``high``, ``medium``,
``low`` or ``info``.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict

#: Canonical ordering, most severe first.
SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")


def severity_key(severity: str) -> int:
    """Return a sortable index for a severity string (invalid -> info)."""
    try:
        return SEVERITY_ORDER.index(severity.lower())
    except ValueError:
        return SEVERITY_ORDER.index("info")


@dataclass
class Finding:
    """A single normalized security finding."""

    #: Scanner that produced the finding, e.g. "semgrep".
    tool: str

    #: Category, e.g. "secrets", "static analysis", "active", "sast".
    category: str = ""

    #: Normalized severity: critical/high/medium/low/info.
    severity: str = "info"

    #: Rule / detector identifier.
    rule: str = ""

    #: Short human-readable title.
    title: str = ""

    #: File path the finding relates to (may be empty for some tools).
    file: str = ""

    #: Line number (0 when unknown).
    line: int = 0

    #: Full description of the finding.
    message: str = ""

    #: Suggested remediation, when the scanner provides one.
    remediation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
