"""
Integration tests: full parse pipeline with real fixture files.
These test the parser → scheduler → API chain end-to-end using
temporary directories that mimic the real ~/.claude and ~/.codex layouts.
"""
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.sources.claude_code_parser import parse_claude_code_sessions
from backend.sources.codex_parser import parse_codex_sessions
import backend.db as db


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ts(days_ago: int = 0, hour: int = 10) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _make_claude_session(path: Path, messages: list[dict]) -> None:
    """Write a Claude Code session JSONL with assistant messages."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


def _make_codex_db(path: Path, responses: list[dict]) -> None:
    """Create a minimal Codex logs_2.sqlite with response.completed entries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE logs (
        id INTEGER PRIMARY KEY,
        ts INTEGER NOT NULL,
        ts_nanos INTEGER NOT NULL,
        level TEXT NOT NULL,
        target TEXT NOT NULL,
        feedback_log_body TEXT,
        module_path TEXT,
        file TEXT,
        line INTEGER,
        thread_id TEXT,
        process_uuid TEXT,
        estimated_bytes INTEGER NOT NULL DEFAULT 0
    )""")
    for i, resp in enumerate(responses):
        body = f'Received message {json.dumps({"type": "response.completed", "response": resp})}'
        conn.execute(
            "INSERT INTO logs (ts, ts_nanos, level, target, feedback_log_body, estimated_bytes) VALUES (?,?,?,?,?,?)",
            (resp.get("created_at", 0), 0, "INFO", "codex", body, len(body)),
        )
    conn.commit()
    conn.close()


# ── Claude Code integration ───────────────────────────────────────────────────

async def test_claude_code_full_pipeline(tmp_path):
    """Parser reads all projects, aggregates correctly, returns expected shape."""
    proj = tmp_path / "projects" / "my-project"
    _make_claude_session(proj / "session1.jsonl", [
        {
            "type": "assistant",
            "timestamp": _ts(0),
            "message": {
                "model": "claude-sonnet-4-6",
                "usage": {"input_tokens": 100, "cache_read_input_tokens": 5000, "output_tokens": 300},
            },
        },
        {
            "type": "assistant",
            "timestamp": _ts(1),
            "message": {
                "model": "claude-sonnet-4-6",
                "usage": {"input_tokens": 50, "cache_read_input_tokens": 2000, "output_tokens": 150},
            },
        },
    ])

    result = await parse_claude_code_sessions(str(tmp_path))

    assert result["configured"] is True
    assert result["error"] is None
    assert result["today"]["input_tokens"] == 100
    assert result["today"]["cache_read_tokens"] == 5000
    assert result["today"]["output_tokens"] == 300
    assert result["today"]["total_tokens"] == 5400
    assert len(result["history"]) == 1
    assert result["history"][0]["input_tokens"] == 50
    assert "claude-sonnet-4-6" in result["by_model"]


async def test_claude_code_multiple_projects(tmp_path):
    """Aggregates across multiple project directories."""
    for proj_name in ["proj-a", "proj-b"]:
        _make_claude_session(
            tmp_path / "projects" / proj_name / "s.jsonl",
            [{"type": "assistant", "timestamp": _ts(0),
              "message": {"model": "claude-sonnet-4-6",
                          "usage": {"input_tokens": 200, "cache_read_input_tokens": 0, "output_tokens": 100}}}],
        )

    result = await parse_claude_code_sessions(str(tmp_path))
    assert result["today"]["input_tokens"] == 400
    assert result["today"]["output_tokens"] == 200


async def test_claude_code_missing_dir(tmp_path):
    result = await parse_claude_code_sessions(str(tmp_path / "nonexistent"))
    assert result["configured"] is False
    assert result["error"] is not None


# ── Codex integration ─────────────────────────────────────────────────────────

def _codex_resp(days_ago: int, input_tokens: int, output_tokens: int, cached: int = 0, model: str = "gpt-5.4") -> dict:
    ts = int((datetime.now(timezone.utc) - timedelta(days=days_ago)).timestamp())
    return {
        "model": model,
        "created_at": ts,
        "status": "completed",
        "usage": {
            "input_tokens": input_tokens,
            "input_tokens_details": {"cached_tokens": cached},
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }


async def test_codex_full_pipeline(tmp_path):
    _make_codex_db(tmp_path / "logs_2.sqlite", [
        _codex_resp(0, input_tokens=1000, output_tokens=50),
        _codex_resp(1, input_tokens=800, output_tokens=40),
        _codex_resp(2, input_tokens=600, output_tokens=30),
    ])
    result = await parse_codex_sessions(str(tmp_path))
    assert result["configured"] is True
    assert result["today"]["input_tokens"] == 1000
    assert result["today"]["output_tokens"] == 50
    assert len(result["history"]) == 2
    assert "gpt-5.4" in result["by_model"]


async def test_codex_missing_db(tmp_path):
    result = await parse_codex_sessions(str(tmp_path / "no-codex"))
    assert result["configured"] is False


async def test_codex_multiple_responses_same_day_aggregated(tmp_path):
    _make_codex_db(tmp_path / "logs_2.sqlite", [
        _codex_resp(0, 500, 20),
        _codex_resp(0, 300, 15),
    ])
    result = await parse_codex_sessions(str(tmp_path))
    assert result["today"]["input_tokens"] == 800
    assert result["today"]["output_tokens"] == 35


# ── Full API integration ──────────────────────────────────────────────────────

@pytest.fixture
def api_client(tmp_path):
    db.init(str(tmp_path / "test.db"))
    with patch("backend.main.refresh_all", new_callable=AsyncMock), \
         patch("backend.main.start_scheduler"):
        from backend.main import app
        with TestClient(app) as c:
            yield c
    db._DB_PATH = None


async def test_stats_endpoint_shape(api_client):
    resp = api_client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "claude_code" in body
    assert "codex" in body
    assert "last_updated" in body
    # Anthropic/OpenAI API cards are gone
    assert "anthropic" not in body
    assert "openai" not in body


async def test_stats_contains_by_model(api_client):
    from backend.cache import cache, ProviderCache
    cache["claude_code"] = ProviderCache(configured=True, data={
        "configured": True, "error": None,
        "today": {"input_tokens": 500, "cache_read_tokens": 10000, "output_tokens": 200, "total_tokens": 10700},
        "history": [],
        "by_model": {"claude-sonnet-4-6": {"input_tokens": 500, "cache_read_tokens": 10000, "output_tokens": 200}},
    })
    body = api_client.get("/api/stats").json()
    assert body["claude_code"]["by_model"]["claude-sonnet-4-6"]["output_tokens"] == 200
