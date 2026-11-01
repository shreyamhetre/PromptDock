from promptdock.core.gates import evaluate_gate
from promptdock.models import Gate, GateRule

GATE = Gate(rules=[GateRule(metric="accuracy", min=0.85), GateRule(metric="latency_ms", max=1200)])


def test_passes_when_all_rules_hold() -> None:
    assert evaluate_gate(GATE, {"accuracy": 0.9, "latency_ms": 800}) == []


def test_reports_every_failing_rule() -> None:
    failures = evaluate_gate(GATE, {"accuracy": 0.8, "latency_ms": 1500})
    assert failures == [
        "accuracy: 0.8 is below the minimum 0.85",
        "latency_ms: 1500 is above the maximum 1200",
    ]


def test_missing_metric_fails() -> None:
    assert evaluate_gate(GATE, {"accuracy": 0.9}) == ["latency_ms: no eval result for this version"]


def test_extra_metrics_are_ignored() -> None:
    assert evaluate_gate(GATE, {"accuracy": 0.9, "latency_ms": 10, "tone": 0.1}) == []


def test_require_better_than_current() -> None:
    gate = Gate(
        rules=[
            GateRule(metric="accuracy", min=0.5),
            GateRule(metric="latency_ms", max=5000),
        ],
        require_better_than_current=True,
    )
    current = {"accuracy": 0.9, "latency_ms": 900}

    assert evaluate_gate(gate, {"accuracy": 0.95, "latency_ms": 800}, current) == []
    # "At least as good": equal scores pass.
    assert evaluate_gate(gate, {"accuracy": 0.9, "latency_ms": 900}, current) == []
    assert evaluate_gate(gate, {"accuracy": 0.89, "latency_ms": 1000}, current) == [
        "accuracy: 0.89 is worse than the current version's 0.9",
        "latency_ms: 1000 is worse than the current version's 900",
    ]


def test_better_than_current_skips_metrics_current_lacks() -> None:
    gate = Gate(rules=[GateRule(metric="accuracy", min=0.5)], require_better_than_current=True)
    assert evaluate_gate(gate, {"accuracy": 0.6}, {}) == []
    assert evaluate_gate(gate, {"accuracy": 0.6}, None) == []
