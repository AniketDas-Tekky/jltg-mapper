"""Pytest fixtures.

Reducer tests are pure and need no DB. REST/WS tests require Postgres (JSONB/UUID/enum
types) and are skipped automatically if the database is unreachable, so ``pytest`` stays
green on a machine without Docker while still running fully when ``make db-up`` is active.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings


def _db_available(url: str) -> bool:
    try:
        eng = create_engine(url)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:  # noqa: BLE001
        return False


DB_URL = settings.database_url
DB_AVAILABLE = _db_available(DB_URL)

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="Postgres not reachable (run `make db-up`)"
)


@pytest.fixture()
def db_engine():
    """Engine bound to a fresh, isolated schema per test for clean separation."""
    import app.models  # noqa: F401 — register tables on Base.metadata
    from app.db import Base

    schema = f"test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(DB_URL)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    admin.dispose()

    engine = create_engine(
        DB_URL,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        admin = create_engine(DB_URL)
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture()
def app_client(db_engine):
    """A TestClient whose get_db dependency points at the isolated test schema."""
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app

    TestSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # Point both the REST dependency and the WS hub's SessionLocal at the test schema.
    import app.db as db_module
    import app.websocket as ws_module

    app.dependency_overrides[get_db] = _override_get_db
    original_sessionlocal = db_module.SessionLocal
    db_module.SessionLocal = TestSession
    ws_module.SessionLocal = TestSession

    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        db_module.SessionLocal = original_sessionlocal
        ws_module.SessionLocal = original_sessionlocal
