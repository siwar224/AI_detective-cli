"""Public parsing functions for log lines and files."""

from __future__ import annotations

from pathlib import Path

from ai_detective.config import DEFAULT_MAX_FILE_SIZE_BYTES, DEFAULT_MAX_LINES
from ai_detective.models.events import LogEvent
from ai_detective.validation import ValidatedInputFile, validate_input_file

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


def parse_file(
    path: str | Path | ValidatedInputFile,
    *,
    max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    max_lines: int = DEFAULT_MAX_LINES,
) -> list[LogEvent]:
    """Validate and parse a UTF-8 log file with bounded resource usage."""
    validated = (
        path
        if isinstance(path, ValidatedInputFile)
        else validate_input_file(
            path,
            max_size_bytes=max_size_bytes,
            max_lines=max_lines,
        )
    )
    with validated.path.open("r", encoding=validated.encoding, errors="strict") as stream:
        return [parse_line(line.rstrip("\r\n"), number) for number, line in enumerate(stream, 1)]

