---
name: backend-swarm-agent
description: How to build multi-agent LLM workflows using SwarmAgents in Codly Backend. Use when creating agent.py files, adding new LLM agents, or building multi-agent swarms with handoffs.
---

# Codly SwarmAgents — Multi-Agent Workflow

**Primary framework** for all multi-agent LLM work. Lives at `llm/agents/swarm/`.

## When to use SwarmAgents

**Always use `SwarmAgents` for all agent work — single agent, multi-agent, simple or complex.** Never use `MaskedReactAgentBuilder` or `ChatSession` for agent implementations.

| Need | Use |
|---|---|
| Any agent work (single or multi-agent) | `SwarmAgents` ← this skill |

## Imports

```python
from llm.agents.swarm import SwarmAgents
from llm.agents.swarm.config import AgentConfig, HandoffConfig
from llm.agents.swarm.state import SwarmState
from llm.agents.swarm.middleware import PIIMaskingMiddleware, LoggingMiddleware, MaskingConfig
from llm.utils.prompt_loader import load_prompt
from manage_user.models import Customer, Account
```

## Minimal swarm pattern

```python
def create_agents(user_input, session_id, customer, account, cred_loader, cloud_provider):
    # 1. Build context dict — injected into every tool via ToolRuntime.context
    context = {
        "customer": customer,
        "account": account,
        "cred_loader": cred_loader,
        "cloud_provider": cloud_provider,
    }

    # 2. Init swarm — model_category maps to LargeLanguageModel tier in DB
    swarm = SwarmAgents(
        customer=customer,
        model_category="medium",   # "default" | "low" | "medium" | "high"
        global_middleware=[PIIMaskingMiddleware()],
        enable_toon_formatting=True,
    )

    # 3. Load prompts from .md files — never inline
    supervisor_prompt = load_prompt("chatbot/myfeature/prompts/Supervisor.md")
    worker_prompt = load_prompt("chatbot/myfeature/prompts/Worker.md")

    # 4. Create agents
    swarm.create_agent(
        agent_name="supervisor",
        agent_description="Routes user requests to the appropriate worker",
        prompt=supervisor_prompt,
        tools=[],
        default_active=True,   # Entry point agent
    )

    swarm.create_agent(
        agent_name="worker",
        agent_description="Executes the actual cloud operations",
        prompt=worker_prompt,
        tools=[my_aws_tool, my_azure_tool],
    )

    # 5. Link agents for handoff
    swarm.link_agents("supervisor", ["worker"])
    swarm.link_agents("worker", ["supervisor"])

    # 6. Build and invoke
    swarm.build_swarm()
    result = swarm.invoke(
        user_input=user_input,
        session_id=str(session_id),
        context=context,
    )

    return {
        "response": result.get("response", ""),
        "session_id": session_id,
    }
```

## Custom state schema

Extend `SwarmState` when you need to store extra data across agents:

```python
from typing import NotRequired
from llm.agents.swarm.state import SwarmState

class MyFeatureState(SwarmState):
    scan_context: NotRequired[dict]
    cost_period: NotRequired[str]
    csv_url: NotRequired[str]
```

Pass via `swarm.build_swarm(state_schema=MyFeatureState)`.

## HandoffConfig — controlled handoffs

Use `HandoffConfig` when you want to pass a task description hint on handoff:

```python
from llm.agents.swarm.config import HandoffConfig

handoff = HandoffConfig(
    agent_name="worker_agent",
    include_task_description=True,
)

swarm.create_agent(
    agent_name="supervisor",
    prompt=supervisor_prompt,
    tools=[],
    handoff_configs=[handoff],
    default_active=True,
)
```

## PII Masking middleware

```python
from llm.agents.swarm.middleware import PIIMaskingMiddleware, MaskingConfig

# Default (AWS patterns)
swarm = SwarmAgents(customer=customer, global_middleware=[PIIMaskingMiddleware()])

# Multi-cloud — specify providers to mask
swarm = SwarmAgents(
    customer=customer,
    global_middleware=[PIIMaskingMiddleware(config=MaskingConfig(
        cloud_providers=["aws", "azure"]
    ))],
)
```

## Per-agent model config

Different agents can use different model tiers:

```python
swarm.create_agent(
    agent_name="supervisor",
    prompt=prompt,
    tools=[],
    model_category="high",     # Override global model_category per agent
)
```

## Tool context injection via ToolRuntime

Tools access runtime context through `ToolRuntime`. Always add `runtime: ToolRuntime = None` param:

```python
from langchain.tools import tool, ToolRuntime

@tool
def get_aws_data(query: str, runtime: ToolRuntime = None) -> dict:
    """Fetch AWS data based on query."""
    context = runtime.context
    cred_loader = context["cred_loader"]
    customer = context["customer"]
    # ... use creds
```

See `chatbot/finops/cost_analytics/tools/aws/aws_tools.py` for full real-world examples.

## Full real-world example

See `chatbot/finops/cost_analytics/agent.py` — 4-agent supervisor swarm with custom state, PII masking, and handoff configs.

See `ticket_management/agents.py` — ticket processing swarm.

## Checklist before shipping

- [ ] `model_category` set on swarm or per-agent
- [ ] All prompts loaded via `load_prompt()` — never inline strings
- [ ] `PIIMaskingMiddleware` applied (or `LoggingMiddleware` + custom)
- [ ] `default_active=True` on exactly one entry-point agent
- [ ] All tools accept `runtime: ToolRuntime = None`
- [ ] `link_agents()` called for all bidirectional handoff pairs
- [ ] Function returns at minimum `{"response": ..., "session_id": ...}`
