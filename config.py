"""
Configuration management with hot-reload capabilities.
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    DNSE_USERNAME: str
    DNSE_PASSWORD: str
    DNSE_ACCOUNT_NO: str
    TRADING_TOKEN: str
    ADMIN_SECRET: str

    # Optional settings with defaults
    API_BASE_URL: str = "https://api.dnse.com.vn"
    JWT_EXPIRATION_HOURS: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache for performance - settings are loaded once and reused.
    """
    return Settings()


def reload_settings() -> Settings:
    """
    Reload settings by clearing the cache and creating a new instance.
    Call this after updating the .env file to pick up new values.

    Returns:
        Settings: Fresh settings instance with updated values
    """
    get_settings.cache_clear()
    return get_settings()
