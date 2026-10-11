"""Turns TwittrAPI responses (simple or raw format) into the text a model sees."""

from __future__ import annotations

import json
from typing import Any

from twittrapi import extract_bottom_cursor
from twittrapi.pagination import is_simple_page, page_is_empty, simple_next_cursor

DEFAULT_MAX_CHARS = 20_000

NO_CURSOR = "next_cursor: none found (this may be the last page)"
EMPTY_PAGE = "next_cursor: none (this page has no results, so it is the last page)"
LAST_PAGE = "next_cursor: none (hasNextPage is false, so this is the last page)"
CURSOR_HINT = "Pass next_cursor as `cursor` to get the next page."


def truncate(text: str, max_chars: int) -> str:
    """Cuts ``text`` to ``max_chars`` and appends a marker that says what was dropped."""
    if len(text) <= max_chars:
        return text
    dropped = len(text) - max_chars
    return (
        text[:max_chars]
        + f"\n\n[TRUNCATED: showing the first {max_chars} of {len(text)} characters "
        f"({dropped} cut). The JSON above is incomplete. Request a smaller count or page "
        "with the cursor to see the rest.]"
    )


def format_result(data: Any, *, max_chars: int = DEFAULT_MAX_CHARS, paginated: bool = False) -> str:
    """Returns the response as compact JSON, cut at ``max_chars``.

    For paginated endpoints the next-page cursor is printed first, outside the truncation
    budget, so the model can always keep paging even when the JSON is cut. Simple-format pages
    carry it as ``nextCursor`` / ``hasNextPage``. For raw pages, detection covers timeline
    cursor entries (Bottom, never Top), the ``/search`` entries wrapper and
    ``slice_info.next_cursor``. Empty timelines (likes, favorites) report no cursor.
    """
    body = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = truncate(body, max_chars)
    if not paginated:
        return text
    if is_simple_page(data):
        simple_cursor = simple_next_cursor(data)
        if not simple_cursor:
            return f"{LAST_PAGE}\n\n{text}"
        return f"next_cursor: {simple_cursor}\n{CURSOR_HINT}\n\n{text}"
    cursor = None if isinstance(data, str) else extract_bottom_cursor(data)
    if cursor and page_is_empty(data):
        # X keeps returning a cursor after the last result; following it only repeats
        # empty pages, so tell the model to stop.
        return f"{EMPTY_PAGE}\n\n{text}"
    header = f"next_cursor: {cursor}" if cursor else NO_CURSOR
    return f"{header}\n{CURSOR_HINT}\n\n{text}"
