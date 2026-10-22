"""Groq adapter for local tool-calling and JSON report generation."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

from .base import LLMConfigurationError, LLMProviderError, LLMResponse, ToolCall

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


class GroqProvider:
    """Use Groq's OpenAI-compatible chat completion API."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None):
        load_dotenv()
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        self._client: Any = None

    def _get_client(self) -> Any:
        if not self._api_key:
            raise LLMConfigurationError(
                "GROQ_API_KEY is missing. Add it to .env or use --no-ai."
            )
        if self._client is None:
            try:
                from groq import Groq

                self._client = Groq(api_key=self._api_key)
            except Exception as exc:
                raise LLMConfigurationError(
                    f"Could not initialize the Groq client: {exc}"
                ) from exc
        return self._client

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        force_json: bool = False,
    ) -> LLMResponse:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 4096,
        }
        if force_json:
            request["response_format"] = {"type": "json_object"}
        elif tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"
            request["parallel_tool_calls"] = False

        try:
            response = self._get_client().chat.completions.create(**request)
            message = response.choices[0].message
        except Exception as exc:
            raise LLMProviderError(f"Groq request failed: {exc}") from exc

        normalized_calls: list[ToolCall] = []
        for tool_call in message.tool_calls or []:
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
                if not isinstance(arguments, dict):
                    raise TypeError("tool arguments must be a JSON object")
                normalized_calls.append(
                    ToolCall(
                        call_id=tool_call.id,
                        name=tool_call.function.name,
                        arguments=arguments,
                    )
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise LLMProviderError(
                    f"Groq returned invalid tool arguments: {exc}"
                ) from exc

        return LLMResponse(
            content=message.content,
            tool_calls=normalized_calls,
        )
