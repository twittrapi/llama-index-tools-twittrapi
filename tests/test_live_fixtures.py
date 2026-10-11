"""Tool output for trimmed real TwittrAPI responses (tests/fixtures/live, captured 2026-10-10).

Each fixture is ``{"request": ..., "capturedAt": ..., "response": <API body>}``; only
``response`` is served. No network access. These are raw-format responses, so the spec is
created with ``api_response_format="raw"``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from llama_index.tools.twittrapi import TwittrAPIToolError, TwittrAPIToolSpec
from llama_index.tools.twittrapi._output import EMPTY_PAGE, NO_CURSOR, format_result
from tests.conftest import MockAPI, query

LIVE = Path(__file__).parent / "fixtures" / "live"


def live(name: str) -> Any:
    return json.loads((LIVE / f"{name}.json").read_text(encoding="utf-8"))["response"]


def first_line(text: str) -> str:
    return text.splitlines()[0]


def timeline_entries(data: Any) -> list:
    instructions = data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
    return [e for i in instructions for e in i.get("entries", [])]


def test_followers_bottom_before_top(api: MockAPI) -> None:
    data = live("user-userid-followers")
    cursors = [e for e in timeline_entries(data) if e["entryId"].startswith("cursor-")]
    assert [c["content"]["cursorType"] for c in cursors] == ["Bottom", "Top"]
    api.respond(data)
    out = TwittrAPIToolSpec(client=api.client(), api_response_format="raw").get_followers(user_id="2244994945", count=20)
    assert first_line(out) == f"next_cursor: {cursors[0]['content']['value']}"
    assert query(api.last) == {"count": "20"}


def test_user_tweets_bottom_cursor(api: MockAPI) -> None:
    data = live("user-userid-tweets")
    bottom = [e for e in timeline_entries(data) if e["entryId"].startswith("cursor-bottom-")][0]
    api.respond(data)
    out = TwittrAPIToolSpec(client=api.client(), api_response_format="raw").get_user_tweets(user_id="2244994945")
    assert first_line(out) == f"next_cursor: {bottom['content']['value']}"


def test_tweet_detail_cursor(api: MockAPI) -> None:
    data = live("tweet-tweetid")
    last = data["data"]["threaded_conversation_with_injections_v2"]["instructions"][1]["entries"][-1]
    value = last["content"].get("value") or last["content"]["itemContent"]["value"]
    api.respond(data)
    out = TwittrAPIToolSpec(client=api.client(), api_response_format="raw").get_tweet("2019881223666233717")
    assert first_line(out) == f"next_cursor: {value}"


def test_search_wrapper(api: MockAPI) -> None:
    data = live("search")
    bottom = [e for e in data["entries"][0]["entries"] if e["entryId"].startswith("cursor-bottom-")][0]
    api.respond(data)
    out = TwittrAPIToolSpec(client=api.client(), api_response_format="raw").search_tweets("openai", category="Latest")
    assert first_line(out) == f"next_cursor: {bottom['content']['value']}"


def test_search_page_with_only_cursors_is_last(api: MockAPI) -> None:
    data = copy.deepcopy(live("search"))
    data["entries"][0]["entries"] = [
        e for e in data["entries"][0]["entries"] if e["entryId"].startswith("cursor-")
    ]
    assert first_line(format_result(data, paginated=True)) == EMPTY_PAGE


@pytest.mark.parametrize(
    "name, path",
    [
        ("communities-search-searchterm", ("data", "communities_search_slice")),
        ("communities-communityid-members", ("data", "communityResults", "result", "members_slice")),
        ("jobs-search-searchterm", ("data", "job_search")),
    ],
)
def test_slice_next_cursor(name: str, path: tuple) -> None:
    data = live(name)
    node = data
    for key in path:
        node = node[key]
    out = format_result(data, paginated=True)
    assert first_line(out) == f"next_cursor: {node['slice_info']['next_cursor']}"


@pytest.mark.parametrize("name", ["user-userid-likes", "tweet-tweetid-favorites"])
def test_empty_timelines_stop(name: str) -> None:
    out = format_result(live(name), paginated=True)
    assert first_line(out) == NO_CURSOR


def test_article_with_empty_tweet_results(api: MockAPI) -> None:
    data = copy.deepcopy(live("user-userid-articles"))
    entries = data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"][0]["entries"]
    deleted = copy.deepcopy(entries[0])
    deleted["entryId"] = "tweet-1"
    deleted["content"]["itemContent"]["tweet_results"] = {}
    entries.insert(0, deleted)
    out = format_result(data, paginated=True)
    assert first_line(out) == "next_cursor: DAABCgABHUS5rv1___sKAAIAAAAAAAAAAAgAAwAAAAIAAA"
    assert '"tweet_results":{}' in out


def test_usernames_to_ids_with_errors_array() -> None:
    data = live("user-usernames-to-ids")
    assert data == {"userIds": {"XDevelopers": "2244994945", "jack": "12"}}
    with_errors = {
        "userIds": {"XDevelopers": "2244994945"},
        "errors": [{"username": "gone", "error": "not_found", "message": "User not found"}],
    }
    out = format_result(with_errors)
    assert json.loads(out) == with_errors


def test_user_id_wins_and_one_at_stripped(api: MockAPI) -> None:
    api.respond(live("user-userid-followers"))
    spec = TwittrAPIToolSpec(client=api.client(), api_response_format="raw")
    spec.get_followers(user_id="2244994945", username="XDevelopers")
    assert api.last.url.path == "/user/2244994945/followers"
    assert "username" not in query(api.last)
    spec.get_followers(username=" @XDevelopers")
    assert api.last.url.path == "/user/-1/followers"
    assert query(api.last) == {"username": "XDevelopers"}


@pytest.mark.parametrize("count, ok", [(1, True), (100, True), (0, False), (101, False)])
def test_count_limits(api: MockAPI, count: int, ok: bool) -> None:
    api.respond(live("user-userid-followers"))
    spec = TwittrAPIToolSpec(client=api.client(), api_response_format="raw")
    if ok:
        spec.get_followers(user_id="12", count=count)
        assert query(api.last)["count"] == str(count)
    else:
        with pytest.raises(TwittrAPIToolError, match="1 to 100"):
            spec.get_followers(user_id="12", count=count)
        assert not api.requests


def test_user_profile_not_paginated(api: MockAPI) -> None:
    api.respond({"data": {"user": {"result": {"rest_id": "12"}}}})
    out = TwittrAPIToolSpec(client=api.client(), api_response_format="raw").get_user_by_id("12")
    assert not out.startswith("next_cursor")
