---
name: backend-single-agent
description: How to use MaskedReactAgentBuilder (single PII-safe ReAct agent) and ChatSession (simple chat/summarization) in Codly Backend. Use for single-agent flows, summarization, or simple tool use.
---

# Codly Single-Agent Patterns

Two options for non-swarm LLM work.

## When to use what

| Pattern | Use when |
|---|---|
| `MaskedReactAgentBuilder` | Single agent, needs tools, needs PII masking |
| `ChatSession` | No tools, summarization, simple Q&A |
| `SwarmAgents` | 2+ agents with handoffs — see `codly:backend-swarm-agent` |

---

## MaskedReactAgentBuilder

```python
from llm.masked_react_agent import MaskedReactAgentBuilder
from llm.utils.prompt_loader import load_prompt

builder = MaskedReactAgentBuilder(category="medium")
builder.set_customer_model_config_from_db(customer=customer, category="medium")

# Load prompt from .md file — never inline
system_prompt = load_prompt("chatbot/myfeature/prompts/MyAgent.md")

agent = builder.build(
    tools=[my_tool_1, my_tool_2],
    system_prompt=system_prompt,
)

result = builder.invoke(
    agent=agent,
    user_input=user_input,
    session_id=str(session_id),
    cloud_provider="AWS",   # Used to select correct PII anonymizer
)
# result is a dict with "response" key
```

### Categories

| Category | Use for |
|---|---|
| `"default"` | Lightweight tasks, routing |
| `"low"` | Simple classification |
| `"medium"` | Standard agent work |
| `"high"` | Complex reasoning, reports |

**Always call `set_customer_model_config_from_db()`** — loads the customer's configured LLM from `LargeLanguageModel` model.

### PII masking

Automatic. Input masked before LLM, tool inputs unmasked for execution, outputs masked before returning, final response unmasked for user. No extra setup needed.

Pass `cloud_provider` to `invoke()` to select correct anonymizer patterns (AWS ARNs vs Azure subscription IDs).

---

## ChatSession

For summarization and simple chat — **no tool use**.

```python
from llm.open_ai import ChatSession
from llm.utils.prompt_loader import load_prompt

chat = ChatSession(
    session_id=str(session_id),
    category="medium",
    customer=customer,
)

system_prompt = load_prompt("chatbot/session_summary/prompts/Summarizer.md")

response = chat.send_message(
    user_message=user_input,
    system_prompt=system_prompt,
)
# response is a string
```

Used in: `chatbot/session_summary/` — session conversation summarization.

---

## Forbidden patterns

```python
# NEVER DO THIS
from langchain_openai import ChatOpenAI        # ❌ direct LLM import
from langchain_google_genai import ChatGoogleGenerativeAI  # ❌
import openai                                   # ❌
from llm.langchain.llm_helper import LangChainModelFactory  # ❌ in feature code

# ALWAYS USE THESE
from llm.masked_react_agent import MaskedReactAgentBuilder  # ✅
from llm.open_ai import ChatSession                          # ✅
from llm.agents.swarm import SwarmAgents                    # ✅
```

Direct LLM calls bypass PII masking and centralized credential management — **CI will flag this**.
