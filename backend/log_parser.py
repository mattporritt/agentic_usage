import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiofiles

logger = logging.getLogger(__name__)

HISTORY_DAYS = 30
SUPPORTED_PROVIDERS = {"anthropic", "openai"}


def _empty_provider() -> dict:
    return {
        "today": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "history": {},
    }


def _parse_record(line: str, cutoff: datetime, today_str: str) -> tuple[str, str, int, int] | None:
    """Parse one JSON log line. Returns (provider, date, input_tokens, output_tokens) or None."""
    try:
        rec = json.loads(line.strip())
    except json.JSONDecodeError:
        return None

    provider = rec.get("provider", "").lower()
    if provider not in SUPPORTED_PROVIDERS:
        return None

    ts_str = rec.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

    if ts < cutoff:
        return None

    date_str = ts.strftime("%Y-%m-%d")
    input_tokens = int(rec.get("input_tokens", 0))
    output_tokens = int(rec.get("output_tokens", 0))
    return provider, date_str, input_tokens, output_tokens


async def parse_log_files(log_dir: str, days: int = HISTORY_DAYS) -> dict:
    """Read all .json/.jsonl files in log_dir and return aggregated token data."""
    if not os.path.isdir(log_dir):
        logger.debug("Log dir %s does not exist, returning empty", log_dir)
        return {"anthropic": _empty_provider(), "openai": _empty_provider()}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    today_str = now.strftime("%Y-%m-%d")

    # {provider: {date: {input_tokens, output_tokens}}}
    aggregated: dict[str, dict[str, dict]] = {
        "anthropic": {},
        "openai": {},
    }

    for path in Path(log_dir).glob("*.json*"):
        try:
            async with aiofiles.open(path, mode="r") as f:
                content = await f.read()
        except OSError as e:
            logger.warning("Could not read %s: %s", path, e)
            continue

        # Support both JSON Lines (one object per line) and JSON arrays
        lines: list[str] = []
        stripped = content.strip()
        if stripped.startswith("["):
            try:
                records = json.loads(stripped)
                lines = [json.dumps(r) for r in records]
            except json.JSONDecodeError:
                lines = stripped.splitlines()
        else:
            lines = stripped.splitlines()

        for line in lines:
            if not line.strip():
                continue
            parsed = _parse_record(line, cutoff, today_str)
            if parsed is None:
                continue
            provider, date_str, inp, out = parsed
            day = aggregated[provider].setdefault(date_str, {"input_tokens": 0, "output_tokens": 0})
            day["input_tokens"] += inp
            day["output_tokens"] += out

    result: dict[str, dict] = {}
    for provider, days_map in aggregated.items():
        today_data = days_map.pop(today_str, {"input_tokens": 0, "output_tokens": 0})
        history = sorted(
            [{"date": d, **v} for d, v in days_map.items()],
            key=lambda x: x["date"],
        )
        result[provider] = {
            "today": {**today_data, "total_tokens": today_data["input_tokens"] + today_data["output_tokens"]},
            "history": history,
        }

    logger.info("Logs: parsed %d anthropic + %d openai history days",
                len(result["anthropic"]["history"]), len(result["openai"]["history"]))
    return result
