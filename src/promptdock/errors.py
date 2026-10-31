"""Exceptions raised by PromptDock."""


class PromptDockError(Exception):
    """Base class for all PromptDock errors."""


class ConfigError(PromptDockError):
    """Configuration is missing or invalid (for example DATABASE_URL)."""


class DatabaseUnavailableError(PromptDockError):
    """The database could not be reached."""


class InvalidInputError(PromptDockError, ValueError):
    """A name, template or argument is not valid."""


class InvalidTemplateError(InvalidInputError):
    """A template has a Jinja syntax error."""


class NotFoundError(PromptDockError, LookupError):
    """A requested object does not exist."""


class PromptNotFoundError(NotFoundError):
    pass


class VersionNotFoundError(NotFoundError):
    pass


class TagNotFoundError(NotFoundError):
    pass


class TagNotSetError(NotFoundError):
    """The tag exists but has never been promoted to a version."""


class AlreadyExistsError(PromptDockError):
    """An object with the same name already exists."""


class GateFailedError(PromptDockError):
    """A promote was refused because the version does not pass the tag's gate."""

    def __init__(self, prompt: str, tag: str, failures: list[str]) -> None:
        self.prompt = prompt
        self.tag = tag
        self.failures = failures
        details = "\n".join(f"  - {failure}" for failure in failures)
        super().__init__(
            f"Gate for tag '{tag}' on prompt '{prompt}' failed:\n{details}\n"
            "Pass force=True with a reason to bypass it."
        )


class NothingToRollBackError(PromptDockError):
    """The tag has no earlier version to roll back to."""


class MissingVariableError(InvalidInputError):
    """``render()`` was called without values for some template variables."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Missing template variables: {', '.join(missing)}")
