import json

from ai_detective.agent.tools import execute_tool
from ai_detective.analyzer.deterministic import analyze_events
from ai_detective.evidence.store import EvidenceStore
from ai_detective.parser.log_parser import parse_line


class FakeSearcher:
    def search(self, error, *, limit):
        return {
            "query": error.message,
            "sources": [
                {
                    "title": "Example",
                    "source_url": "https://stackoverflow.com/questions/1/example",
                    "answer_url": "https://stackoverflow.com/questions/1/example/2",
                    "excerpt": "Example solution",
                    "score": 3,
                    "accepted": True,
                }
            ],
        }


def test_execute_tool_is_allow_listed() -> None:
    events = [parse_line("raw backend failure", 1)]
    store = EvidenceStore(events, analyze_events(events))

    result = json.loads(execute_tool("not_allowed", {}, store))

    assert result["is_error"] is True
    assert "not_allowed" in result["error"]


def test_external_tool_uses_a_deterministic_error_group() -> None:
    events = [parse_line("2026-10-21T10:00:00Z ERROR api [db] MongoDB connection refused", 1)]
    store = EvidenceStore(events, analyze_events(events))

    result = json.loads(
        execute_tool(
            "search_external_solutions",
            {"error_index": 0, "limit": 1},
            store,
            external_searcher=FakeSearcher(),
        )
    )

    assert result["query"] == "mongodb connection refused"
    assert result["sources"][0]["accepted"] is True
