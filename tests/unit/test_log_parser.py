from ai_detective.parser.log_parser import parse_line


def test_parse_standard_text_line() -> None:
    event = parse_line(
        "2026-10-21T10:15:04Z ERROR api [database] MongoDB connection refused",
        1,
    )

    assert event.source_format == "text"
    assert event.parse_status == "valid"
    assert event.line_number == 1
    assert event.level == "ERROR"
    assert event.service == "api"
    assert event.message == "MongoDB connection refused"
    assert event.metadata["component"] == "database"


def test_parse_json_line() -> None:
    event = parse_line(
        '{"timestamp":"2026-10-21T10:16:04Z","level":"ERROR",'
        '"service":"auth","message":"Token expired"}',
        2,
    )

    assert event.source_format == "json"
    assert event.parse_status == "valid"
    assert event.level == "ERROR"
    assert event.service == "auth"
    assert event.message == "Token expired"


def test_unknown_line_is_preserved_as_raw_evidence() -> None:
    event = parse_line("MongoServerSelectionError: connect ECONNREFUSED", 3)

    assert event.source_format == "raw"
    assert event.parse_status == "partial"
    assert event.raw_line == event.message
    assert event.line_number == 3

