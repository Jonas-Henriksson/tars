"""Chat API — WebSocket streaming and REST conversation management."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.auth.jwt import verify_token
from backend.auth.middleware import CurrentUser, get_current_user
from backend.database import get_db
from backend.database.queries import (
    generate_id, get_conversation_messages, get_row,
    insert_row, list_rows, now_iso, update_row,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ConversationCreate(BaseModel):
    title: str = ""
    team_id: str = ""


class MessageSend(BaseModel):
    content: str
    conversation_id: str = ""


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@router.get("/conversations")
async def list_conversations(
    team_id: str = "",
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
):
    """List user's conversations."""
    with get_db() as db:
        filters: dict[str, Any] = {"user_id": user.id, "is_archived": 0}
        if team_id:
            filters["team_id"] = team_id
        conversations = list_rows(db, "conversations", filters=filters, limit=limit)

    return {"conversations": conversations}


@router.post("/conversations", status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new conversation."""
    conv_id = generate_id()
    with get_db() as db:
        conv = insert_row(db, "conversations", {
            "id": conv_id,
            "user_id": user.id,
            "team_id": body.team_id or user.team_id,
            "channel": "web",
            "title": body.title or "New conversation",
        })

    return {"conversation": conv}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a conversation with its messages."""
    with get_db() as db:
        conv = get_row(db, "conversations", conversation_id)
        if not conv or conv["user_id"] != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = get_conversation_messages(db, conversation_id)

    return {"conversation": conv, "messages": messages}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    limit: int = 50,
    before: str = "",
    user: CurrentUser = Depends(get_current_user),
):
    """Get messages for a conversation with pagination."""
    with get_db() as db:
        conv = get_row(db, "conversations", conversation_id)
        if not conv or conv["user_id"] != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = get_conversation_messages(
            db, conversation_id, limit=limit, before=before,
        )

    return {"messages": messages}


@router.delete("/conversations/{conversation_id}")
async def archive_conversation(
    conversation_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Archive (soft-delete) a conversation."""
    with get_db() as db:
        conv = get_row(db, "conversations", conversation_id)
        if not conv or conv["user_id"] != user.id:
            raise HTTPException(status_code=404)
        update_row(db, "conversations", conversation_id, {"is_archived": 1})

    return {"message": "Conversation archived"}


# ---------------------------------------------------------------------------
# WebSocket — real-time chat with streaming
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages WebSocket connections for real-time chat."""

    def __init__(self) -> None:
        self.active: dict[str, WebSocket] = {}  # user_id -> websocket

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        self.active.pop(user_id, None)

    async def send_json(self, user_id: str, data: dict) -> None:
        ws = self.active.get(user_id)
        if ws:
            await ws.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with TARS.

    Protocol:
    - Client sends: {"type": "message", "content": "...", "conversation_id": "..."}
    - Server sends: {"type": "token", "content": "..."} for streaming
    - Server sends: {"type": "message_complete", "content": "...", "message_id": "..."}
    - Server sends: {"type": "tool_call", "name": "...", "arguments": {...}}
    - Server sends: {"type": "tool_result", "name": "...", "result": {...}}
    - Server sends: {"type": "error", "detail": "..."}
    """
    # Authenticate via query param
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = verify_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = payload.get("sub", "")
    team_id = payload.get("team_id", "")

    await manager.connect(user_id, websocket)
    logger.info("WebSocket connected: user=%s", user_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "message":
                await _handle_chat_message(
                    websocket, user_id, team_id,
                    data.get("content", ""),
                    data.get("conversation_id", ""),
                )
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s", user_id)
    except Exception as exc:
        logger.exception("WebSocket error: user=%s", user_id)
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except Exception:
            pass
    finally:
        manager.disconnect(user_id)


async def _handle_chat_message(
    websocket: WebSocket,
    user_id: str,
    team_id: str,
    content: str,
    conversation_id: str,
) -> None:
    """Process a chat message through the TARS agent and stream the response."""
    if not content.strip():
        return

    # Create or get conversation
    if not conversation_id:
        conversation_id = generate_id()
        with get_db() as db:
            insert_row(db, "conversations", {
                "id": conversation_id,
                "user_id": user_id,
                "team_id": team_id,
                "channel": "web",
                "title": content[:50],
            })
        await websocket.send_json({
            "type": "conversation_created",
            "conversation_id": conversation_id,
        })

    # Save user message
    user_msg_id = generate_id()
    with get_db() as db:
        insert_row(db, "messages", {
            "id": user_msg_id,
            "conversation_id": conversation_id,
            "role": "user",
            "content": content,
        })

    # Run agent with streaming
    try:
        from backend.agent.core import run_streaming

        full_response = ""
        async for event in run_streaming(user_id, team_id, conversation_id, content):
            event_type = event.get("type", "")

            if event_type == "token":
                full_response += event.get("content", "")
                await websocket.send_json(event)
            elif event_type in ("tool_call", "tool_result"):
                await websocket.send_json(event)
            elif event_type == "error":
                await websocket.send_json(event)
                return

        # Save assistant message
        msg_id = generate_id()
        with get_db() as db:
            insert_row(db, "messages", {
                "id": msg_id,
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": full_response,
            })
            update_row(db, "conversations", conversation_id, {
                "updated_at": now_iso(),
            })

        await websocket.send_json({
            "type": "message_complete",
            "content": full_response,
            "message_id": msg_id,
            "conversation_id": conversation_id,
        })

    except Exception as exc:
        logger.exception("Agent error for user %s", user_id)
        await websocket.send_json({"type": "error", "detail": str(exc)})
