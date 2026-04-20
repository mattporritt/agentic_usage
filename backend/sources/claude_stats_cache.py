"""Read ~/.claude/stats-cache.json and persist historical daily totals to DB.

stats-cache records input+output tokens per model per day (no cache reads).
Input is ~1% of that total for Claude Code, so we store these as output_tokens
as a close approximation for the chart. Live JSONL data will overwrite any
stats-cache row if the source file still exists for that date.
"""
import json
import logging
from pathlib import Path

import backend.db as db

logger = logging.getLogger(__name__)


def _read(claude_dir: str) -> list[dict]:
    """Return parsed dailyModelTokens from stats-cache.json, or []."""
    path = Path(claude_dir) / "stats-cache.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("stats-cache.json read failed: %s", e)
        return []

    entries = data.get("dailyModelTokens")
    if not isinstance(entries, list):
        return []

    result = []
    for entry in entries:
        date = entry.get("date")
        by_model = entry.get("tokensByModel", {})
        if date and isinstance(by_model, dict):
            result.append({"date": date, "total": sum(by_model.values())})
    return result


async def persist_stats_cache(claude_dir: str) -> None:
    """Write any stats-cache dates that are not yet in the DB.

    Called before the JSONL parser so live data can overwrite these entries
    for dates it still covers.
    """
    entries = _read(claude_dir)
    if not entries:
        return

    existing = {row["date"] for row in await db.get_history("claude_code")}

    for entry in entries:
        if entry["date"] not in existing:
            # Store total as output_tokens (input is ~1% of non-cache total).
            await db.upsert_day(
                "claude_code", entry["date"],
                input_tokens=0,
                cache_tokens=0,
                output_tokens=entry["total"],
                total_tokens=entry["total"],
            )
            logger.debug("stats-cache fill-in: %s = %d tokens", entry["date"], entry["total"])
