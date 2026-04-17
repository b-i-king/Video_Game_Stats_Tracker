import os
from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Personal Supabase ─────────────────────────────────────────────────────────
    # Preferred: single DSN  →  PERSONAL_DATABASE_URL=postgresql://user:pass@host/db
    # Legacy fallback (still works if DSN not set): five separate parts below.
    # Remove legacy vars from Render after PERSONAL_DATABASE_URL is confirmed live.
    personal_database_url: str = Field(default="", alias="PERSONAL_DATABASE_URL")

    # Legacy parts — kept for backward compatibility only
    db_host:     str = Field(default="", alias="DB_URL")
    db_name:     str = Field(default="postgres", alias="DB_NAME")
    db_user:     str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_port:     int = Field(default=6543, alias="DB_PORT")

    # ── Public Supabase ───────────────────────────────────────────────────────────
    # Preferred: PUBLIC_DATABASE_URL  (rename from PUBLIC_DB_URL in Render)
    # Legacy alias kept until Render env var is renamed.
    public_database_url:   str = Field(default="", alias="PUBLIC_DATABASE_URL")
    public_db_url_legacy:  str = Field(default="", alias="PUBLIC_DB_URL")

    # ── Auth ──────────────────────────────────────────────────────────────────────
    secret_key: str                  = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str               = "HS256"
    access_token_expire_minutes: int = 60

    # ── API key ───────────────────────────────────────────────────────────────────
    # Preferred: API_KEY  (rename from FASTAPI_API_KEY in Render)
    api_key:         str = Field(default="", alias="API_KEY")
    api_key_legacy:  str = Field(default="", alias="FASTAPI_API_KEY")

    # ── Trusted / owner email lists (comma-separated) ─────────────────────────────
    trusted_emails: str = Field(default="", alias="TRUSTED_EMAILS")
    owner_emails: str   = Field(default="", alias="OWNER_EMAILS")

    # ── CORS ──────────────────────────────────────────────────────────────────────
    allowed_origins: str = Field(default="*", alias="ALLOWED_ORIGINS")

    # ── GCS ───────────────────────────────────────────────────────────────────────
    gcs_bucket: str = Field(default="gaming-stats-images-thebolgroup", alias="GCS_BUCKET_NAME")

    # ── Gemini ────────────────────────────────────────────────────────────────────
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # ── OBS overlay ───────────────────────────────────────────────────────────────
    obs_secret_key: str = Field(default="", alias="OBS_SECRET_KEY")

    # ── Cron ──────────────────────────────────────────────────────────────────────
    cron_secret: str = Field(default="", alias="CRON_SECRET")

    # ── Instagram / IFTTT ─────────────────────────────────────────────────────────
    instagram_access_token: str = Field(default="", alias="INSTAGRAM_ACCESS_TOKEN")
    ifttt_key: str              = Field(default="", alias="IFTTT_KEY")

    # ── Resolved DSNs — set by model_validator, used everywhere else ──────────────
    personal_db_url: str = ""
    public_db_url:   str = ""

    @model_validator(mode="after")
    def resolve_dsns(self) -> "Settings":
        # Personal: prefer new single DSN, fall back to legacy parts
        if self.personal_database_url:
            self.personal_db_url = self.personal_database_url
        elif self.db_host and self.db_user and self.db_password:
            self.personal_db_url = (
                f"postgresql://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )

        # Public: prefer new name, fall back to old name
        self.public_db_url = self.public_database_url or self.public_db_url_legacy

        # API key: prefer new name, fall back to old name
        if not self.api_key:
            self.api_key = self.api_key_legacy

        return self

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
        "populate_by_name": True,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
