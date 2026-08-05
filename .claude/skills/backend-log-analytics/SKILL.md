---
name: backend-log-analytics
description: Log analytics patterns for Codly Backend — multi-cloud log analysis agents, agent configs, provider structure. Use when working on chatbot/log_analytics/ or adding new log analysis features.
---

# Codly — Log Analytics

App: `chatbot/log_analytics/`

## Architecture

```
chatbot/log_analytics/
├── views.py             # Thin routing
├── agents.py            # Provider dispatch + GCP agent
├── agent_configs.py     # LogAnalyticsAgents class, agent registry
├── config.py            # LogAnalyticsConfig
├── base/                # Abstract base classes
├── providers/           # Provider-specific agent builders
├── aws_agents/          # AWS-specific log agents (CloudTrail, VPC Flow, ALB, CloudWatch)
│   ├── cloudtrail_agent/
│   ├── vpc_flow_agent/
│   ├── alb_agent/
│   └── cloudwatch_agent/
├── azure_agents/        # Azure Monitor, App Gateway, etc.
│   └── app_gateway_log_agent/
└── gcp_agents/          # GCP Cloud Logging
```

## Agent config registry

```python
from chatbot.log_analytics.agent_configs import LogAnalyticsAgents

# Get all registered agents
agents = LogAnalyticsAgents.get_all_agents()
# Returns dict: {agent_name: agent_config}

# Get agent config for a specific log type
config = LogAnalyticsAgents.get_agent_config("cloudtrail")
```

## Invoking log analytics

```python
from chatbot.log_analytics.agents import (
    gcp_log_analytics_agent_v2,
)

# AWS/Azure — routed through views → agent_configs → provider agents
# GCP
result = gcp_log_analytics_agent_v2(
    user_input=user_input,
    session_id=session_id,
    customer=customer,
    account=account,
    cred_loader=cred_loader,
)
```

## Adding a new log source

1. Create `aws_agents/<log_source>_agent/` directory
2. Add `agent.py` — `get_<log_source>_agent()` function returning SwarmAgents result
3. Add `tools.py` — `@tool` functions for log querying
4. Add `prompts/AWS<LogSource>.md`
5. Register in `agent_configs.py` `LogAnalyticsAgents` class

## Log sources supported

| Provider | Log Source | Agent |
|---|---|---|
| AWS | CloudTrail | `cloudtrail_agent` |
| AWS | VPC Flow Logs | `vpc_flow_agent` |
| AWS | ALB Access Logs | `alb_agent` |
| AWS | CloudWatch Logs | `cloudwatch_agent` |
| Azure | Azure Monitor | `azure_monitor_agent` |
| Azure | App Gateway | `app_gateway_log_agent` |
| GCP | Cloud Logging | `gcp_log_analytics_agent_v2` |

## Tool pattern for log tools

Log tools typically query time-windowed log data:

```python
@tool
def query_cloudtrail_logs(
    start_time: str,    # ISO format: "2024-01-01T00:00:00Z"
    end_time: str,
    event_name: str = None,
    user_identity: str = None,
    runtime: ToolRuntime = None,
) -> dict:
    """Query CloudTrail logs for API activity."""
    context = runtime.context
    env_vars = context["cred_loader"].get_env_values()
    # ... boto3 CloudTrail client
```
