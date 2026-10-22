import pytest

from ai_detective.parser.log_parser import parse_file
from ai_detective.validation import InputFileError, validate_input_file


def test_missing_file_is_rejected(tmp_path) -> None:
    with pytest.raises(InputFileError, match="does not exist"):
        validate_input_file(tmp_path / "missing.log")


def test_empty_file_is_rejected(tmp_path) -> None:
    path = tmp_path / "empty.log"
    path.write_bytes(b"")

    with pytest.raises(InputFileError, match="empty"):
        validate_input_file(path)


def test_whitespace_only_file_is_rejected(tmp_path) -> None:
    path = tmp_path / "blank.log"
    path.write_text("  \n\t\n", encoding="utf-8")

    with pytest.raises(InputFileError, match="no log content"):
        validate_input_file(path)


def test_file_over_size_limit_is_rejected(tmp_path) -> None:
    path = tmp_path / "large.log"
    path.write_text("12345", encoding="utf-8")

    with pytest.raises(InputFileError, match="too large"):
        validate_input_file(path, max_size_bytes=4)


def test_invalid_utf8_is_rejected(tmp_path) -> None:
    path = tmp_path / "invalid-encoding.log"
    path.write_bytes(b"ERROR \xff\xfe")

    with pytest.raises(InputFileError, match="UTF-8"):
        validate_input_file(path)


def test_line_limit_is_enforced(tmp_path) -> None:
    path = tmp_path / "many-lines.log"
    path.write_text("line 1\nline 2\n", encoding="utf-8")

    with pytest.raises(InputFileError, match="too many lines"):
        parse_file(path, max_lines=1)


def test_source_file_is_not_modified(tmp_path) -> None:
    path = tmp_path / "source.log"
    original = b"2026-10-21T10:15:04Z ERROR api [database] MongoDB connection refused\n"
    path.write_bytes(original)

    parse_file(path)

    assert path.read_bytes() == original

