import logging
from datetime import datetime, timedelta, timezone

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openai.com"
HISTORY_DAYS = 30


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.openai_admin_key}"}


def _parse_day(bucket: dict) -> dict | None:
    results = bucket.get("results", [])
    if not results:
        return None
    input_tokens = sum(r.get("input_tokens", 0) for r in results)
    output_tokens = sum(r.get("output_tokens", 0) for r in results)
    # Convert Unix timestamp to YYYY-MM-DD
    ts = bucket.get("start_time", 0)
    date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    return {"date": date_str, "input_tokens": input_tokens, "output_tokens": output_tokens}


async def fetch_openai_usage(days: int = HISTORY_DAYS) -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    params: dict = {
        "start_time": int(start.timestamp()),
        "end_time": int(now.timestamp()),
        "bucket_width": "1d",
    }

    all_buckets: list[dict] = []

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        while True:
            resp = await client.get(
                "/v1/organization/usage/completions",
                headers=_headers(),
                params=params,
            )

            if resp.status_code == 401:
                raise ValueError("OpenAI: invalid API key (401)")
            if resp.status_code == 403:
                raise ValueError("OpenAI: org-level admin key required (403)")
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

    logger.info("OpenAI: fetched %d days of history", len(history))
    return {"today": today, "history": history}
