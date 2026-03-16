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
from integrations.ms365_auth import (
    complete_device_flow,
    get_account_info,
    get_token_silent,
    is_configured,
    start_device_flow,
)

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome message."""
    await update.message.reply_text(
        "Hey. I'm TARS, your executive assistant.\n\n"
        "I can help you manage your calendar, email, tasks, and documents "
        "through Microsoft 365. Just tell me what you need.\n\n"
        "Commands:\n"
        "/start — This message\n"
        "/login — Connect Microsoft 365\n"
        "/logout — Disconnect Microsoft 365\n"
        "/clear — Reset our conversation\n"
        "/status — Check connected services\n\n"
        "Humor setting: 75%"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear — reset conversation history."""
    clear_history(update.effective_chat.id)
    await update.message.reply_text("Conversation cleared. Fresh start.")


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /login — authenticate with Microsoft 365 via device code flow."""
    if not is_configured():
        await update.message.reply_text(
            "Microsoft 365 is not configured.\n\n"
            "Set MS_CLIENT_ID and MS_TENANT_ID in your .env file.\n"
            "See scripts/register_app.ps1 to create an app registration."
        )
        return

    # Check if already authenticated
    if get_token_silent():
        account = get_account_info()
        name = account["name"] if account else "Unknown"
        await update.message.reply_text(
            f"Already connected to Microsoft 365 as {name}.\n"
            "Use /logout to disconnect, or /status to check."
        )
        return

    flow = start_device_flow()
    if not flow:
        await update.message.reply_text("Failed to start authentication. Check logs.")
        return

    await update.message.reply_text(
        "To connect Microsoft 365:\n\n"
        f"1. Go to https://microsoft.com/devicelogin\n"
        f"2. Enter code: {flow['user_code']}\n"
        f"3. Sign in with your Microsoft account\n\n"
        "Waiting for you to complete sign-in..."
    )

    # Wait for the user to complete auth (runs in background)
    token = await asyncio.to_thread(complete_device_flow, flow)
    if token:
        account = get_account_info()
        name = account["name"] if account else "your account"
        await update.message.reply_text(
            f"Connected to Microsoft 365 as {name}.\n\n"
            "I can now access your calendar, email, and tasks. Try:\n"
            '• "What\'s on my calendar this week?"\n'
            '• "Check my inbox"\n'
            '• "Schedule a meeting tomorrow at 2pm"'
        )
    else:
        await update.message.reply_text(
            "Authentication failed or timed out. Try /login again."
        )


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /logout — clear MS365 tokens."""
    from pathlib import Path
    cache_path = Path(__file__).parent.parent / "token_cache.json"
    if cache_path.exists():
        cache_path.unlink()
    await update.message.reply_text("Disconnected from Microsoft 365. Use /login to reconnect.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — show connection status."""
    if not is_configured():
        m365_status = "⬜ Microsoft 365: Not configured"
        m365_detail = "\n\nSet MS_CLIENT_ID and MS_TENANT_ID in .env to enable M365."
    elif get_token_silent():
        account = get_account_info()
        name = account["username"] if account else "Unknown"
        m365_status = f"✅ Microsoft 365: Connected ({name})"
        m365_detail = ""
    else:
        m365_status = "🔑 Microsoft 365: Configured (not signed in)"
        m365_detail = "\n\nUse /login to connect your Microsoft account."

    await update.message.reply_text(
        "TARS Status\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Telegram: Connected\n"
        "✅ Claude AI: Ready\n"
        f"{m365_status}\n"
        "━━━━━━━━━━━━━━━━━━━━"
        f"{m365_detail}"
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
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("status", status_command))
    # Message handler — must be added last (catches all text)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
