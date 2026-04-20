import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.cache import cache
from backend.config import settings
from backend.scheduler import refresh_all, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initial data fetch")
    await refresh_all()
    start_scheduler(settings.poll_interval_seconds)
    yield
    logger.info("Shutting down")


app = FastAPI(title="Agentic Usage Dashboard", lifespan=lifespan)


def _provider_response(key: str) -> dict:
    entry = cache[key]
    if not entry.configured:
        return {"configured": False, "error": None, "today": None, "history": []}
    return {
        "configured": True,
        "error": entry.error,
        "today": entry.data.get("today") if entry.data else None,
        "history": entry.data.get("history", []) if entry.data else [],
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def get_stats():
    last_fetched = (
        cache["anthropic"].last_fetched
        or cache["openai"].last_fetched
        or datetime.now(timezone.utc)
    )
    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "anthropic": _provider_response("anthropic"),
        "openai": _provider_response("openai"),
        "logs": cache["logs"].data or {"anthropic": None, "openai": None},
    }


# Mount static files AFTER all API routes
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    logger.warning("Frontend dist not found at %s — API-only mode", FRONTEND_DIST)
