"""Read-only evidence lookup for the investigation tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ai_detective.analyzer.deterministic import normalize_error_message
from ai_detective.models.analysis import DeterministicAnalysis
from ai_detective.models.events import LogEvent


class EvidenceLookupError(ValueError):
    """Raised when a tool receives an invalid evidence lookup request."""


def _utc_timestamp(timestamp: datetime) -> datetime:
    """Compare naive and timezone-aware timestamps consistently."""
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


class EvidenceStore:
    """Bounded, read-only access to parsed events and deterministic analysis."""

    def __init__(self, events: list[LogEvent], analysis: DeterministicAnalysis):
        self._events = tuple(events)
        self._analysis = analysis
        self._by_line = {event.line_number: event for event in events}

    def get_error_summary(
        self,
        *,
        limit: int = 10,
        category: str | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 10:
            raise EvidenceLookupError("limit must be between 1 and 10")

        errors = self._analysis.top_errors
        if category:
            errors = [error for error in errors if error.category == category]

        return {
            "errors": [error.model_dump(mode="json") for error in errors[:limit]],
            "total_error_groups": len(errors),
        }

    def get_event(self, line_number: int) -> LogEvent | None:
        """Return one source event for backend-side evidence validation."""
        return self._by_line.get(line_number)

    def get_error_group(self, index: int) -> Any:
        """Return one deterministic error group for external lookup."""
        if not 0 <= index < len(self._analysis.top_errors):
            raise EvidenceLookupError(f"Error group index {index} does not exist")
        return self._analysis.top_errors[index]

    def get_events_around(
        self,
        *,
        line_number: int | None = None,
        timestamp: datetime | None = None,
        before: int = 2,
        after: int = 2,
    ) -> dict[str, Any]:
        if (line_number is None) == (timestamp is None):
            raise EvidenceLookupError(
                "Provide exactly one of line_number or timestamp"
            )
        if not 0 <= before <= 5 or not 0 <= after <= 5:
            raise EvidenceLookupError("before and after must be between 0 and 5")

        if line_number is not None:
            if line_number not in self._by_line:
                raise EvidenceLookupError(f"Line {line_number} does not exist")
            center_index = next(
                index
                for index, event in enumerate(self._events)
                if event.line_number == line_number
            )
        else:
            timestamped = [
                (index, event)
                for index, event in enumerate(self._events)
                if event.timestamp is not None
            ]
            if not timestamped:
                return {"events": [], "message": "No timestamped events available"}

            center_index, _ = min(
                timestamped,
                key=lambda item: abs(
                    _utc_timestamp(item[1].timestamp)
                    - _utc_timestamp(timestamp)
                ),
            )

        start = max(0, center_index - before)
        end = min(len(self._events), center_index + after + 1)
        return {
            "events": [
                event.model_dump(mode="json") for event in self._events[start:end]
            ]
        }

    def search_similar_lines(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        if not query.strip():
            raise EvidenceLookupError("query cannot be empty")
        if not 1 <= limit <= 10:
            raise EvidenceLookupError("limit must be between 1 and 10")

        query_tokens = set(normalize_error_message(query).split())
        matches: list[tuple[float, LogEvent]] = []
        normalized_query = normalize_error_message(query)

        for event in self._events:
            candidate = normalize_error_message(event.message or event.raw_line)
            candidate_tokens = set(candidate.split())
            overlap = len(query_tokens & candidate_tokens)
            score = overlap / len(query_tokens) if query_tokens else 0.0
            if normalized_query in candidate or candidate in normalized_query:
                score = max(score, 1.0)
            if score > 0:
                matches.append((score, event))

        matches.sort(key=lambda item: (-item[0], item[1].line_number))
        return {
            "matches": [
                {
                    "score": round(score, 3),
                    **event.model_dump(mode="json"),
                }
                for score, event in matches[:limit]
            ]
        }

