"""Validation of log input files before parsing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_ENCODING, DEFAULT_MAX_FILE_SIZE_BYTES, DEFAULT_MAX_LINES


class InputFileError(ValueError):
    """Raised when an input file cannot be safely analysed."""


@dataclass(frozen=True)
class ValidatedInputFile:
    """Metadata about an input file that passed validation."""

    path: Path
    size_bytes: int
    line_count: int
    encoding: str


def validate_input_file(
    path: str | Path,
    *,
    max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    max_lines: int = DEFAULT_MAX_LINES,
    encoding: str = DEFAULT_ENCODING,
) -> ValidatedInputFile:
    """Validate existence, access, size, encoding and line count.

    The source file is opened only for reading and is never modified.
    """
    if max_size_bytes <= 0:
        raise ValueError("max_size_bytes must be greater than zero")
    if max_lines <= 0:
        raise ValueError("max_lines must be greater than zero")

    source_path = Path(path)
    if not source_path.exists():
        raise InputFileError(f"Input file does not exist: {source_path}")
    if not source_path.is_file():
        raise InputFileError(f"Input path is not a file: {source_path}")

    try:
        size_bytes = source_path.stat().st_size
    except OSError as exc:
        raise InputFileError(f"Cannot access input file: {source_path}") from exc

    if size_bytes == 0:
        raise InputFileError(f"Input file is empty: {source_path}")
    if size_bytes > max_size_bytes:
        raise InputFileError(
            f"Input file is too large: {size_bytes} bytes "
            f"(maximum: {max_size_bytes} bytes)"
        )

    line_count = 0
    has_content = False
    try:
        with source_path.open("r", encoding=encoding, errors="strict") as stream:
            for line_count, line in enumerate(stream, 1):
                if line.strip():
                    has_content = True
                if line_count > max_lines:
                    raise InputFileError(
                        f"Input file has too many lines: more than {max_lines}"
                    )
    except UnicodeDecodeError as exc:
        raise InputFileError(
            f"Input file is not valid {encoding.upper()} near byte {exc.start}"
        ) from exc
    except PermissionError as exc:
        raise InputFileError(f"Input file is not readable: {source_path}") from exc
    except OSError as exc:
        raise InputFileError(f"Cannot read input file: {source_path}") from exc

    if not has_content:
        raise InputFileError(f"Input file contains no log content: {source_path}")

    return ValidatedInputFile(
        path=source_path,
        size_bytes=size_bytes,
        line_count=line_count,
        encoding=encoding,
    )

