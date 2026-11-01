"""Score a prompt version with an LLM judge (gpt-4o-mini) and push the results.

    pip install promptdock openai
    export DATABASE_URL=...            # or PROMPTDOCK_URL (+ PROMPTDOCK_TOKEN)
    export OPENAI_API_KEY=...
    python examples/push_evals_llm_judge.py support-bot 3

For each test question it renders the version, gets an answer with the version's own
model_config, asks gpt-4o-mini to grade the answer 0-1 against a reference, and pushes
two metrics: `accuracy` (mean grade, higher is better) and `latency_ms` (mean answer time,
lower is better). Then: `promptdock leaderboard support-bot`, and gate prod on them with
`promptdock gate set support-bot prod --min accuracy=0.8 --max latency_ms=3000`.
"""

import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

from openai import OpenAI

from promptdock import Client

DATASET = [
    {
        "question": "How do I reset my password?",
        "reference": "Use 'Forgot password' on the sign-in page; a reset link is emailed.",
    },
    {
        "question": "Can I change my plan mid-month?",
        "reference": "Yes. Upgrades apply at once (prorated); downgrades apply next cycle.",
    },
    {
        "question": "Do you offer refunds?",
        "reference": "Refunds are available within 14 days of purchase via support.",
    },
]

JUDGE_PROMPT = """You grade a support answer against a reference answer.
Question: {question}
Reference: {reference}
Answer: {answer}
Reply with JSON only: {{"score": <number from 0 to 1>, "reason": "<one sentence>"}}"""

name, version = sys.argv[1], int(sys.argv[2])
url = os.environ.get("PROMPTDOCK_URL")
prompts = Client(base_url=url) if url else Client()
llm = OpenAI()

prompt = prompts.get_prompt(name, version=version)
config = prompt.model_config
scores, latencies = [], []

for case in DATASET:
    rendered = prompt.render(product="PromptDock", user="Ana", question=case["question"])
    messages = [{"role": "user", "content": rendered}] if isinstance(rendered, str) else rendered

    started = time.perf_counter()
    answer = llm.chat.completions.create(
        model=config.get("model", "gpt-4o-mini"),
        messages=messages,  # type: ignore[arg-type]
        temperature=config.get("temperature", 0),
        max_tokens=config.get("max_tokens"),
    )
    latencies.append((time.perf_counter() - started) * 1000)
    answer_text = answer.choices[0].message.content or ""

    verdict = llm.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": JUDGE_PROMPT.format(answer=answer_text, **case),
            }
        ],
    )
    grade = json.loads(verdict.choices[0].message.content or "{}")
    scores.append(float(grade.get("score", 0)))
    print(f"{grade.get('score')}: {case['question']} - {grade.get('reason')}")

run_id = f"judge-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
common = {
    "prompt": name,
    "version": version,
    "run_id": run_id,
    "evaluator": "llm-judge-gpt-4o-mini",
    "metadata": {"dataset": "support-faq-3", "n": len(DATASET)},
}
prompts.add_eval_results(
    [
        {**common, "metric": "accuracy", "score": statistics.mean(scores)},
        {**common, "metric": "latency_ms", "score": statistics.mean(latencies)},
    ]
)
print(f"Pushed accuracy={statistics.mean(scores):.2f}, latency_ms={statistics.mean(latencies):.0f}")
