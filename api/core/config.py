import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase / Postgres
    personal_db_url: str = os.getenv("SUPABASE_DB_URL", "")   # asyncpg DSN, port 6543 (Transaction pooler)
    public_db_url: str   = os.getenv("PUBLIC_DB_URL", "")     # asyncpg DSN for public pool

    # Auth
    secret_key: str = os.getenv("SECRET_KEY", "change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60  # 60 min

    # API key — separate from FLASK_API_KEY so both services run independently
    # during transition. Deprecate FLASK_API_KEY when Flask is archived.
    api_key: str = os.getenv("FASTAPI_API_KEY", "")

    # Trusted / owner email lists (comma-separated)
    trusted_emails: str = os.getenv("TRUSTED_EMAILS", "")
    owner_emails: str = os.getenv("OWNER_EMAILS", "")

    # CORS — comma-separated list in env
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "*")

    # GCS
    gcs_bucket: str = os.getenv("GCS_BUCKET_NAME", "gaming-stats-images-thebolgroup")

    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    # Instagram / IFTTT
    instagram_access_token: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    ifttt_key: str = os.getenv("IFTTT_KEY", "")

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
