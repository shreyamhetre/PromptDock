import functools
import threading
from collections.abc import Callable, Sequence

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from promptdock.core import service
from promptdock.db.tables import EvalResult as EvalResultRow
from promptdock.errors import (
    AlreadyExistsError,
    GateFailedError,
    InvalidInputError,
    InvalidTemplateError,
    NothingToRollBackError,
    PromptNotFoundError,
    TagNotFoundError,
    TagNotSetError,
    VersionNotFoundError,
)
from promptdock.models import EvalResultIn, Gate, GateRule, PromptVersionCreate

NAME = "support-bot"


def _version(template: object = "Hi {{ name }}", **kwargs: object) -> PromptVersionCreate:
    return PromptVersionCreate.model_validate({"template": template, **kwargs})


def _evals(version: int, **scores: float) -> list[EvalResultIn]:
    return [
        EvalResultIn(prompt=NAME, version=version, metric=metric, score=score)
        for metric, score in scores.items()
    ]


def _with_versions(session: Session, count: int) -> None:
    service.create_prompt(session, NAME)
    for i in range(1, count + 1):
        service.create_version(session, NAME, _version(f"v{i} {{{{ name }}}}"))


# --- prompts -------------------------------------------------------------------------------


def test_create_prompt_adds_unset_default_tags(session: Session) -> None:
    prompt = service.create_prompt(session, NAME, description="FAQ bot")
    assert (prompt.name, prompt.project, prompt.description) == (NAME, "default", "FAQ bot")

    tags = service.list_tags(session, NAME)
    assert [(t.name, t.version) for t in tags] == [("dev", None), ("preprod", None), ("prod", None)]


def test_duplicate_prompt_rejected(session: Session) -> None:
    service.create_prompt(session, NAME)
    with pytest.raises(AlreadyExistsError):
        service.create_prompt(session, NAME)


def test_same_name_allowed_in_another_project(session: Session) -> None:
    service.create_prompt(session, NAME)
    service.create_prompt(session, NAME, project="team-b")
    assert [p.name for p in service.list_prompts(session, project="team-b")] == [NAME]


@pytest.mark.parametrize("name", ["", "has space", "-leading", "a/b"])
def test_invalid_prompt_names(session: Session, name: str) -> None:
    with pytest.raises(InvalidInputError):
        service.create_prompt(session, name)


def test_unknown_prompt(session: Session) -> None:
    with pytest.raises(PromptNotFoundError):
        service.get_prompt(session, "nope")


# --- versions ------------------------------------------------------------------------------


def test_versions_auto_increment_and_extract_variables(session: Session) -> None:
    service.create_prompt(session, NAME)
    v1 = service.create_version(session, NAME, _version("Hello {{ name }}, about {{ topic }}"))
    v2 = service.create_version(
        session,
        NAME,
        _version(
            [
                {"role": "system", "content": "You help with {{ product }}."},
                {"role": "user", "content": "{{ question }}"},
            ],
            model_config={"model": "gpt-4o", "temperature": 0.2},
            commit_message="switch to chat",
        ),
        actor="shreya",
    )

    assert (v1.version, v1.template_type, v1.variables) == (1, "text", ["name", "topic"])
    assert (v2.version, v2.template_type, v2.variables) == (2, "chat", ["product", "question"])
    assert v2.llm_config == {"model": "gpt-4o", "temperature": 0.2}
    assert (v2.commit_message, v2.created_by) == ("switch to chat", "shreya")
    assert [v.version for v in service.list_versions(session, NAME)] == [1, 2]


def test_identical_content_returns_latest_version(session: Session) -> None:
    service.create_prompt(session, NAME)
    first = service.create_version(session, NAME, _version(model_config={"a": 1, "b": 2}))
    # Same content, different key order and commit message: still a duplicate.
    again = service.create_version(
        session, NAME, _version(model_config={"b": 2, "a": 1}, commit_message="retry")
    )
    assert again.id == first.id
    assert len(service.list_versions(session, NAME)) == 1


def test_dedupe_only_compares_with_latest(session: Session) -> None:
    service.create_prompt(session, NAME)
    service.create_version(session, NAME, _version("A"))
    service.create_version(session, NAME, _version("B"))
    back_to_a = service.create_version(session, NAME, _version("A"))
    assert back_to_a.version == 3


def test_model_config_change_creates_new_version(session: Session) -> None:
    service.create_prompt(session, NAME)
    service.create_version(session, NAME, _version(model_config={"temperature": 0}))
    v2 = service.create_version(session, NAME, _version(model_config={"temperature": 1}))
    assert v2.version == 2


def test_template_syntax_error(session: Session) -> None:
    service.create_prompt(session, NAME)
    with pytest.raises(InvalidTemplateError, match="syntax error"):
        service.create_version(session, NAME, _version("Hello {{ name "))


def test_get_version(session: Session) -> None:
    _with_versions(session, 3)
    assert service.get_version(session, NAME, 2).template == "v2 {{ name }}"
    assert service.get_version(session, NAME).version == 3
    with pytest.raises(VersionNotFoundError):
        service.get_version(session, NAME, 9)


def test_version_on_unknown_prompt(session: Session) -> None:
    with pytest.raises(PromptNotFoundError):
        service.create_version(session, "nope", _version())


# --- tags ----------------------------------------------------------------------------------


def test_get_by_tag(session: Session) -> None:
    _with_versions(session, 2)
    with pytest.raises(TagNotSetError):
        service.get_by_tag(session, NAME, "prod")
    with pytest.raises(TagNotFoundError):
        service.get_by_tag(session, NAME, "canary")

    service.promote(session, NAME, "prod", 1, actor="shreya")
    assert service.get_by_tag(session, NAME, "prod").version == 1


def test_promote_creates_custom_tag(session: Session) -> None:
    _with_versions(session, 1)
    tag = service.promote(session, NAME, "canary-eu", 1, actor="parth")
    assert (tag.name, tag.version, tag.updated_by) == ("canary-eu", 1, "parth")
    assert "canary-eu" in [t.name for t in service.list_tags(session, NAME)]


def test_promote_unknown_version(session: Session) -> None:
    _with_versions(session, 1)
    with pytest.raises(VersionNotFoundError):
        service.promote(session, NAME, "prod", 5)


def test_promote_to_current_version_is_a_no_op(session: Session) -> None:
    _with_versions(session, 1)
    service.promote(session, NAME, "prod", 1)
    service.promote(session, NAME, "prod", 1)
    assert len(service.list_tag_events(session, NAME, "prod")) == 1


def test_rollback_walks_back_like_undo(session: Session) -> None:
    _with_versions(session, 4)
    for v in (1, 2, 3):
        service.promote(session, NAME, "prod", v)

    assert service.rollback(session, NAME, "prod").version == 2
    assert service.rollback(session, NAME, "prod").version == 1
    with pytest.raises(NothingToRollBackError):
        service.rollback(session, NAME, "prod")

    # A new promote after rolling back can itself be undone.
    service.promote(session, NAME, "prod", 4)
    assert service.rollback(session, NAME, "prod").version == 1


def test_rollback_with_no_history(session: Session) -> None:
    _with_versions(session, 1)
    with pytest.raises(NothingToRollBackError):
        service.rollback(session, NAME, "prod")
    service.promote(session, NAME, "prod", 1)
    with pytest.raises(NothingToRollBackError):
        service.rollback(session, NAME, "prod")


def test_tags_are_independent(session: Session) -> None:
    _with_versions(session, 2)
    service.promote(session, NAME, "dev", 1)
    service.promote(session, NAME, "dev", 2)
    service.promote(session, NAME, "prod", 1)
    service.rollback(session, NAME, "dev")
    versions = {t.name: t.version for t in service.list_tags(session, NAME)}
    assert versions == {"dev": 1, "preprod": None, "prod": 1}


# --- evals and gates -----------------------------------------------------------------------


def test_eval_results_round_trip(session: Session) -> None:
    _with_versions(session, 2)
    stored = service.add_eval_results(
        session,
        [
            EvalResultIn(
                prompt=NAME,
                version=1,
                metric="accuracy",
                score=0.87,
                run_id="run-1",
                evaluator="llm-judge",
                metadata={"dataset": "faq-100"},
            ),
            *_evals(2, accuracy=0.9),
        ],
    )
    assert [(r.version, r.score) for r in stored] == [(1, 0.87), (2, 0.9)]

    v1 = service.get_eval_results(session, NAME, 1)
    assert len(v1) == 1
    assert (v1[0].run_id, v1[0].evaluator, v1[0].metadata) == (
        "run-1",
        "llm-judge",
        {"dataset": "faq-100"},
    )
    assert len(service.get_eval_results(session, NAME)) == 2


def test_eval_batch_is_all_or_nothing(engine: Engine) -> None:
    with Session(engine) as s, s.begin():
        _with_versions(s, 1)

    with pytest.raises(VersionNotFoundError), Session(engine) as s, s.begin():
        service.add_eval_results(s, [*_evals(1, accuracy=0.9), *_evals(7, accuracy=0.9)])

    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(EvalResultRow)) == 0


def test_gate_uses_latest_score_per_metric(session: Session) -> None:
    _with_versions(session, 1)
    service.add_eval_results(session, _evals(1, accuracy=0.95))
    service.add_eval_results(session, _evals(1, accuracy=0.70))
    service.set_gate(session, NAME, "prod", Gate(rules=[GateRule(metric="accuracy", min=0.85)]))
    with pytest.raises(GateFailedError, match="0.7 is below the minimum 0.85"):
        service.promote(session, NAME, "prod", 1)


def test_create_eval_promote_gate_fail_rollback(session: Session) -> None:
    """The Phase 2 'done when' flow."""
    _with_versions(session, 3)
    gate = Gate(
        rules=[GateRule(metric="accuracy", min=0.85), GateRule(metric="latency_ms", max=1200)]
    )
    assert service.set_gate(session, NAME, "prod", gate).gate == gate

    service.add_eval_results(session, _evals(1, accuracy=0.88, latency_ms=900))
    service.add_eval_results(session, _evals(2, accuracy=0.91, latency_ms=700))
    service.add_eval_results(session, _evals(3, accuracy=0.80))

    service.promote(session, NAME, "prod", 1, actor="shreya")
    service.promote(session, NAME, "prod", 2, actor="shreya")

    with pytest.raises(GateFailedError) as refused:
        service.promote(session, NAME, "prod", 3, actor="parth")
    assert refused.value.failures == [
        "accuracy: 0.8 is below the minimum 0.85",
        "latency_ms: no eval result for this version",
    ]
    assert service.get_by_tag(session, NAME, "prod").version == 2

    with pytest.raises(InvalidInputError, match="requires a reason"):
        service.promote(session, NAME, "prod", 3, actor="parth", force=True)

    # Plan signature: promote(name, tag, version, actor, reason, force)
    service.promote(session, NAME, "prod", 3, "parth", "hotfix", True)
    assert service.get_by_tag(session, NAME, "prod").version == 3

    service.rollback(session, NAME, "prod", actor="shreya", reason="bad answers")
    assert service.get_by_tag(session, NAME, "prod").version == 2

    history = service.list_tag_events(session, NAME, "prod")
    assert [(e.action, e.from_version, e.to_version, e.forced, e.actor) for e in history] == [
        ("rollback", 3, 2, False, "shreya"),
        ("promote", 2, 3, True, "parth"),
        ("promote", 1, 2, False, "shreya"),
        ("promote", None, 1, False, "shreya"),
    ]
    assert history[1].reason == "hotfix"


def test_force_on_passing_gate_is_not_marked_forced(session: Session) -> None:
    _with_versions(session, 1)
    service.add_eval_results(session, _evals(1, accuracy=0.9))
    service.set_gate(session, NAME, "prod", Gate(rules=[GateRule(metric="accuracy", min=0.5)]))
    service.promote(session, NAME, "prod", 1, force=True, reason="just in case")
    assert service.list_tag_events(session, NAME, "prod")[0].forced is False


def test_require_better_than_current(session: Session) -> None:
    _with_versions(session, 3)
    gate = Gate(rules=[GateRule(metric="accuracy", min=0.5)], require_better_than_current=True)
    service.set_gate(session, NAME, "prod", gate)
    service.add_eval_results(session, _evals(1, accuracy=0.8))
    service.add_eval_results(session, _evals(2, accuracy=0.7))
    service.add_eval_results(session, _evals(3, accuracy=0.9))

    service.promote(session, NAME, "prod", 1)
    with pytest.raises(GateFailedError, match="worse than"):
        service.promote(session, NAME, "prod", 2)
    service.promote(session, NAME, "prod", 3)


def test_rollback_ignores_gate(session: Session) -> None:
    _with_versions(session, 2)
    service.promote(session, NAME, "prod", 1)
    service.promote(session, NAME, "prod", 2)
    service.set_gate(session, NAME, "prod", Gate(rules=[GateRule(metric="accuracy", min=0.9)]))
    assert service.rollback(session, NAME, "prod").version == 1


def test_clear_gate(session: Session) -> None:
    _with_versions(session, 1)
    service.set_gate(session, NAME, "prod", Gate(rules=[GateRule(metric="accuracy", min=0.9)]))
    assert service.set_gate(session, NAME, "prod", None).gate is None
    service.promote(session, NAME, "prod", 1)


# --- concurrency ---------------------------------------------------------------------------


def _run_concurrently(
    engine: Engine, jobs: Sequence[Callable[[Session], object]]
) -> list[BaseException]:
    barrier = threading.Barrier(len(jobs))
    errors: list[BaseException] = []

    def worker(job: Callable[[Session], object]) -> None:
        try:
            with Session(engine) as s, s.begin():
                barrier.wait()
                job(s)
        except BaseException as exc:  # noqa: BLE001 - collected and asserted below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(job,)) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_concurrent_promotes_keep_history_consistent(engine: Engine) -> None:
    count = 8
    with Session(engine) as s, s.begin():
        _with_versions(s, count)

    jobs = [
        functools.partial(service.promote, name=NAME, tag="prod", version=v)
        for v in range(1, count + 1)
    ]
    assert _run_concurrently(engine, jobs) == []

    with Session(engine) as s:
        history = list(reversed(service.list_tag_events(s, NAME, "prod")))
        assert len(history) == count
        # Each move starts where the previous one ended: no lost updates.
        assert history[0].from_version is None
        for prev, nxt in zip(history, history[1:], strict=False):
            assert nxt.from_version == prev.to_version
        assert service.get_by_tag(s, NAME, "prod").version == history[-1].to_version


def test_concurrent_version_creation_numbers_are_unique(engine: Engine) -> None:
    with Session(engine) as s, s.begin():
        service.create_prompt(s, NAME)

    jobs = [
        functools.partial(service.create_version, name=NAME, data=_version(f"t{i}"))
        for i in range(8)
    ]
    assert _run_concurrently(engine, jobs) == []

    with Session(engine) as s:
        assert [v.version for v in service.list_versions(s, NAME)] == list(range(1, 9))
