"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="JLTG_", extra="ignore")

    app_name: str = "jltg-mapper"
    environment: str = "development"

    # Postgres connection (override in .env). Defaults to a local dev database.
    database_url: str = "postgresql+psycopg://jltg:jltg@localhost:5432/jltg"

    # Comma-separated list of allowed CORS origins for the frontend dev server.
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
