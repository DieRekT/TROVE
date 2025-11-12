"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Trove API Configuration
    trove_api_key: str = Field(default="", description="Trove API key from user profile")
    trove_base_url: str = Field(
        default="https://api.trove.nla.gov.au/v3", description="Base URL for Trove API"
    )
    trove_timeout: float = Field(default=15.0, description="HTTP request timeout in seconds")

    # Application Configuration
    app_title: str = Field(default="Trove Fetcher", description="Application title")
    app_version: str = Field(default="2.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    log_json: bool = Field(default=True, description="Use JSON log format")
    log_file: str | None = Field(default=None, description="Optional log file path")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
