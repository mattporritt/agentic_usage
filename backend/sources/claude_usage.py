"""Fetch Claude Pro/Max usage utilization from claude.ai via desktop app session.

The Claude desktop app (Electron/Chromium) stores session cookies encrypted in
~/Library/Application Support/Claude/Cookies using AES-128-CBC with a key derived
from the macOS Keychain entry "Claude Safe Storage". We decrypt them and call
claude.ai's internal usage API using curl_cffi to match Chrome's TLS fingerprint
(required to pass Cloudflare's bot check).

The usage endpoint returns 5-hour and 7-day rolling utilization percentages plus
optional extra-usage credit spend.
"""
import hashlib
import logging
import os
import platform
import shutil
import sqlite3
import subprocess
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

_COOKIES_PATH = os.path.expanduser(
    "~/Library/Application Support/Claude/Cookies"
)
_KEYCHAIN_SERVICE = "Claude Safe Storage"
_KEYCHAIN_ACCOUNT = "Claude"

# Cached decrypted cookies — refreshed when the session cookie changes on disk.
_cookie_cache: dict[str, str] = {}
_cookie_mtime: float = 0.0


def _keychain_password() -> bytes | None:
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-s", _KEYCHAIN_SERVICE, "-a", _KEYCHAIN_ACCOUNT, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().encode()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _aes_key(password: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)


def _decrypt_cookie(enc: bytes, key: bytes) -> str:
    """Decrypt a v10 Chromium cookie value (AES-128-CBC, IV=spaces).

    Chromium prepends a 32-byte internal header to the plaintext before
    encrypting, so we skip those bytes when extracting the actual value.
    """
    if not enc.startswith(b"v10"):
        return enc.decode("utf-8", errors="replace")
    try:
        from Crypto.Cipher import AES as _AES
    except ImportError:
        logger.warning("pycryptodome not installed — cannot decrypt cookies")
        return ""
    ct = enc[3:]
    dec = _AES.new(key, _AES.MODE_CBC, b" " * 16).decrypt(ct)
    pad = dec[-1]
    dec = dec[:-pad] if 1 <= pad <= 16 else dec
    # Skip the 32-byte internal header Chromium adds before the plaintext value
    value = dec[32:].decode("utf-8", errors="replace")
    if not value or not value.isprintable():
        value = dec[16:].decode("utf-8", errors="replace")
    return value


def _load_cookies() -> dict[str, str]:
    """Read and decrypt claude.ai cookies from the Electron cookie store."""
    global _cookie_cache, _cookie_mtime

    if not os.path.exists(_COOKIES_PATH):
        return {}

    try:
        mtime = os.path.getmtime(_COOKIES_PATH)
    except OSError:
        return {}

    if _cookie_cache and mtime == _cookie_mtime:
        return _cookie_cache

    password = _keychain_password()
    if not password:
        return {}
    key = _aes_key(password)

    tmp = tempfile.mktemp(suffix=".db")
    try:
        shutil.copy2(_COOKIES_PATH, tmp)
        conn = sqlite3.connect(tmp)
        rows = conn.execute(
            "SELECT name, encrypted_value FROM cookies "
            "WHERE host_key LIKE '%.claude.ai' OR host_key LIKE '%claude.ai'"
        ).fetchall()
        conn.close()
    except Exception as e:
        logger.debug("Cookie DB read failed: %s", e)
        return {}
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    result = {}
    for name, enc_val in rows:
        value = _decrypt_cookie(enc_val, key)
        if value:
            result[name] = value

    _cookie_cache = result
    _cookie_mtime = mtime
    return result


def _org_id_from_cookies(cookies: dict[str, str]) -> str | None:
    return cookies.get("lastActiveOrg")


async def fetch_usage(org_id: str | None = None) -> dict[str, Any] | None:
    """Return Claude usage utilization from claude.ai, or None if unavailable.

    Returns:
        {
            "five_hour":  {"utilization": float, "resets_at": str},
            "seven_day":  {"utilization": float, "resets_at": str},
            "extra_usage": {"used_credits": float, "monthly_limit": int,
                            "currency": str} | None,
        }
    """
    try:
        from curl_cffi import requests as cf_requests
    except ImportError:
        logger.warning("curl_cffi not installed — cannot fetch Claude usage")
        return None

    cookies = _load_cookies()
    if not cookies.get("sessionKey"):
        logger.debug("No claude.ai session cookies found")
        return None

    oid = org_id or _org_id_from_cookies(cookies)
    if not oid:
        return None

    url = f"https://claude.ai/api/organizations/{oid}/usage"
    try:
        r = cf_requests.get(url, cookies=cookies, impersonate="chrome131", timeout=8)
        if r.status_code != 200:
            logger.debug("Claude usage API returned %d", r.status_code)
            return None
        data = r.json()
    except Exception as e:
        logger.debug("Claude usage fetch failed: %s", e)
        return None

    result: dict[str, Any] = {}
    for window in ("five_hour", "seven_day"):
        w = data.get(window)
        if w and w.get("utilization") is not None:
            result[window] = {
                "utilization": w["utilization"],
                "resets_at": w.get("resets_at"),
            }

    extra = data.get("extra_usage")
    if extra and extra.get("is_enabled"):
        result["extra_usage"] = {
            "used_credits": extra.get("used_credits"),
            "monthly_limit": extra.get("monthly_limit"),
            "currency": extra.get("currency", "USD"),
        }

    return result if result else None
