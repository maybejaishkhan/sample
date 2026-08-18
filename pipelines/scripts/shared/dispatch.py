"""Dispatcher that maps raw report file names to the right parser.

Each scanner writes its output under a well-known file name (configured in
pipelines/variables/security.yml) and the policy check parses it:

    trufflehog.json  -> parser.trufflehog
    semgrep.json     -> parser.semgrep
    semgrep.sarif    -> parser.semgrep
    zap.json         -> parser.zap

To add a new scanner, add its file name here plus a parser module. Nothing else
in the pipeline needs to change.
"""

import os
from typing import Callable, Dict, List

from parser.semgrep import parse as parse_semgrep
from parser.trufflehog import parse as parse_trufflehog
from parser.zap import parse as parse_zap

from shared.models import Finding

#: File name (as written by the run-* step) -> parser entry point.
PARSERS: Dict[str, Callable[[str], List[Finding]]] = {
    "trufflehog.json": parse_trufflehog,
    "semgrep.json": parse_semgrep,
    "semgrep.sarif": parse_semgrep,
    "zap.json": parse_zap,
}


def parse_file(path: str) -> List[Finding]:
    """Parse a single raw report file into normalized findings."""
    parser = PARSERS.get(os.path.basename(path))
    if parser is None:
        raise ValueError(f"No parser registered for {os.path.basename(path)!r}")
    return parser(path)