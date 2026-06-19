"""SQLAlchemy 2.0 declarative models for the event-sourced game store.

Tables:
- ``games``         — one row per game session.
- ``players``       — participants; ``token`` is the bearer credential.
- ``events``        — the append-only event log; ``server_seq`` is monotonic per game,
                      ``client_event_id`` is unique for idempotency.
- ``derived_state`` — a reducer-computed snapshot cache (one row per game).

Geometry is stored as GeoJSON in JSONB (no PostGIS dependency in v1).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GameStatus(enum.StrEnum):
    lobby = "lobby"
    hiding = "hiding"
    seeking = "seeking"
    paused = "paused"
    ended = "ended"


class PlayerRole(enum.StrEnum):
    host = "host"
    seeker = "seeker"
    hider = "hider"


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Game(Base):
    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    join_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus, name="game_status"), default=GameStatus.lobby, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    players: Mapped[list[Player]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[PlayerRole] = mapped_column(Enum(PlayerRole, name="player_role"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    game: Mapped[Game] = relationship(back_populates="players")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("game_id", "server_seq", name="uq_events_game_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False
    )
    server_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    client_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, index=True, nullable=False
    )
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    game: Mapped[Game] = relationship(back_populates="events")


class DerivedState(Base):
    __tablename__ = "derived_state"

    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    last_seq: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    remaining_zone_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    remaining_area: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    scoreboard: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=GameStatus.lobby.value, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
