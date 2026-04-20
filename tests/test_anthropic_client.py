"""Tests for the Anthropic usage API client."""
import json
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest
import respx

from backend.providers.anthropic_client import fetch_anthropic_usage


def _bucket(date_str: str, uncached_input: int, cache_read: int, output: int) -> dict:
    return {
        "starting_at": f"{date_str}T00:00:00Z",
        "ending_at": f"{date_str}T23:59:59Z",
        "results": [
            {
                "uncached_input_tokens": uncached_input,
                "cache_read_input_tokens": cache_read,
                "output_tokens": output,
            }
        ],
    }


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _past_str(days_ago: int = 1) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


@respx.mock
async def test_fetch_returns_today_and_history():
    today = _today_str()
    yesterday = _past_str(1)

    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(200, json={
            "data": [
                _bucket(today, uncached_input=1000, cache_read=200, output=500),
                _bucket(yesterday, uncached_input=800, cache_read=100, output=300),
            ],
            "has_more": False,
            "next_page": None,
        })
    )

    with patch("backend.providers.anthropic_client.settings") as mock_settings:
        mock_settings.anthropic_admin_key = "sk-ant-admin-test"
        result = await fetch_anthropic_usage()

    # Today: uncached + cache_read = 1200 input, 500 output
    assert result["today"]["input_tokens"] == 1200
    assert result["today"]["output_tokens"] == 500
    assert result["today"]["total_tokens"] == 1700

    # History has yesterday only
    assert len(result["history"]) == 1
    assert result["history"][0]["input_tokens"] == 900  # 800 + 100
    assert result["history"][0]["output_tokens"] == 300


@respx.mock
async def test_today_missing_defaults_to_zero():
    yesterday = _past_str(1)
    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(200, json={
            "data": [_bucket(yesterday, 500, 0, 200)],
            "has_more": False,
            "next_page": None,
        })
    )
    with patch("backend.providers.anthropic_client.settings") as s:
        s.anthropic_admin_key = "sk-ant-admin-test"
        result = await fetch_anthropic_usage()

    assert result["today"]["total_tokens"] == 0
    assert len(result["history"]) == 1


@respx.mock
async def test_pagination_followed():
    today = _today_str()

    calls = 0

    def side_effect(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={
                "data": [_bucket(today, 500, 0, 200)],
                "has_more": True,
                "next_page": "cursor-abc",
            })
        return httpx.Response(200, json={
            "data": [_bucket(_past_str(1), 300, 50, 100)],
            "has_more": False,
            "next_page": None,
        })

    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(side_effect=side_effect)

    with patch("backend.providers.anthropic_client.settings") as s:
        s.anthropic_admin_key = "sk-ant-admin-test"
        result = await fetch_anthropic_usage()

    assert calls == 2
    assert result["today"]["input_tokens"] == 500
    assert len(result["history"]) == 1


@respx.mock
async def test_401_raises_value_error():
    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    with patch("backend.providers.anthropic_client.settings") as s:
        s.anthropic_admin_key = "bad-key"
        with pytest.raises(ValueError, match="401"):
            await fetch_anthropic_usage()


@respx.mock
async def test_403_raises_descriptive_error():
    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    with patch("backend.providers.anthropic_client.settings") as s:
        s.anthropic_admin_key = "sk-ant-admin-test"
        with pytest.raises(ValueError, match="admin key required"):
            await fetch_anthropic_usage()


@respx.mock
async def test_history_sorted():
    d1 = _past_str(3)
    d2 = _past_str(1)
    d3 = _past_str(5)

    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(200, json={
            "data": [
                _bucket(d1, 100, 0, 50),
                _bucket(d2, 200, 0, 80),
                _bucket(d3, 150, 0, 60),
            ],
            "has_more": False,
            "next_page": None,
        })
    )
    with patch("backend.providers.anthropic_client.settings") as s:
        s.anthropic_admin_key = "sk-ant-admin-test"
        result = await fetch_anthropic_usage()

    dates = [r["date"] for r in result["history"]]
    assert dates == sorted(dates)


@respx.mock
async def test_empty_results_bucket_skipped():
    today = _today_str()
    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(200, json={
            "data": [{"starting_at": f"{today}T00:00:00Z", "ending_at": f"{today}T23:59:59Z", "results": []}],
            "has_more": False,
            "next_page": None,
        })
    )
    with patch("backend.providers.anthropic_client.settings") as s:
        s.anthropic_admin_key = "sk-ant-admin-test"
        result = await fetch_anthropic_usage()

    assert result["today"]["total_tokens"] == 0
