from __future__ import annotations

import json
from typing import Any, List

import httpx
import pytest
from twittrapi import AsyncTwittrAPI, TwittrAPI

CURSOR_PAGE = {
    "data": {
        "timeline": {
            "instructions": [
                {
                    "entries": [
                        {"entryId": "tweet-1", "content": {"text": "hello"}},
                        {
                            "entryId": "cursor-bottom-1",
                            "content": {
                                "entryType": "TimelineTimelineCursor",
                                "cursorType": "Bottom",
                                "value": "NEXT_CURSOR_123",
                            },
                        },
                    ]
                }
            ]
        }
    }
}


def json_response(data: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(data).encode())


class MockAPI:
    """Fake TwittrAPI server: records requests and answers with ``reply``."""

    def __init__(self) -> None:
        self.reply: httpx.Response = json_response({"ok": True})
        self.requests: List[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.reply

    def respond(self, data: Any, status: int = 200) -> None:
        self.reply = json_response(data, status)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def client(self, **kwargs: Any) -> TwittrAPI:
        kwargs.setdefault("api_key", "test-key")
        return TwittrAPI(
            http_client=httpx.Client(transport=httpx.MockTransport(self.handler)),
            max_retries=0,
            **kwargs,
        )

    def async_client(self, **kwargs: Any) -> AsyncTwittrAPI:
        kwargs.setdefault("api_key", "test-key")
        return AsyncTwittrAPI(
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(self.handler)),
            max_retries=0,
            **kwargs,
        )


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TWITTRAPI_API_KEY", "RAPIDAPI_KEY", "TWITTRAPI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def api() -> MockAPI:
    return MockAPI()


def query(request: httpx.Request) -> dict:
    return dict(request.url.params)
