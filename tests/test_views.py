from sqlalchemy import text
from sqlalchemy.orm import Session

from promptdock.core import service
from promptdock.models import EvalResultIn, PromptVersionCreate

NAME = "support-bot"


def _rows(session: Session, query: str) -> list[tuple[object, ...]]:
    return [tuple(row) for row in session.execute(text(query)).all()]


def _setup(session: Session) -> None:
    service.create_prompt(session, NAME)
    for template in ("v1 {{ a }}", "v2 {{ a }}"):
        service.create_version(session, NAME, PromptVersionCreate(template=template))
    service.promote(session, NAME, "dev", 2, actor="shreya")
    service.promote(session, NAME, "prod", 1, actor="shreya")
    service.promote(session, NAME, "prod", 2, actor="parth")
    service.rollback(session, NAME, "prod", actor="parth", reason="broken")
    service.promote(session, NAME, "canary", 2)
    service.add_eval_results(
        session, [EvalResultIn(prompt=NAME, version=2, metric="accuracy", score=0.9)]
    )


def test_prompt_status(session: Session) -> None:
    _setup(session)
    assert _rows(
        session,
        "SELECT prompt, latest_version, dev, preprod, prod, other_tags FROM v_prompt_status",
    ) == [(NAME, 2, 2, None, 1, "canary=v2")]


def test_versions_list_current_tags(session: Session) -> None:
    _setup(session)
    assert _rows(session, "SELECT prompt, version, tags FROM v_versions ORDER BY version") == [
        (NAME, 1, "prod"),
        (NAME, 2, "canary, dev"),
    ]


def test_tags(session: Session) -> None:
    _setup(session)
    assert _rows(session, "SELECT tag, version FROM v_tags ORDER BY tag") == [
        ("canary", 2),
        ("dev", 2),
        ("preprod", None),
        ("prod", 1),
    ]


def test_tag_history(session: Session) -> None:
    _setup(session)
    assert _rows(
        session,
        "SELECT step, tag, action, from_version, to_version, actor, reason"
        " FROM v_tag_history ORDER BY step",
    ) == [
        (1, "dev", "promote", None, 2, "shreya", None),
        (2, "prod", "promote", None, 1, "shreya", None),
        (3, "prod", "promote", 1, 2, "parth", None),
        (4, "prod", "rollback", 2, 1, "parth", "broken"),
        (5, "canary", "promote", None, 2, None, None),
    ]


def test_eval_results(session: Session) -> None:
    _setup(session)
    assert _rows(session, "SELECT prompt, version, metric, score FROM v_eval_results") == [
        (NAME, 2, "accuracy", 0.9)
    ]


def test_tag_ids_have_no_gaps(session: Session) -> None:
    _setup(session)
    ids = session.execute(text("SELECT id FROM tags ORDER BY id")).scalars().all()
    assert ids == list(range(1, len(ids) + 1))
