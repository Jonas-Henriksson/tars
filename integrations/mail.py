"""Microsoft 365 Mail integration — read inbox and send emails."""
from __future__ import annotations

import logging
from typing import Any

from integrations.ms_auth import get_token_silent
from integrations.ms_graph import graph_get, graph_post

logger = logging.getLogger(__name__)


def _require_token() -> str:
    """Get a valid token or raise with a helpful message."""
    token = get_token_silent()
    if token is None:
        raise RuntimeError(
            "Not signed in to Microsoft 365. "
            "Use /login to connect your account first."
        )
    return token


def _format_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a Graph API message object."""
    from_addr = msg.get("from", {}).get("emailAddress", {})
    return {
        "id": msg.get("id", ""),
        "subject": msg.get("subject", "(No subject)"),
        "from_name": from_addr.get("name", ""),
        "from_email": from_addr.get("address", ""),
        "received": msg.get("receivedDateTime", ""),
        "is_read": msg.get("isRead", False),
        "preview": msg.get("bodyPreview", ""),
        "has_attachments": msg.get("hasAttachments", False),
        "importance": msg.get("importance", "normal"),
    }


async def get_messages(
    folder: str = "inbox",
    unread_only: bool = False,
    max_results: int = 15,
) -> dict[str, Any]:
    """Get recent email messages.

    Args:
        folder: Mail folder — "inbox", "sentitems", "drafts", etc.
        unread_only: Only return unread messages.
        max_results: Max messages to return.

    Returns:
        Dict with "messages" list and "count".
    """
    token = _require_token()

    params: dict[str, str] = {
        "$top": str(max_results),
        "$orderby": "receivedDateTime desc",
        "$select": "subject,from,receivedDateTime,isRead,bodyPreview,hasAttachments,importance",
    }
    if unread_only:
        params["$filter"] = "isRead eq false"

    data = await graph_get(f"/me/mailFolders/{folder}/messages", token, params)
    messages = [_format_message(m) for m in data.get("value", [])]

    return {"messages": messages, "count": len(messages)}


async def read_message(message_id: str) -> dict[str, Any]:
    """Read the full body of a specific email.

    Args:
        message_id: The message ID (from get_messages).

    Returns:
        Dict with full message details including body.
    """
    token = _require_token()

    data = await graph_get(f"/me/messages/{message_id}", token)
    result = _format_message(data)
    body = data.get("body", {})
    result["body"] = body.get("content", "")
    result["body_type"] = body.get("contentType", "text")

    to_list = data.get("toRecipients", [])
    result["to"] = [
        r.get("emailAddress", {}).get("address", "") for r in to_list
    ]

    cc_list = data.get("ccRecipients", [])
    result["cc"] = [
        r.get("emailAddress", {}).get("address", "") for r in cc_list
    ]

    return result


async def send_message(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    importance: str = "normal",
) -> dict[str, Any]:
    """Send an email.

    Args:
        to: List of recipient email addresses.
        subject: Email subject.
        body: Email body (plain text).
        cc: Optional list of CC addresses.
        importance: "low", "normal", or "high".

    Returns:
        Dict confirming the message was sent.
    """
    token = _require_token()

    message: dict[str, Any] = {
        "subject": subject,
        "body": {"contentType": "text", "content": body},
        "toRecipients": [
            {"emailAddress": {"address": addr}} for addr in to
        ],
        "importance": importance,
    }

    if cc:
        message["ccRecipients"] = [
            {"emailAddress": {"address": addr}} for addr in cc
        ]

    await graph_post("/me/sendMail", token, {"message": message})

    return {
        "status": "sent",
        "to": to,
        "subject": subject,
    }
