from __future__ import annotations

import pytest
from live_gateway.source_connector import SourceConnectorError, validate_url


def test_loopback_source_is_allowed() -> None:
    assert validate_url("http://127.0.0.1:5000/logs") == "http://127.0.0.1:5000/logs"


def test_remote_source_requires_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("AI_DETECTIVE_ALLOW_REMOTE_SOURCE", raising=False)
    with pytest.raises(SourceConnectorError, match="Remote sources are disabled"):
        validate_url("https://example.com/logs")
