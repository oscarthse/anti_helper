"""
Application Configuration

Settings management using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://gravity:gravity@localhost:5432/antigravity"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Providers
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4o"

    # Application
    debug: bool = False
    log_level: str = "INFO"

    # Security
    confidence_review_threshold: float = 0.7

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
