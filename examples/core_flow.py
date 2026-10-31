"""Walk through the core flow against the database in DATABASE_URL.

    python -m uv run python examples/core_flow.py

Creates a prompt with a unique name each run, so it is safe to run repeatedly.
"""

import time

from sqlalchemy.orm import Session

from promptdock.core import service
from promptdock.db.engine import make_engine
from promptdock.errors import GateFailedError, NothingToRollBackError
from promptdock.models import EvalResultIn, Gate, GateRule, PromptVersionCreate

name = f"demo-bot-{int(time.time())}"
engine = make_engine()

with Session(engine) as s, s.begin():
    service.create_prompt(s, name, description="Demo prompt")
    print(f"Created prompt '{name}' with tags:", [t.name for t in service.list_tags(s, name)])

    for text in ["Hi {{ user }}!", "Hello {{ user }}, how can I help with {{ product }}?"]:
        v = service.create_version(s, name, PromptVersionCreate(template=text))
        print(f"  v{v.version}: {v.template!r}  variables={v.variables}")
    v3 = service.create_version(
        s,
        name,
        PromptVersionCreate.model_validate(
            {
                "template": [
                    {"role": "system", "content": "You support {{ product }}."},
                    {"role": "user", "content": "{{ question }}"},
                ],
                "model_config": {"model": "gpt-4o", "temperature": 0.2},
            }
        ),
    )
    print(f"  v{v3.version}: chat template  variables={v3.variables}")

    gate = Gate(rules=[GateRule(metric="accuracy", min=0.85)])
    service.set_gate(s, name, "prod", gate)
    print("\nGate on prod: accuracy >= 0.85")

    for version, score in [(1, 0.88), (2, 0.92), (3, 0.70)]:
        service.add_eval_results(
            s, [EvalResultIn(prompt=name, version=version, metric="accuracy", score=score)]
        )
        print(f"  eval v{version}: accuracy={score}")

    print()
    for version in (1, 2):
        service.promote(s, name, "prod", version, actor="demo")
        print(f"promote v{version} -> prod is now v{service.get_by_tag(s, name, 'prod').version}")

    try:
        service.promote(s, name, "prod", 3, actor="demo")
    except GateFailedError as exc:
        print(f"promote v3 refused:\n{exc}")

    service.promote(s, name, "prod", 3, actor="demo", force=True, reason="demo override")
    print("forced v3 -> prod is now v3")

    while True:
        try:
            tag = service.rollback(s, name, "prod", actor="demo")
            print(f"rollback -> prod is now v{tag.version}")
        except NothingToRollBackError as exc:
            print(f"rollback refused: {exc}")
            break

    print("\nAudit log for prod (newest first):")
    for e in service.get_tag_history(s, name, "prod"):
        forced = " (forced)" if e.forced else ""
        print(f"  {e.action:8} v{e.from_version} -> v{e.to_version}{forced}  reason={e.reason}")
