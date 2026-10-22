"""Models for deterministic log analysis results."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ErrorFrequency(BaseModel):
    """One repeated error message and its source lines."""

    message: str
    count: int = Field(ge=1)
    line_numbers: list[int]
    category: str | None = None


class TimelineEvent(BaseModel):
    """An event with a usable timestamp."""

    line_number: int
    timestamp: datetime
    level: str | None = None
    message: str | None = None
    category: str | None = None


class ErrorPeak(BaseModel):
    """A time window containing a high number of errors."""

    window_start: datetime
    window_end: datetime
    error_count: int = Field(ge=1)
    line_numbers: list[int]


class DeterministicAnalysis(BaseModel):
    """Analysis that does not require an external model or API."""

    total_lines: int = Field(ge=0)
    parsed_events: int = Field(ge=0)
    invalid_lines: list[int]
    levels_count: dict[str, int]
    top_errors: list[ErrorFrequency]
    timeline: list[TimelineEvent]
    error_peaks: list[ErrorPeak]
    limitations: list[str]

