"""Use a PromptDock prompt with Claude (Anthropic SDK).

    pip install promptdock anthropic
    export DATABASE_URL=...            # or Client(base_url=...) for a PromptDock server
    export ANTHROPIC_API_KEY=...
    python examples/anthropic_app.py "How do I reset my password?"

The app always asks for a tag ("prod"), never a version number, so promoting or rolling
back in PromptDock changes what it sends with no code change.

From a checkout of this repo, run it with uv (which adds the SDK just for this run):
    uv run --with anthropic python examples/anthropic_app.py ...
"""

import sys

import anthropic

from promptdock import Client

DEFAULT_MODEL = "claude-opus-5-5"

prompts = Client()
claude = anthropic.Anthropic()

question = sys.argv[1] if len(sys.argv) > 1 else "How do I reset my password?"
prompt = prompts.get_prompt("support-bot", tag="prod")
rendered = prompt.render(product="PromptDock", question=question, user="Ana")

# Chat templates render to [{"role", "content"}, ...]; Claude takes the system prompt as a
# separate parameter. Text templates become a single user message.
if isinstance(rendered, str):
    system, messages = None, [{"role": "user", "content": rendered}]
else:
    system = "\n\n".join(m["content"] for m in rendered if m["role"] == "system") or None
    messages = [m for m in rendered if m["role"] != "system"]

config = prompt.model_config  # stored with the version, e.g. {"model": ..., "max_tokens": ...}
request = {
    "model": config.get("model", DEFAULT_MODEL),
    "max_tokens": config.get("max_tokens", 16000),
    "messages": messages,
    # If a request is declined for safety reasons, retry it on a suitable fallback model.
    "betas": ["server-side-fallback-2026-07-01"],
    "fallbacks": "default",
}
if system:
    request["system"] = system
if "effort" in config:  # current Claude models take effort, not temperature
    request["output_config"] = {"effort": config["effort"]}

response = claude.beta.messages.create(**request)

if response.stop_reason == "refusal":
    print("Claude declined this request.")
else:
    print(f"[{prompt.name} v{prompt.version} via tag '{prompt.tag}']")
    print("".join(block.text for block in response.content if block.type == "text"))
