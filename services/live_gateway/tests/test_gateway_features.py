from __future__ import annotations

import asyncio
import json

from live_gateway import api
from live_gateway.source_connector import parse_log_content
from starlette.requests import Request


def _request(client_host: str = "127.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/prompt/generate",
            "headers": [],
            "client": (client_host, 1234),
            "server": ("127.0.0.1", 8000),
            "scheme": "http",
        }
    )


def test_parse_uploaded_json_records_into_log_lines() -> None:
    content = json.dumps(
        [
            {"level": "ERROR", "message": "database unavailable"},
            {"level": "INFO", "message": "request completed"},
        ]
    )

    lines = parse_log_content(content, 100, content_type="application/json")

    assert len(lines) == 2
    assert '"database unavailable"' in lines[0]


def test_plain_text_log_starting_with_bracket_is_not_forced_to_json() -> None:
    lines = parse_log_content("[INFO] request completed\n[ERROR] timeout", 100, content_type="text/plain")

    assert lines == ["[INFO] request completed", "[ERROR] timeout"]


def test_prompt_generation_uses_groq_and_reuses_cached_result(monkeypatch) -> None:
    class FakeProvider:
        calls = 0

        def complete(self, messages, *, force_json=False, tools=None):
            self.calls += 1
            return type("Response", (), {"content": json.dumps({"prompt": "Prompt professionnel"})})()

    fake = FakeProvider()
    monkeypatch.setattr(api, "GroqProvider", lambda: fake)
    api._prompt_cache.clear()
    api._prompt_last_request.clear()
    payload = api.PromptRequest(
        problem="La base de données refuse la connexion.",
        cause="Le service de base de données est indisponible.",
        error_count=2,
        recommendations=["Vérifier le service de base de données."],
        evidence=["Ligne 1: connection refused"],
    )

    first = asyncio.run(api.generate_prompt(payload, _request()))
    second = asyncio.run(api.generate_prompt(payload, _request()))

    assert first.prompt == "Prompt professionnel"
    assert second.prompt == first.prompt
    assert fake.calls == 1
