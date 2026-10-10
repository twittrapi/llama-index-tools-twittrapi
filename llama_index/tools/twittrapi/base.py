"""TwittrAPI tool spec: read X (Twitter) data from LlamaIndex agents.

Every tool is read-only and calls the official ``twittrapi`` SDK. Results are X's raw JSON,
cut to ``max_chars`` characters. Paginated tools print ``next_cursor`` first so the agent can
ask for the next page.
"""

# No ``from __future__ import annotations`` here: LlamaIndex builds the tool schemas from the
# method signatures at runtime.

import asyncio
from typing import Annotated, Any, Awaitable, Callable, List, Literal, Optional

from llama_index.core.tools.tool_spec.base import BaseToolSpec
from twittrapi import AsyncTwittrAPI, TwittrAPI, TwittrAPIError

from llama_index.tools.twittrapi._output import DEFAULT_MAX_CHARS, format_result

__all__ = ["TwittrAPIToolSpec", "TwittrAPIToolError", "TOOL_NAMES"]

SearchCategory = Literal["Top", "Latest", "People", "Photos", "Videos"]
RankingMode = Literal["Relevance", "Recency", "Likes"]

# Argument types. The string in each Annotated[...] is the parameter description the model sees.
Username = Annotated[str, 'X handle without the URL, e.g. "elonmusk" (a leading @ is fine).']
UserId = Annotated[str, "Numeric X user ID (rest_id), digits only."]
OptUserId = Annotated[
    Optional[str], "Numeric X user ID (rest_id). Provide this or username. Using the ID is faster."
]
OptUsername = Annotated[
    Optional[str], "X handle, used when you do not have the user ID. Provide this or user_id."
]
Count = Annotated[Optional[int], "How many items to request per page, 1 to 100 (default 20)."]
Cursor = Annotated[
    Optional[str],
    "Pagination cursor. Leave empty for the first page; pass next_cursor from a previous result to get the next page.",
]
Query = Annotated[str, "Search query, max 512 characters. May contain X search operators."]
Category = Annotated[
    Optional[SearchCategory], "Result tab: Top (default), Latest, People, Photos or Videos."
]
TweetId = Annotated[str, "Numeric tweet ID, the number at the end of a tweet URL."]
Ranking = Annotated[
    Optional[RankingMode], "Sort order of the replies: Relevance (default), Recency or Likes."
]
ListId = Annotated[str, "Numeric list ID, from the list URL."]
CommunityId = Annotated[str, "Numeric community ID."]
LocationId = Annotated[str, 'Yahoo WOEID of the location, e.g. "1" for worldwide, "23424977" for the United States.']

TOOL_NAMES: List[str] = [
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


class TwittrAPIToolError(Exception):
    """Raised when a TwittrAPI call fails. Agents show the message to the model as a tool error."""


def _check_count(count: Optional[int]) -> None:
    if count is not None and (isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 100):
        raise ValueError(f"count must be an integer from 1 to 100, got {count!r}")


def _user_target(user_id: Optional[str], username: Optional[str]) -> dict:
    if user_id:
        return {"user_id": str(user_id)}
    if isinstance(username, str):
        handle = username.strip()
        handle = handle[1:].strip() if handle.startswith("@") else handle
        if handle:
            return {"username": handle}
    raise ValueError("Provide either user_id or username.")


class TwittrAPIToolSpec(BaseToolSpec):
    """Read-only X (Twitter) tools backed by TwittrAPI (https://twittrapi.com).

    Auth: pass ``api_key`` (direct API) or ``rapidapi_key`` (RapidAPI). With neither, the SDK
    reads ``TWITTRAPI_API_KEY`` and then ``RAPIDAPI_KEY`` from the environment. You can also
    pass ready-made ``client`` / ``async_client`` instances from the ``twittrapi`` SDK.

    Each tool has a sync and an async implementation; agents that run tools asynchronously
    use ``AsyncTwittrAPI``.
    """

    spec_functions = [(name, f"a{name}") for name in TOOL_NAMES]

    def __init__(
        self,
        api_key: Optional[str] = None,
        rapidapi_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        client: Optional[TwittrAPI] = None,
        async_client: Optional[AsyncTwittrAPI] = None,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 100:
            raise ValueError("max_chars must be an integer >= 100")
        if client is None and async_client is None:
            kwargs = {"api_key": api_key, "rapidapi_key": rapidapi_key, "base_url": base_url}
            try:
                client = TwittrAPI(**kwargs)
                async_client = AsyncTwittrAPI(**kwargs)
            except TwittrAPIError as exc:
                raise ValueError(str(exc)) from exc
        self.client = client
        self.async_client = async_client
        self.max_chars = max_chars

    # -- plumbing ------------------------------------------------------------

    def _run(self, call: Callable[[Any], Any], paginated: bool) -> str:
        if self.client is None:
            raise TwittrAPIToolError(
                "No synchronous TwittrAPI client is configured; call this tool asynchronously."
            )
        try:
            data = call(self.client)
        except TwittrAPIError as exc:
            raise TwittrAPIToolError(f"TwittrAPI error: {exc}") from exc
        except (ValueError, TypeError) as exc:
            raise TwittrAPIToolError(f"Invalid arguments: {exc}") from exc
        return format_result(data, max_chars=self.max_chars, paginated=paginated)

    async def _arun(self, call: Callable[[Any], Awaitable[Any]], paginated: bool) -> str:
        if self.async_client is None:
            # Only a sync client was supplied: run it in a worker thread.
            return await asyncio.to_thread(self._run, call, paginated)
        try:
            data = await call(self.async_client)
        except TwittrAPIError as exc:
            raise TwittrAPIToolError(f"TwittrAPI error: {exc}") from exc
        except (ValueError, TypeError) as exc:
            raise TwittrAPIToolError(f"Invalid arguments: {exc}") from exc
        return format_result(data, max_chars=self.max_chars, paginated=paginated)

    # -- users -----------------------------------------------------------------

    def get_user_by_username(self, username: Username) -> str:
        """
        Get an X (Twitter) user's profile by handle: name, bio, follower/following counts, verification, created date, and the numeric user ID (rest_id) needed by other tools.
        """
        return self._run(lambda api: api.users.get_by_username(username), False)

    async def aget_user_by_username(self, username: Username) -> str:
        """Async version of get_user_by_username."""
        return await self._arun(lambda api: api.users.get_by_username(username), False)

    def get_user_by_id(self, user_id: UserId) -> str:
        """
        Get an X user's profile by numeric user ID (rest_id). Same data as get_user_by_username.
        """
        return self._run(lambda api: api.users.get_by_id(user_id), False)

    async def aget_user_by_id(self, user_id: UserId) -> str:
        """Async version of get_user_by_id."""
        return await self._arun(lambda api: api.users.get_by_id(user_id), False)

    def get_user_tweets(
        self,
        user_id: OptUserId = None,
        username: OptUsername = None,
        count: Count = None,
        cursor: Cursor = None,
    ) -> str:
        """
        Get a user's recent tweets (their profile timeline, without replies), newest first, including retweets and the pinned tweet. Paginated.
        """
        return self._run(lambda api: self._user_call(api.users.tweets, user_id, username, count, cursor), True)

    async def aget_user_tweets(
        self,
        user_id: OptUserId = None,
        username: OptUsername = None,
        count: Count = None,
        cursor: Cursor = None,
    ) -> str:
        """Async version of get_user_tweets."""
        return await self._arun(
            lambda api: self._user_call(api.users.tweets, user_id, username, count, cursor), True
        )

    def get_followers(
        self,
        user_id: OptUserId = None,
        username: OptUsername = None,
        count: Count = None,
        cursor: Cursor = None,
    ) -> str:
        """
        Get accounts that follow a user, newest followers first. Paginated.
        """
        return self._run(
            lambda api: self._user_call(api.users.followers, user_id, username, count, cursor), True
        )

    async def aget_followers(
        self,
        user_id: OptUserId = None,
        username: OptUsername = None,
        count: Count = None,
        cursor: Cursor = None,
    ) -> str:
        """Async version of get_followers."""
        return await self._arun(
            lambda api: self._user_call(api.users.followers, user_id, username, count, cursor), True
        )

    def get_following(
        self,
        user_id: OptUserId = None,
        username: OptUsername = None,
        count: Count = None,
        cursor: Cursor = None,
    ) -> str:
        """
        Get accounts a user follows. Paginated.
        """
        return self._run(
            lambda api: self._user_call(api.users.following, user_id, username, count, cursor), True
        )

    async def aget_following(
        self,
        user_id: OptUserId = None,
        username: OptUsername = None,
        count: Count = None,
        cursor: Cursor = None,
    ) -> str:
        """Async version of get_following."""
        return await self._arun(
            lambda api: self._user_call(api.users.following, user_id, username, count, cursor), True
        )

    @staticmethod
    def _user_call(
        method: Callable[..., Any],
        user_id: Optional[str],
        username: Optional[str],
        count: Optional[int],
        cursor: Optional[str],
    ) -> Any:
        _check_count(count)
        return method(**_user_target(user_id, username), count=count, cursor=cursor or None)

    # -- search and tweets -------------------------------------------------------

    def search_tweets(
        self,
        query: Query,
        category: Category = None,
        count: Count = None,
        cursor: Cursor = None,
    ) -> str:
        """
        Search X like the search box. Supports X search operators in the query, e.g. from:user, to:user, "exact phrase", lang:en, since:2025-01-01, until:2025-02-01, min_faves:100, filter:media, -filter:replies. category Latest gives newest first; People returns accounts instead of tweets. Paginated.
        """
        return self._run(lambda api: self._search(api, query, category, count, cursor), True)

    async def asearch_tweets(
        self,
        query: Query,
        category: Category = None,
        count: Count = None,
        cursor: Cursor = None,
    ) -> str:
        """Async version of search_tweets."""
        return await self._arun(lambda api: self._search(api, query, category, count, cursor), True)

    @staticmethod
    def _search(api: Any, query: str, category: Optional[str], count: Optional[int], cursor: Optional[str]) -> Any:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if len(query) > 512:
            raise ValueError("query must be at most 512 characters")
        _check_count(count)
        return api.search.tweets(query, category=category or None, count=count, cursor=cursor or None)

    def get_tweet(
        self,
        tweet_id: TweetId,
        ranking_mode: Ranking = None,
        cursor: Cursor = None,
    ) -> str:
        """
        Get a tweet by ID with full text, author, media, engagement counts and the reply thread (conversation). Use cursor to load more replies.
        """
        return self._run(
            lambda api: api.tweets.get(tweet_id, ranking_mode=ranking_mode or None, cursor=cursor or None), True
        )

    async def aget_tweet(
        self,
        tweet_id: TweetId,
        ranking_mode: Ranking = None,
        cursor: Cursor = None,
    ) -> str:
        """Async version of get_tweet."""
        return await self._arun(
            lambda api: api.tweets.get(tweet_id, ranking_mode=ranking_mode or None, cursor=cursor or None), True
        )

    def get_tweet_retweets(self, tweet_id: TweetId, count: Count = None, cursor: Cursor = None) -> str:
        """
        Get the users who retweeted a tweet. Paginated.
        """
        return self._run(lambda api: self._paged(api.tweets.retweeters, tweet_id, count, cursor), True)

    async def aget_tweet_retweets(
        self, tweet_id: TweetId, count: Count = None, cursor: Cursor = None
    ) -> str:
        """Async version of get_tweet_retweets."""
        return await self._arun(lambda api: self._paged(api.tweets.retweeters, tweet_id, count, cursor), True)

    def get_tweet_quotes(self, tweet_id: TweetId, count: Count = None, cursor: Cursor = None) -> str:
        """
        Get tweets that quote a given tweet. Paginated.
        """
        return self._run(lambda api: self._paged(api.tweets.quotes, tweet_id, count, cursor), True)

    async def aget_tweet_quotes(
        self, tweet_id: TweetId, count: Count = None, cursor: Cursor = None
    ) -> str:
        """Async version of get_tweet_quotes."""
        return await self._arun(lambda api: self._paged(api.tweets.quotes, tweet_id, count, cursor), True)

    @staticmethod
    def _paged(method: Callable[..., Any], item_id: str, count: Optional[int], cursor: Optional[str]) -> Any:
        _check_count(count)
        return method(item_id, count=count, cursor=cursor or None)

    # -- lists, communities, trends ------------------------------------------------

    def get_list_tweets(self, list_id: ListId, count: Count = None, cursor: Cursor = None) -> str:
        """
        Get the tweet timeline of an X list (tweets from its members), newest first. Paginated.
        """
        return self._run(lambda api: self._paged(api.lists.tweets, list_id, count, cursor), True)

    async def aget_list_tweets(
        self, list_id: ListId, count: Count = None, cursor: Cursor = None
    ) -> str:
        """Async version of get_list_tweets."""
        return await self._arun(lambda api: self._paged(api.lists.tweets, list_id, count, cursor), True)

    def get_community_tweets(
        self, community_id: CommunityId, count: Count = None, cursor: Cursor = None
    ) -> str:
        """
        Get tweets posted in an X Community. Paginated.
        """
        return self._run(lambda api: self._paged(api.communities.tweets, community_id, count, cursor), True)

    async def aget_community_tweets(
        self, community_id: CommunityId, count: Count = None, cursor: Cursor = None
    ) -> str:
        """Async version of get_community_tweets."""
        return await self._arun(lambda api: self._paged(api.communities.tweets, community_id, count, cursor), True)

    def get_trends(self, location_id: LocationId = "1") -> str:
        """
        Get trending topics for a location by WOEID (1 = worldwide, 23424977 = United States, 23424975 = United Kingdom). Use get_trend_locations to look up other WOEIDs.
        """
        return self._run(lambda api: api.trends.get(location_id or "1"), False)

    async def aget_trends(self, location_id: LocationId = "1") -> str:
        """Async version of get_trends."""
        return await self._arun(lambda api: api.trends.get(location_id or "1"), False)

    def get_trend_locations(self) -> str:
        """List the locations (countries and cities) that have trends, with their WOEIDs for get_trends."""
        return self._run(lambda api: api.trends.locations(), False)

    async def aget_trend_locations(self) -> str:
        """Async version of get_trend_locations."""
        return await self._arun(lambda api: api.trends.locations(), False)
