"""Integrations package — initializes MS365 tools when credentials are available."""
from integrations.ms365_auth import is_configured


def init_integrations() -> None:
    """Register all available integration tools."""
    if is_configured():
        from integrations.ms365_tools import register_ms365_tools
        register_ms365_tools()
