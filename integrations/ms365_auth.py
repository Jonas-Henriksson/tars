"""Microsoft 365 authentication via MSAL device code flow.

Uses the device code flow since TARS runs as a Telegram bot (no browser
redirect available). The user authenticates by visiting
https://microsoft.com/devicelogin and entering a code.

Token caching is handled via MSAL's SerializableTokenCache, persisted
to disk so the user doesn't need to re-authenticate every restart.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import msal

from config import MS_CLIENT_ID, MS_TENANT_ID

logger = logging.getLogger(__name__)

# Scopes needed for calendar and mail access
SCOPES = [
    "User.Read",
    "Calendars.ReadWrite",
    "Mail.ReadWrite",
    "Mail.Send",
    "Tasks.ReadWrite",
]

_TOKEN_CACHE_PATH = Path(__file__).parent.parent / "token_cache.json"

# Per-chat auth state: stores the MSAL app and cached accounts
_auth_apps: dict[int, msal.PublicClientApplication] = {}


def _load_cache() -> msal.SerializableTokenCache:
    """Load the token cache from disk."""
    cache = msal.SerializableTokenCache()
    if _TOKEN_CACHE_PATH.exists():
        cache.deserialize(_TOKEN_CACHE_PATH.read_text())
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    """Persist the token cache to disk."""
    if cache.has_state_changed:
        _TOKEN_CACHE_PATH.write_text(cache.serialize())


def _get_app() -> msal.PublicClientApplication:
    """Get or create the MSAL public client application."""
    authority = f"https://login.microsoftonline.com/{MS_TENANT_ID}" if MS_TENANT_ID else None
    cache = _load_cache()
    app = msal.PublicClientApplication(
        client_id=MS_CLIENT_ID,
        authority=authority,
        token_cache=cache,
    )
    return app


def is_configured() -> bool:
    """Check if MS365 credentials are configured."""
    return bool(MS_CLIENT_ID and MS_TENANT_ID)


def get_token_silent() -> str | None:
    """Try to get an access token silently (from cache).

    Returns the access token string, or None if interactive auth is needed.
    """
    if not is_configured():
        return None

    app = _get_app()
    accounts = app.get_accounts()
    if not accounts:
        return None

    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if result and "access_token" in result:
        _save_cache(app.token_cache)
        return result["access_token"]
    return None


def start_device_flow() -> dict[str, Any] | None:
    """Initiate the device code flow.

    Returns the flow dict containing 'user_code' and 'message',
    or None if not configured.
    """
    if not is_configured():
        return None

    app = _get_app()
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        logger.error("Failed to initiate device flow: %s", flow)
        return None
    return flow


def complete_device_flow(flow: dict[str, Any]) -> str | None:
    """Complete the device code flow after user has authenticated.

    Returns the access token string, or None on failure.
    """
    app = _get_app()
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        _save_cache(app.token_cache)
        return result["access_token"]
    logger.error("Device flow auth failed: %s", result.get("error_description", result))
    return None


def get_account_info() -> dict[str, str] | None:
    """Get info about the currently signed-in account.

    Returns dict with 'username' and 'name', or None.
    """
    if not is_configured():
        return None
    app = _get_app()
    accounts = app.get_accounts()
    if accounts:
        return {
            "username": accounts[0].get("username", "Unknown"),
            "name": accounts[0].get("name", accounts[0].get("username", "Unknown")),
        }
    return None
