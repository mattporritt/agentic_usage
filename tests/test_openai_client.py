"""Tests for the OpenAI usage API client."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest
import respx

from backend.providers.openai_client import fetch_openai_usage


def _ts(days_ago: int = 0) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days_ago)).timestamp())


def _bucket(days_ago: int, input_tokens: int, output_tokens: int, cached: int = 0) -> dict:
    start = _ts(days_ago)
    return {
        "start_time": start,
        "end_time": start + 86400,
        "results": [
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_cached_tokens": cached,
                "num_model_requests": 10,
            }
        ],
    }


@respx.mock
async def test_fetch_returns_today_and_history():
    respx.get("https://api.openai.com/v1/organization/usage/completions").mock(
        return_value=httpx.Response(200, json={
            "data": [
                _bucket(0, input_tokens=2000, output_tokens=800),
                _bucket(1, input_tokens=1500, output_tokens=600),
            ],
            "has_more": False,
            "next_page": None,
        })
    )
    with patch("backend.providers.openai_client.settings") as s:
        s.openai_admin_key = "sk-test"
        result = await fetch_openai_usage()

    assert result["today"]["input_tokens"] == 2000
    assert result["today"]["output_tokens"] == 800
    assert result["today"]["total_tokens"] == 2800
    assert len(result["history"]) == 1
    assert result["history"][0]["input_tokens"] == 1500


@respx.mock
async def test_input_tokens_not_double_counted():
    """input_tokens already includes cached tokens — must not add cache_read separately."""
    respx.get("https://api.openai.com/v1/organization/usage/completions").mock(
        return_value=httpx.Response(200, json={
            "data": [_bucket(0, input_tokens=1000, output_tokens=400, cached=300)],
            "has_more": False,
            "next_page": None,
        })
    )
    with patch("backend.providers.openai_client.settings") as s:
        s.openai_admin_key = "sk-test"
        result = await fetch_openai_usage()

    assert result["today"]["input_tokens"] == 1000  # not 1300


@respx.mock
async def test_today_missing_defaults_to_zero():
    respx.get("https://api.openai.com/v1/organization/usage/completions").mock(
        return_value=httpx.Response(200, json={
            "data": [_bucket(2, 500, 200)],
            "has_more": False,
            "next_page": None,
        })
    )
    with patch("backend.providers.openai_client.settings") as s:
        s.openai_admin_key = "sk-test"
        result = await fetch_openai_usage()

    assert result["today"]["total_tokens"] == 0
    assert len(result["history"]) == 1


@respx.mock
async def test_pagination_followed():
    calls = 0

    def side_effect(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={
                "data": [_bucket(0, 1000, 400)],
                "has_more": True,
                "next_page": "cursor-xyz",
            })
        return httpx.Response(200, json={
            "data": [_bucket(1, 800, 300)],
            "has_more": False,
            "next_page": None,
        })

    respx.get("https://api.openai.com/v1/organization/usage/completions").mock(side_effect=side_effect)

    with patch("backend.providers.openai_client.settings") as s:
        s.openai_admin_key = "sk-test"
        result = await fetch_openai_usage()

    assert calls == 2
    assert result["today"]["input_tokens"] == 1000
    assert len(result["history"]) == 1


@respx.mock
async def test_401_raises_value_error():
    respx.get("https://api.openai.com/v1/organization/usage/completions").mock(
        return_value=httpx.Response(401)
    )
    with patch("backend.providers.openai_client.settings") as s:
        s.openai_admin_key = "bad-key"
        with pytest.raises(ValueError, match="401"):
            await fetch_openai_usage()


@respx.mock
async def test_403_raises_descriptive_error():
    respx.get("https://api.openai.com/v1/organization/usage/completions").mock(
        return_value=httpx.Response(403)
    )
    with patch("backend.providers.openai_client.settings") as s:
        s.openai_admin_key = "sk-test"
        with pytest.raises(ValueError, match="admin key required"):
            await fetch_openai_usage()


@respx.mock
async def test_history_sorted():
    respx.get("https://api.openai.com/v1/organization/usage/completions").mock(
        return_value=httpx.Response(200, json={
            "data": [
                _bucket(5, 100, 40),
                _bucket(1, 200, 80),
                _bucket(3, 150, 60),
            ],
            "has_more": False,
            "next_page": None,
        })
    )
    with patch("backend.providers.openai_client.settings") as s:
        s.openai_admin_key = "sk-test"
        result = await fetch_openai_usage()

    dates = [r["date"] for r in result["history"]]
    assert dates == sorted(dates)
