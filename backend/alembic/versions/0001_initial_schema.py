"""Initial schema: games, players, events, derived_state.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-18

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


game_status = postgresql.ENUM(
    "lobby", "hiding", "seeking", "paused", "ended", name="game_status"
)
player_role = postgresql.ENUM("host", "seeker", "hider", name="player_role")


def _ts(name: str) -> sa.Column:
    """A non-null timestamptz column defaulting to now()."""
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _jsonb(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind()
    game_status.create(bind, checkfirst=True)
    player_role.create(bind, checkfirst=True)

    op.create_table(
        "games",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("join_code", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "lobby", "hiding", "seeking", "paused", "ended",
                name="game_status", create_type=False,
            ),
            nullable=False,
        ),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_games_join_code", "games", ["join_code"], unique=True)

    op.create_table(
        "players",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "host", "seeker", "hider", name="player_role", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        _ts("created_at"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_players_game_id", "players", ["game_id"])
    op.create_index("ix_players_token", "players", ["token"], unique=True)

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_seq", sa.BigInteger(), nullable=False),
        sa.Column("client_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        _jsonb("payload"),
        _ts("created_at"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "server_seq", name="uq_events_game_seq"),
    )
    op.create_index("ix_events_game_id", "events", ["game_id"])
    op.create_index(
        "ix_events_client_event_id", "events", ["client_event_id"], unique=True
    )

    op.create_table(
        "derived_state",
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_seq", sa.BigInteger(), nullable=False),
        _jsonb("remaining_zone_ids"),
        _jsonb("remaining_area", nullable=True),
        _jsonb("timers"),
        _jsonb("scoreboard"),
        sa.Column("status", sa.String(length=16), nullable=False),
        _ts("updated_at"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("game_id"),
    )


def downgrade() -> None:
    op.drop_table("derived_state")
    op.drop_index("ix_events_client_event_id", table_name="events")
    op.drop_index("ix_events_game_id", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_players_token", table_name="players")
    op.drop_index("ix_players_game_id", table_name="players")
    op.drop_table("players")
    op.drop_index("ix_games_join_code", table_name="games")
    op.drop_table("games")

    bind = op.get_bind()
    player_role.drop(bind, checkfirst=True)
    game_status.drop(bind, checkfirst=True)
