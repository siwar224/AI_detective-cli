from ai_detective.analyzer.classifier import classify_event
from ai_detective.parser.log_parser import parse_line


def test_classifies_mongodb_error() -> None:
    event = parse_line(
        "2026-10-21T10:15:04Z ERROR api [database] MongoDB connection refused",
        1,
    )

    assert classify_event(event) == "mongodb"


def test_classifies_http_timeout() -> None:
    event = parse_line(
        "2026-10-21T10:15:04Z ERROR api [http] Request timeout",
        1,
    )

    assert classify_event(event) == "timeout"


def test_unknown_error_is_not_discarded() -> None:
    event = parse_line(
        "2026-10-21T10:15:04Z ERROR api [worker] Unexpected backend failure",
        1,
    )

    assert classify_event(event) == "unknown"

