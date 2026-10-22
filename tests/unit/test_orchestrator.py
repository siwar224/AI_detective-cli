from ai_detective.agent.orchestrator import run_investigation
from ai_detective.analyzer.deterministic import analyze_events
from ai_detective.llm.base import LLMResponse, ToolCall
from ai_detective.models.report import (
    EvidenceReference,
    Hypothesis,
    InvestigationReport,
)
from ai_detective.parser.log_parser import parse_line


class FakeProvider:
    def __init__(self, report_json: str):
        self.report_json = report_json
        self.calls = 0

    def complete(self, messages, *, tools=None, force_json=False):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        call_id="call-1",
                        name="get_events_around",
                        arguments={"line_number": 1, "before": 0, "after": 0},
                    )
                ]
            )
        return LLMResponse(content=self.report_json)


class ExternalFakeProvider:
    def __init__(self, report_json: str):
        self.report_json = report_json
        self.calls = 0

    def complete(self, messages, *, tools=None, force_json=False):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        call_id="external-call-1",
                        name="search_external_solutions",
                        arguments={"error_index": 0, "limit": 1},
                    )
                ]
            )
        return LLMResponse(content=self.report_json)


class ExternalFakeSearcher:
    def search(self, error, *, limit):
        return {
            "query": error.message,
            "sources": [
                {
                    "title": "MongoDB example",
                    "source_url": "https://stackoverflow.com/questions/42/example",
                    "answer_url": "https://stackoverflow.com/questions/42/example/99",
                    "excerpt": "Check that MongoDB is running.",
                    "score": 8,
                    "accepted": True,
                }
            ],
        }


def _events():
    return [
        parse_line(
            "2026-10-21T10:00:00Z ERROR api [database] MongoDB connection refused",
            1,
        )
    ]


def test_investigation_uses_tools_and_validates_evidence() -> None:
    events = _events()
    analysis = analyze_events(events)
    report = InvestigationReport(
        incident_summary="MongoDB is unreachable.",
        statistics=analysis,
        timeline=analysis.timeline,
        hypotheses=[
            Hypothesis(
                cause="MongoDB is not accepting connections.",
                confidence="high",
                supporting_evidence=[
                    EvidenceReference(
                        line_number=1,
                        quote="MongoDB connection refused",
                        reason="The backend reports a refused database connection.",
                    )
                ],
            )
        ],
        recommendations=["Check MongoDB availability and the configured URI."],
    )

    fake = FakeProvider(report.model_dump_json())
    result = run_investigation(
        events,
        analysis,
        provider=fake,
        max_external_calls=0,
    )

    assert result.hypotheses[0].supporting_evidence[0].line_number == 1
    assert fake.calls == 2


def test_invalid_evidence_falls_back_to_deterministic_report() -> None:
    events = _events()
    analysis = analyze_events(events)
    invalid = InvestigationReport(
        incident_summary="Unsupported claim.",
        statistics=analysis,
        timeline=analysis.timeline,
        hypotheses=[
            Hypothesis(
                cause="Unknown cause",
                confidence="low",
                supporting_evidence=[
                    EvidenceReference(
                        line_number=99,
                        quote="missing",
                        reason="This line does not exist.",
                    )
                ],
            )
        ],
    )

    result = run_investigation(
        events,
        analysis,
        provider=FakeProvider(invalid.model_dump_json()),
        max_external_calls=0,
    )

    assert result.hypotheses == []
    assert any("does not exist" in limitation for limitation in result.limitations)


def test_external_solutions_are_separated_from_log_evidence() -> None:
    events = _events()
    analysis = analyze_events(events)
    report = InvestigationReport(
        incident_summary="MongoDB cannot be reached.",
        statistics=analysis,
        timeline=analysis.timeline,
        resolution_steps=[
            {
                "action": "Check whether MongoDB is running.",
                "reason": "The external answer describes this verification.",
                "source_urls": [
                    "https://stackoverflow.com/questions/42/example/99"
                ],
            }
        ],
    )

    result = run_investigation(
        events,
        analysis,
        provider=ExternalFakeProvider(report.model_dump_json()),
        external_searcher=ExternalFakeSearcher(),
    )

    assert result.external_solutions[0].accepted is True
    assert result.resolution_steps[0].source_urls == [
        "https://stackoverflow.com/questions/42/example/99"
    ]
