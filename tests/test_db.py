"""Tests for the SQLite persistence layer."""
import pytest
import backend.db as db


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path):
    db.init(str(tmp_path / "test.db"))
    yield
    db._DB_PATH = None


async def test_upsert_and_retrieve():
    await db.upsert_day("claude_code", "2026-04-15", 1000, 50000, 500, 51500)
    rows = await db.get_history("claude_code")
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-04-15"
    assert rows[0]["input_tokens"] == 1000
    assert rows[0]["output_tokens"] == 500


async def test_upsert_overwrites_existing():
    await db.upsert_day("claude_code", "2026-04-15", 1000, 0, 500, 1500)
    await db.upsert_day("claude_code", "2026-04-15", 2000, 0, 800, 2800)
    rows = await db.get_history("claude_code")
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 2000
    assert rows[0]["output_tokens"] == 800


async def test_sources_isolated():
    await db.upsert_day("claude_code", "2026-04-15", 1000, 0, 500, 1500)
    await db.upsert_day("codex", "2026-04-15", 200, 0, 100, 300)
    cc = await db.get_history("claude_code")
    cx = await db.get_history("codex")
    assert len(cc) == 1
    assert len(cx) == 1
    assert cc[0]["input_tokens"] == 1000
    assert cx[0]["input_tokens"] == 200


async def test_history_sorted_by_date():
    await db.upsert_day("codex", "2026-04-17", 100, 0, 50, 150)
    await db.upsert_day("codex", "2026-04-12", 200, 0, 80, 280)
    await db.upsert_day("codex", "2026-04-14", 150, 0, 60, 210)
    rows = await db.get_history("codex")
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates)


async def test_merge_adds_db_gaps():
    """DB rows for pruned dates should appear in merged history."""
    await db.upsert_day("claude_code", "2026-03-20", 500, 10000, 200, 10700)
    live_history = [
        {"date": "2026-04-16", "input_tokens": 800, "cache_read_tokens": 0, "output_tokens": 400},
    ]
    merged = await db.merge_with_db("claude_code", "2026-04-20", live_history)
    dates = [d["date"] for d in merged]
    assert "2026-03-20" in dates
    assert "2026-04-16" in dates


async def test_merge_live_data_not_duplicated():
    """Dates covered by live source should not be doubled from DB."""
    await db.upsert_day("claude_code", "2026-04-16", 999, 0, 999, 1998)
    live_history = [
        {"date": "2026-04-16", "input_tokens": 800, "cache_read_tokens": 0, "output_tokens": 400},
    ]
    merged = await db.merge_with_db("claude_code", "2026-04-20", live_history)
    entries_for_date = [d for d in merged if d["date"] == "2026-04-16"]
    assert len(entries_for_date) == 1
    assert entries_for_date[0]["input_tokens"] == 800  # live wins


async def test_merge_today_excluded_from_history():
    """Today's date should never appear in the merged history list."""
    await db.upsert_day("codex", "2026-04-20", 100, 0, 50, 150)
    merged = await db.merge_with_db("codex", "2026-04-20", [])
    assert not any(d["date"] == "2026-04-20" for d in merged)


async def test_no_db_path_returns_empty():
    db._DB_PATH = None
    rows = await db.get_history("claude_code")
    assert rows == []


async def test_persist_source_saves_today_and_history():
    today = {"input_tokens": 200, "cache_read_tokens": 5000, "output_tokens": 100, "total_tokens": 5300}
    history = [{"date": "2026-04-19", "input_tokens": 150, "cache_read_tokens": 4000, "output_tokens": 80}]
    await db.persist_source("claude_code", "2026-04-20", today, history)
    rows = await db.get_history("claude_code")
    dates = [r["date"] for r in rows]
    assert "2026-04-20" in dates
    assert "2026-04-19" in dates
