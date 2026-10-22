"""Detect the input format of one log line."""

from __future__ import annotations

import json
import re

from ai_detective.models.events import LogFormat

TEXT_LOG_PATTERN = re.compile(
    r"^\S+\s+[A-Za-z]+\s+\S+\s+\[[^\]]+\]\s+.+$"
)


def detect_format(raw_line: str) -> LogFormat:
    """Return the best parser format for a single line.

    Detection is deliberately conservative. A line that cannot be identified
    safely is sent to the raw fallback instead of being discarded.
    """
    stripped = raw_line.strip()
    if not stripped:
        return "raw"

    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return "raw"
        if isinstance(parsed, dict):
            return "json"

    if TEXT_LOG_PATTERN.match(stripped):
        return "text"

    return "raw"

