"""Configuration loader — reads environment variables from .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the tars/ directory (or parent)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()  # Fall back to default .env search

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID", "")
MS_TENANT_ID = os.environ.get("MS_TENANT_ID", "")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
