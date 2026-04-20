import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.cache import cache
from backend.providers.anthropic_client import fetch_anthropic_usage
from backend.providers.openai_client import fetch_openai_usage
from backend.log_parser import parse_log_files
from backend.config import settings

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def refresh_all() -> None:
    if settings.anthropic_admin_key:
        try:
            cache["anthropic"].data = await fetch_anthropic_usage()
            cache["anthropic"].error = None
            cache["anthropic"].configured = True
        except Exception as e:
            logger.error("Anthropic fetch failed: %s", e)
            cache["anthropic"].error = str(e)
    else:
        cache["anthropic"].configured = False

    if settings.openai_admin_key:
        try:
            cache["openai"].data = await fetch_openai_usage()
            cache["openai"].error = None
            cache["openai"].configured = True
        except Exception as e:
            logger.error("OpenAI fetch failed: %s", e)
            cache["openai"].error = str(e)
    else:
        cache["openai"].configured = False

    try:
        cache["logs"].data = await parse_log_files(settings.log_dir)
        cache["logs"].error = None
    except Exception as e:
        logger.error("Log parse failed: %s", e)
        cache["logs"].error = str(e)


def start_scheduler(interval_seconds: int) -> None:
    scheduler.add_job(refresh_all, "interval", seconds=interval_seconds, id="refresh_all")
    scheduler.start()
    logger.info("Scheduler started, polling every %ds", interval_seconds)
