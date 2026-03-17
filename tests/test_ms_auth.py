"""Tests for Microsoft 365 authentication module."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from integrations.ms_auth import get_token_silent, is_configured


class TestIsConfigured:
    def test_configured_when_both_set(self):
        with (
            patch("integrations.ms_auth.MS_CLIENT_ID", "test-client-id"),
            patch("integrations.ms_auth.MS_TENANT_ID", "test-tenant-id"),
        ):
            assert is_configured() is True

    def test_not_configured_when_empty(self):
        with (
            patch("integrations.ms_auth.MS_CLIENT_ID", ""),
            patch("integrations.ms_auth.MS_TENANT_ID", ""),
        ):
            assert is_configured() is False

    def test_not_configured_when_partial(self):
        with (
            patch("integrations.ms_auth.MS_CLIENT_ID", "test-client-id"),
            patch("integrations.ms_auth.MS_TENANT_ID", ""),
        ):
            assert is_configured() is False


class TestGetTokenSilent:
    def test_returns_none_when_not_configured(self):
        with (
            patch("integrations.ms_auth.MS_CLIENT_ID", ""),
            patch("integrations.ms_auth.MS_TENANT_ID", ""),
        ):
            assert get_token_silent() is None

    def test_returns_none_when_no_accounts(self):
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = []

        with (
            patch("integrations.ms_auth.MS_CLIENT_ID", "test-id"),
            patch("integrations.ms_auth.MS_TENANT_ID", "test-tenant"),
            patch("integrations.ms_auth._get_app", return_value=mock_app),
        ):
            assert get_token_silent() is None

    def test_returns_token_from_cache(self):
        mock_app = MagicMock()
        mock_app.get_accounts.return_value = [{"username": "user@example.com"}]
        mock_app.acquire_token_silent.return_value = {"access_token": "cached-token"}
        mock_app.token_cache = MagicMock(has_state_changed=False)

        with (
            patch("integrations.ms_auth.MS_CLIENT_ID", "test-id"),
            patch("integrations.ms_auth.MS_TENANT_ID", "test-tenant"),
            patch("integrations.ms_auth._get_app", return_value=mock_app),
        ):
            assert get_token_silent() == "cached-token"
