"""
Parses OpenAI Codex CLI session data from ~/.codex/logs_2.sqlite.
Extracts token usage from response.completed log entries.
"""
import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_DAYS = 30
_COMPLETED_PATTERN = re.compile(r'Received message (\{.*\})')


def _empty_result(configured: bool = True, error: str | None = None) -> dict:
    return {
        "configured": configured,
        "error": error,
        "today": {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "history": [],
        "by_model": {},
    }


def _parse_db(db_path: Path, cutoff: datetime, today_str: str) -> dict:
    """Read logs_2.sqlite and aggregate token usage from response.completed entries."""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT ts, feedback_log_body FROM logs "
            "WHERE feedback_log_body LIKE '%response.completed%'"
        ).fetchall()
    finally:
        conn.close()

    daily: dict[str, dict] = {}
    by_model: dict[str, dict] = {}

    for ts_nanos, body in rows:
        m = _COMPLETED_PATTERN.search(body)
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue

        resp = data.get("response", {})
        usage = resp.get("usage")
        if not usage:
            continue

        created_at = resp.get("created_at") or (ts_nanos // 1_000_000_000)
        try:
            ts = datetime.fromtimestamp(created_at, tz=timezone.utc)
        except (OSError, ValueError):
            continue

        if ts < cutoff:
            continue

        date_str = ts.astimezone().strftime("%Y-%m-%d")  # local date
        inp = usage.get("input_tokens", 0)
        cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
        out = usage.get("output_tokens", 0)

        day = daily.setdefault(date_str, {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0})
        day["input_tokens"] += inp
        day["cached_tokens"] += cached
        day["output_tokens"] += out

        model = resp.get("model", "unknown")
        m_entry = by_model.setdefault(model, {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0})
        m_entry["input_tokens"] += inp
        m_entry["cached_tokens"] += cached
        m_entry["output_tokens"] += out

    today_raw = daily.pop(today_str, {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0})
    today = {
        **today_raw,
        "total_tokens": today_raw["input_tokens"] + today_raw["output_tokens"],
    }

    history = sorted(
        [{"date": d, **v} for d, v in daily.items()],
        key=lambda x: x["date"],
    )

    logger.info("Codex: %d history days from SQLite", len(history))
    return {
        "configured": True,
        "error": None,
        "today": today,
        "history": history,
        "by_model": by_model,
    }


async def parse_codex_sessions(codex_dir: str, days: int = HISTORY_DAYS) -> dict:
    """Parse Codex CLI token usage from ~/.codex/logs_2.sqlite."""
    db_path = Path(codex_dir) / "logs_2.sqlite"

    if not db_path.exists():
        logger.debug("Codex DB not found: %s", db_path)
        return _empty_result(configured=False, error=f"Codex database not found: {db_path}")

    now = datetime.now().astimezone()  # local timezone for day boundaries
    cutoff = now - timedelta(days=days)
    today_str = now.strftime("%Y-%m-%d")

    try:
        return _parse_db(db_path, cutoff, today_str)
    except Exception as e:
        logger.error("Codex DB parse error: %s", e)
        return _empty_result(error=str(e))
