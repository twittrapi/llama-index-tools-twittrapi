from __future__ import annotations

from typing import Any, Dict

import pytest
from llama_index.core.tools import FunctionTool
from llama_index.core.tools.calling import acall_tool, call_tool
from llama_index.core.tools.tool_spec.base import BaseToolSpec

from llama_index.tools.twittrapi import TOOL_NAMES, TwittrAPIToolError, TwittrAPIToolSpec
from tests.conftest import CURSOR_PAGE, MockAPI, query

EXPECTED_NAMES = [
    "get_user_by_username",
    "get_user_by_id",
    "get_user_tweets",
    "get_followers",
    "get_following",
    "search_tweets",
    "get_tweet",
    "get_tweet_retweets",
    "get_tweet_quotes",
    "get_list_tweets",
    "get_community_tweets",
    "get_trends",
    "get_trend_locations",
]

# tool name, args, expected path, expected query params, paginated
CASES = [
    ("get_user_by_username", {"username": "@jack"}, "/user/by/username/jack", {}, False),
    ("get_user_by_id", {"user_id": "12"}, "/user/12", {}, False),
    ("get_user_tweets", {"user_id": "12", "count": 5}, "/user/12/tweets", {"count": "5"}, True),
    ("get_user_tweets", {"username": "jack"}, "/user/-1/tweets", {"username": "jack"}, True),
    ("get_followers", {"user_id": "12", "cursor": "C1"}, "/user/12/followers", {"cursor": "C1"}, True),
    ("get_following", {"username": "@jack"}, "/user/-1/followings", {"username": "jack"}, True),
    (
        "search_tweets",
        {"query": "from:jack lang:en", "category": "Latest", "count": 20},
        "/search",
        {"searchItem": "from:jack lang:en", "category": "Latest", "count": "20"},
        True,
    ),
    ("get_tweet", {"tweet_id": "20", "ranking_mode": "Recency"}, "/tweet/20", {"rankingMode": "Recency"}, True),
    ("get_tweet_retweets", {"tweet_id": "20", "count": 3}, "/tweet/20/retweets", {"count": "3"}, True),
    ("get_tweet_quotes", {"tweet_id": "20"}, "/tweet/20/quotes", {}, True),
    ("get_list_tweets", {"list_id": "99", "cursor": "C2"}, "/lists/tweets", {"listId": "99", "cursor": "C2"}, True),
    ("get_community_tweets", {"community_id": "77"}, "/communities/77/tweets", {}, True),
    ("get_trends", {"location_id": "23424977"}, "/trends/23424977", {}, False),
    ("get_trends", {}, "/trends/1", {}, False),
    ("get_trend_locations", {}, "/misc/locations", {}, False),
]


def tools_by_name(spec: TwittrAPIToolSpec) -> Dict[str, FunctionTool]:
    return {t.metadata.name: t for t in spec.to_tool_list()}


def test_class() -> None:
    assert BaseToolSpec.__name__ in [b.__name__ for b in TwittrAPIToolSpec.__mro__]


def test_tool_list() -> None:
    assert TOOL_NAMES == EXPECTED_NAMES
    tools = TwittrAPIToolSpec(api_key="k").to_tool_list()
    assert [t.metadata.name for t in tools] == EXPECTED_NAMES
    for tool in tools:
        assert tool.fn is not None and tool.async_fn is not None
        assert tool.async_fn.__name__ == "a" + tool.metadata.name


def test_spec_functions_resolve() -> None:
    spec = TwittrAPIToolSpec(api_key="k")
    for sync_name, async_name in spec.spec_functions:
        assert callable(getattr(spec, sync_name)) and callable(getattr(spec, async_name))


@pytest.mark.parametrize("name,args,path,params,paginated", CASES)
def test_sync_argument_passing(api: MockAPI, name: str, args: Dict[str, Any], path: str, params: dict, paginated: bool) -> None:
    api.respond(CURSOR_PAGE)
    tool = tools_by_name(TwittrAPIToolSpec(client=api.client()))[name]
    out = tool.call(**args).content
    assert api.last.method == "GET"
    assert api.last.url.path == path
    assert query(api.last) == params
    assert out.startswith("next_cursor: NEXT_CURSOR_123") == paginated


@pytest.mark.parametrize("name,args,path,params,paginated", CASES)
async def test_async_argument_passing(api: MockAPI, name: str, args: Dict[str, Any], path: str, params: dict, paginated: bool) -> None:
    api.respond(CURSOR_PAGE)
    spec = TwittrAPIToolSpec(async_client=api.async_client())
    assert spec.client is None
    out = (await tools_by_name(spec)[name].acall(**args)).content
    assert api.last.url.path == path
    assert query(api.last) == params
    assert ("next_cursor: NEXT_CURSOR_123" in out) == paginated


async def test_async_falls_back_to_sync_client(api: MockAPI) -> None:
    spec = TwittrAPIToolSpec(client=api.client())
    assert await spec.aget_user_by_id("12") == '{"ok":true}'
    assert api.last.url.path == "/user/12"


def test_sync_without_sync_client(api: MockAPI) -> None:
    spec = TwittrAPIToolSpec(async_client=api.async_client())
    with pytest.raises(TwittrAPIToolError, match="No synchronous TwittrAPI client"):
        spec.get_user_by_id("1")


# --- auth -----------------------------------------------------------------------


def test_auth_header_direct(api: MockAPI) -> None:
    TwittrAPIToolSpec(client=api.client(api_key="direct-key")).get_user_by_id("1")
    assert api.last.headers["X-API-KEY"] == "direct-key"


def test_auth_header_rapidapi(api: MockAPI) -> None:
    TwittrAPIToolSpec(client=api.client(api_key=None, rapidapi_key="rapid-key")).get_user_by_id("1")
    assert api.last.headers["x-rapidapi-key"] == "rapid-key"
    assert api.last.url.host == "twitter-aio.p.rapidapi.com"


def test_builds_clients_from_keys() -> None:
    direct = TwittrAPIToolSpec(api_key="k")
    assert direct.client.auth_mode == direct.async_client.auth_mode == "direct"
    rapid = TwittrAPIToolSpec(rapidapi_key="k")
    assert rapid.client.auth_mode == rapid.async_client.auth_mode == "rapidapi"


def test_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "env")
    assert TwittrAPIToolSpec().client.auth_mode == "rapidapi"


def test_missing_key() -> None:
    with pytest.raises(ValueError, match="TWITTRAPI_API_KEY"):
        TwittrAPIToolSpec()


def test_both_keys_rejected() -> None:
    with pytest.raises(ValueError, match="not both"):
        TwittrAPIToolSpec(api_key="a", rapidapi_key="b")


def test_bad_max_chars() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        TwittrAPIToolSpec(api_key="k", max_chars=10)


# --- schemas ----------------------------------------------------------------------

EXPECTED_REQUIRED = {
    "get_user_by_username": ["username"],
    "get_user_by_id": ["user_id"],
    "get_user_tweets": [],
    "get_followers": [],
    "get_following": [],
    "search_tweets": ["query"],
    "get_tweet": ["tweet_id"],
    "get_tweet_retweets": ["tweet_id"],
    "get_tweet_quotes": ["tweet_id"],
    "get_list_tweets": ["list_id"],
    "get_community_tweets": ["community_id"],
    "get_trends": [],
    "get_trend_locations": [],
}


@pytest.mark.parametrize("name,required", list(EXPECTED_REQUIRED.items()))
def test_schema(name: str, required: list) -> None:
    tool = tools_by_name(TwittrAPIToolSpec(api_key="k"))[name]
    params = tool.metadata.get_parameters_dict()
    assert params.get("required", []) == required
    assert len(tool.metadata.description) > 40
    for prop_name, prop in params["properties"].items():
        assert prop.get("description"), f"{name}.{prop_name} has no description"


def test_schema_enums() -> None:
    tools = tools_by_name(TwittrAPIToolSpec(api_key="k"))
    category = tools["search_tweets"].metadata.get_parameters_dict()["properties"]["category"]
    assert category["anyOf"][0]["enum"] == ["Top", "Latest", "People", "Photos", "Videos"]
    mode = tools["get_tweet"].metadata.get_parameters_dict()["properties"]["ranking_mode"]
    assert mode["anyOf"][0]["enum"] == ["Relevance", "Recency", "Likes"]


# --- truncation -------------------------------------------------------------------


def test_truncates_to_max_chars(api: MockAPI) -> None:
    api.respond({"text": "y" * 5000})
    out = TwittrAPIToolSpec(client=api.client(), max_chars=200).get_user_by_id("1")
    assert "[TRUNCATED: showing the first 200 of" in out
    assert len(out) < 450


def test_cursor_survives_truncation(api: MockAPI) -> None:
    api.respond(dict(CURSOR_PAGE, padding="z" * 5000))
    out = TwittrAPIToolSpec(client=api.client(), max_chars=100).get_user_tweets(user_id="1")
    assert out.startswith("next_cursor: NEXT_CURSOR_123")
    assert "[TRUNCATED:" in out


# --- errors -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,body,fragment",
    [
        (401, {"error": "Invalid API key"}, "Invalid API key"),
        (402, {"error": "Insufficient balance"}, "Insufficient balance"),
        (404, {"error": "User not found"}, "User not found"),
        (429, {"error": "Too many requests"}, "429"),
        (500, {"error": "boom"}, "500"),
    ],
)
def test_api_errors_raise_tool_error(api: MockAPI, status: int, body: dict, fragment: str) -> None:
    api.respond(body, status)
    with pytest.raises(TwittrAPIToolError, match="TwittrAPI error:") as info:
        TwittrAPIToolSpec(client=api.client()).get_user_by_id("1")
    assert fragment in str(info.value)


def test_agent_sees_error_as_tool_error(api: MockAPI) -> None:
    api.respond({"error": "Invalid API key"}, 401)
    tool = tools_by_name(TwittrAPIToolSpec(client=api.client()))["get_user_by_id"]
    output = call_tool(tool, {"user_id": "1"})
    assert output.is_error
    assert "TwittrAPI error: Invalid API key" in output.content


async def test_agent_sees_async_error_as_tool_error(api: MockAPI) -> None:
    api.respond({"error": "Not found"}, 404)
    tool = tools_by_name(TwittrAPIToolSpec(async_client=api.async_client()))["get_tweet"]
    output = await acall_tool(tool, {"tweet_id": "1"})
    assert output.is_error
    assert "Not found" in output.content


@pytest.mark.parametrize(
    "method,kwargs,fragment",
    [
        ("get_followers", {}, "Provide either user_id or username."),
        ("get_user_by_id", {"user_id": "abc"}, "numeric ID"),
        ("get_tweet", {"tweet_id": "12x"}, "numeric ID"),
        ("search_tweets", {"query": ""}, "non-empty"),
        ("search_tweets", {"query": "x" * 513}, "512"),
        ("search_tweets", {"query": "a", "category": "Nope"}, "category"),
        ("get_user_tweets", {"user_id": "1", "count": 0}, "count"),
        ("get_tweet_quotes", {"tweet_id": "1", "count": 101}, "count"),
    ],
)
def test_invalid_arguments(api: MockAPI, method: str, kwargs: dict, fragment: str) -> None:
    spec = TwittrAPIToolSpec(client=api.client())
    with pytest.raises(TwittrAPIToolError, match="Invalid arguments") as info:
        getattr(spec, method)(**kwargs)
    assert fragment in str(info.value)
    assert api.requests == []


async def test_invalid_arguments_async(api: MockAPI) -> None:
    spec = TwittrAPIToolSpec(async_client=api.async_client())
    with pytest.raises(TwittrAPIToolError, match="count"):
        await spec.aget_list_tweets("1", count=500)
    assert api.requests == []
