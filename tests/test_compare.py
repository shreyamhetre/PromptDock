"""Phase 6: gates, leaderboard, diff and the new-variables check, in every client mode."""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from promptdock import Client, GateFailedError
from promptdock.core import compare, service
from promptdock.errors import InvalidInputError, NewVariablesError
from promptdock.models import EvalResultIn, Gate, PromptVersionCreate

NAME = "support-bot"

MakeClient = Callable[..., Client]


def _versions(client: Client, count: int) -> None:
    client.create_prompt(NAME)
    for i in range(1, count + 1):
        client.create_version(NAME, f"Answer {{{{ question }}}} (style {i})")


def test_done_when(make_client: MakeClient) -> None:
    """Phase 6 'done when': a failing version is refused, rollback ignores the gate, and the
    leaderboard returns 20 versions in one call."""
    client = make_client()
    _versions(client, 20)
    client.add_eval_results(
        [
            {"prompt": NAME, "version": v, "metric": "accuracy", "score": 0.5 + v / 100}
            for v in range(1, 21)
        ]
        + [
            {"prompt": NAME, "version": v, "metric": "latency_ms", "score": 1000 + v}
            for v in (19, 20)
        ]
    )
    client.set_gate(NAME, "prod", {"rules": [{"metric": "accuracy", "min": 0.6}]})

    with pytest.raises(GateFailedError, match="0.55 is below the minimum 0.6"):
        client.promote(NAME, "prod", 5)
    client.promote(NAME, "prod", 15)
    client.promote(NAME, "prod", 20)
    client.set_gate(NAME, "prod", {"rules": [{"metric": "accuracy", "min": 0.99}]})
    assert client.rollback(NAME, "prod").version == 15  # v15 fails the new gate: ignored

    board = client.get_leaderboard(NAME)
    assert len(board.rows) == 20
    assert board.metrics == ["accuracy", "latency_ms"]
    assert [r.version for r in board.rows[:3]] == [20, 19, 18]
    assert board.rows[0].scores == {"accuracy": 0.7, "latency_ms": 1020}
    assert board.rows[2].scores["latency_ms"] is None
    assert {r.version: r.tags for r in board.rows}[15] == ["prod"]


def test_leaderboard_sorting(make_client: MakeClient) -> None:
    client = make_client()
    _versions(client, 4)
    client.add_eval_results(
        [
            {"prompt": NAME, "version": 1, "metric": "accuracy", "score": 0.7},
            {"prompt": NAME, "version": 2, "metric": "accuracy", "score": 0.9},
            {"prompt": NAME, "version": 3, "metric": "accuracy", "score": 0.8},
            {"prompt": NAME, "version": 3, "metric": "accuracy", "score": 0.95},  # latest wins
        ]
    )
    by_accuracy = client.get_leaderboard(NAME, sort_by="accuracy")
    assert [r.version for r in by_accuracy.rows] == [3, 2, 1, 4]  # unscored last
    ascending = client.get_leaderboard(NAME, sort_by="accuracy", descending=False)
    assert [r.version for r in ascending.rows] == [1, 2, 3, 4]
    oldest_first = client.get_leaderboard(NAME, sort_by="version", descending=False)
    assert [r.version for r in oldest_first.rows] == [1, 2, 3, 4]
    with pytest.raises(InvalidInputError, match="Cannot sort by 'nope'"):
        client.get_leaderboard(NAME, sort_by="nope")


def test_diff(make_client: MakeClient) -> None:
    client = make_client()
    client.create_prompt(NAME)
    client.create_version(
        NAME, "Hello {{ user }}.\nBe brief.", model_config={"model": "gpt-4o", "temperature": 0}
    )
    client.create_version(
        NAME,
        "Hello {{ user }}.\nBe friendly about {{ product }}.",
        model_config={"model": "gpt-4o-mini", "max_tokens": 200},
    )
    d = client.diff(NAME, 1, 2)
    assert d.template_changed
    assert (
        "-Be brief." in d.template_diff and "+Be friendly about {{ product }}." in d.template_diff
    )
    assert d.template_diff.startswith("--- v1\n+++ v2\n")
    changes = {c.key: (c.change, c.a, c.b) for c in d.model_config_changes}
    assert changes == {
        "max_tokens": ("added", None, 200),
        "model": ("changed", "gpt-4o", "gpt-4o-mini"),
        "temperature": ("removed", 0, None),
    }
    assert (d.variables_added, d.variables_removed) == (["product"], [])

    same = client.diff(NAME, 1, 1)
    assert (same.template_changed, same.template_diff, same.model_config_changes) == (
        False,
        "",
        [],
    )


def test_diff_of_chat_templates(make_client: MakeClient) -> None:
    client = make_client()
    client.create_prompt(NAME)
    client.create_version(NAME, [{"role": "system", "content": "A"}])
    client.create_version(
        NAME, [{"role": "system", "content": "A"}, {"role": "user", "content": "{{ q }}"}]
    )
    d = client.diff(NAME, 1, 2)
    assert "+[user]" in d.template_diff and "+{{ q }}" in d.template_diff


def test_new_variables_warn_or_refuse(make_client: MakeClient) -> None:
    client = make_client()
    client.create_prompt(NAME)
    client.create_version(NAME, "Hi {{ user }}")
    client.create_version(NAME, "Hi {{ user }}, about {{ product }} on {{ plan }}")
    assert client.promote(NAME, "prod", 1).warnings == []  # first promote: nothing to compare

    with pytest.raises(NewVariablesError, match="needs variables that v1"):
        client.promote(NAME, "prod", 2, strict=True)
    assert client.get_prompt(NAME, tag="prod").version == 1

    moved = client.promote(NAME, "prod", 2)
    assert moved.version == 2
    assert moved.warnings == [
        "v2 needs variables that v1 (current 'prod') did not: plan, product; "
        "make sure apps reading this tag pass them"
    ]


def test_require_better_than_current_allows_equal(session: Session) -> None:
    service.create_prompt(session, NAME)
    for i in range(3):
        service.create_version(session, NAME, PromptVersionCreate(template=f"t{i}"))
    service.set_gate(
        session,
        NAME,
        "prod",
        Gate.model_validate(
            {"rules": [{"metric": "accuracy", "min": 0.5}], "require_better_than_current": True}
        ),
    )
    service.add_eval_results(
        session,
        [
            EvalResultIn(prompt=NAME, version=1, metric="accuracy", score=0.8),
            EvalResultIn(prompt=NAME, version=2, metric="accuracy", score=0.8),
            EvalResultIn(prompt=NAME, version=3, metric="accuracy", score=0.79),
        ],
    )
    service.promote(session, NAME, "prod", 1)
    service.promote(session, NAME, "prod", 2)  # equal: at least as good
    with pytest.raises(GateFailedError, match="worse than the current version's 0.8"):
        service.promote(session, NAME, "prod", 3)
    assert compare.leaderboard(session, NAME).rows[1].tags == ["prod"]  # v2
