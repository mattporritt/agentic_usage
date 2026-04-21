"""
Parses Claude Code local session files from ~/.claude/projects/**/*.jsonl
and returns daily token usage aggregated across all projects/sessions.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiofiles

logger = logging.getLogger(__name__)

HISTORY_DAYS = 30


def _empty_result() -> dict:
    return {
        "configured": True,
        "error": None,
        "today": {"input_tokens": 0, "cache_read_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "history": [],
        "by_model": {},
    }


def _extract_usage(line: str) -> tuple[str, dict] | None:
    """
    Parse one line from a session JSONL file.
    Returns (iso_timestamp, usage_dict) for assistant messages that have usage, else None.
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None

    if obj.get("type") != "assistant":
        return None

    msg = obj.get("message", {})
    usage = msg.get("usage")
    if not usage:
        return None

    ts = obj.get("timestamp", "")
    if not ts:
        return None

    return ts, usage


async def parse_claude_code_sessions(claude_dir: str, days: int = HISTORY_DAYS) -> dict:
    """
    Walk all project session files under claude_dir/projects/ and aggregate
    token usage by day for the last `days` days.
    """
    projects_dir = Path(claude_dir) / "projects"

    if not projects_dir.is_dir():
        logger.debug("Claude Code projects dir not found: %s", projects_dir)
        result = _empty_result()
        result["configured"] = False
        result["error"] = f"Claude Code directory not found: {projects_dir}"
        return result

    now = datetime.now().astimezone()  # local timezone for day boundaries
    cutoff = now - timedelta(days=days)
    today_str = now.strftime("%Y-%m-%d")

    # date_str -> {input_tokens, cache_read_tokens, output_tokens}
    daily: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    files_read = 0
    messages_parsed = 0

    for jsonl_path in projects_dir.rglob("*.jsonl"):
        try:
            async with aiofiles.open(jsonl_path, mode="r") as f:
                content = await f.read()
        except OSError as e:
            logger.debug("Could not read %s: %s", jsonl_path, e)
            continue

        files_read += 1
        for line in content.splitlines():
            if not line.strip():
                continue
            parsed = _extract_usage(line)
            if parsed is None:
                continue

            ts_str, usage = parsed
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            if ts < cutoff:
                continue

            messages_parsed += 1
            date_str = ts.astimezone().strftime("%Y-%m-%d")  # local date

            inp = usage.get("input_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            out = usage.get("output_tokens", 0)

            day = daily.setdefault(date_str, {"input_tokens": 0, "cache_read_tokens": 0, "output_tokens": 0})
            day["input_tokens"] += inp
            day["cache_read_tokens"] += cache_read
            day["output_tokens"] += out

            # Aggregate by model (lifetime within the window)
            # Model is on the message object
            try:
                obj = json.loads(line)
                model = obj.get("message", {}).get("model", "unknown")
            except Exception:
                model = "unknown"

            m = by_model.setdefault(model, {"input_tokens": 0, "cache_read_tokens": 0, "output_tokens": 0})
            m["input_tokens"] += inp
            m["cache_read_tokens"] += cache_read
            m["output_tokens"] += out

    today_raw = daily.pop(today_str, {"input_tokens": 0, "cache_read_tokens": 0, "output_tokens": 0})
    today = {
        **today_raw,
        "total_tokens": today_raw["input_tokens"] + today_raw["cache_read_tokens"] + today_raw["output_tokens"],
    }

    history = sorted(
        [{"date": d, **v} for d, v in daily.items()],
        key=lambda x: x["date"],
    )

    logger.info(
        "Claude Code: %d session files, %d messages, %d history days",
        files_read, messages_parsed, len(history),
    )

    return {
        "configured": True,
        "error": None,
        "today": today,
        "history": history,
        "by_model": by_model,
    }
