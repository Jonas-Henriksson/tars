"""Web server for TARS voice call interface.

Serves the call UI and provides ephemeral tokens for OpenAI Realtime API.

Usage:
    python -m web.server
    Then open http://localhost:8080 in your browser.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

app = FastAPI(title="TARS Voice Call")

# TARS system instructions for the Realtime API
TARS_INSTRUCTIONS = """\
You are TARS, an executive assistant AI. You are direct, efficient, and \
occasionally witty — like the robot from Interstellar, but focused on \
productivity instead of space travel. Your humor setting is at 75%.

You help your user manage their calendar, email, tasks, and documents \
through Microsoft 365. Keep responses concise and conversational — you're \
in a voice call, so be natural and don't use markdown or bullet points. \
Speak like a helpful, slightly witty colleague.

If the user asks about calendar, email, tasks, or other M365 features, \
let them know those work through the Telegram bot for now, and you're \
here for general conversation and quick questions.\
"""


@app.get("/")
async def index():
    """Serve the call UI."""
    return FileResponse("web/static/call.html")


@app.get("/api/token")
async def get_ephemeral_token():
    """Get an ephemeral token for OpenAI Realtime API.

    The browser uses this to connect directly to OpenAI,
    so audio doesn't need to route through our server.
    """
    if not OPENAI_API_KEY:
        return JSONResponse(
            {"error": "OPENAI_API_KEY not configured"},
            status_code=500,
        )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/realtime/sessions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini-realtime-preview",
                    "voice": "ash",
                    "instructions": TARS_INSTRUCTIONS,
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "silence_duration_ms": 800,
                    },
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

        return JSONResponse({
            "token": data["client_secret"]["value"],
            "expires_at": data.get("expires_at"),
        })

    except httpx.HTTPStatusError as exc:
        logger.exception("Failed to get ephemeral token")
        return JSONResponse(
            {"error": f"OpenAI API error: {exc.response.status_code}"},
            status_code=502,
        )
    except Exception as exc:
        logger.exception("Failed to get ephemeral token")
        return JSONResponse(
            {"error": str(exc)},
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
