"""Deterministic statistics and timeline analysis for parsed log events."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta

from ai_detective.models.analysis import (
    DeterministicAnalysis,
    ErrorFrequency,
    ErrorPeak,
    TimelineEvent,
)
from ai_detective.models.events import LogEvent

from .classifier import ERROR_LEVELS, classify_event

UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"\b\d+\b")
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_error_message(message: str) -> str:
    """Normalize common variable parts for deterministic grouping."""
    normalized = message.strip().lower()
    normalized = UUID_PATTERN.sub("<uuid>", normalized)
    normalized = NUMBER_PATTERN.sub("<number>", normalized)
    return WHITESPACE_PATTERN.sub(" ", normalized)


def _utc_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _build_top_errors(events: list[LogEvent]) -> list[ErrorFrequency]:
    groups: dict[str, ErrorFrequency] = {}

    for event in events:
        if event.level not in ERROR_LEVELS or not event.message:
            continue

        normalized = normalize_error_message(event.message)
        category = classify_event(event)
        if normalized not in groups:
            groups[normalized] = ErrorFrequency(
                message=normalized,
                count=1,
                line_numbers=[event.line_number],
                category=category,
            )
            continue

        group = groups[normalized]
        group.count += 1
        group.line_numbers.append(event.line_number)
        if group.category != category:
            group.category = None

    return sorted(
        groups.values(),
        key=lambda error: (-error.count, error.line_numbers[0]),
    )


def _build_timeline(events: list[LogEvent]) -> list[TimelineEvent]:
    timestamped_events = [event for event in events if event.timestamp is not None]
    timestamped_events.sort(
        key=lambda event: (_utc_timestamp(event.timestamp), event.line_number)
    )

    return [
        TimelineEvent(
            line_number=event.line_number,
            timestamp=event.timestamp,
            level=event.level,
            message=event.message,
            category=classify_event(event),
        )
        for event in timestamped_events
    ]


def _build_error_peaks(
    events: list[LogEvent],
    *,
    bucket_seconds: int,
    peak_threshold: int,
) -> list[ErrorPeak]:
    buckets: dict[int, list[LogEvent]] = {}

    for event in events:
        if event.level not in ERROR_LEVELS or event.timestamp is None:
            continue
        timestamp = _utc_timestamp(event.timestamp)
        bucket_id = int(timestamp.timestamp()) // bucket_seconds
        buckets.setdefault(bucket_id, []).append(event)

    peaks: list[ErrorPeak] = []
    for bucket_id, bucket_events in sorted(buckets.items()):
        if len(bucket_events) < peak_threshold:
            continue

        window_start = datetime.fromtimestamp(
            bucket_id * bucket_seconds,
            tz=UTC,
        )
        peaks.append(
            ErrorPeak(
                window_start=window_start,
                window_end=window_start + timedelta(seconds=bucket_seconds),
                error_count=len(bucket_events),
                line_numbers=[event.line_number for event in bucket_events],
            )
        )

    return peaks


def _build_limitations(events: list[LogEvent], timeline: list[TimelineEvent]) -> list[str]:
    limitations: list[str] = []
    invalid_lines = [event.line_number for event in events if event.parse_status == "invalid"]
    partial_lines = [event.line_number for event in events if event.parse_status == "partial"]
    missing_timestamps = [event.line_number for event in events if event.timestamp is None]
    missing_levels = [event.line_number for event in events if event.level is None]
    raw_lines = [event.line_number for event in events if event.source_format == "raw"]

    if invalid_lines:
        limitations.append(f"Invalid lines: {invalid_lines}")
    if partial_lines:
        limitations.append(f"Partially parsed lines: {partial_lines}")
    if missing_timestamps:
        limitations.append(f"Missing timestamps on lines: {missing_timestamps}")
    if missing_levels:
        limitations.append(f"Missing log levels on lines: {missing_levels}")
    if raw_lines:
        limitations.append(f"Unknown input format on lines: {raw_lines}")
    if not timeline:
        limitations.append("No usable timestamps were found for the timeline")

    return limitations


def analyze_events(
    events: list[LogEvent],
    *,
    bucket_seconds: int = 60,
    peak_threshold: int = 3,
) -> DeterministicAnalysis:
    """Compute reproducible statistics, groups, timeline and error peaks."""
    if bucket_seconds <= 0:
        raise ValueError("bucket_seconds must be greater than zero")
    if peak_threshold <= 0:
        raise ValueError("peak_threshold must be greater than zero")

    levels_count = Counter(event.level for event in events if event.level is not None)
    timeline = _build_timeline(events)
    invalid_lines = [event.line_number for event in events if event.parse_status == "invalid"]
    parsed_events = sum(event.parse_status != "invalid" for event in events)

    return DeterministicAnalysis(
        total_lines=len(events),
        parsed_events=parsed_events,
        invalid_lines=invalid_lines,
        levels_count=dict(levels_count),
        top_errors=_build_top_errors(events),
        timeline=timeline,
        error_peaks=_build_error_peaks(
            events,
            bucket_seconds=bucket_seconds,
            peak_threshold=peak_threshold,
        ),
        limitations=_build_limitations(events, timeline),
    )

