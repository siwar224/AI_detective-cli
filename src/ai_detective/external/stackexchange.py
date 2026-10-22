"""Read-only Stack Exchange search for incident-resolution suggestions."""

from __future__ import annotations

import json
import os
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from ai_detective.models.analysis import ErrorFrequency

STACK_EXCHANGE_API = "https://api.stackexchange.com/2.3"
DEFAULT_TIMEOUT_SECONDS = 8
MAX_EXCERPT_LENGTH = 2000
SECRET_PATTERN = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|authorization)\s*[:=]\s*\S+"
)
URL_PATTERN = re.compile(r"(?i)\b(?:https?|mongodb(?:\+srv)?)://\S+")


class ExternalSearchError(RuntimeError):
    """Raised when the external knowledge provider cannot be queried safely."""


class _HTMLTextExtractor(HTMLParser):
    """Convert answer HTML into a bounded plain-text excerpt."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(unescape(part).strip() for part in self.parts if part.strip())


def _answer_excerpt(answer: dict[str, Any] | None, fallback: str) -> str:
    if not answer:
        return fallback
    markdown = answer.get("body_markdown")
    if markdown:
        return str(markdown)
    html_body = answer.get("body")
    if html_body:
        extractor = _HTMLTextExtractor()
        extractor.feed(str(html_body))
        return extractor.text() or fallback
    return fallback


def _category_tag(category: str | None) -> str | None:
    return {
        "mongodb": "mongodb",
        "http": "http",
        "authentication": "authentication",
        "permission": "permissions",
        "timeout": "timeout",
    }.get(category)


def _safe_query(message: str) -> str:
    """Remove common credentials and connection URLs before external lookup."""
    sanitized = URL_PATTERN.sub("", message)
    sanitized = SECRET_PATTERN.sub("", sanitized)
    return " ".join(sanitized.split())[:300]


def _is_stackoverflow_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.netloc in {
        "stackoverflow.com",
        "www.stackoverflow.com",
    }


class StackExchangeSearcher:
    """Search Stack Overflow through the official read-only API."""

    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        api_key: str | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or os.getenv("STACKEXCHANGE_API_KEY")

    def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {key: value for key, value in params.items() if value is not None}
        url = f"{STACK_EXCHANGE_API}{path}?{urlencode(query)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "AI-Detective-CLI/0.1",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except Exception as exc:
            raise ExternalSearchError(f"Stack Exchange request failed: {exc}") from exc

        if payload.get("backoff") is not None:
            raise ExternalSearchError(
                f"Stack Exchange requested a backoff of {payload['backoff']} seconds"
            )
        if payload.get("error_name"):
            raise ExternalSearchError(
                f"Stack Exchange API error: {payload.get('error_message', payload['error_name'])}"
            )
        return payload

    def search(self, error: ErrorFrequency, *, limit: int = 3) -> dict[str, Any]:
        """Return bounded question/answer excerpts for one deterministic error group."""
        if not 1 <= limit <= 3:
            raise ValueError("limit must be between 1 and 3")

        query = _safe_query(error.message)
        if not query:
            raise ExternalSearchError("The error message contains no safe search terms")
        tag = _category_tag(error.category)
        search_payload = self._get_json(
            "/search/advanced",
            {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "tagged": tag,
                "accepted": "true",
                "answers": 1,
                "site": "stackoverflow",
                "pagesize": limit,
                "key": self.api_key,
            },
        )
        questions = search_payload.get("items", [])[:limit]
        if not questions:
            return {
                "query": query,
                "sources": [],
                "message": "No Stack Overflow results were found",
            }

        question_ids = ";".join(str(item["question_id"]) for item in questions)
        answers_payload = self._get_json(
            f"/questions/{question_ids}/answers",
            {
                "order": "desc",
                "sort": "votes",
                "site": "stackoverflow",
                "filter": "withbody",
                "key": self.api_key,
            },
        )
        answers_by_question: dict[int, list[dict[str, Any]]] = {}
        for answer in answers_payload.get("items", []):
            answers_by_question.setdefault(answer["question_id"], []).append(answer)

        sources: list[dict[str, Any]] = []
        for question in questions:
            question_id = question["question_id"]
            answers = answers_by_question.get(question_id, [])
            answer = answers[0] if answers else None
            source_url = question.get(
                "link",
                f"https://stackoverflow.com/questions/{question_id}",
            )
            if not _is_stackoverflow_url(source_url):
                continue
            answer_url = (
                f"{source_url}/{answer['answer_id']}" if answer else None
            )
            excerpt = _answer_excerpt(
                answer,
                unescape(question.get("title", "")),
            )
            sources.append(
                {
                    "title": unescape(
                        question.get("title", "Untitled Stack Overflow question")
                    ),
                    "source_url": source_url,
                    "answer_url": answer_url,
                    "excerpt": excerpt[:MAX_EXCERPT_LENGTH],
                    "score": answer.get("score") if answer else question.get("score"),
                    "accepted": bool(answer and answer.get("is_accepted", False)),
                }
            )

        return {"query": query, "sources": sources}
