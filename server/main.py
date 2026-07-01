"""FastAPI entry point for the market review API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api.dates import router as dates_router
from server.api.review import router as review_router
from server.services.review_queries import DB_PATH


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

app = FastAPI(title="发家致富 API", description="A股复盘系统后端接口")

# CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(dates_router)
app.include_router(review_router)


@app.on_event("startup")
def ensure_database_schema():
    """Ensure old deployed databases have the latest columns."""
    from db import MarketDB

    db = MarketDB(DB_PATH)
    try:
        db.init_schema()
    finally:
        db.close()


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


# Production: serve frontend static files if web/dist exists
web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_dist.exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    assets_dir = web_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        requested = web_dist / full_path
        if full_path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(web_dist / "index.html")
