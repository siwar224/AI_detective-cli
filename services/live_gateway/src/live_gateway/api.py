"""Optional HTTP gateway for detecting already-running backend services."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_detective.agent.orchestrator import run_investigation
from ai_detective.analyzer.deterministic import analyze_events
from ai_detective.llm.base import LLMConfigurationError, LLMProviderError
from ai_detective.llm.groq_provider import GroqProvider
from ai_detective.models.events import LogEvent
from ai_detective.models.report import (
    EvidenceReference,
    Hypothesis,
    InvestigationReport,
)
from ai_detective.parser.log_parser import parse_line
from ai_detective.parser.raw_parser import parse_raw_line

from .source_connector import (
    DEFAULT_BACKEND_URLS,
    SourceConnectorError,
    parse_log_content,
    probe_backend,
    read_log_source,
    validate_url,
)

GATEWAY_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(GATEWAY_ROOT / ".env")


class ConnectRequest(BaseModel):
    """A backend URL and the URL that exposes its log stream."""

    backend_url: str | None = None
    log_source_url: str = Field(min_length=1, max_length=2048)


class AnalysisRequest(BaseModel):
    """Analysis settings for the connected log source."""

    log_source_url: str = Field(min_length=1, max_length=2048)
    use_ai: bool = False
    max_lines: int = Field(default=100_000, ge=1, le=100_000)


class ContentAnalysisRequest(BaseModel):
    """Analysis settings for a JSON file read by the separate frontend."""

    file_name: str = Field(default="uploaded-logs.json", min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=10_000_000)
    use_ai: bool = False
    max_lines: int = Field(default=100_000, ge=1, le=100_000)


class PromptRequest(BaseModel):
    """Small, evidence-based context used to generate a copyable LLM prompt."""

    problem: str = Field(min_length=1, max_length=2000)
    cause: str | None = Field(default=None, max_length=500)
    error_count: int = Field(default=0, ge=0)
    recommendations: list[str] = Field(default_factory=list, max_length=5)
    evidence: list[str] = Field(default_factory=list, max_length=5)


class PromptResponse(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)


class SourceMetadata(BaseModel):
    url: str
    backend_url: str | None = None
    port: int | None
    line_count: int
    content_type: str | None = None
    fetched_at: datetime
    analysis_mode: str


class LiveAnalysisResponse(BaseModel):
    report: InvestigationReport
    source: SourceMetadata


class GatewayError(RuntimeError):
    """Raised when the gateway cannot produce an analysis."""


ANALYSIS_CACHE_TTL_SECONDS = 10.0
PROMPT_CACHE_TTL_SECONDS = 300.0
PROMPT_MIN_INTERVAL_SECONDS = 5.0
_analysis_cache: dict[str, tuple[float, LiveAnalysisResponse]] = {}
_prompt_cache: dict[str, tuple[float, PromptResponse]] = {}
_prompt_last_request: dict[str, float] = {}


def _cors_origins() -> list[str]:
    configured = os.getenv("AI_DETECTIVE_CORS_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def _parse_events(lines: list[str]) -> list[LogEvent]:
    events: list[LogEvent] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            events.append(parse_line(line, line_number))
        except (TypeError, ValueError):
            events.append(parse_raw_line(line, line_number))
    return events


def _deterministic_report(events: list[LogEvent], source_url: str) -> InvestigationReport:
    analysis = analyze_events(events)
    top_error = analysis.top_errors[0] if analysis.top_errors else None
    event_by_line = {event.line_number: event for event in events}

    if top_error:
        summary = f"The backend reported {top_error.count} occurrence(s) of {top_error.message}."
        evidence = []
        for line_number in top_error.line_numbers[:3]:
            event = event_by_line.get(line_number)
            quote = (event.message if event and event.message else event.raw_line) if event else top_error.message
            evidence.append(
                EvidenceReference(
                    line_number=line_number,
                    quote=quote[:500],
                    reason="This line belongs to the most frequent error group in the connected log source.",
                )
            )
        hypotheses = [
            Hypothesis(
                cause=f"The backend is repeatedly reporting: {top_error.message}.",
                confidence="medium" if top_error.count > 1 else "low",
                supporting_evidence=evidence,
                recommended_checks=[
                    "Inspect the backend logs around the cited lines.",
                    "Check the health of the dependency named in the error.",
                ],
            )
        ]
        recommendations = [
            "Inspect the most frequent error group first.",
            "Check the backend health endpoint and its dependent services.",
            "Review the cited log lines before applying a fix.",
        ]
    else:
        summary = "The connected backend returned no ERROR-level events in the analysed window."
        hypotheses = []
        recommendations = [
            "Continue monitoring the connected log source for new error-level events.",
            "Review partially parsed lines if the source format is not standard.",
        ]

    return InvestigationReport(
        incident_summary=summary,
        statistics=analysis,
        timeline=analysis.timeline,
        hypotheses=hypotheses,
        recommendations=recommendations,
        limitations=[
            *analysis.limitations,
            f"Source fetched from {source_url}.",
            "AI reasoning is disabled for this request; the report is deterministic.",
        ],
    )


def _build_report(lines: list[str], source_url: str, use_ai: bool) -> InvestigationReport:
    events = _parse_events(lines)
    if not events:
        raise GatewayError("No parseable log events were returned")
    analysis = analyze_events(events)
    if use_ai:
        try:
            # One bounded Stack Exchange search enriches the AI recommendations
            # without turning every log line into an external request.
            return run_investigation(events, analysis, max_external_calls=1)
        except Exception:  # noqa: BLE001 - deterministic analysis is the safe fallback
            return _deterministic_report(events, source_url)
    return _deterministic_report(events, source_url)


def _cache_key(*parts: object) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _get_analysis_cache(key: str) -> LiveAnalysisResponse | None:
    cached = _analysis_cache.get(key)
    if not cached:
        return None
    created_at, response = cached
    if time.monotonic() - created_at > ANALYSIS_CACHE_TTL_SECONDS:
        _analysis_cache.pop(key, None)
        return None
    return response


def _make_analysis_response(
    lines: list[str],
    *,
    source_url: str,
    content_type: str | None,
    use_ai: bool,
    backend_url: str | None = None,
) -> LiveAnalysisResponse:
    report = _build_report(lines, source_url, use_ai)
    parsed = source_url.split("://", 1)[-1].split("/", 1)[0]
    port = int(parsed.rsplit(":", 1)[1]) if ":" in parsed and parsed.rsplit(":", 1)[1].isdigit() else None
    return LiveAnalysisResponse(
        report=report,
        source=SourceMetadata(
            url=source_url,
            backend_url=backend_url,
            port=port,
            line_count=len(lines),
            content_type=content_type,
            fetched_at=datetime.now(UTC),
            analysis_mode="ai-assisted" if use_ai else "deterministic",
        ),
    )


app = FastAPI(
    title="AI Detective Live Gateway",
    version="0.2.0",
    description="Detect an existing backend and analyse a user-provided log source.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-detective-live-gateway"}


@app.get("/api/backends/discover")
async def discover_backends() -> dict[str, Any]:
    """Probe the default ports without starting or controlling any process."""
    results = []
    for url in DEFAULT_BACKEND_URLS:
        results.append(await probe_backend(url))
    return {"backends": results}


@app.post("/api/backends/connect")
async def connect_backend(request: ConnectRequest) -> dict[str, Any]:
    """Verify the backend and remember no process state or command."""
    try:
        log_source_url = validate_url(request.log_source_url)
        backend_url = validate_url(request.backend_url) if request.backend_url else None
        probe = await probe_backend(backend_url) if backend_url else None
    except SourceConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "connected": bool(probe is None or probe["reachable"]),
        "backend": probe,
        "log_source_url": log_source_url,
        "message": "Backend reachable; log detection can begin."
        if probe is None or probe["reachable"]
        else "Backend is not reachable yet.",
    }


@app.post("/api/analyze/source", response_model=LiveAnalysisResponse)
async def analyze_source(request: AnalysisRequest) -> LiveAnalysisResponse:
    """Fetch and analyse a user-provided source; never starts a backend."""
    try:
        lines, content_type = await read_log_source(request.log_source_url, request.max_lines)
        source_url = validate_url(request.log_source_url)
        cache_key = _cache_key("url", source_url, request.use_ai, request.max_lines)
        cached = _get_analysis_cache(cache_key)
        if cached:
            return cached
        response = _make_analysis_response(
            lines,
            source_url=source_url,
            content_type=content_type,
            use_ai=request.use_ai,
        )
        _analysis_cache[cache_key] = (time.monotonic(), response)
        return response
    except (SourceConnectorError, GatewayError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/analyze/content", response_model=LiveAnalysisResponse)
async def analyze_content(request: ContentAnalysisRequest) -> LiveAnalysisResponse:
    """Analyse uploaded content in memory; the gateway never stores the file."""
    try:
        lines = parse_log_content(
            request.content,
            request.max_lines,
            content_type="application/json",
        )
        source_url = f"file://{request.file_name}"
        content_hash = hashlib.sha256(request.content.encode("utf-8")).hexdigest()
        cache_key = _cache_key("file", content_hash, request.use_ai, request.max_lines)
        cached = _get_analysis_cache(cache_key)
        if cached:
            return cached
        response = _make_analysis_response(
            lines,
            source_url=source_url,
            content_type="application/json",
            use_ai=request.use_ai,
        )
        _analysis_cache[cache_key] = (time.monotonic(), response)
        return response
    except (SourceConnectorError, GatewayError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/prompt/generate", response_model=PromptResponse)
async def generate_prompt(request: PromptRequest, http_request: Request) -> PromptResponse:
    """Generate one professional copyable prompt with the configured Groq model."""
    payload_key = _cache_key(request.model_dump())
    cached = _prompt_cache.get(payload_key)
    if cached and time.monotonic() - cached[0] <= PROMPT_CACHE_TTL_SECONDS:
        return cached[1]

    client_key = http_request.client.host if http_request.client else "local-client"
    now = time.monotonic()
    last_request = _prompt_last_request.get(client_key)
    if last_request and now - last_request < PROMPT_MIN_INTERVAL_SECONDS:
        retry_after = max(1, int(PROMPT_MIN_INTERVAL_SECONDS - (now - last_request)))
        raise HTTPException(
            status_code=429,
            detail=f"Wait {retry_after} second(s) before generating another prompt.",
            headers={"Retry-After": str(retry_after)},
        )
    _prompt_last_request[client_key] = now

    system_message = (
        "You are a senior software architect. Generate a professional prompt in English, "
        "ready to paste into another LLM to resolve a backend incident. The prompt must request "
        "a careful analysis, affected files, a step-by-step plan, a minimal fix, tests and "
        "verification commands. It must separate facts from hypotheses and never invent information. "
        "Return only a JSON object with a prompt key."
    )
    user_message = {
        "problem": request.problem,
        "probable_cause": request.cause,
        "error_count": request.error_count,
        "recommended_actions": request.recommendations,
        "evidence": request.evidence,
    }

    try:
        llm_response = GroqProvider().complete(
            [
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": json.dumps(user_message, ensure_ascii=False),
                },
            ],
            force_json=True,
        )
        parsed = json.loads(llm_response.content or "{}")
        prompt = parsed.get("prompt") if isinstance(parsed, dict) else None
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Groq returned an empty prompt")
    except (LLMConfigurationError, LLMProviderError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail=f"Groq prompt generation unavailable: {exc}") from exc

    response = PromptResponse(prompt=prompt.strip())
    _prompt_cache[payload_key] = (time.monotonic(), response)
    return response


def main() -> None:
    uvicorn.run(
        "live_gateway.api:app",
        host=os.getenv("AI_DETECTIVE_API_HOST", "127.0.0.1"),
        port=int(os.getenv("AI_DETECTIVE_API_PORT", "8000")),
        reload=os.getenv("AI_DETECTIVE_API_RELOAD", "false").lower() == "true",
    )
