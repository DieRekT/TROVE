"""FastAPI dependencies."""

from app.config import get_settings
from app.trove_client import TroveClient


def get_trove_client() -> TroveClient:
    """Get Trove client instance via dependency injection."""
    settings = get_settings()
    if not settings.trove_api_key:
        from app.exceptions import ConfigurationError

        raise ConfigurationError("TROVE_API_KEY is not configured. Please set it in .env")
    return TroveClient(
        api_key=settings.trove_api_key,
        base_url=settings.trove_base_url,
        timeout=settings.trove_timeout,
    )
