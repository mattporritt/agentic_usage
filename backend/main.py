import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.cache import cache
from backend.config import settings
import backend.db as db
from backend.scheduler import refresh_all, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init(settings.db_path)
    logger.info("Starting up — initial data fetch")
    await refresh_all()
    start_scheduler(settings.poll_interval_seconds)
    yield
    logger.info("Shutting down")


app = FastAPI(title="Agentic Usage Dashboard", lifespan=lifespan)


def _local_source_response(key: str) -> dict:
    entry = cache[key]
    if not entry.data:
        return {"configured": entry.configured, "error": entry.error, "today": None, "history": [], "by_model": {}}
    d = entry.data
    return {
        "configured": d.get("configured", True),
        "error": d.get("error"),
        "today": d.get("today"),
        "history": d.get("history", []),
        "by_model": d.get("by_model", {}),
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def get_stats():
    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "claude_code": _local_source_response("claude_code"),
        "codex": _local_source_response("codex"),
        "logs": cache["logs"].data or {"anthropic": None, "openai": None},
    }


# Mount static files AFTER all API routes
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    logger.warning("Frontend dist not found at %s — API-only mode", FRONTEND_DIST)
