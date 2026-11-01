"""Use a PromptDock prompt with OpenAI.

pip install promptdock openai
export DATABASE_URL=...            # or Client(base_url=...) for a PromptDock server
export OPENAI_API_KEY=...
python examples/openai_app.py "How do I reset my password?"

From a checkout of this repo, run it with uv (which adds the SDK just for this run):
    uv run --with openai python examples/openai_app.py ...
"""

import sys

from openai import OpenAI

from promptdock import Client

prompts = Client()
llm = OpenAI()

question = sys.argv[1] if len(sys.argv) > 1 else "How do I reset my password?"
prompt = prompts.get_prompt("support-bot", tag="prod")
rendered = prompt.render(product="PromptDock", question=question, user="Ana")

# Chat templates already are OpenAI-style messages; a text template becomes one user turn.
messages = [{"role": "user", "content": rendered}] if isinstance(rendered, str) else rendered

config = prompt.model_config  # e.g. {"model": "gpt-4o", "temperature": 0.2}
response = llm.chat.completions.create(
    model=config.get("model", "gpt-4o-mini"),
    messages=messages,  # type: ignore[arg-type]
    **{k: v for k, v in config.items() if k in ("temperature", "max_tokens", "top_p")},
)

print(f"[{prompt.name} v{prompt.version} via tag '{prompt.tag}']")
print(response.choices[0].message.content)
