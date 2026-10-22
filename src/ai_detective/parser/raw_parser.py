"""Fallback parser for lines with an unknown structure."""

from __future__ import annotations

from ai_detective.models.events import LogEvent


def parse_raw_line(raw_line: str, line_number: int) -> LogEvent:
    """Preserve an unrecognised line as evidence."""
    message = raw_line.strip() or None
    status = "partial" if message is not None else "invalid"
    return LogEvent(
        line_number=line_number,
        raw_line=raw_line,
        message=message,
        parse_status=status,
        source_format="raw",
    )

