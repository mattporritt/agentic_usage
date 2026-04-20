"""Tests for the FastAPI /api/* endpoints."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.cache import cache, ProviderCache


def _fresh_cache():
    cache["anthropic"] = ProviderCache(configured=True, error=None, data={
        "today": {"input_tokens": 5000, "output_tokens": 2000, "total_tokens": 7000},
        "history": [{"date": "2026-04-19", "input_tokens": 4000, "output_tokens": 1500}],
    })
    cache["openai"] = ProviderCache(configured=True, error=None, data={
        "today": {"input_tokens": 3000, "output_tokens": 1000, "total_tokens": 4000},
        "history": [{"date": "2026-04-19", "input_tokens": 2500, "output_tokens": 800}],
    })
    cache["logs"] = ProviderCache(data={
        "anthropic": {"today": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}, "history": []},
        "openai": {"today": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, "history": []},
    })


@pytest.fixture
def client():
    # Patch out the lifespan so tests don't trigger real API calls
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
    assert "anthropic" in body
    assert "openai" in body
    assert "logs" in body


def test_stats_configured_provider(client):
    _fresh_cache()
    body = client.get("/api/stats").json()
    assert body["anthropic"]["configured"] is True
    assert body["anthropic"]["error"] is None
    assert body["anthropic"]["today"]["total_tokens"] == 7000
    assert len(body["anthropic"]["history"]) == 1


def test_stats_unconfigured_provider(client):
    _fresh_cache()
    cache["openai"] = ProviderCache(configured=False)
    body = client.get("/api/stats").json()
    assert body["openai"]["configured"] is False
    assert body["openai"]["today"] is None
    assert body["openai"]["history"] == []


def test_stats_provider_error(client):
    _fresh_cache()
    cache["anthropic"].error = "Anthropic: admin key required (403)"
    body = client.get("/api/stats").json()
    assert body["anthropic"]["error"] == "Anthropic: admin key required (403)"
    # Should still return cached data
    assert body["anthropic"]["today"]["total_tokens"] == 7000


def test_stats_includes_log_data(client):
    _fresh_cache()
    body = client.get("/api/stats").json()
    assert body["logs"]["anthropic"]["today"]["total_tokens"] == 150


def test_stats_fast_response(client):
    """Stats endpoint must respond from cache — not hit external APIs."""
    _fresh_cache()
    import time
    start = time.monotonic()
    client.get("/api/stats")
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"Stats took {elapsed:.2f}s — should be instant from cache"
