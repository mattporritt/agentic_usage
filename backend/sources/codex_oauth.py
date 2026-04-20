"""Fetch OpenAI billing/subscription data using Codex's stored OAuth token.

Codex stores an OAuth Bearer token in ~/.codex/auth.json that can be used
with OpenAI's legacy billing API to retrieve subscription plan and monthly
usage without requiring an admin API key.
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


def _jwt_exp(token: str) -> int:
    """Decode the exp claim from a JWT without verifying signature."""
    try:
        segment = token.split(".")[1]
        segment += "=" * (-len(segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(segment))
        return int(payload.get("exp", 0))
    except Exception:
        return 0


def _jwt_claim(token: str, key: str) -> str | None:
    try:
        segment = token.split(".")[1]
        segment += "=" * (-len(segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(segment))
        return payload.get(key)
    except Exception:
        return None


async def _refresh(refresh_token: str, client_id: str) -> str | None:
    """Exchange a refresh_token for a new access_token."""
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
    """Return quota dict from OpenAI billing API, or None if unavailable.

    Returns:
        {
            "plan": str,
            "hard_limit_usd": float | None,
            "used_usd": float | None,
        }
    """
    auth = _read_auth(codex_dir)
    if not auth:
        return None

    tokens = auth.get("tokens", {})
    access_token = tokens.get("access_token")
    if not access_token:
        return None

    # Refresh if expired or expiring within 2 minutes
    if _jwt_exp(access_token) < time.time() + 120:
        refresh = tokens.get("refresh_token")
        client_id = _jwt_claim(access_token, "client_id") or "app_EMoamEEZ73f0CkXaXp7hrann"
        if refresh:
            new_token = await _refresh(refresh, client_id)
            if new_token:
                access_token = new_token
                logger.debug("OAuth token refreshed")

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            sub_resp = await client.get(f"{_BILLING}/subscription", headers=headers)
            if sub_resp.status_code != 200:
                logger.debug("Billing subscription returned %d", sub_resp.status_code)
                return None
            sub = sub_resp.json()

            # Monthly usage (current calendar month)
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            start = now.replace(day=1).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
            usage_resp = await client.get(
                f"{_BILLING}/usage",
                params={"start_date": start, "end_date": end},
                headers=headers,
            )
            used_cents = 0
            if usage_resp.status_code == 200:
                used_cents = usage_resp.json().get("total_usage", 0)

        plan_title = (sub.get("plan") or {}).get("title", "Unknown")
        hard_limit = sub.get("hard_limit_usd")
        soft_limit = sub.get("soft_limit_usd")

        return {
            "plan": plan_title,
            "hard_limit_usd": hard_limit,
            "soft_limit_usd": soft_limit,
            "used_usd": round(used_cents / 100, 4),
        }

    except httpx.HTTPError as e:
        logger.debug("Billing API request failed: %s", e)
        return None
