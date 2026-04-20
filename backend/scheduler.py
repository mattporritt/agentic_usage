import logging
import os
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.cache import cache
from backend.log_parser import parse_log_files
from backend.sources.claude_code_parser import parse_claude_code_sessions
from backend.sources.codex_parser import parse_codex_sessions
from backend.config import settings
import backend.db as db

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def refresh_all() -> None:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        cache["logs"].data = await parse_log_files(settings.log_dir)
        cache["logs"].error = None
    except Exception as e:
        logger.error("Log parse failed: %s", e)
        cache["logs"].error = str(e)

    try:
        claude_dir = os.path.expanduser(settings.claude_code_dir)
        result = await parse_claude_code_sessions(claude_dir)

        if result.get("configured") and result.get("today"):
            await db.persist_source("claude_code", today_str, result["today"], result.get("history", []))
            result["history"] = await db.merge_with_db("claude_code", today_str, result.get("history", []))

        cache["claude_code"].data = result
        cache["claude_code"].configured = result["configured"]
        cache["claude_code"].error = result.get("error")
    except Exception as e:
        logger.error("Claude Code parse failed: %s", e)
        cache["claude_code"].error = str(e)

    try:
        codex_dir = os.path.expanduser(settings.codex_dir)
        result = await parse_codex_sessions(codex_dir)

        if result.get("configured") and result.get("today"):
            await db.persist_source("codex", today_str, result["today"], result.get("history", []))
            result["history"] = await db.merge_with_db("codex", today_str, result.get("history", []))

        cache["codex"].data = result
        cache["codex"].configured = result["configured"]
        cache["codex"].error = result.get("error")
    except Exception as e:
        logger.error("Codex parse failed: %s", e)
        cache["codex"].error = str(e)


def start_scheduler(interval_seconds: int) -> None:
    scheduler.add_job(refresh_all, "interval", seconds=interval_seconds, id="refresh_all")
    scheduler.start()
    logger.info("Scheduler started, polling every %ds", interval_seconds)
