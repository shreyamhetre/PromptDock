"""Exceptions raised by PromptDock."""


class PromptDockError(Exception):
    """Base class for all PromptDock errors."""


class ConfigError(PromptDockError):
    """Configuration is missing or invalid (for example DATABASE_URL)."""


class DatabaseUnavailableError(PromptDockError):
    """The database could not be reached."""
