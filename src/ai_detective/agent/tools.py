"""Tool schemas and safe local execution for the investigation agent."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ai_detective.evidence.store import EvidenceLookupError, EvidenceStore


class ErrorSummaryArguments(BaseModel):
    limit: int = Field(default=10, ge=1, le=10)
    category: str | None = None


class EventsAroundArguments(BaseModel):
    line_number: int | None = Field(default=None, ge=1)
    timestamp: str | None = None
    before: int = Field(default=2, ge=0, le=5)
    after: int = Field(default=2, ge=0, le=5)

    @model_validator(mode="after")
    def exactly_one_target(self) -> EventsAroundArguments:
        if (self.line_number is None) == (self.timestamp is None):
            raise ValueError("Provide exactly one of line_number or timestamp")
        return self


class SimilarLinesArguments(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=10)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_error_summary",
            "description": "Read recurring errors and their frequencies from the deterministic analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                    "category": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_events_around",
            "description": "Read a bounded context around one existing line number or timestamp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "line_number": {"type": "integer", "minimum": 1},
                    "timestamp": {"type": "string"},
                    "before": {"type": "integer", "minimum": 0, "maximum": 5},
                    "after": {"type": "integer", "minimum": 0, "maximum": 5},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_lines",
            "description": "Find bounded deterministic text matches in the parsed evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 500},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    store: EvidenceStore,
) -> str:
    """Validate and execute exactly one allow-listed read-only tool."""
    try:
        if name == "get_error_summary":
            args = ErrorSummaryArguments.model_validate(arguments)
            result = store.get_error_summary(
                limit=args.limit,
                category=args.category,
            )
        elif name == "get_events_around":
            args = EventsAroundArguments.model_validate(arguments)
            timestamp = (
                datetime.fromisoformat(args.timestamp)
                if args.timestamp
                else None
            )
            result = store.get_events_around(
                line_number=args.line_number,
                timestamp=timestamp,
                before=args.before,
                after=args.after,
            )
        elif name == "search_similar_lines":
            args = SimilarLinesArguments.model_validate(arguments)
            result = store.search_similar_lines(args.query, limit=args.limit)
        else:
            raise EvidenceLookupError(f"Tool is not allowed: {name}")
    except (EvidenceLookupError, TypeError, ValueError) as exc:
        result = {"error": str(exc), "is_error": True}

    return json.dumps(result, ensure_ascii=False)

