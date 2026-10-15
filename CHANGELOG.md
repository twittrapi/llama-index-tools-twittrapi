# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-15

First stable release: the API is stable and follows semantic versioning.

### Added

- `rapidapi_host` on `TwittrAPIToolSpec`, for customers subscribed to another TwittrAPI
  listing on RapidAPI (e.g. `rapidapi_host="twttr.p.rapidapi.com"`). Passed to the SDK only
  when set; otherwise the SDK reads `RAPIDAPI_HOST` and falls back to
  `twitter-aio.p.rapidapi.com`.

### Changed

- Requires `twittrapi>=1.0.0,<2` (the stable SDK release, which adds `rapidapi_host`).

## [0.2.0] - 2026-10-11

Pre-1.0, so the breaking change below bumps the minor version (0.1.x to 0.2.0).

### Breaking

- Tools now return the API's simple format (`format=simple`,
  https://twittrapi.com/docs/simple-format) by default instead of X's raw JSON: flat,
  camelCase tweets and users with `nextCursor` / `hasNextPage`, far fewer tokens per call.
  Every tool request now carries `format=simple`. To keep the old output, pass
  `api_response_format="raw"` to `TwittrAPIToolSpec`.
- Requires `twittrapi>=0.2.0,<0.3` (the SDK release that adds `response_format`).

### Added

- `api_response_format` (`"simple"` or `"raw"`) on `TwittrAPIToolSpec`. It is sent on every
  call and wins over the default of a `client` you pass in. Same name as in
  `langchain-twittrapi`.
- Paginated tools read `nextCursor` / `hasNextPage` from simple-format pages and say when a
  page is the last one; raw pages keep the existing cursor detection.
- Tests with the API's simple-format output (`tests/fixtures/simple/`).
- Tests against trimmed real API responses (`tests/fixtures/live/`): followers (Bottom cursor
  before Top), tweet detail, search wrapper, slice `next_cursor`, empty likes and favorites,
  articles with an empty `tweet_results`, usernames-to-ids with the optional `errors` array,
  `count` limits 1..100 and user ID winning over username.

### Fixed

- Paginated tools no longer print a `next_cursor` for a page that has only cursor entries and no
  results (X keeps returning one at the end); they say it is the last page instead.
- Usernames: only one leading `@` is stripped, like the SDK.

## [0.1.0] - 2026-10-10

### Added

- `TwittrAPIToolSpec` (a `BaseToolSpec`) with 13 read-only tools: `get_user_by_username`, `get_user_by_id`, `get_user_tweets`, `get_followers`, `get_following`, `search_tweets`, `get_tweet`, `get_tweet_retweets`, `get_tweet_quotes`, `get_list_tweets`, `get_community_tweets`, `get_trends`, `get_trend_locations`.
- Sync and async implementation for every tool (async uses `AsyncTwittrAPI`).
- Direct API key and RapidAPI key auth through the `twittrapi` SDK.
- Output cut at `max_chars` (default 20,000) with a `[TRUNCATED: ...]` marker; the next-page cursor is printed first.
- API errors raised as `TwittrAPIToolError`, which agents show to the model as tool errors.

[1.0.0]: https://github.com/twittrapi/llama-index-tools-twittrapi/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/twittrapi/llama-index-tools-twittrapi/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/twittrapi/llama-index-tools-twittrapi/releases/tag/v0.1.0
