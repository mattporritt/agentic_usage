"""Fetch Codex (ChatGPT Plus) rate-limit utilization via stored OAuth token.

The Codex desktop app stores an OAuth access token in ~/.codex/auth.json.
chatgpt.com/backend-api/wham/usage accepts this Bearer token directly and
returns primary (5-hour) and secondary (7-day) rolling window utilization.
curl_cffi is used to match Chrome's TLS fingerprint.
"""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
_AUTH_URL = "https://auth.openai.com/oauth/token"


def _read_auth(codex_dir: str) -> dict | None:
    path = Path(codex_dir) / "auth.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _access_token(codex_dir: str) -> str | None:
    auth = _read_auth(codex_dir)
    if not auth:
        return None
    return (auth.get("tokens") or {}).get("access_token")


async def _refresh_token(codex_dir: str) -> str | None:
    """Attempt to refresh the OAuth access token using the stored refresh token."""
    auth = _read_auth(codex_dir)
    if not auth:
        return None
    tokens = auth.get("tokens", {})
    refresh = tokens.get("refresh_token")
    if not refresh:
        return None

    import base64
    try:
        seg = tokens.get("access_token", "").split(".")[1]
        seg += "=" * (-len(seg) % 4)
        client_id = json.loads(base64.urlsafe_b64decode(seg)).get(
            "client_id", "app_EMoamEEZ73f0CkXaXp7hrann"
        )
    except Exception:
        client_id = "app_EMoamEEZ73f0CkXaXp7hrann"

    try:
        from curl_cffi import requests as cf_requests
        r = cf_requests.post(_AUTH_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
        }, impersonate="chrome131", timeout=10)
        if r.status_code == 200:
            new_token = r.json().get("access_token")
            if new_token:
                tokens["access_token"] = new_token
                if "refresh_token" in r.json():
                    tokens["refresh_token"] = r.json()["refresh_token"]
                auth["tokens"] = tokens
                Path(codex_dir, "auth.json").write_text(json.dumps(auth, indent=2))
                return new_token
    except Exception as e:
        logger.debug("Codex token refresh failed: %s", e)
    return None


async def fetch_usage(codex_dir: str) -> dict[str, Any] | None:
    """Return Codex rate-limit utilization, or None if unavailable.

    Returns:
        {
            "primary_window":   {"used_percent": int, "window_hours": 5,
                                 "reset_at": str},
            "secondary_window": {"used_percent": int, "window_hours": 168,
                                 "reset_at": str},
            "limit_reached": bool,
        }
    """
    try:
        from curl_cffi import requests as cf_requests
    except ImportError:
        logger.warning("curl_cffi not installed — cannot fetch Codex usage")
        return None

    token = _access_token(codex_dir)
    if not token:
        return None

    def _iso(unix_ts: int) -> str:
        return datetime.fromtimestamp(unix_ts, tz=timezone.utc).isoformat()

    async def _call(tok: str) -> dict | None:
        try:
            r = cf_requests.get(
                _USAGE_URL,
                headers={"Authorization": f"Bearer {tok}"},
                impersonate="chrome131",
                timeout=8,
            )
            if r.status_code == 200:
                return r.json()
            if r.status_code == 401:
                return None  # signal for refresh
            logger.debug("Codex wham/usage returned %d", r.status_code)
        except Exception as e:
            logger.debug("Codex usage fetch failed: %s", e)
        return False  # non-401 failure

    data = await _call(token)
    if data is None:  # 401 — try refreshing
        token = await _refresh_token(codex_dir)
        if token:
            data = await _call(token)

    if not data:
        return None

    result: dict[str, Any] = {
        "limit_reached": data.get("rate_limit", {}).get("limit_reached", False),
    }

    rl = data.get("rate_limit", {})
    for key, label in (("primary_window", "primary"), ("secondary_window", "secondary")):
        w = rl.get(key)
        if w and w.get("used_percent") is not None:
            result[label] = {
                "used_percent": w["used_percent"],
                "window_hours": w["limit_window_seconds"] // 3600,
                "reset_at": _iso(w["reset_at"]) if w.get("reset_at") else None,
            }

    return result if len(result) > 1 else None
