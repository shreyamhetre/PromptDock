"""Walk a prompt through dev -> preprod -> prod against the database in DATABASE_URL.

    python -m uv run python examples/core_flow.py              # prompt named "demo-bot"
    python -m uv run python examples/core_flow.py my-prompt    # or pick a name

Prints where each tag points after every step. Afterwards, look at the same story in
the database with:  SELECT * FROM v_prompt_status;  SELECT * FROM v_tag_history;
"""

import sys

from sqlalchemy.orm import Session

from promptdock.core import service
from promptdock.db.engine import make_engine
from promptdock.errors import AlreadyExistsError, GateFailedError
from promptdock.models import EvalResultIn, Gate, GateRule, PromptVersionCreate

NAME = sys.argv[1] if len(sys.argv) > 1 else "demo-bot"
ROW = "{:>4}  {:<50}  {:<14}  {:<5}  {:<7}  {:<5}"


def save(s: Session, template: str) -> int:
    return service.create_version(s, NAME, PromptVersionCreate(template=template)).version


def evaluate(s: Session, version: int, accuracy: float) -> None:
    result = EvalResultIn(prompt=NAME, version=version, metric="accuracy", score=accuracy)
    service.add_eval_results(s, [result])


def show(s: Session, step: int, what: str) -> None:
    s.commit()
    versions = ", ".join(f"v{v.version}" for v in service.list_versions(s, NAME)) or "-"
    tags = {t.name: f"v{t.version}" if t.version else "-" for t in service.list_tags(s, NAME)}
    print(ROW.format(step, what, versions, tags["dev"], tags["preprod"], tags["prod"]))


with Session(make_engine()) as s:
    try:
        service.create_prompt(s, NAME, description="Support bot demo")
    except AlreadyExistsError:
        sys.exit(
            f"Prompt '{NAME}' already exists. Run with another name, e.g.\n"
            f"  python -m uv run python examples/core_flow.py {NAME}-2"
        )
    service.set_gate(s, NAME, "prod", Gate(rules=[GateRule(metric="accuracy", min=0.85)]))

    print(f"Prompt '{NAME}'. Gate on prod: accuracy >= 0.85\n")
    print(ROW.format("step", "what you do", "versions", "dev", "preprod", "prod"))
    print("-" * 95)

    v1 = save(s, "Hi {{ user }}, how can I help?")
    show(s, 1, "save prompt text")

    service.promote(s, NAME, "dev", v1, actor="demo")
    show(s, 2, "promote v1 to dev")

    service.promote(s, NAME, "preprod", v1, actor="demo")
    show(s, 3, "tests look good: promote v1 to preprod")

    evaluate(s, v1, 0.90)
    service.promote(s, NAME, "prod", v1, actor="demo")
    show(s, 4, "eval accuracy=0.90 passes: promote v1 to prod")

    v2 = save(s, "Hello {{ user }}! Ask me anything about {{ product }}.")
    show(s, 5, "edit the prompt and save")

    service.promote(s, NAME, "dev", v2, actor="demo")
    show(s, 6, "promote v2 to dev to try it")

    evaluate(s, v2, 0.93)
    service.promote(s, NAME, "preprod", v2, actor="demo")
    service.promote(s, NAME, "prod", v2, actor="demo")
    show(s, 7, "v2 is good (0.93): promote to preprod, then prod")

    service.rollback(s, NAME, "prod", actor="demo", reason="v2 broke in prod")
    show(s, 8, "v2 breaks in prod: rollback prod")

    v3 = save(s, "Yo {{ user }}. What do you want?")
    evaluate(s, v3, 0.70)
    s.commit()  # keep v3 and its eval when the refused promote is rolled back
    try:
        service.promote(s, NAME, "prod", v3, actor="demo")
    except GateFailedError:
        s.rollback()
        show(s, 9, "save v3, eval 0.70: promote to prod REFUSED")

    same = save(s, "Yo {{ user }}. What do you want?")
    show(s, 10, f"save v3's text again: no new version (got v{same})")

    print("\nHistory of tag moves:")
    for e in reversed(service.get_tag_history(s, NAME)):
        start = f"v{e.from_version}" if e.from_version else "(none)"
        reason = f"  reason: {e.reason}" if e.reason else ""
        print(f"  {e.tag:<8} {e.action:<9} {start:>6} -> v{e.to_version}{reason}")
