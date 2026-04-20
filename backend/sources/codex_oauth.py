"""Read Codex plan information and attempt OpenAI billing API via stored OAuth token.

Codex stores an OAuth Bearer token in ~/.codex/auth.json. The JWT payload
contains chatgpt_plan_type directly (no API call needed). The OpenAI legacy
billing API requires a browser session cookie (not OAuth Bearer), so quota
data is not accessible; we gracefully return None for that part.
"""
import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BILLING = "https://api.openai.com/v1/dashboard/billing"
_AUTH_URL = "https://auth.openai.com/oauth/token"


def _read_auth(codex_dir: str) -> dict | None:
    path = Path(codex_dir) / "auth.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _jwt_payload(token: str) -> dict:
    """Decode JWT payload without verifying signature."""
    try:
        segment = token.split(".")[1]
        segment += "=" * (-len(segment) % 4)
        return json.loads(base64.urlsafe_b64decode(segment))
    except Exception:
        return {}


def _jwt_exp(token: str) -> int:
    return int(_jwt_payload(token).get("exp", 0))


def get_plan_info(codex_dir: str) -> dict[str, Any] | None:
    """Return Codex plan info decoded directly from the stored JWT.

    Returns:
        {"subscription_type": "plus"|"free"|..., "account_id": str}
        or None if auth.json is missing or malformed.
    """
    auth = _read_auth(codex_dir)
    if not auth:
        return None

    access_token = (auth.get("tokens") or {}).get("access_token")
    if not access_token:
        return None

    payload = _jwt_payload(access_token)
    openai_auth = payload.get("https://api.openai.com/auth", {})
    plan_type = openai_auth.get("chatgpt_plan_type")

    if not plan_type:
        return None

    return {
        "subscription_type": plan_type,
        "account_id": auth.get("account_id"),
    }


async def _refresh(refresh_token: str, client_id: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_AUTH_URL, data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
            })
            if resp.status_code == 200:
                return resp.json().get("access_token")
    except httpx.HTTPError as e:
        logger.debug("Token refresh failed: %s", e)
    return None


async def fetch_quota(codex_dir: str) -> dict[str, Any] | None:
    """Attempt OpenAI billing API for quota data.

    Returns a quota dict if accessible, or None. The billing endpoint
    requires a browser session cookie (not OAuth Bearer), so this will
    return None for ChatGPT subscription accounts.
    """
    auth = _read_auth(codex_dir)
    if not auth:
        return None

    tokens = auth.get("tokens", {})
    access_token = tokens.get("access_token")
    if not access_token:
        return None

    if _jwt_exp(access_token) < time.time() + 120:
        refresh = tokens.get("refresh_token")
        client_id = _jwt_payload(access_token).get("client_id", "app_EMoamEEZ73f0CkXaXp7hrann")
        if refresh:
            new_token = await _refresh(refresh, client_id)
            if new_token:
                access_token = new_token

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            sub_resp = await client.get(f"{_BILLING}/subscription", headers=headers)
            if sub_resp.status_code != 200:
                logger.debug("Billing subscription returned %d (browser session required)", sub_resp.status_code)
                return None
            sub = sub_resp.json()

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            start = now.replace(day=1).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
            usage_resp = await client.get(
                f"{_BILLING}/usage",
                params={"start_date": start, "end_date": end},
                headers=headers,
            )
            used_cents = usage_resp.json().get("total_usage", 0) if usage_resp.status_code == 200 else 0

        plan_title = (sub.get("plan") or {}).get("title", "Unknown")
        return {
            "plan": plan_title,
            "hard_limit_usd": sub.get("hard_limit_usd"),
            "soft_limit_usd": sub.get("soft_limit_usd"),
            "used_usd": round(used_cents / 100, 4),
        }

    except httpx.HTTPError as e:
        logger.debug("Billing API request failed: %s", e)
        return None
