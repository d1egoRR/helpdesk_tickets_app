from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application runtime configuration validated at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Helpdesk Tickets App")
    app_env: Literal["development", "testing", "production"] = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    openai_api_key: SecretStr | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
