"""TARS Backend — FastAPI application entry point.

Usage:
    uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import init_db
from backend.tools.handlers import register_all_tools

# Configure logging
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="TARS",
    description="Executive Assistant Platform",
    version="2.0.0",
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize database and register tools on startup."""
    logger.info("Initializing TARS v2...")
    init_db()
    register_all_tools()
    logger.info("TARS v2 ready.")


# ---------------------------------------------------------------------------
# Register API routers
# ---------------------------------------------------------------------------

from backend.api.auth import router as auth_router
from backend.api.chat import router as chat_router
from backend.api.data import router as data_router

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(data_router)


# ---------------------------------------------------------------------------
# Serve React frontend (production build)
# ---------------------------------------------------------------------------

_FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if _FRONTEND_DIR.is_dir():
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve React SPA — all non-API routes go to index.html."""
        file_path = _FRONTEND_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_FRONTEND_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        return {"message": "TARS API running. Frontend not built yet — run 'npm run build' in frontend/"}


# ---------------------------------------------------------------------------
# Keep old web server compatibility (static files for voice UI)
# ---------------------------------------------------------------------------

_OLD_STATIC = Path(__file__).parent.parent / "web" / "static"
if _OLD_STATIC.is_dir():
    _js_dir = _OLD_STATIC / "js"
    if _js_dir.is_dir():
        app.mount("/static/js", StaticFiles(directory=_js_dir), name="legacy-js")

    @app.get("/call")
    async def legacy_call():
        """Legacy voice call UI."""
        return FileResponse(_OLD_STATIC / "call.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
