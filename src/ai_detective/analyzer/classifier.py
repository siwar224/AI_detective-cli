"""Deterministic error classification rules."""

from __future__ import annotations

import re

from ai_detective.models.events import LogEvent

ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}

CLASSIFICATION_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "mongodb",
        ("mongodb", "mongoerror", "mongoserverselectionerror"),
    ),
    (
        "authentication",
        ("token expired", "invalid token", "unauthorized", "authentication failed", "401"),
    ),
    (
        "permission",
        ("permission denied", "access denied", "eacces", "forbidden", "403"),
    ),
    (
        "timeout",
        ("timeout", "timed out", "deadline exceeded", "gateway timeout", "504"),
    ),
    (
        "http",
        ("bad gateway", "service unavailable", "http 4", "http 5", "502", "503"),
    ),
)


def classify_event(event: LogEvent) -> str | None:
    """Return a deterministic category for an error event.

    Non-error informational events return ``None``. Unknown error messages
    return ``"unknown"`` so they remain visible to later analysis.
    """
    searchable_text = " ".join(
        value.lower()
        for value in (event.message or "", event.raw_line)
        if value
    )

    is_error = event.level in ERROR_LEVELS or bool(
        re.search(r"\b(error|exception|failed|failure)\b", searchable_text)
    )
    if not is_error:
        return None

    component = str(event.metadata.get("component", "")).lower()
    if "mongodb" in searchable_text or "mongo" in component:
        return "mongodb"

    for category, terms in CLASSIFICATION_RULES[1:]:
        if any(term in searchable_text for term in terms):
            return category

    return "unknown"

