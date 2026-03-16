"""TARS — Executive Assistant Telegram Bot.

Entry point. Starts the Telegram bot with polling.

Usage:
    python app.py
"""
import logging
import sys

from telegram.ext import ApplicationBuilder

from config import TELEGRAM_BOT_TOKEN
from telegram_bot.handlers import register_handlers

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    logger.info("Starting TARS...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(app)
    logger.info("TARS is online. Polling for messages...")
    app.run_polling()


if __name__ == "__main__":
    main()
