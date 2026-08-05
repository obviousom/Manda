---
name: backend-tools
description: Use when writing @tool decorated functions for Codly Backend agents. Covers ToolRuntime context injection, closure pattern, error handling, return formats, and multi-cloud tool patterns for SwarmAgents.
---

# Codly — @tool Functions

LangChain `@tool` functions are the action layer for all agents.

## Imports

```python
from langchain.tools import tool, ToolRuntime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)
```

## Standard pattern — ToolRuntime context injection

Context (credentials, customer, account) is injected at runtime by SwarmAgents via `ToolRuntime`. Never hardcode credentials or use `os.getenv()`.

```python
@tool
def get_resource_data(
    resource_id: str,
    region: str = "us-east-1",
    runtime: ToolRuntime = None,
) -> Dict[str, Any]:
    """
    Fetch data for a specific cloud resource.
    
    Args:
        resource_id: The cloud resource identifier
        region: AWS region (default us-east-1)
        runtime: Injected by SwarmAgents — do not pass manually
    
    Returns:
        dict with resource data and metadata
    """
    if not runtime or not runtime.context:
        return {"error": "No runtime context available"}

    context = runtime.context
    cred_loader = context.get("cred_loader")
    customer = context.get("customer")
    account = context.get("account")

    env_vars = cred_loader.get_env_values()

    try:
        import boto3
        client = boto3.client(
            "ec2",
            aws_access_key_id=env_vars["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=env_vars["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=env_vars.get("AWS_SESSION_TOKEN"),
            region_name=region,
        )
        response = client.describe_instances(InstanceIds=[resource_id])
        return {"resource": response, "account_id": account.id}
    except Exception as e:
        logger.exception("get_resource_data failed for %s", resource_id)
        return {"error": str(e), "resource_id": resource_id}
```

## Context dict — what's in runtime.context

Set by the `create_agents()` caller before `swarm.invoke()`:

```python
context = {
    "cred_loader": cred_loader,          # CloudCredentials — call .get_env_values()
    "customer": customer,                # Customer model instance
    "account": account,                  # Account model instance
    "cloud_provider": "AWS",             # "AWS" | "AZURE" | "GCP"
    # add any feature-specific data here
}
result = swarm.invoke(user_input=..., session_id=..., context=context)
```

## Closure pattern (injected at creation, not via ToolRuntime)

Older pattern, still used in some modules. Context captured in closure at tool creation time:

```python
def make_aws_tool(client, customer, account):
    @tool
    def get_data(resource_id: str) -> dict:
        """Fetch resource data."""
        try:
            return client.describe_resource(Id=resource_id)
        except Exception as e:
            logger.exception("get_data failed")
            return {"error": str(e)}
    return get_data

# Usage in agent.py:
aws_tool = make_aws_tool(boto3_client, customer, account)
swarm.create_agent(..., tools=[aws_tool])
```

Prefer ToolRuntime pattern for SwarmAgents — it's more testable and thread-safe.

## Return format conventions

Always return a dict. Agents format text for users from tool results.

```python
# Success
return {
    "data": [...],
    "total": 42,
    "period": "2024-01",
    "metadata": {...},
}

# Error
return {
    "error": "Human-readable description of what failed",
    "resource_id": resource_id,  # echo inputs for debugging
}

# Empty result
return {
    "data": [],
    "message": "No resources found matching the criteria",
}
```

## Multi-cloud tool — one tool, branch by provider

```python
@tool
def get_compute_instances(
    region: str,
    runtime: ToolRuntime = None,
) -> Dict[str, Any]:
    """Get compute instances for the current cloud provider."""
    context = runtime.context
    cloud_provider = context.get("cloud_provider", "AWS")
    env_vars = context["cred_loader"].get_env_values()

    if cloud_provider == "AWS":
        return _get_aws_ec2(env_vars, region)
    elif cloud_provider == "AZURE":
        return _get_azure_vms(env_vars, region)
    else:
        return {"error": f"Unsupported provider: {cloud_provider}"}
```

Or create separate tools per provider and pass the right set based on `cloud_provider` in `agent.py`.

## Tool docstring rules

The docstring is the LLM's instruction for when/how to call this tool. Write it clearly:

- First line: what it returns
- `Args:` section: describe each param including units, valid values, defaults
- Include `WARNING:` notes for gotchas (e.g., "This returns aggregate only, not per-resource")
- If the tool has a sibling tool to call for detail, mention it

See `chatbot/finops/cost_analytics/tools/aws/aws_tools.py` for well-documented tool examples.

## Checklist

- [ ] `runtime: ToolRuntime = None` as last param
- [ ] Guard: `if not runtime or not runtime.context: return {"error": ...}`
- [ ] All cloud clients built from `cred_loader.get_env_values()` — not `os.getenv()`
- [ ] `try/except` around all cloud API calls
- [ ] `logger.exception()` on unexpected errors
- [ ] Return dict — not string, not raw boto3 response
- [ ] Docstring explains WHEN to call this tool, not just what it does
- [ ] No hardcoded region, account ID, or credentials
