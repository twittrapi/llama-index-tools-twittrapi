"""Simple response format (``format=simple``), the default since 0.2.0.

Fixtures in tests/fixtures/simple are the API's simple-format output for real captured
responses, copied from the backend's normalize testdata. No network access.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llama_index.tools.twittrapi import DEFAULT_API_RESPONSE_FORMAT, TwittrAPIToolSpec
from llama_index.tools.twittrapi._output import CURSOR_HINT, LAST_PAGE, format_result
from tests.conftest import MockAPI, query

SIMPLE = Path(__file__).parent / "fixtures" / "simple"


def simple(name: str) -> Any:
    return json.loads((SIMPLE / f"{name}.json").read_text(encoding="utf-8"))


def test_default_is_simple(api: MockAPI) -> None:
    assert DEFAULT_API_RESPONSE_FORMAT == "simple"
    spec = TwittrAPIToolSpec(client=api.client())
    assert spec.api_response_format == "simple"
    spec.get_user_by_username("XDevelopers")
    assert query(api.last) == {"format": "simple"}


def test_raw_opt_out(api: MockAPI) -> None:
    spec = TwittrAPIToolSpec(client=api.client(), api_response_format="raw")
    spec.get_user_tweets(user_id="12", count=5)
    assert query(api.last) == {"count": "5"}
    spec.search_tweets("python")
    assert query(api.last) == {"searchItem": "python"}


def test_spec_setting_wins_over_client_default(api: MockAPI) -> None:
    TwittrAPIToolSpec(client=api.client()).get_tweet_quotes("20")
    assert query(api.last) == {"format": "simple"}
    TwittrAPIToolSpec(client=api.client(response_format="simple"), api_response_format="raw").get_tweet_quotes("20")
    assert query(api.last) == {}


def test_spec_built_from_keys_uses_simple() -> None:
    spec = TwittrAPIToolSpec(api_key="k")
    assert spec.api_response_format == "simple"


@pytest.mark.parametrize("bad", ["json", "", None])
def test_invalid_format_rejected(api: MockAPI, bad: Any) -> None:
    with pytest.raises(ValueError, match="api_response_format"):
        TwittrAPIToolSpec(client=api.client(), api_response_format=bad)


def test_tool_schemas_unchanged(api: MockAPI) -> None:
    # The option is a spec setting, not something the model can pass.
    for tool in TwittrAPIToolSpec(client=api.client()).to_tool_list():
        props = tool.metadata.get_parameters_dict().get("properties", {})
        assert "api_response_format" not in props and "response_format" not in props


async def test_async_sends_simple(api: MockAPI) -> None:
    page = simple("user-userid-followers")
    api.respond(page)
    out = await TwittrAPIToolSpec(async_client=api.async_client()).aget_followers(username="XDevelopers")
    assert query(api.last) == {"username": "XDevelopers", "format": "simple"}
    assert out.startswith(f"next_cursor: {page['nextCursor']}")


def test_simple_page_cursor_first(api: MockAPI) -> None:
    page = simple("user-userid-tweets")
    api.respond(page)
    out = TwittrAPIToolSpec(client=api.client()).get_user_tweets(user_id="2244994945")
    lines = out.splitlines()
    assert lines[0] == f"next_cursor: {page['nextCursor']}"
    assert lines[1] == CURSOR_HINT
    body = json.loads("\n".join(lines[3:]))
    assert body["data"][0]["id"] == "2019881223666233717"
    assert body["hasNextPage"] is True


def test_simple_last_page(api: MockAPI) -> None:
    api.respond(simple("tweet-tweetid-favorites"))
    out = TwittrAPIToolSpec(client=api.client()).search_tweets("nothing here")
    assert out.splitlines()[0] == LAST_PAGE
    assert "Pass next_cursor" not in out


def test_has_next_page_false_wins_over_cursor() -> None:
    page = dict(simple("user-userid-tweets"), hasNextPage=False)
    assert format_result(page, paginated=True).splitlines()[0] == LAST_PAGE


def test_simple_cursor_survives_truncation() -> None:
    page = simple("user-userid-followers")
    out = format_result(page, max_chars=100, paginated=True)
    assert out.startswith(f"next_cursor: {page['nextCursor']}")
    assert "[TRUNCATED:" in out


def test_simple_profile_is_compact_json(api: MockAPI) -> None:
    profile = simple("user-by-username-username")
    api.respond(profile)
    out = TwittrAPIToolSpec(client=api.client()).get_user_by_username("XDevelopers")
    assert not out.startswith("next_cursor")
    assert json.loads(out) == profile
    assert '"username":"XDevelopers"' in out
