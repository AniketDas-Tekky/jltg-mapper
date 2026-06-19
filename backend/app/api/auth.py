"""Bearer-token authentication.

Tokens are opaque per-player secrets stored in ``players.token``. The dependency resolves
the bearer credential to a :class:`~app.models.Player` or raises 401. A non-raising helper
(:func:`authenticate_token`) backs the WebSocket hub, which authenticates via query param.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Player

bearer_scheme = HTTPBearer(auto_error=False)


def authenticate_token(db: Session, token: str | None) -> Player | None:
    """Return the player for ``token`` or None. No exceptions (used by WS)."""
    if not token:
        return None
    return db.scalar(select(Player).where(Player.token == token))


def get_current_player(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Player:
    """FastAPI dependency: resolve the bearer token to a Player or raise 401."""
    token = credentials.credentials if credentials else None
    player = authenticate_token(db, token)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return player
