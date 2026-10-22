from datetime import datetime

import pytest

from ai_detective.analyzer.deterministic import analyze_events
from ai_detective.evidence.store import EvidenceLookupError, EvidenceStore
from ai_detective.parser.log_parser import parse_line


def _store() -> EvidenceStore:
    events = [
        parse_line(
            "2026-10-21T10:00:00Z ERROR api [database] MongoDB connection refused",
            1,
        ),
        parse_line(
            "2026-10-21T10:00:01Z INFO api [database] retrying MongoDB connection",
            2,
        ),
        parse_line(
            "2026-10-21T10:00:02Z ERROR api [database] MongoDB connection refused",
            3,
        ),
    ]
    return EvidenceStore(events, analyze_events(events))


def test_tools_can_read_summary_context_and_similar_lines() -> None:
    store = _store()

    summary = store.get_error_summary()
    context = store.get_events_around(line_number=1, before=0, after=1)
    similar = store.search_similar_lines("MongoDB connection refused")

    assert summary["errors"][0]["count"] == 2
    assert [event["line_number"] for event in context["events"]] == [1, 2]
    assert similar["matches"][0]["line_number"] == 1


def test_timestamp_lookup_handles_timezone_difference() -> None:
    result = _store().get_events_around(
        timestamp=datetime.fromisoformat("2026-10-21T10:00:01"),
        before=0,
        after=0,
    )

    assert result["events"][0]["line_number"] == 2


def test_unknown_line_is_rejected() -> None:
    with pytest.raises(EvidenceLookupError):
        _store().get_events_around(line_number=99)
