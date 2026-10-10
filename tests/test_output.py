from llama_index.tools.twittrapi._output import DEFAULT_MAX_CHARS, format_result, truncate

from tests.conftest import CURSOR_PAGE


def test_default_max_chars() -> None:
    assert DEFAULT_MAX_CHARS == 20_000


def test_truncation_marker() -> None:
    out = truncate("x" * 500, 100)
    assert out.startswith("x" * 100) and "x" * 101 not in out
    assert "[TRUNCATED: showing the first 100 of 500 characters (400 cut)." in out


def test_non_paginated_is_plain_json() -> None:
    assert format_result({"a": 1}) == '{"a":1}'


def test_cursor_first_and_outside_budget() -> None:
    out = format_result(CURSOR_PAGE, max_chars=100, paginated=True)
    assert out.splitlines()[0] == "next_cursor: NEXT_CURSOR_123"
    assert "[TRUNCATED:" in out


def test_missing_cursor_is_explicit() -> None:
    assert format_result({}, paginated=True).startswith("next_cursor: none found")
