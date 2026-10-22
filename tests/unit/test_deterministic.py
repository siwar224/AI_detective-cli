from ai_detective.analyzer.deterministic import analyze_events
from ai_detective.parser.log_parser import parse_line


def test_counts_levels_and_groups_repeated_errors() -> None:
    events = [
        parse_line(
            "2026-10-21T10:15:04Z ERROR api [database] MongoDB connection refused",
            1,
        ),
        parse_line(
            "2026-10-21T10:15:05Z ERROR api [database] MongoDB connection refused",
            2,
        ),
        parse_line(
            "2026-10-21T10:15:06Z INFO api [startup] Retrying connection",
            3,
        ),
    ]

    analysis = analyze_events(events)

    assert analysis.total_lines == 3
    assert analysis.parsed_events == 3
    assert analysis.levels_count == {"ERROR": 2, "INFO": 1}
    assert analysis.top_errors[0].count == 2
    assert analysis.top_errors[0].line_numbers == [1, 2]
    assert len(analysis.timeline) == 3


def test_detects_error_peak_in_a_time_bucket() -> None:
    events = [
        parse_line(
            "2026-10-21T10:15:01Z ERROR api [database] MongoDB connection refused",
            1,
        ),
        parse_line(
            "2026-10-21T10:15:10Z ERROR api [database] MongoDB connection refused",
            2,
        ),
        parse_line(
            "2026-10-21T10:15:20Z ERROR api [database] MongoDB connection refused",
            3,
        ),
    ]

    analysis = analyze_events(events, peak_threshold=3)

    assert len(analysis.error_peaks) == 1
    assert analysis.error_peaks[0].error_count == 3
    assert analysis.error_peaks[0].line_numbers == [1, 2, 3]


def test_reports_missing_data_and_unknown_lines() -> None:
    events = [
        parse_line("2026-10-21T10:15:01Z ERROR api [worker] Backend failure", 1),
        parse_line("line without a known format", 2),
    ]

    analysis = analyze_events(events)

    assert analysis.invalid_lines == []
    assert analysis.parsed_events == 2
    assert any("Missing timestamps" in item for item in analysis.limitations)
    assert any("Unknown input format" in item for item in analysis.limitations)

