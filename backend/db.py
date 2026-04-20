"""
SQLite persistence for daily token usage aggregates.
Ensures historical data survives even if source CLI files are pruned.
"""
import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_DB_PATH: Path | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_usage (
    date            TEXT    NOT NULL,
    source          TEXT    NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    cache_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, source)
);
"""


def init(db_path: str) -> None:
    global _DB_PATH
    _DB_PATH = Path(db_path)
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)


async def _ensure_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript(SCHEMA)
    await conn.commit()


async def upsert_day(source: str, date: str, input_tokens: int, cache_tokens: int, output_tokens: int, total_tokens: int) -> None:
    """Insert or replace a single day's aggregate for a source."""
    if _DB_PATH is None:
        return
    async with aiosqlite.connect(_DB_PATH) as conn:
        await _ensure_schema(conn)
        await conn.execute(
            """INSERT INTO daily_usage (date, source, input_tokens, cache_tokens, output_tokens, total_tokens)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(date, source) DO UPDATE SET
                   input_tokens  = excluded.input_tokens,
                   cache_tokens  = excluded.cache_tokens,
                   output_tokens = excluded.output_tokens,
                   total_tokens  = excluded.total_tokens""",
            (date, source, input_tokens, cache_tokens, output_tokens, total_tokens),
        )
        await conn.commit()


async def get_history(source: str, days: int = 30) -> list[dict]:
    """Return all stored daily rows for a source within the last N days."""
    if _DB_PATH is None or not _DB_PATH.exists():
        return []
    async with aiosqlite.connect(_DB_PATH) as conn:
        await _ensure_schema(conn)
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """SELECT date, input_tokens, cache_tokens, output_tokens, total_tokens
               FROM daily_usage
               WHERE source = ?
               ORDER BY date ASC""",
            (source,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def persist_source(source: str, today_str: str, today: dict, history: list[dict]) -> None:
    """Save today + all history days for a source to the DB."""
    if _DB_PATH is None:
        return

    # Persist today
    await upsert_day(
        source, today_str,
        today.get("input_tokens", 0),
        today.get("cache_read_tokens") or today.get("cache_tokens") or today.get("cached_tokens", 0),
        today.get("output_tokens", 0),
        today.get("total_tokens", 0),
    )

    # Persist history days (these are the source-authoritative values)
    for day in history:
        await upsert_day(
            source, day["date"],
            day.get("input_tokens", 0),
            day.get("cache_read_tokens") or day.get("cache_tokens") or day.get("cached_tokens", 0),
            day.get("output_tokens", 0),
            day.get("input_tokens", 0) + day.get("output_tokens", 0),
        )


async def merge_with_db(source: str, today_str: str, live_history: list[dict]) -> list[dict]:
    """
    Merge live source history with DB history.
    Live data wins for any date it covers; DB fills gaps for pruned dates.
    """
    db_rows = await get_history(source)

    live_dates = {d["date"] for d in live_history}
    live_dates.add(today_str)  # today is never in history list

    # Map DB rows to history-compatible dicts, skip dates already in live data
    db_extras: list[dict] = []
    for row in db_rows:
        if row["date"] not in live_dates and row["date"] != today_str:
            db_extras.append({
                "date": row["date"],
                "input_tokens": row["input_tokens"],
                "cache_read_tokens": row["cache_tokens"],
                "output_tokens": row["output_tokens"],
            })

    combined = live_history + db_extras
    combined.sort(key=lambda x: x["date"])
    return combined
