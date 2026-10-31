"""The ``Prompt`` object returned by ``Client.get_prompt``."""

from datetime import datetime
from typing import Any

from promptdock.models import PromptVersion, Template, TemplateType
from promptdock.templates import render


class Prompt:
    """One prompt version, ready to render.

    ``tag`` is the tag it was fetched by (None when fetched by version number).
    ``is_stale`` is True when the database was unreachable and this is the last known
    good copy rather than a fresh read.
    """

    def __init__(
        self, data: PromptVersion, tag: str | None = None, *, is_stale: bool = False
    ) -> None:
        self._data = data
        self.tag = tag
        self.is_stale = is_stale

    @property
    def name(self) -> str:
        return self._data.prompt

    @property
    def version(self) -> int:
        return self._data.version

    @property
    def template(self) -> Template:
        return self._data.template

    @property
    def template_type(self) -> TemplateType:
        return self._data.template_type

    @property
    def variables(self) -> list[str]:
        return list(self._data.variables)

    @property
    def model_config(self) -> dict[str, Any]:
        """Model settings saved with this version (model, temperature, max_tokens, ...)."""
        return dict(self._data.llm_config)

    @property
    def commit_message(self) -> str | None:
        return self._data.commit_message

    @property
    def created_at(self) -> datetime:
        return self._data.created_at

    @property
    def data(self) -> PromptVersion:
        """The full stored version record."""
        return self._data

    def render(self, **values: Any) -> str | list[dict[str, str]]:
        """Fill in the template variables.

        Returns a string for text prompts and a list of ``{"role", "content"}`` dicts
        for chat prompts. Raises ``MissingVariableError`` naming any variable not given.
        """
        return render(self._data.template, self._data.variables, values)

    def __repr__(self) -> str:
        via = f" tag={self.tag!r}" if self.tag else ""
        stale = " stale" if self.is_stale else ""
        return f"<Prompt {self.name!r} v{self.version}{via}{stale}>"
