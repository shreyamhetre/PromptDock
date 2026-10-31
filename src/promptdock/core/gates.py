"""Eval gate evaluation. Pure functions: no database access."""

from collections.abc import Mapping

from promptdock.models import Gate


def evaluate_gate(
    gate: Gate,
    scores: Mapping[str, float],
    current_scores: Mapping[str, float] | None = None,
) -> list[str]:
    """Return a human-readable reason for every rule the candidate fails (empty = passes).

    ``scores`` holds the latest score per metric for the candidate version and
    ``current_scores`` the same for the version the tag points to now (None if unset).
    A missing metric fails. ``require_better_than_current`` only compares metrics the
    current version also has a score for.
    """
    failures: list[str] = []
    for rule in gate.rules:
        score = scores.get(rule.metric)
        if score is None:
            failures.append(f"{rule.metric}: no eval result for this version")
            continue
        if rule.min is not None and score < rule.min:
            failures.append(f"{rule.metric}: {score:g} is below the minimum {rule.min:g}")
        if rule.max is not None and score > rule.max:
            failures.append(f"{rule.metric}: {score:g} is above the maximum {rule.max:g}")
        if gate.require_better_than_current and current_scores is not None:
            current = current_scores.get(rule.metric)
            if current is None:
                continue
            better = score > current if rule.higher_is_better else score < current
            if not better:
                failures.append(
                    f"{rule.metric}: {score:g} is not better than the current version's {current:g}"
                )
    return failures
