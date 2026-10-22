"""Models representing parsed log events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ParseStatus = Literal["valid", "partial", "invalid"]
LogFormat = Literal["text", "json", "raw"]


class LogEvent(BaseModel):
    """One source log line, with structured fields when available."""

    line_number: int = Field(ge=1)
    raw_line: str
    timestamp: datetime | None = None
    level: str | None = None
    service: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    parse_status: ParseStatus
    source_format: LogFormat

