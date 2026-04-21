"""Read Claude Code plan information.

Preference order:
  1. CLAUDE_SUBSCRIPTION_TYPE / CLAUDE_RATE_LIMIT_TIER env vars (set by init_plan.sh
     for Docker, or manually for any non-macOS environment).
  2. macOS Keychain — "Claude Code-credentials" (local dev on Mac only).
"""
import json
import logging
import os
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
    """Return Claude plan info.

    Checks env vars first (Docker / non-macOS), then falls back to Keychain.
    Returns:
        {"subscription_type": "pro"|"max"|"free", "rate_limit_tier": str}
        or None if unavailable.
    """
    global _cached_plan, _cache_until

    now = time.time()
    if _cached_plan is not None and now < _cache_until:
        return _cached_plan

    # Env vars take priority — set by init_plan.sh for Docker deployments.
    sub_type = os.environ.get("CLAUDE_SUBSCRIPTION_TYPE", "").strip() or None
    rate_tier = os.environ.get("CLAUDE_RATE_LIMIT_TIER", "").strip() or None

    if sub_type:
        plan = {"subscription_type": sub_type, "rate_limit_tier": rate_tier}
        _cached_plan = plan
        _cache_until = now + 86400  # env vars are static; re-check daily
        logger.debug("Claude plan from env: %s / %s", sub_type, rate_tier)
        return plan

    # Fallback: macOS Keychain (local dev)
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

    plan = {"subscription_type": sub_type, "rate_limit_tier": rate_tier}

    expires_at = expires_at_ms / 1000 if expires_at_ms > 1e10 else expires_at_ms
    _cache_until = max(expires_at - 300, now + 3600)
    _cached_plan = plan

    logger.debug("Claude plan from Keychain: %s / %s", sub_type, rate_tier)
    return plan
