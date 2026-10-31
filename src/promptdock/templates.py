"""Jinja2 templates in a sandbox: variable detection and rendering."""

from collections.abc import Mapping, Sequence
from typing import Any

from jinja2 import StrictUndefined, TemplateError, TemplateSyntaxError, UndefinedError, meta
from jinja2.exceptions import SecurityError
from jinja2.sandbox import SandboxedEnvironment

from promptdock.errors import InvalidInputError, InvalidTemplateError, MissingVariableError
from promptdock.models import Template

# Prompts are plain text, not HTML, so no autoescaping. StrictUndefined turns a missing
# value into an error instead of silently rendering an empty string.
_env = SandboxedEnvironment(undefined=StrictUndefined, keep_trailing_newline=True)


def extract_variables(template: Template) -> list[str]:
    """Return the sorted names of the variables a template uses.

    For chat templates, variables from every message are combined.
    Raises ``InvalidTemplateError`` if any part has a Jinja syntax error.
    """
    names: set[str] = set()
    for source in _sources(template):
        try:
            names |= meta.find_undeclared_variables(_env.parse(source))
        except TemplateSyntaxError as exc:
            raise InvalidTemplateError(
                f"Template syntax error on line {exc.lineno}: {exc.message}"
            ) from None
    return sorted(names)


def render(
    template: Template, variables: Sequence[str], values: Mapping[str, Any]
) -> str | list[dict[str, str]]:
    """Render a template with ``values``.

    Text templates return a string; chat templates return a list of
    ``{"role": ..., "content": ...}`` dicts. Raises ``MissingVariableError`` naming every
    variable without a value. Extra values are ignored.
    """
    missing = [name for name in variables if name not in values]
    if missing:
        raise MissingVariableError(missing)
    if isinstance(template, str):
        return _render_one(template, values)
    return [{"role": m.role, "content": _render_one(m.content, values)} for m in template]


def _render_one(source: str, values: Mapping[str, Any]) -> str:
    try:
        return _env.from_string(source).render(values)
    except SecurityError as exc:
        raise InvalidInputError(f"Template tried an unsafe operation: {exc}") from None
    except UndefinedError as exc:
        raise InvalidInputError(f"Template rendering failed: {exc.message}") from None
    except TemplateError as exc:
        raise InvalidTemplateError(f"Template rendering failed: {exc}") from None


def _sources(template: Template) -> list[str]:
    return [template] if isinstance(template, str) else [m.content for m in template]
