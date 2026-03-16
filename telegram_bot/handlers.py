"""Telegram bot command and message handlers."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent.core import clear_history, run

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome message."""
    await update.message.reply_text(
        "Hey. I'm TARS, your executive assistant.\n\n"
        "I can help you manage your calendar, email, tasks, and documents "
        "through Microsoft 365. Just tell me what you need.\n\n"
        "Commands:\n"
        "/start — This message\n"
        "/clear — Reset our conversation\n"
        "/status — Check connected services\n\n"
        "Humor setting: 75%"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear — reset conversation history."""
    clear_history(update.effective_chat.id)
    await update.message.reply_text("Conversation cleared. Fresh start.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — show connection status."""
    # Phase 1: No M365 integrations yet
    await update.message.reply_text(
        "TARS Status\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Telegram: Connected\n"
        "✅ Claude AI: Ready\n"
        "⬜ Microsoft 365: Not configured\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "M365 integration coming in a future update."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all regular text messages — route to TARS agent."""
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Show typing indicator while processing
    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        response = await run(chat_id, user_text)
        await update.message.reply_text(response)
    except Exception:
        logger.exception("Error processing message")
        await update.message.reply_text(
            "Something went wrong on my end. Try again in a moment."
        )


def register_handlers(app: Application) -> None:
    """Register all handlers with the Telegram application."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))
    # Message handler — must be added last (catches all text)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
