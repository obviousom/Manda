---
name: backend-agent-hub
description: Agent Hub patterns for Codly Backend — user-defined agents, MCP agents, marketplace, and agent execution. Use when working on agent_hub/ app or building custom agent execution flows.
---

# Codly — Agent Hub

App: `agent_hub/`

## Architecture

```
agent_hub/
├── models.py                    # Agent definitions, instances
├── serializers.py
├── views/
│   ├── definitions.py           # CRUD for agent definitions
│   ├── marketplace.py           # Marketplace agent browsing/install
│   ├── mcp_agents.py            # MCP-based agent management
│   ├── mcp_servers.py           # MCP server config
│   └── invoke.py                # Execute an agent
└── user_defined/
    └── executor.py              # execute_user_defined_agent()
```

## Executing a user-defined agent

```python
from agent_hub.user_defined.executor import execute_user_defined_agent, AgentResponse

response: AgentResponse = execute_user_defined_agent(
    agent_instance_id=instance_id,
    user_input=user_input,
    session_id=session_id,
    customer=customer,
)

response.response      # Agent text response
response.success       # bool
response.error         # str | None
```

## AgentResponse

```python
from agent_hub.user_defined.executor import AgentResponse

# response.response     — text response from agent
# response.success      — True if no errors
# response.error        — error message if failed
# response.metadata     — dict with extra data
```

## MCP agent patterns

MCP (Model Context Protocol) agents use external tool servers. Config stored in `TicketIntegration`-style per-customer records.

```python
from agent_hub.views.mcp_agents import _run_mcp_agent, _get_customer_for_request

# Get customer safely
customer = _get_customer_for_request(request)
```

## Customer isolation in agent_hub

Agent hub views use a shared helper — always validate customer ownership:

```python
from agent_hub.views.mcp_agents import _get_customer_for_request

customer = _get_customer_for_request(request)
# Handles both AdminUser (from query param) and regular User (from token)
```
