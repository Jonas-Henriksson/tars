"""Microsoft Graph API client — thin wrapper around httpx."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


async def graph_get(endpoint: str, token: str, params: dict | None = None) -> dict[str, Any]:
    """GET request to Microsoft Graph API."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def graph_post(endpoint: str, token: str, body: dict) -> dict[str, Any]:
    """POST request to Microsoft Graph API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE}{endpoint}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        # Some endpoints (e.g. sendMail) return 202 with no body
        if resp.status_code == 202 or not resp.content:
            return {}
        return resp.json()


async def graph_patch(endpoint: str, token: str, body: dict) -> dict[str, Any]:
    """PATCH request to Microsoft Graph API."""
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{GRAPH_BASE}{endpoint}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
