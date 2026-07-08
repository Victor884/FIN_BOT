class FinbotError(Exception):
    """Base exception for application errors."""


class ConfigurationError(FinbotError):
    """Raised when required configuration is missing or invalid."""

