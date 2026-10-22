import json

from ai_detective.agent.tools import execute_tool
from ai_detective.analyzer.deterministic import analyze_events
from ai_detective.evidence.store import EvidenceStore
from ai_detective.parser.log_parser import parse_line


def test_execute_tool_is_allow_listed() -> None:
    events = [parse_line("raw backend failure", 1)]
    store = EvidenceStore(events, analyze_events(events))

    result = json.loads(execute_tool("not_allowed", {}, store))

    assert result["is_error"] is True
    assert "not_allowed" in result["error"]
