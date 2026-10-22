"""Small provider-neutral contracts for tool-calling models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMConfigurationError(RuntimeError):
    """Raised when the provider cannot be configured safely."""


class LLMProviderError(RuntimeError):
    """Raised when a provider request or response fails."""


@dataclass(frozen=True)
class ToolCall:
    """A tool call requested by the model."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    """Normalized provider response consumed by the orchestrator."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(Protocol):
    """Provider interface that makes the orchestrator easy to test."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        force_json: bool = False,
    ) -> LLMResponse: ...
