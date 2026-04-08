import os
from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Personal Supabase — individual parts matching existing Render env vars ───
    # TODO Phase 3 cleanup: consolidate into a single PERSONAL_DATABASE_URL DSN
    # and remove these five vars from Render once Flask is archived.
    db_host: str     = Field(default="", alias="DB_URL")       # host only, e.g. aws-0-us-west-2.pooler.supabase.com
    db_name: str     = Field(default="postgres", alias="DB_NAME")
    db_user: str     = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_port: int     = Field(default=6543, alias="DB_PORT")    # 6543 = Supabase transaction pooler

    # ── Public Supabase — full DSN ────────────────────────────────────────────────
    # TODO Phase 3 cleanup: rename to PUBLIC_DATABASE_URL for consistency
    public_db_url: str = Field(default="", alias="PUBLIC_DB_URL")

    # ── Auth ──────────────────────────────────────────────────────────────────────
    secret_key: str            = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str         = "HS256"
    access_token_expire_minutes: int = 60

    # ── API key — separate from FLASK_API_KEY during transition ───────────────────
    # TODO Phase 3 cleanup: rename to API_KEY once Flask is archived
    api_key: str               = Field(default="", alias="FASTAPI_API_KEY")

    # ── Trusted / owner email lists (comma-separated) ─────────────────────────────
    trusted_emails: str        = Field(default="", alias="TRUSTED_EMAILS")
    owner_emails: str          = Field(default="", alias="OWNER_EMAILS")

    # ── CORS ──────────────────────────────────────────────────────────────────────
    allowed_origins: str       = Field(default="*", alias="ALLOWED_ORIGINS")

    # ── GCS ───────────────────────────────────────────────────────────────────────
    gcs_bucket: str            = Field(default="gaming-stats-images-thebolgroup", alias="GCS_BUCKET_NAME")

    # ── Gemini ────────────────────────────────────────────────────────────────────
    gemini_api_key: str        = Field(default="", alias="GEMINI_API_KEY")

    # ── OBS overlay — browser source uses ?key= query param (no JWT possible) ────
    obs_secret_key: str         = Field(default="", alias="OBS_SECRET_KEY")

    # ── Cron — protects /api/process_queue called by Render cron job ─────────────
    cron_secret: str            = Field(default="", alias="CRON_SECRET")

    # ── Instagram / IFTTT ─────────────────────────────────────────────────────────
    instagram_access_token: str = Field(default="", alias="INSTAGRAM_ACCESS_TOKEN")
    ifttt_key: str              = Field(default="", alias="IFTTT_KEY")

    # ── Constructed DSN — built from parts, used by database.py ──────────────────
    # Not an env var — derived automatically via model_validator below
    personal_db_url: str = ""

    @model_validator(mode="after")
    def build_personal_dsn(self) -> "Settings":
        """Construct the asyncpg DSN from individual Render env var parts."""
        if self.db_host and self.db_user and self.db_password:
            self.personal_db_url = (
                f"postgresql://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
        "populate_by_name": True,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
