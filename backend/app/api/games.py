"""Game lifecycle endpoints: create a game, join by code."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.schemas import (
    CreateGameRequest,
    CreateGameResponse,
    JoinGameRequest,
    JoinGameResponse,
)

router = APIRouter(prefix="/games", tags=["games"])


@router.post("", response_model=CreateGameResponse, status_code=status.HTTP_201_CREATED)
def create_game(body: CreateGameRequest, db: Session = Depends(get_db)) -> CreateGameResponse:
    game, host = services.create_game(db, host_name=body.host_name)
    return CreateGameResponse(
        game_id=game.id,
        join_code=game.join_code,
        player_id=host.id,
        token=host.token,
    )


@router.post(
    "/{join_code}/join",
    response_model=JoinGameResponse,
    status_code=status.HTTP_201_CREATED,
)
def join_game(
    join_code: str, body: JoinGameRequest, db: Session = Depends(get_db)
) -> JoinGameResponse:
    try:
        game, player = services.join_game(
            db, join_code=join_code.upper(), name=body.name, role=body.role
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Game not found"
        ) from None
    return JoinGameResponse(
        game_id=game.id,
        player_id=player.id,
        token=player.token,
        role=player.role.value,
    )
