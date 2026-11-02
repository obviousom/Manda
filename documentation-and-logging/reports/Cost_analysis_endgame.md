# Cost Analysis Endgame — Log Analytics Worker Integration

**Goal:** Integrate the existing `log_analytics` system as a specialist worker inside
the cost analysis swarm (Athena/AWS + V4/Azure). When a user asks about a cost spike
or wants attribution, the supervisor auto-routes to the LogAnalyticsWorker — or the
user can type `/logs` to trigger it manually.

**Scope:** AWS (Athena + CloudWatch/CloudTrail) + Azure (V4/Synapse + Monitor/Activity Logs)

---

## 1. Architecture Overview

```
Cost Analysis Swarm (existing)
├── AthenaV4Supervisor              ← AWS supervisor (MODIFIED — new routing rule)
│   ├── ServiceCostAthenaAnalyst    (unchanged)
│   ├── ResourceCostAthenaAnalyst   (unchanged)
│   └── [NEW] LogAnalyticsWorker   ← bridge into log_analytics_agent()
│
└── CostAnalyticsV4Supervisor       ← Azure supervisor (MODIFIED — same routing rule)
    ├── ServiceCostV4Analyst        (unchanged)
    ├── ResourceCostV4Analyst       (unchanged)
    └── [NEW] LogAnalyticsWorker   ← bridge into azure_log_analytics_agent()
```

The `LogAnalyticsWorker` is NOT a re-implementation of log analytics.
It is a **tool function** that calls the existing log analytics agent and returns
its structured finding back into the cost swarm conversation.

---

## 2. Real Function Signatures (verified)

### AWS log agent
```python
# chatbot/log_analytics/agents.py:58
log_analytics_agent(
    cred_loader,
    user_input: str,
    session_id: str,
    log_group_name: str = None,
    region: str = "ap-south-1",
    customer=None,
    account=None,
) -> tuple[str, str, dict, dict]  # (message, last_agent, token_usage, cumul_token_usage)
```

### Azure log agent
```python
# chatbot/log_analytics/agents.py:640
azure_log_analytics_agent(
    cred_loader,
    user_input: str,
    session_id: str,
    workspace_id: str = None,
    region: str = "centralindia",
    customer=None,
    account=None,
) -> tuple[str, str, dict, dict]  # (message, last_agent, token_usage, cumul_token_usage)
```

### Cost analysis frontend
- Chat UI: `src/components/FinOps.jsx` — `sendMessage()` function
- Endpoint: `POST /chatbot/report_forecast_agent/`
- Payload: `{ session_id, input, customer_id, account_id, region, v2?, v3? }`

---

## 3. Trigger Logic

### Auto-trigger (supervisor detects RCA/attribution intent)
The supervisor prompt gets a new routing rule:

```
IF user query contains any of:
  "why did cost spike", "cost increased", "what caused", "who created",
  "which service caused", "root cause", "investigate", "anomaly explain",
  "who made the API call", "which role", "what happened on [date]"
THEN hand off to LogAnalyticsWorker before answering
```

### Manual trigger
User types `/logs` or `investigate logs` anywhere in the cost analysis chat →
supervisor detects keyword → routes immediately to LogAnalyticsWorker.

---

## 4. Files to Create / Modify

### 4.1 NEW: Preflight checker
```
Codly_Backend/chatbot/finops/cost_analytics/log_preflight.py
```

```python
import boto3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def preflight_aws_logs(cred_loader, region: str) -> dict:
    """
    Check what AWS log sources are available before querying.
    Returns structured dict the LogAnalyticsWorker reads before doing anything.
    """
    result = {
        "cloudtrail_enabled": False,
        "cloudwatch_log_groups": [],
        "any_available": False,
        "setup_guide": None,
    }
    try:
        env_vars = cred_loader.get_env_values()
        session = boto3.Session(
            aws_access_key_id=env_vars.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=env_vars.get("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=env_vars.get("AWS_SESSION_TOKEN"),
            region_name=region,
        )

        # 1. CloudTrail check
        ct = session.client("cloudtrail")
        trails = ct.describe_trails(includeShadowTrails=False).get("trailList", [])
        result["cloudtrail_enabled"] = len(trails) > 0

        # 2. CloudWatch log groups
        cw = session.client("logs")
        paginator = cw.get_paginator("describe_log_groups")
        groups = []
        for page in paginator.paginate():
            groups.extend([g["logGroupName"] for g in page.get("logGroups", [])])
        result["cloudwatch_log_groups"] = groups[:50]  # cap at 50 for prompt injection

        result["any_available"] = result["cloudtrail_enabled"] or len(groups) > 0

    except Exception as e:
        logger.warning(f"AWS log preflight failed: {e}")
        result["setup_guide"] = _aws_setup_guide()

    if not result["any_available"] and result["setup_guide"] is None:
        result["setup_guide"] = _aws_setup_guide()

    return result


def preflight_azure_logs(cred_loader) -> dict:
    """
    Check what Azure log sources are available before querying.
    """
    result = {
        "diagnostic_settings_enabled": False,
        "log_analytics_workspace": None,
        "any_available": False,
        "setup_guide": None,
    }
    try:
        env_vars = cred_loader.get_env_values()
        from azure.identity import ClientSecretCredential
        from azure.mgmt.monitor import MonitorManagementClient

        credential = ClientSecretCredential(
            tenant_id=env_vars["AZURE_TENANT_ID"],
            client_id=env_vars["AZURE_CLIENT_ID"],
            client_secret=env_vars["AZURE_CLIENT_SECRET"],
        )
        subscription_id = env_vars["AZURE_SUBSCRIPTION_ID"]

        monitor = MonitorManagementClient(credential, subscription_id)
        # Check subscription-level diagnostic settings
        diag = list(monitor.subscription_diagnostic_settings.list())
        result["diagnostic_settings_enabled"] = len(diag) > 0

        # Try to find a Log Analytics workspace ID from existing settings
        for d in diag:
            wid = getattr(d, "workspace_id", None)
            if wid:
                result["log_analytics_workspace"] = wid
                break

        result["any_available"] = (
            result["diagnostic_settings_enabled"]
            or result["log_analytics_workspace"] is not None
        )

    except Exception as e:
        logger.warning(f"Azure log preflight failed: {e}")
        result["setup_guide"] = _azure_setup_guide()

    if not result["any_available"] and result["setup_guide"] is None:
        result["setup_guide"] = _azure_setup_guide()

    return result


def _aws_setup_guide() -> str:
    return (
        "**CloudTrail is not enabled for this account.**\n\n"
        "To enable it:\n"
        "1. Go to AWS Console → CloudTrail → Create Trail\n"
        "2. Apply to all regions (recommended)\n"
        "3. Store logs in an S3 bucket\n"
        "4. Enable CloudWatch Logs integration for real-time querying\n"
        "5. Estimated cost: ~$2/100,000 events (management events free for first trail)\n\n"
        "Once enabled, re-run this investigation. Historical events from before "
        "enablement will not be available."
    )


def _azure_setup_guide() -> str:
    return (
        "**Diagnostic Settings are not configured for this subscription.**\n\n"
        "To enable it:\n"
        "1. Go to Azure Portal → Monitor → Diagnostic Settings\n"
        "2. Select the subscription scope\n"
        "3. Route logs to a Log Analytics Workspace (create one if needed)\n"
        "4. Enable: Administrative, Security, ServiceHealth, Alert, Policy categories\n"
        "5. Estimated cost: ~$2.30/GB ingestion\n\n"
        "Once configured, re-run this investigation. Activity Log retains 90 days by "
        "default, so historical data may already be available."
    )
```

---

### 4.2 NEW: AWS bridge tool
```
Codly_Backend/chatbot/finops/cost_analytics/athena/log_worker_tool.py
```

```python
import logging
from langchain_core.tools import tool
from chatbot.finops.cost_analytics.log_preflight import preflight_aws_logs
from chatbot.log_analytics.agents import log_analytics_agent

logger = logging.getLogger(__name__)


def create_aws_log_worker_tool(cred_loader, session_id: str, customer, account, region: str):
    """
    Factory: returns a @tool that bridges the cost analysis swarm into the
    existing AWS log analytics agent. Call once during agent construction.
    """

    @tool
    def investigate_logs_for_cost_spike(
        query: str,
        log_group_name: str = None,
        time_range_hours: int = 24,
    ) -> str:
        """
        Investigate CloudWatch/CloudTrail logs to find the root cause of a cost spike
        or attribute cost to a specific IAM actor or resource creation event.
        Provide a natural-language question. Returns a structured log investigation report.
        """
        # 1. Preflight — check what's available
        preflight = preflight_aws_logs(cred_loader, region)

        if not preflight["any_available"]:
            return f"**Log Investigation — Setup Required**\n\n{preflight['setup_guide']}"

        # 2. Enrich query with cost + time context injected by supervisor
        enriched = (
            f"{query}\n\n"
            f"Focus on: API calls, resource creation/deletion, scaling events, "
            f"IAM principal attribution in the last {time_range_hours} hours.\n\n"
            f"Available log sources: "
            f"CloudTrail={'enabled' if preflight['cloudtrail_enabled'] else 'not enabled'}, "
            f"CloudWatch groups={len(preflight['cloudwatch_log_groups'])} found."
        )

        # 3. Delegate to the existing log analytics agent
        # session_id suffix creates an isolated memory thread in Redis
        log_session = f"{session_id}_log_worker"
        try:
            message, last_agent, _, _ = log_analytics_agent(
                cred_loader=cred_loader,
                user_input=enriched,
                session_id=log_session,
                log_group_name=log_group_name,
                region=region,
                customer=customer,
                account=account,
            )
        except Exception as e:
            logger.error(f"Log worker AWS call failed: {e}")
            return f"Log investigation failed: {str(e)}"

        return f"**Log Investigation Result (via {last_agent}):**\n\n{message}"

    return investigate_logs_for_cost_spike
```

---

### 4.3 NEW: Azure bridge tool
```
Codly_Backend/chatbot/finops/cost_analytics/v4/log_worker_tool.py
```

```python
import logging
from langchain_core.tools import tool
from chatbot.finops.cost_analytics.log_preflight import preflight_azure_logs
from chatbot.log_analytics.agents import azure_log_analytics_agent

logger = logging.getLogger(__name__)


def create_azure_log_worker_tool(cred_loader, session_id: str, customer, account, region: str):
    """
    Factory: returns a @tool that bridges the cost analysis swarm into the
    existing Azure log analytics agent.
    """

    @tool
    def investigate_logs_for_cost_spike(
        query: str,
        workspace_id: str = None,
        time_range_hours: int = 24,
    ) -> str:
        """
        Investigate Azure Activity Logs / Monitor to find the root cause of a cost spike
        or attribute cost to a specific principal or resource operation.
        Provide a natural-language question. Returns a structured log investigation report.
        """
        # 1. Preflight
        preflight = preflight_azure_logs(cred_loader)

        if not preflight["any_available"]:
            return f"**Log Investigation — Setup Required**\n\n{preflight['setup_guide']}"

        # 2. Use workspace from preflight if not explicitly provided
        resolved_workspace = workspace_id or preflight.get("log_analytics_workspace")

        # 3. Enrich query
        enriched = (
            f"{query}\n\n"
            f"Focus on: resource create/write operations, principal attribution, "
            f"suspicious scaling or replication events in the last {time_range_hours} hours.\n\n"
            f"Diagnostic settings={'enabled' if preflight['diagnostic_settings_enabled'] else 'not enabled'}, "
            f"workspace={'found' if resolved_workspace else 'not found'}."
        )

        log_session = f"{session_id}_log_worker"
        try:
            message, last_agent, _, _ = azure_log_analytics_agent(
                cred_loader=cred_loader,
                user_input=enriched,
                session_id=log_session,
                workspace_id=resolved_workspace,
                region=region,
                customer=customer,
                account=account,
            )
        except Exception as e:
            logger.error(f"Log worker Azure call failed: {e}")
            return f"Log investigation failed: {str(e)}"

        return f"**Log Investigation Result (via {last_agent}):**\n\n{message}"

    return investigate_logs_for_cost_spike
```

---

### 4.4 NEW: LogAnalyticsWorker prompt
```
Codly_Backend/chatbot/finops/cost_analytics/prompts/LogAnalyticsWorker.md
```

Place the LogAnalyticsWorker prompt (provided) verbatim into this file.
The prompt covers: decision tree, AWS steps, Azure steps, finding format,
setup guides, hard rules, manual trigger behaviour, and output checklist.
Single file, referenced by both Athena and V4 agents via `load_prompt()`.

---

### 4.5 MODIFY: Athena agent — wire the log worker
```
Codly_Backend/chatbot/finops/cost_analytics/athena/agent.py
```

**Changes:**

1. Import at top:
```python
from .log_worker_tool import create_aws_log_worker_tool
```

2. Add constant:
```python
LOG_WORKER_AGENT = "LogAnalyticsWorker"
LOG_WORKER_PROMPT_PATH = "chatbot/finops/cost_analytics/prompts/LogAnalyticsWorker.md"
```

3. Extend state:
```python
class CostAnalyticsAthenaState(SwarmState):
    athena_query_count: NotRequired[int]
    last_sql_preview: NotRequired[str]
    log_investigation_result: NotRequired[str]   # NEW
    log_sources_available: NotRequired[dict]     # NEW
```

4. In `create_athena_agent()`, after building the existing tools, add:
```python
log_worker_tool = create_aws_log_worker_tool(
    cred_loader=athena_config["cred_loader"],
    session_id=session_id,
    customer=customer,
    account=account,
    region=athena_config.get("aws_region", "us-east-1"),
)
```

5. Add LogAnalyticsWorker as a swarm agent:
```python
log_worker_prompt = load_prompt(LOG_WORKER_PROMPT_PATH)
# inject UTC, customer name
swarm.create_agent(
    agent_name=LOG_WORKER_AGENT,
    agent_description="Investigates CloudTrail and CloudWatch logs to find root cause of cost spikes and attribute cost to specific IAM actors or resource creation events.",
    prompt=log_worker_prompt,
    tools=[log_worker_tool],
    model_category="high",
    default_active=False,
)
```

6. Add handoff config from supervisor to log worker:
```python
supervisor_to_log_worker = HandoffConfig(
    agent_name=LOG_WORKER_AGENT,
    include_task_description=True,
    pass_full_history=False,
    description="Route to LogAnalyticsWorker when user asks WHY cost spiked, WHO caused a cost, or requests root cause analysis. Also trigger on /logs or 'investigate logs'.",
    task_description_hint="Include the suspected resource type and time range in the task description. Example: 'Investigate why EC2 costs spiked on June 15 — check last 48 hours of CloudTrail events'",
)
swarm.link_agents(SUPERVISOR_AGENT, [
    ...<existing handoffs>...,
    supervisor_to_log_worker,
])
```

---

### 4.6 MODIFY: Athena supervisor prompt
```
Codly_Backend/chatbot/finops/cost_analytics/athena/prompts/AthenaV4Supervisor.md
```

Add this section:

```markdown
## Log Investigation Routing

When the user's query is about WHY costs changed, WHO caused a cost,
or ROOT CAUSE of a spike — route to `LogAnalyticsWorker` first to gather log
evidence, then synthesize the cost data + log findings into a final answer.

**Trigger keywords (auto-route to LogAnalyticsWorker):**
- "why did cost spike", "cost increased", "what caused", "who created"
- "root cause", "investigate", "anomaly", "explain the spike"
- "who made the API call", "which role", "which IAM", "what happened on [date]"

**Manual trigger:** If user says `/logs` or `investigate logs` → route immediately
to LogAnalyticsWorker with the current query context.

When LogAnalyticsWorker returns, incorporate its findings into your final summary:
- Reference the actor and event timeline it found
- Connect the log events to the cost numbers from the Athena query
- Present a unified "what happened + how much it cost" answer
```

---

### 4.7 MODIFY: V4 agent — wire the Azure log worker
```
Codly_Backend/chatbot/finops/cost_analytics/v4/agent.py
```

Identical pattern to Athena agent changes above, but:
- Import `create_azure_log_worker_tool` from `v4/log_worker_tool.py`
- Apply to both `create_v4_agent()` (single-table) and `create_v4_multi_agent()` (multi-cost-type)
- Use `synapse_config.get("azure_region", "centralindia")` for the region param

---

### 4.8 MODIFY: V4 supervisor prompts — add routing rule
```
Codly_Backend/chatbot/finops/cost_analytics/v4/prompts/CostAnalyticsV4Supervisor.md
Codly_Backend/chatbot/finops/cost_analytics/v4/prompts/CostAnalyticsSupervisorV4Multi.md
```

Same routing rule section as Athena supervisor prompt (Section 4.6 above).

---

## 5. Frontend — Manual `/logs` Trigger

**File:** `Codly-Frontend/src/components/FinOps.jsx`
**Function:** `sendMessage()` (line ~289)

Add detection before the API call:
```javascript
// Detect /logs command — annotate the payload so backend can fast-track
if (messageToSend.startsWith("/logs") || messageToSend.toLowerCase().startsWith("investigate logs")) {
  payload.force_log_investigation = true;
}
```

The backend supervisor prompt already handles the routing; this flag is optional
enrichment if we want the backend to skip cost queries entirely and go straight
to logs. Can be added in Phase 3 after backend is confirmed working.

---

## 6. Implementation Order

### Phase 1 — AWS backend (start here)
1. Create `chatbot/finops/cost_analytics/log_preflight.py` (AWS section)
2. Create `chatbot/finops/cost_analytics/athena/log_worker_tool.py`
3. Create `chatbot/finops/cost_analytics/shared/prompts/LogAnalyticsWorker.md`
   (paste the user-provided prompt verbatim)
4. Extend `CostAnalyticsAthenaState` in `athena/agent.py`
5. Wire log worker into `athena/agent.py` (`create_athena_agent()`)
6. Update `athena/prompts/AthenaV4Supervisor.md` with routing rule
7. **Test:** Ask "Why did my EC2 cost spike?" in the cost analysis chat → verify
   log worker fires and returns a structured finding

### Phase 2 — Azure backend
8. Add Azure section to `log_preflight.py`
9. Create `chatbot/finops/cost_analytics/v4/log_worker_tool.py`
10. Wire log worker into `v4/agent.py` (both single + multi-cost-type)
11. Update V4 supervisor prompts
12. **Test:** Same spike question with an Azure account

### Phase 3 — Frontend (after backend confirmed)
13. Add `/logs` command detection in `FinOps.jsx` `sendMessage()`
14. Optionally show a "Log Investigation" badge/section in the response UI
    when the response contains `**Log Investigation Result**` in the markdown

---

## 7. Research Answers (all resolved from codebase)

### Q1 — `cred_loader` is a live object passed directly ✅
`create_athena_agent()` receives `cred_loader` as its own top-level parameter
(not inside `athena_config`). It is stored in the `context` dict as
`context["cred_loader"]`. The Athena tools call `cred_loader.get_env_values()`
at query time. The log worker tool factory can receive `cred_loader` directly —
same object, no reload needed.

**Implementation:** `create_aws_log_worker_tool(cred_loader=cred_loader, ...)`
called inside `create_athena_agent()` right after `context` is built.

---

### Q2 — `azure-mgmt-monitor==7.0.0` is already in deps ✅
Confirmed in `pyproject.toml` line 28. `MonitorManagementClient` from
`azure.mgmt.monitor` is available. Azure preflight can use it as written.

---

### Q3 — `session_id` is a top-level param of `create_athena_agent()` ✅
Signature:
```python
def create_athena_agent(user_input, session_id, customer, account, cred_loader, athena_config, user=None, save_history=True)
```
`session_id` is directly available to pass into `create_aws_log_worker_tool()`.
Same for `create_v4_agent()` — identical signature pattern.

---

### Q4 — Use existing `prompts/` at root of `cost_analytics/` ✅
`chatbot/finops/cost_analytics/prompts/` already exists (used by legacy v2/v3
agents). Place `LogAnalyticsWorker.md` there — one file, referenced by both
Athena and V4 agents. No new directory needed.

**Final path:** `chatbot/finops/cost_analytics/prompts/LogAnalyticsWorker.md`

---

## 8. Success Criteria

- "Why did my EC2 cost spike on June 15?" → supervisor auto-routes to log worker →
  worker returns CloudTrail `RunInstances` events → final response merges cost data
  + log evidence in one answer.
- "Who created the RDS instance costing $2000?" → log worker finds `CreateDBInstance`
  + IAM principal → attributed in the response.
- CloudTrail not enabled → agent returns clear setup guide, not an error.
- Azure Activity Log not configured → same setup guide behavior.
- `/logs` typed in chat → immediately invokes log investigation with a clarifying
  question before firing queries.
- Log worker result is self-contained and ready for the cost supervisor to merge
  with Athena/Synapse numbers.
