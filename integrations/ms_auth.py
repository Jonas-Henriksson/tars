"""Microsoft 365 authentication via MSAL (device-code flow).

Uses MSAL's PublicClientApplication with device-code flow so the user
can authenticate from Telegram without needing a web server callback.
Tokens are cached to disk so the user only needs to log in once.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import msal

from config import MS_CLIENT_ID, MS_TENANT_ID

logger = logging.getLogger(__name__)

# Scopes needed for M365 integrations
SCOPES = [
    "Calendars.ReadWrite",
    "Tasks.ReadWrite",
    "Mail.ReadWrite",
    "Mail.Send",
    "User.Read",
]

_TOKEN_CACHE_PATH = Path(__file__).parent.parent / "token_cache.json"

# Singleton app instance
_app: msal.PublicClientApplication | None = None


def _get_cache() -> msal.SerializableTokenCache:
    """Load or create a persistent token cache."""
    cache = msal.SerializableTokenCache()
    if _TOKEN_CACHE_PATH.exists():
        cache.deserialize(_TOKEN_CACHE_PATH.read_text())
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    """Persist token cache to disk if changed."""
    if cache.has_state_changed:
        _TOKEN_CACHE_PATH.write_text(cache.serialize())


def _get_app() -> msal.PublicClientApplication:
    """Return the MSAL public client application (singleton)."""
    global _app
    if _app is None:
        if not MS_CLIENT_ID or not MS_TENANT_ID:
            raise RuntimeError(
                "MS_CLIENT_ID and MS_TENANT_ID must be set in .env"
            )
        cache = _get_cache()
        _app = msal.PublicClientApplication(
            client_id=MS_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{MS_TENANT_ID}",
            token_cache=cache,
        )
    return _app


def is_configured() -> bool:
    """Return True if MS credentials are set."""
    return bool(MS_CLIENT_ID and MS_TENANT_ID)


def get_token_silent() -> str | None:
    """Try to get an access token silently (from cache/refresh token).

    Returns the access token string, or None if interactive login is needed.
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


def start_device_flow() -> dict[str, Any]:
    """Initiate device-code flow. Returns the flow dict with user_code and verification_uri."""
    app = _get_app()
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Device flow failed: {flow.get('error_description', 'unknown error')}")
    return flow


def complete_device_flow(flow: dict[str, Any]) -> str:
    """Complete device-code flow (blocks until user authenticates or timeout).

    Returns the access token string.
    Raises RuntimeError if authentication fails.
    """
    app = _get_app()
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        _save_cache(app.token_cache)
        return result["access_token"]
    raise RuntimeError(
        f"Authentication failed: {result.get('error_description', result.get('error', 'unknown'))}"
    )
