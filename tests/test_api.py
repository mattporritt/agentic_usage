"""Tests for the FastAPI /api/* endpoints."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.cache import cache, ProviderCache


def _fresh_cache():
    cache["claude_code"] = ProviderCache(configured=True, error=None, data={
        "configured": True, "error": None,
        "today": {"input_tokens": 5000, "cache_read_tokens": 20000, "output_tokens": 2000, "total_tokens": 27000},
        "history": [{"date": "2026-04-19", "input_tokens": 4000, "cache_read_tokens": 15000, "output_tokens": 1500}],
        "by_model": {"claude-sonnet-4-6": {"input_tokens": 5000, "cache_read_tokens": 20000, "output_tokens": 2000}},
    })
    cache["codex"] = ProviderCache(configured=True, error=None, data={
        "configured": True, "error": None,
        "today": {"input_tokens": 3000, "cached_tokens": 500, "output_tokens": 1000, "total_tokens": 4000},
        "history": [{"date": "2026-04-19", "input_tokens": 2500, "cached_tokens": 200, "output_tokens": 800}],
        "by_model": {"gpt-5.4": {"input_tokens": 3000, "cached_tokens": 500, "output_tokens": 1000}},
    })
    cache["logs"] = ProviderCache(data={
        "today": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        "history": [],
    })


@pytest.fixture
def client():
    with patch("backend.main.refresh_all", new_callable=AsyncMock), \
         patch("backend.main.start_scheduler"):
        from backend.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_stats_structure(client):
    _fresh_cache()
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "last_updated" in body
    assert "claude_code" in body
    assert "codex" in body
    assert "anthropic" not in body
    assert "openai" not in body


def test_stats_configured_provider(client):
    _fresh_cache()
    body = client.get("/api/stats").json()
    assert body["claude_code"]["configured"] is True
    assert body["claude_code"]["error"] is None
    assert body["claude_code"]["today"]["total_tokens"] == 27000
    assert len(body["claude_code"]["history"]) == 1


def test_stats_unconfigured_provider(client):
    _fresh_cache()
    cache["codex"] = ProviderCache(configured=False)
    body = client.get("/api/stats").json()
    assert body["codex"]["configured"] is False
    assert body["codex"]["today"] is None
    assert body["codex"]["history"] == []


def test_stats_provider_error(client):
    _fresh_cache()
    cache["claude_code"].data["error"] = "Directory not found"
    body = client.get("/api/stats").json()
    assert body["claude_code"]["error"] == "Directory not found"
    assert body["claude_code"]["today"]["total_tokens"] == 27000


def test_stats_by_model(client):
    _fresh_cache()
    body = client.get("/api/stats").json()
    assert "claude-sonnet-4-6" in body["claude_code"]["by_model"]
    assert "gpt-5.4" in body["codex"]["by_model"]


def test_stats_fast_response(client):
    """Stats endpoint must respond from cache — not hit external APIs."""
    _fresh_cache()
    import time
    start = time.monotonic()
    client.get("/api/stats")
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"Stats took {elapsed:.2f}s — should be instant from cache"
