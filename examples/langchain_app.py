"""Use a PromptDock prompt in LangChain.

    pip install promptdock langchain-openai
    export DATABASE_URL=...
    export OPENAI_API_KEY=...
    python examples/langchain_app.py "How do I reset my password?"

PromptDock renders the template (so its variable checks apply); LangChain receives plain
messages. Swap ChatOpenAI for any LangChain chat model.
"""

import sys

from langchain_openai import ChatOpenAI

from promptdock import Client

prompts = Client()

question = sys.argv[1] if len(sys.argv) > 1 else "How do I reset my password?"
prompt = prompts.get_prompt("support-bot", tag="prod")
rendered = prompt.render(product="PromptDock", question=question, user="Ana")
messages = (
    [("user", rendered)]
    if isinstance(rendered, str)
    else [(m["role"], m["content"]) for m in rendered]
)

config = prompt.model_config
llm = ChatOpenAI(
    model=config.get("model", "gpt-4o-mini"),
    temperature=config.get("temperature", 0.7),
)
reply = llm.invoke(messages)

print(f"[{prompt.name} v{prompt.version} via tag '{prompt.tag}']")
print(reply.content)
