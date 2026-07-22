from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://alma:alma_secret@127.0.0.1:5432/alma_db"
    secret_key: str = "dev"
    environment: str = "development"
    allowed_origins: str = "http://localhost:3000,http://localhost:8080"

    chatbot_base_url: str = "http://127.0.0.1:8000"
    chatbot_service_token: str = ""
    chatbot_timeout_seconds: float = 120.0
    chatbot_required: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
