from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from promptdock.models import (
    EvalResultIn,
    Gate,
    GateRule,
    PromptVersion,
    PromptVersionCreate,
    Tag,
)

NOW = datetime.now(timezone.utc)


def _version(**overrides: object) -> PromptVersion:
    data: dict[str, object] = {
        "id": 1,
        "prompt": "support-bot",
        "version": 1,
        "template_type": "text",
        "template": "Hello {{ name }}",
        "created_at": NOW,
        "content_hash": "abc",
    }
    data.update(overrides)
    return PromptVersion.model_validate(data)


def test_eval_result_matches_plan_example() -> None:
    result = EvalResultIn.model_validate(
        {
            "prompt": "support-bot",
            "version": 4,
            "metric": "accuracy",
            "score": 0.87,
            "run_id": "run-2026-10-30",
            "evaluator": "llm-judge-gpt",
            "metadata": {"dataset": "faq-100", "n": 100},
        }
    )
    assert result.project == "default"
    assert result.score == 0.87


@pytest.mark.parametrize("score", [float("nan"), float("inf"), "high"])
def test_eval_result_rejects_bad_scores(score: object) -> None:
    with pytest.raises(ValidationError):
        EvalResultIn(prompt="p", version=1, metric="m", score=score)


def test_eval_result_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvalResultIn.model_validate(
            {"prompt": "p", "version": 1, "metric": "m", "score": 1, "scroe": 2}
        )


def test_gate_matches_plan_example() -> None:
    gate = Gate.model_validate(
        {
            "rules": [
                {"metric": "accuracy", "min": 0.85},
                {"metric": "latency_ms", "max": 1200},
            ],
            "require_better_than_current": False,
        }
    )
    assert gate.rules[0].higher_is_better is True
    assert gate.rules[1].max == 1200


def test_gate_rule_needs_a_bound() -> None:
    with pytest.raises(ValidationError, match="needs a min or a max"):
        GateRule(metric="accuracy")


def test_gate_rule_min_not_above_max() -> None:
    with pytest.raises(ValidationError):
        GateRule(metric="accuracy", min=0.9, max=0.5)


def test_version_accepts_text_and_chat() -> None:
    assert _version().template == "Hello {{ name }}"
    chat = _version(
        template_type="chat",
        template=[{"role": "system", "content": "Be kind"}, {"role": "user", "content": "{{q}}"}],
    )
    assert chat.template[0].role == "system"  # type: ignore[union-attr]


def test_version_type_must_match_template() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        _version(template_type="chat")


def test_model_config_alias_round_trip() -> None:
    version = _version(model_config={"model": "gpt-4o", "temperature": 0.2})
    assert version.llm_config["temperature"] == 0.2
    assert version.model_dump(by_alias=True)["model_config"]["model"] == "gpt-4o"


def test_version_create_rejects_empty_chat() -> None:
    with pytest.raises(ValidationError):
        PromptVersionCreate(template=[])


def test_tag_name_validation() -> None:
    Tag(id=1, prompt="p", name="canary-eu", updated_at=NOW)
    with pytest.raises(ValidationError):
        Tag(id=1, prompt="p", name="has space", updated_at=NOW)
