"""Jinja2 templates: variable detection (rendering arrives with the client)."""

from jinja2 import TemplateSyntaxError, meta
from jinja2.sandbox import SandboxedEnvironment

from promptdock.errors import InvalidTemplateError
from promptdock.models import Template

_env = SandboxedEnvironment()


def extract_variables(template: Template) -> list[str]:
    """Return the sorted names of the variables a template uses.

    For chat templates, variables from every message are combined.
    Raises ``InvalidTemplateError`` if any part has a Jinja syntax error.
    """
    sources = [template] if isinstance(template, str) else [m.content for m in template]
    names: set[str] = set()
    for source in sources:
        try:
            names |= meta.find_undeclared_variables(_env.parse(source))
        except TemplateSyntaxError as exc:
            raise InvalidTemplateError(
                f"Template syntax error on line {exc.lineno}: {exc.message}"
            ) from None
    return sorted(names)
