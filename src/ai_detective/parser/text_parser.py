"""Parser for the documented plain-text log format."""

from __future__ import annotations

import re
from datetime import datetime

from ai_detective.models.events import LogEvent

TEXT_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\S+)\s+"
    r"(?P<level>[A-Za-z]+)\s+"
    r"(?P<service>\S+)\s+"
    r"\[(?P<component>[^\]]+)\]\s+"
    r"(?P<message>.+)$"
)


def _parse_timestamp(value: str) -> datetime | None:
    """Parse ISO-8601 timestamps, including the common trailing Z form."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_text_line(raw_line: str, line_number: int) -> LogEvent:
    """Parse one line using the documented text format."""
    stripped = raw_line.strip()
    match = TEXT_LOG_PATTERN.match(stripped)
    if match is None:
        raise ValueError("Line does not match the standard text format")

    data = match.groupdict()
    timestamp = _parse_timestamp(data["timestamp"])
    status = "valid" if timestamp is not None else "partial"

    return LogEvent(
        line_number=line_number,
        raw_line=raw_line,
        timestamp=timestamp,
        level=data["level"].upper(),
        service=data["service"],
        message=data["message"],
        metadata={"component": data["component"]},
        parse_status=status,
        source_format="text",
    )

