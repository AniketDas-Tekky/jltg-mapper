"""Database engine, session factory, and FastAPI dependency.

Uses a synchronous SQLAlchemy 2.0 engine over the psycopg driver configured in
``app.config.settings.database_url``. Sync keeps the event-sourced write path simple
(SELECT ... FOR UPDATE for server_seq assignment) and matches the driver in `.env`.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
