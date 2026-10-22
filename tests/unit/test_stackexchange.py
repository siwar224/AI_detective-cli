import io
import json

from ai_detective.external.stackexchange import StackExchangeSearcher
from ai_detective.models.analysis import ErrorFrequency


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def test_stackexchange_search_returns_bounded_sources(monkeypatch) -> None:
    payloads = [
        {
            "items": [
                {
                    "question_id": 42,
                    "title": "MongoDB connection refused",
                    "link": "https://stackoverflow.com/questions/42/example",
                    "score": 10,
                }
            ]
        },
        {
            "items": [
                {
                    "question_id": 42,
                    "answer_id": 99,
                    "score": 8,
                    "is_accepted": True,
                    "body": "<p>Check that <strong>MongoDB</strong> is running.</p>",
                }
            ]
        },
    ]

    def fake_urlopen(request, timeout):
        return FakeResponse(json.dumps(payloads.pop(0)).encode())

    monkeypatch.setattr(
        "ai_detective.external.stackexchange.urlopen",
        fake_urlopen,
    )
    error = ErrorFrequency(
        message="mongodb connection refused",
        count=2,
        line_numbers=[1, 2],
        category="mongodb",
    )

    result = StackExchangeSearcher().search(error, limit=1)

    assert result["sources"][0]["answer_url"].endswith("/42/example/99")
    assert result["sources"][0]["accepted"] is True
    assert result["sources"][0]["excerpt"] == "Check that MongoDB is running."
    assert len(payloads) == 0


def test_stackexchange_search_removes_secrets_from_query(monkeypatch) -> None:
    captured_urls = []

    def fake_urlopen(request, timeout):
        captured_urls.append(request.full_url)
        return FakeResponse(json.dumps({"items": []}).encode())

    monkeypatch.setattr(
        "ai_detective.external.stackexchange.urlopen",
        fake_urlopen,
    )
    error = ErrorFrequency(
        message="mongodb password=super-secret mongodb://user:pass@host refused",
        count=1,
        line_numbers=[1],
        category="mongodb",
    )

    StackExchangeSearcher().search(error, limit=1)

    assert "super-secret" not in captured_urls[0]
    assert "user%3Apass" not in captured_urls[0]
