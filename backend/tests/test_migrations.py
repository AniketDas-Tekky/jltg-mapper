"""Alembic migration round-trip test (requires Postgres; skipped if unreachable).

Runs ``upgrade head`` -> ``downgrade base`` -> ``upgrade head`` inside an isolated schema
so it can't disturb application data, verifying the initial migration is reversible.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.config import settings
from tests.conftest import requires_db

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config(schema: str):
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # Route every connection to the isolated schema via search_path. configparser treats
    # '%' as interpolation, so escape it ('%%') when injecting into the URL option.
    url = settings.database_url
    sep = "?" if "?" not in url else "&"
    cfg.set_main_option(
        "sqlalchemy.url",
        f"{url}{sep}options=-csearch_path%%3D{schema}",
    )
    return cfg


@requires_db
def test_migration_upgrade_downgrade_roundtrip():
    from alembic import command

    schema = f"mig_{uuid.uuid4().hex[:10]}"
    admin = create_engine(settings.database_url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
    )
    cfg = _alembic_config(schema)
    try:
        command.upgrade(cfg, "head")
        tables = set(inspect(engine).get_table_names(schema=schema))
        assert {"games", "players", "events", "derived_state"}.issubset(tables)

        command.downgrade(cfg, "base")
        tables_after = set(inspect(engine).get_table_names(schema=schema))
        assert "games" not in tables_after

        # Round-trips back up cleanly.
        command.upgrade(cfg, "head")
        tables_again = set(inspect(engine).get_table_names(schema=schema))
        assert {"games", "players", "events", "derived_state"}.issubset(tables_again)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
