"""FastAPI application entrypoint.

This is a minimal skeleton for the dev environment: a health check and CORS wired up.
Game/event routes, the WebSocket hub, and the deduction engine are added in later work
(see ../docs/DESIGN.md).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

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
