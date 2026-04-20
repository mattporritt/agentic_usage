import logging
from datetime import datetime, timedelta, timezone

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.anthropic.com"
HISTORY_DAYS = 30


def _headers() -> dict:
    return {
        "x-api-key": settings.anthropic_admin_key,
        "anthropic-version": "2023-06-01",
    }


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_day(bucket: dict) -> dict | None:
    """Extract aggregated token counts from a single daily bucket."""
    results = bucket.get("results", [])
    if not results:
        return None
    input_tokens = sum(
        r.get("uncached_input_tokens", 0) + r.get("cache_read_input_tokens", 0)
        for r in results
    )
    output_tokens = sum(r.get("output_tokens", 0) for r in results)
    date_str = bucket.get("starting_at", "")[:10]  # YYYY-MM-DD
    return {"date": date_str, "input_tokens": input_tokens, "output_tokens": output_tokens}


async def fetch_anthropic_usage(days: int = HISTORY_DAYS) -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    params = {
        "starting_at": _date_str(start),
        "ending_at": _date_str(now),
        "bucket_width": "1d",
    }

    all_buckets: list[dict] = []

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        while True:
            resp = await client.get(
                "/v1/organizations/usage_report/messages",
                headers=_headers(),
                params=params,
            )

            if resp.status_code == 401:
                raise ValueError("Anthropic: invalid API key (401)")
            if resp.status_code == 403:
                raise ValueError(
                    "Anthropic: admin key required, or individual account does not support usage API (403)"
                )
            resp.raise_for_status()

            payload = resp.json()
            all_buckets.extend(payload.get("data", []))

            if not payload.get("has_more"):
                break
            params["page"] = payload["next_page"]

    today_str = now.strftime("%Y-%m-%d")
    history: list[dict] = []
    today: dict | None = None

    for bucket in all_buckets:
        parsed = _parse_day(bucket)
        if parsed is None:
            continue
        if parsed["date"] == today_str:
            today = {**parsed, "total_tokens": parsed["input_tokens"] + parsed["output_tokens"]}
        else:
            history.append(parsed)

    history.sort(key=lambda x: x["date"])

    if today is None:
        today = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    logger.info("Anthropic: fetched %d days of history", len(history))
    return {"today": today, "history": history}
