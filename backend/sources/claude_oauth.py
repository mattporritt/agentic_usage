"""Read Claude Code plan information from macOS Keychain.

Claude Code stores OAuth credentials in the Keychain under "Claude Code-credentials".
The token payload includes subscriptionType and rateLimitTier directly — no API call
needed. All Anthropic usage API endpoints require admin keys; there is no personal
quota endpoint accessible via OAuth.
"""
import json
import logging
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)

_KEYCHAIN_SERVICE = "Claude Code-credentials"

# In-memory cache: avoid re-prompting Keychain on every poll cycle.
_cached_plan: dict[str, Any] | None = None
_cache_until: float = 0.0


def _read_keychain() -> dict | None:
    """Read Claude Code credentials from macOS Keychain. Returns None on failure."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def get_plan_info() -> dict[str, Any] | None:
    """Return Claude plan info from cached Keychain credentials.

    Returns:
        {"subscription_type": "pro"|"max"|"free", "rate_limit_tier": str}
        or None if Keychain is unavailable.
    """
    global _cached_plan, _cache_until

    now = time.time()
    if _cached_plan is not None and now < _cache_until:
        return _cached_plan

    creds = _read_keychain()
    if not creds:
        logger.debug("Claude Code Keychain credentials unavailable")
        return None

    oauth = creds.get("claudeAiOauth", {})
    sub_type = oauth.get("subscriptionType")
    rate_tier = oauth.get("rateLimitTier")
    expires_at_ms = oauth.get("expiresAt", 0)

    if not sub_type:
        return None

    plan = {
        "subscription_type": sub_type,
        "rate_limit_tier": rate_tier,
    }

    # Cache until token expiry (re-read when token needs refresh)
    expires_at = expires_at_ms / 1000 if expires_at_ms > 1e10 else expires_at_ms
    _cache_until = max(expires_at - 300, now + 3600)  # 5-min buffer, min 1h
    _cached_plan = plan

    logger.debug("Claude plan from Keychain: %s / %s", sub_type, rate_tier)
    return plan
