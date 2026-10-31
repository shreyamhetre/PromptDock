import pytest

from promptdock.errors import InvalidInputError, MissingVariableError
from promptdock.models import ChatMessage
from promptdock.templates import extract_variables, render


def test_render_text() -> None:
    assert render("Hi {{ name }}!", ["name"], {"name": "Ana"}) == "Hi Ana!"


def test_render_chat() -> None:
    template = [
        ChatMessage(role="system", content="You support {{ product }}."),
        ChatMessage(role="user", content="{{ question }}"),
    ]
    assert render(template, ["product", "question"], {"product": "X", "question": "Why?"}) == [
        {"role": "system", "content": "You support X."},
        {"role": "user", "content": "Why?"},
    ]


def test_missing_variables_are_all_named() -> None:
    template = "{{ a }} {{ b }} {{ c }}"
    with pytest.raises(MissingVariableError) as err:
        render(template, extract_variables(template), {"b": 1})
    assert err.value.missing == ["a", "c"]
    assert str(err.value) == "Missing template variables: a, c"


def test_extra_values_are_ignored() -> None:
    assert render("{{ a }}", ["a"], {"a": 1, "unused": 2}) == "1"


def test_jinja_features_work() -> None:
    template = "{% for item in items %}- {{ item | upper }}\n{% endfor %}"
    assert render(template, extract_variables(template), {"items": ["a", "b"]}) == "- A\n- B\n"


def test_no_html_escaping() -> None:
    assert render("{{ x }}", ["x"], {"x": "<b>&</b>"}) == "<b>&</b>"


def test_sandbox_blocks_unsafe_access() -> None:
    template = "{{ x.__class__.__mro__[1].__subclasses__() }}"
    with pytest.raises(InvalidInputError):
        render(template, ["x"], {"x": ""})
