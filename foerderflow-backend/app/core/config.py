"""Application settings, loaded from environment (pydantic-settings).

Mirrors the monolith's env contract (DATABASE_URL, AUTH_SECRET, EMAIL_*) so the
two systems can share infrastructure during the migration.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "FörderFlow API"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    api_prefix: str = "/api"

    # --- Database ---
    # SQLAlchemy 2 + psycopg3 sync driver. The monolith uses the same Postgres DB
    # (snake_case schema), so models preserve Prisma @@map table/column names.
    database_url: str = Field(
        default="postgresql+psycopg://foerderflow:password@localhost:5432/foerderflow",
    )

    # --- Auth (magic-link -> JWT, per migration decision) ---
    auth_secret: str = Field(default="dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 60 * 24  # 24h, matches DB-session feel
    magic_link_expires_minutes: int = 60 * 24
    magic_link_rate_limit_max: int = 5
    magic_link_rate_limit_window_seconds: int = 60 * 60  # 1h, matches middleware.ts

    # --- Frontend / CORS ---
    frontend_url: str = Field(default="http://localhost:3000")
    backend_url: str = Field(default="http://localhost:8000")

    # --- File storage (Belege uploads) ---
    upload_dir: str = Field(default="uploads")

    # --- Bescheid OCR (Mistral) ---
    mistral_api_key: str = Field(default="")

    # --- Email (magic link) ---
    email_server_host: str = Field(default="mailpit")
    email_server_port: int = Field(default=1025)
    email_server_user: str = Field(default="")
    email_server_password: str = Field(default="")
    email_from: str = Field(default="FörderFlow <noreply@foerderflow.local>")

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
