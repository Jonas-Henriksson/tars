"""Tests for the TARS voice call web server."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.server import app


client = TestClient(app)


class TestIndex:
    def test_serves_call_page(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "TARS" in resp.text
        assert "callBtn" in resp.text


class TestEphemeralToken:
    def test_returns_error_when_no_api_key(self):
        with patch("web.server.OPENAI_API_KEY", ""):
            resp = client.get("/api/token")
        assert resp.status_code == 500
        assert "not configured" in resp.json()["error"]

    def test_returns_token_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "client_secret": {"value": "eph-token-123"},
            "expires_at": 1234567890,
        }

        async def mock_post(*args, **kwargs):
            return mock_resp

        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("web.server.OPENAI_API_KEY", "sk-test"),
            patch("web.server.httpx.AsyncClient", return_value=mock_client),
        ):
            resp = client.get("/api/token")

        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "eph-token-123"
