"""Public parsing functions for log lines and files."""

from __future__ import annotations

from pathlib import Path

from ai_detective.models.events import LogEvent

from .format_detector import detect_format
from .json_parser import parse_json_line
from .raw_parser import parse_raw_line
from .text_parser import parse_text_line


def parse_line(raw_line: str, line_number: int) -> LogEvent:
    """Detect a line format and dispatch to the matching parser."""
    source_format = detect_format(raw_line)
    if source_format == "text":
        return parse_text_line(raw_line, line_number)
    if source_format == "json":
        return parse_json_line(raw_line, line_number)
    return parse_raw_line(raw_line, line_number)


def parse_file(path: str | Path) -> list[LogEvent]:
    """Parse a UTF-8 log file while preserving one-based line numbers."""
    source_path = Path(path)
    with source_path.open("r", encoding="utf-8", errors="replace") as stream:
        return [parse_line(line.rstrip("\r\n"), number) for number, line in enumerate(stream, 1)]

