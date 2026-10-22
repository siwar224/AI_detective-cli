"""HTTP discovery and log-source access for already running backends."""

from __future__ import annotations

import json
import os
import time
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_BACKEND_URLS = (
    "http://127.0.0.1:5000",
    "http://127.0.0.1:3000",
)
MAX_SOURCE_BYTES = 10 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 3.0


class SourceConnectorError(RuntimeError):
    """Raised when a backend or log source cannot be reached safely."""


def _is_loopback(hostname: str | None) -> bool:
    if not hostname:
        return False
    normalized = hostname.strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SourceConnectorError("The source must be a complete HTTP or HTTPS URL")
    remote_allowed = os.getenv("AI_DETECTIVE_ALLOW_REMOTE_SOURCE", "false").lower() == "true"
    if not _is_loopback(parsed.hostname) and not remote_allowed:
        raise SourceConnectorError(
            "Remote sources are disabled; use localhost or set "
            "AI_DETECTIVE_ALLOW_REMOTE_SOURCE=true"
        )
    if parsed.username or parsed.password:
        raise SourceConnectorError("Credentials in source URLs are not allowed")
    return value.rstrip("/")


def _records_to_lines(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return payload.splitlines()
    if isinstance(payload, list):
        return [item if isinstance(item, str) else json.dumps(item, ensure_ascii=False) for item in payload]
    if isinstance(payload, dict):
        for key in ("logs", "log", "content", "data", "events", "entries"):
            if key in payload:
                return _records_to_lines(payload[key])
        return [json.dumps(payload, ensure_ascii=False)]
    return [json.dumps(payload, ensure_ascii=False)]


def _response_lines(response: httpx.Response, max_lines: int) -> list[str]:
    if len(response.content) > MAX_SOURCE_BYTES:
        raise SourceConnectorError("The log response is too large")
    content_type = response.headers.get("content-type", "").lower()
    return parse_log_content(response.text, max_lines, content_type=content_type)


def parse_log_content(content: str, max_lines: int, *, content_type: str | None = None) -> list[str]:
    """Convert HTTP or uploaded JSON content into bounded log lines."""
    if len(content.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise SourceConnectorError("The log content is too large")

    normalized_type = (content_type or "").lower()
    looks_like_json = "json" in normalized_type
    if looks_like_json:
        try:
            payload = json.loads(content)
            lines = _records_to_lines(payload)
        except json.JSONDecodeError as exc:
            raise SourceConnectorError("The source returned invalid JSON") from exc
    else:
        lines = content.splitlines()

    lines = [line.rstrip("\r\n") for line in lines if line.strip()]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if not lines:
        raise SourceConnectorError("The source returned no log lines")
    return lines


async def probe_backend(url: str) -> dict[str, Any]:
    """Check whether an already-running HTTP backend responds."""
    target = validate_url(url)
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS), follow_redirects=False) as client:
            parsed = urlparse(target)
            candidates = [target]
            if parsed.path in {"", "/"}:
                candidates = [
                    f"{target}/api/v1/health",
                    f"{target}/health",
                    f"{target}/api/health",
                    target,
                ]

            response = None
            checked_url = target
            for candidate in candidates:
                candidate_response = await client.get(
                    candidate,
                    headers={"Accept": "application/json, text/plain, text/html"},
                )
                checked_url = candidate
                response = candidate_response
                if candidate_response.status_code < 500:
                    break

            assert response is not None
        return {
            "url": target,
            "checked_url": checked_url,
            "reachable": True,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "detail": "Backend responded",
        }
    except (httpx.HTTPError, SourceConnectorError) as exc:
        return {
            "url": target,
            "reachable": False,
            "status_code": None,
            "content_type": None,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "detail": exc.__class__.__name__,
        }


async def read_log_source(url: str, max_lines: int) -> tuple[list[str], str | None]:
    """Read a user-provided HTTP log source; this never starts a backend."""
    target = validate_url(url)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS), follow_redirects=False) as client:
            response = await client.get(target, headers={"Accept": "application/json, text/plain"})
            response.raise_for_status()
        return _response_lines(response, max_lines), response.headers.get("content-type")
    except (httpx.HTTPError, SourceConnectorError) as exc:
        raise SourceConnectorError(f"Unable to read {target}: {exc}") from exc
