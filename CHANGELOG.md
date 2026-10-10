# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Paginated tools no longer print a `next_cursor` for a page that has only cursor entries and no
  results (X keeps returning one at the end); they say it is the last page instead.
- Usernames: only one leading `@` is stripped, like the SDK.

### Added

- Tests against trimmed real API responses (`tests/fixtures/live/`): followers (Bottom cursor
  before Top), tweet detail, search wrapper, slice `next_cursor`, empty likes and favorites,
  articles with an empty `tweet_results`, usernames-to-ids with the optional `errors` array,
  `count` limits 1..100 and user ID winning over username.

## [0.1.0] - 2026-10-10

### Added

- `TwittrAPIToolSpec` (a `BaseToolSpec`) with 13 read-only tools: `get_user_by_username`, `get_user_by_id`, `get_user_tweets`, `get_followers`, `get_following`, `search_tweets`, `get_tweet`, `get_tweet_retweets`, `get_tweet_quotes`, `get_list_tweets`, `get_community_tweets`, `get_trends`, `get_trend_locations`.
- Sync and async implementation for every tool (async uses `AsyncTwittrAPI`).
- Direct API key and RapidAPI key auth through the `twittrapi` SDK.
- Output cut at `max_chars` (default 20,000) with a `[TRUNCATED: ...]` marker; the next-page cursor is printed first.
- API errors raised as `TwittrAPIToolError`, which agents show to the model as tool errors.

[Unreleased]: https://github.com/twittrapi/llama-index-tools-twittrapi/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/twittrapi/llama-index-tools-twittrapi/releases/tag/v0.1.0
