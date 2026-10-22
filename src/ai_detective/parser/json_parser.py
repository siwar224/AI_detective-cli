"""Parser for newline-delimited JSON log records."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ai_detective.models.events import LogEvent


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_json_line(raw_line: str, line_number: int) -> LogEvent:
    """Parse one JSON object and preserve unknown fields as metadata."""
    try:
        payload = json.loads(raw_line.strip())
    except json.JSONDecodeError as exc:
        raise ValueError("Line is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise TypeError("A JSON log record must be an object")

    timestamp = _parse_timestamp(payload.get("timestamp"))
    level = payload.get("level")
    service = payload.get("service")
    message = payload.get("message")
    metadata = payload.get("metadata", {})

    if not isinstance(metadata, dict):
        metadata = {"metadata": metadata}
    else:
        metadata = dict(metadata)

    if "component" in payload:
        metadata.setdefault("component", payload["component"])

    known_fields = {"timestamp", "level", "service", "message", "metadata", "component"}
    metadata.update(
        {key: value for key, value in payload.items() if key not in known_fields}
    )

    required_fields_are_valid = all(
        isinstance(value, str) and bool(value.strip())
        for value in (payload.get("timestamp"), level, service, message)
    )
    status = "valid" if required_fields_are_valid and timestamp is not None else "partial"

    return LogEvent(
        line_number=line_number,
        raw_line=raw_line,
        timestamp=timestamp,
        level=level.upper() if isinstance(level, str) else None,
        service=service if isinstance(service, str) else None,
        message=message if isinstance(message, str) else None,
        metadata=metadata,
        parse_status=status,
        source_format="json",
    )

