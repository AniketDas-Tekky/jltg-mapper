"""FastAPI application entrypoint.

Wires CORS, the REST routers (games + events under ``/api``), and the WebSocket hub
(``/ws/{game_id}``). The deduction engine (task 8) is plugged into the reducer separately.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import events, games
from app.config import settings
from app.websocket import router as ws_router

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by the platform and the frontend connectivity check."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


app.include_router(games.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(ws_router)
