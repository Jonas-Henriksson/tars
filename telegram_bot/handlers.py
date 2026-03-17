"""Telegram bot command and message handlers."""
from __future__ import annotations

import asyncio
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
from integrations.ms_auth import (
    complete_device_flow,
    get_token_silent,
    is_configured,
    start_device_flow,
)

logger = logging.getLogger(__name__)

# Telegram message length limit
_MAX_MSG_LEN = 4096


async def _send_long_message(update: Update, text: str) -> None:
    """Send a message, splitting into chunks if it exceeds Telegram's limit."""
    if len(text) <= _MAX_MSG_LEN:
        await update.message.reply_text(text)
        return

    # Split on paragraph boundaries where possible
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > _MAX_MSG_LEN - 20:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

    for chunk in chunks:
        await update.message.reply_text(chunk.strip())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome message."""
    await update.message.reply_text(
        "Hey. I'm TARS, your executive assistant.\n\n"
        "I can help you manage your calendar, email, tasks, and documents "
        "through Microsoft 365. Just tell me what you need.\n\n"
        "Commands:\n"
        "/start — This message\n"
        "/login — Connect your Microsoft 365 account\n"
        "/briefing — Today's calendar, tasks & unread emails\n"
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
    if not is_configured():
        m365_status = "⬜ Microsoft 365: Not configured (set MS_CLIENT_ID and MS_TENANT_ID)"
    elif get_token_silent():
        m365_status = "✅ Microsoft 365: Connected"
    else:
        m365_status = "🔑 Microsoft 365: Configured but not signed in (use /login)"

    await update.message.reply_text(
        "TARS Status\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Telegram: Connected\n"
        "✅ Claude AI: Ready\n"
        f"{m365_status}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /login — start Microsoft 365 device-code authentication."""
    if not is_configured():
        await update.message.reply_text(
            "Microsoft 365 is not configured.\n"
            "Set MS_CLIENT_ID and MS_TENANT_ID in the .env file first."
        )
        return

    # Check if already signed in
    if get_token_silent():
        await update.message.reply_text(
            "You're already signed in to Microsoft 365. ✅"
        )
        return

    try:
        flow = start_device_flow()
    except RuntimeError as exc:
        await update.message.reply_text(f"Login failed: {exc}")
        return

    user_code = flow.get("user_code", "")
    verification_uri = flow.get("verification_uri", "https://microsoft.com/devicelogin")

    await update.message.reply_text(
        "To sign in to Microsoft 365:\n\n"
        f"1. Go to: {verification_uri}\n"
        f"2. Enter code: {user_code}\n"
        f"3. Sign in with your Microsoft account\n\n"
        "Waiting for you to complete sign-in..."
    )

    # Complete the flow in a thread to avoid blocking the bot
    try:
        token = await asyncio.to_thread(complete_device_flow, flow)
        await update.message.reply_text(
            "Successfully connected to Microsoft 365! ✅\n\n"
            "You can now ask me about your calendar, e.g.:\n"
            '• "What\'s on my calendar this week?"\n'
            '• "Schedule a meeting with Alex tomorrow at 2pm"\n\n'
            "Or try /briefing for a daily summary."
        )
    except RuntimeError as exc:
        await update.message.reply_text(f"Sign-in failed: {exc}")


async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /briefing — daily summary of calendar, tasks, and email."""
    if not is_configured() or not get_token_silent():
        await update.message.reply_text(
            "You need to be signed in to Microsoft 365 first.\n"
            "Use /login to connect your account."
        )
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    # Route through the agent so Claude formats it nicely
    chat_id = update.effective_chat.id
    try:
        response = await run(
            chat_id,
            "Give me my daily briefing: today's calendar events, my pending tasks, "
            "and any unread emails. Be concise but thorough.",
        )
        await _send_long_message(update, response)
    except Exception:
        logger.exception("Error generating briefing")
        await update.message.reply_text(
            "Couldn't generate your briefing. Try again in a moment."
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
        await _send_long_message(update, response)
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
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("briefing", briefing_command))
    # Message handler — must be added last (catches all text)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
