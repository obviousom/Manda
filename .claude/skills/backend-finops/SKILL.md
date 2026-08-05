---
name: backend-finops
description: FinOps patterns for Codly Backend — cost analytics, cost optimization, waste management, tag management, and report generation. Use when working on chatbot/finops/ or adding new cost analysis features.
---

# Codly — FinOps

App: `chatbot/finops/`

## Sub-modules

| Module | Purpose |
|---|---|
| `cost_analytics/` | Multi-cloud cost breakdown, forecasting, anomaly detection |
| `cost_optimization/` | Savings recommendations, rightsizing |
| `waste_management/` | Idle/unused resource detection |
| `tag_manager/` | AWS tag management |
| `tag_manager_gcp/` | GCP label management |
| `report/` | Cost report generation (PDF, email) |

## Cost analytics agent — canonical multi-agent example

`chatbot/finops/cost_analytics/` is the reference implementation of the full multi-cloud SwarmAgents pattern.

```python
from chatbot.finops.cost_analytics.agent import create_agents

result = create_agents(
    user_input=user_input,
    session_id=session_id,
    customer=customer,
    account=account,
    cred_loader=cred_loader,
    cloud_provider=account.cloud_provider,   # "AWS" | "AZURE" | "GCP"
    user=request.user,
    approved_tags=None,
)
```

## Agent architecture (4-agent cost analytics swarm)

```
Supervisor
├── CostAnalyzer          — high-level service/region breakdown
├── DetailedCostAnalyzer  — drill-down, usage types, anomaly detail
└── ResourceLevelCostAnalyzer — resource-level attribution
```

## CostDataCollector — cross-turn state

Persists cost data across conversation turns in the same session:

```python
from chatbot.finops.cost_analytics.base.cost_data_collector import CostDataCollector
from django.core.cache import cache

CACHE_TTL = 60 * 60
cache_key = f"cost_analytics:collector:{session_id}"

collector = CostDataCollector(cloud_provider=cloud_provider)
# Restore previous turn's data
cached = cache.get(cache_key)
if cached:
    collector.restore_state(cached)
```

After agent run, save collector state:
```python
cache.set(cache_key, collector.get_state(), CACHE_TTL)
```

## Tool context for cost analytics

```python
from chatbot.finops.cost_analytics.agent_config import create_cost_analytics_context

context = create_cost_analytics_context(
    cred_loader=cred_loader,
    cloud_provider=cloud_provider,
    customer=customer,
    account=account,
    cost_collector=cost_collector,
    user=user,
)
```

## Cost tool patterns

AWS tools use `ToolRuntime` context. Key tools:
- `get_aws_cost_breakdown` — aggregate service/region totals
- `get_aws_detailed_service_cost_breakdown` — usage type drill-down
- `get_aws_resource_level_costs` — per-resource attribution
- `get_aws_ec2_resource_costs`, `get_aws_rds_resource_costs`, `get_aws_s3_resource_costs`

See `chatbot/finops/cost_analytics/tools/aws/aws_tools.py` and `aws_tools_additional.py` for complete tool set.

## Versioned agent variants

Cost analytics has multiple generations (don't create new v1/v2/v3 — use main `agent.py`):

| File | Status | Use |
|---|---|---|
| `agent.py` | Current | All new work |
| `v4/agent.py` | Current Azure/Athena | Azure cost + Athena queries |
| `v3/agent.py` | Legacy | Don't use |
| `v2/agent.py` | Legacy | Don't use |

## Adding a new FinOps feature

1. Create `chatbot/finops/<feature_name>/` directory
2. Follow multi-cloud feature structure from `codly:backend-new-feature`
3. Add agent functions to `agent.py`
4. Provider tools in `tools/aws/` and `tools/azure/`
5. Prompts in `prompts/`
6. Register URL in `chatbot/finops/urls.py`

## Currency conversion

Use the utility — never hardcode exchange rates:

```python
from common.tools import convert_usd_to_inr

inr_amount = convert_usd_to_inr(usd_amount)
```
