"""Custom exceptions for the Trove application."""


class TroveAppError(Exception):
    """Base exception for Trove application."""

    pass


class TroveAPIError(TroveAppError):
    """Exception raised when Trove API returns an error."""

    def __init__(self, status_code: int, message: str, response_text: str = ""):
        self.status_code = status_code
        self.message = message
        self.response_text = response_text
        super().__init__(f"Trove API error {status_code}: {message}")


class ConfigurationError(TroveAppError):
    """Exception raised for configuration errors."""

    pass


class NetworkError(TroveAppError):
    """Exception raised for network/connection errors."""

    pass
