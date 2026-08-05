# RunBook Builder — Backend Implementation Plan
> **Date**: April 2026  
> **Scope**: Admin Portal RunBook Builder — EC2 Post-Deploy use case  
> **Status**: Planning (pending answers to RUNBOOK_BACKEND_QUESTIONS.md)

---

## What We Are Building

The **Admin Portal RunBook Builder** backend — a system that lets admins design multi-step automation workflows (RunBooks), save them to the DB, and execute them in sequence using Codly's existing agents (OS Management, OS Hardening, Compliance, etc.), with real-time step-by-step streaming, human checkpoint pausing, and execution history.

**Primary Use Case**: EC2 Post-Deploy RunBook  
Trigger: CloudTrail `RunInstances` event → Compliance Scan → OS Patching → OS Hardening → Human Checkpoint (approval) → Install Monitoring Agents → Create ITSM Ticket.

---

## What Already Exists (Do NOT Rebuild)

| Component | Location | What It Does |
|-----------|----------|-------------|
| OS Management Agent | `chatbot/os_management/` | SSH patching, health check, install agents |
| OS Hardening Agent | `chatbot/os_hardening/` | CIS hardening via LangGraph graph |
| Compliance Agent | `compliance/` | CIS benchmark scans |
| Inventory Agent | `chatbot/inventory_management/` | EC2/VM discovery |
| AIWorkflow, WorkflowTrigger, WorkflowRun models | `ai_ops/models.py` | Customer-facing AI ops (existing, DO NOT reuse — new app) |
| WebSocket streaming pattern | `ai_ops/consumers.py` | AsyncWebsocketConsumer with group_send |
| Human Intervention pattern | `ai_ops/models.py` + `ai_ops/consumers.py` | Pausing run, awaiting human response |
| Admin auth | `admin_portal/views.py` | `CookieJWTAdminAuthentication` + `CustomIsAdminAuthenticated` |
| Celery + Celery Beat | `docker-compose.yml` | Background tasks + scheduled triggers |

---

## Architecture Overview

```
Admin Portal (Next.js)
        │
        │  REST + WebSocket
        ▼
Codly_Backend/runbooks/          ← NEW Django app
├── models.py                    ← RunBook, RunBookStep, RunBookTrigger, RunBookRun, RunBookStepRun
├── views.py                     ← CRUD + execution APIs (admin-auth only)
├── serializers.py               ← DRF serializers
├── urls.py
├── consumers.py                 ← WebSocket consumer (streams step-by-step progress)
├── routing.py
├── executor/
│   ├── engine.py                ← Core sequential executor (chains agent steps)
│   ├── step_runners/
│   │   ├── compliance_runner.py ← wraps compliance agent
│   │   ├── os_management_runner.py ← wraps os_management agent
│   │   ├── os_hardening_runner.py  ← wraps os_hardening agent
│   │   ├── human_checkpoint_runner.py ← pauses, waits for admin approval
│   │   └── notification_runner.py ← Slack/email/ticket creation
│   └── registry.py              ← maps step_type → runner class
├── triggers/
│   ├── cloudtrail_webhook.py    ← listens for RunInstances event from EventBridge
│   └── scheduled.py            ← Celery Beat tasks for cron triggers
├── admin.py
├── apps.py
└── migrations/
```

---

## Phase 1 — Django Models

### New app: `runbooks/`

#### 1.1 `RunBook` model
```
RunBook
├── id (UUID)
├── name
├── description
├── customer → FK(Customer)
├── account → FK(Account), null=True  (can be account-specific or multi-account)
├── status  → "draft" | "active" | "paused"
├── permission_level → "read_only" | "operator" | "power_user"
├── tags → JSONField (list of strings)
├── created_by → FK(AdminUser)
├── is_active
├── created_at, updated_at
```

#### 1.2 `RunBookStep` model
```
RunBookStep
├── id
├── runbook → FK(RunBook)
├── step_order  (1, 2, 3...)
├── step_type   → "compliance_scan" | "os_patching" | "os_hardening" | "human_checkpoint" 
│                 | "install_agents" | "create_ticket" | "notify_slack" | "script_runner"
├── label       (display name e.g. "CIS Level 1 Benchmark Scan")
├── config      → JSONField (step-specific params)
│                 e.g. {"benchmark": "CIS_L1", "auto_remediate": false}
│                 e.g. {"platform": "linux", "patch_type": "security"}
├── condition   → JSONField (run if prev result matches)
│                 e.g. {"field": "violations_count", "operator": ">", "value": 0}
├── on_failure  → "continue" | "stop" | "alert"
├── timeout_seconds
├── is_active
```

#### 1.3 `RunBookTrigger` model
```
RunBookTrigger
├── id
├── runbook → FK(RunBook)
├── trigger_type → "manual" | "cloudtrail_event" | "scheduled" | "ticket" | "webhook"
├── config → JSONField
│   Examples:
│   manual:            {}
│   cloudtrail_event:  {"event_name": "RunInstances", "account_id": "..."}
│   scheduled:         {"cron": "0 2 * * *", "timezone": "Asia/Kolkata"}
│   webhook:           {"secret_token": "...", "allowed_ips": [...]}
├── is_active
├── created_at
```

#### 1.4 `RunBookRun` model
```
RunBookRun
├── id (UUID, also the session_id for WebSocket)
├── runbook → FK(RunBook)
├── customer → FK(Customer)
├── account → FK(Account)
├── triggered_by → "manual" | "cloudtrail_event" | "scheduled" | "webhook"
├── trigger_context → JSONField (event payload that triggered this)
│   e.g. {"instance_id": "i-0abc123", "region": "us-east-1"}
├── status → "pending" | "running" | "paused_awaiting_human" | "completed" | "failed"
├── started_by → FK(AdminUser), null for automated triggers
├── current_step_order → int (which step is currently running)
├── human_checkpoint_pending → bool
├── human_checkpoint_data → JSONField (prompt + options shown to admin)
├── human_checkpoint_response → JSONField (admin's choice + note)
├── result → JSONField (final summary)
├── error_message
├── created_at, updated_at
```

#### 1.5 `RunBookStepRun` model
```
RunBookStepRun
├── id
├── run → FK(RunBookRun)
├── step → FK(RunBookStep)
├── step_order
├── status → "pending" | "running" | "success" | "failed" | "skipped" | "waiting"
├── input_context → JSONField (what was passed in)
├── output → JSONField (structured result from agent)
├── raw_output_text → TextField (human-readable summary)
├── started_at, completed_at
├── duration_seconds → float
├── error_message
```

---

## Phase 2 — REST API Endpoints

All endpoints use `CookieJWTAdminAuthentication` + `CustomIsAdminAuthenticated`.

### RunBook CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin-api/runbooks/` | List all RunBooks (filterable by customer, status, cloud) |
| POST | `/admin-api/runbooks/` | Create a new RunBook |
| GET | `/admin-api/runbooks/{id}/` | Get RunBook detail (with steps + triggers) |
| PUT | `/admin-api/runbooks/{id}/` | Update RunBook metadata |
| DELETE | `/admin-api/runbooks/{id}/` | Soft delete (set is_active=False) |
| POST | `/admin-api/runbooks/{id}/duplicate/` | Clone RunBook |
| PATCH | `/admin-api/runbooks/{id}/status/` | Toggle active/paused/draft |

### Step CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin-api/runbooks/{id}/steps/` | List steps (ordered) |
| POST | `/admin-api/runbooks/{id}/steps/` | Add a step |
| PUT | `/admin-api/runbooks/{id}/steps/{step_id}/` | Update step config |
| DELETE | `/admin-api/runbooks/{id}/steps/{step_id}/` | Remove step |
| POST | `/admin-api/runbooks/{id}/steps/reorder/` | Reorder steps (accepts ordered list of IDs) |

### Trigger Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin-api/runbooks/{id}/triggers/` | List triggers |
| POST | `/admin-api/runbooks/{id}/triggers/` | Add trigger |
| DELETE | `/admin-api/runbooks/{id}/triggers/{trigger_id}/` | Remove trigger |

### Execution

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin-api/runbooks/{id}/run/` | Start a manual run → returns `run_id` for WebSocket |
| GET | `/admin-api/runbooks/{id}/runs/` | List all runs for this RunBook |
| GET | `/admin-api/runbooks/runs/{run_id}/` | Get run detail with all step statuses |
| POST | `/admin-api/runbooks/runs/{run_id}/respond/` | Submit human checkpoint response |
| POST | `/admin-api/runbooks/runs/{run_id}/cancel/` | Cancel a running run |

### Supporting

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin-api/runbooks/available-steps/` | List all available step types with their config schemas |
| GET | `/admin-api/runbooks/available-agents/` | List Codly agents available to use in steps |

### External Trigger (Webhook)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhooks/runbook-trigger/{trigger_id}/` | External webhook (EventBridge → this endpoint) — **NO auth cookie, uses HMAC secret** |

---

## Phase 3 — WebSocket (Real-Time Execution Streaming)

**Channel**: `ws/runbooks/run/{run_id}/`  
**Pattern**: Same as `ai_ops/consumers.py`

### Outbound message types (backend → frontend)

```json
{"type": "connected", "run_id": "..."}
{"type": "step_started", "step_order": 2, "step_label": "OS Patching", "step_type": "os_patching"}
{"type": "step_progress", "step_order": 2, "message": "Applying security patches...", "node": "os_patch_worker"}
{"type": "step_completed", "step_order": 2, "status": "success", "duration": "1m 12s", "summary": "12 patches applied"}
{"type": "step_failed", "step_order": 2, "error": "SSH connection refused", "on_failure": "stop"}
{"type": "step_skipped", "step_order": 3, "reason": "Condition not met: violations_count = 0"}
{"type": "human_checkpoint", "step_order": 4, "message": "OS Hardening complete. Proceed to install monitoring agents?", "options": ["Approve", "Reject", "Skip"]}
{"type": "run_completed", "status": "completed", "duration": "3m 41s", "summary": {...}}
{"type": "run_failed", "error": "...", "failed_at_step": 3}
```

### Inbound message types (frontend → backend)

```json
{"type": "human_response", "choice": "Approve", "note": "Looks good"}
{"type": "cancel_run"}
```

---

## Phase 4 — RunBook Executor Engine

**Location**: `runbooks/executor/engine.py`

### Core Logic

```
RunBookExecutor.execute(run_id)
  ├── Load RunBookRun + all RunBookSteps (ordered)
  ├── For each step:
  │    ├── Check condition (skip if not met)
  │    ├── Create RunBookStepRun record
  │    ├── Update run.current_step_order
  │    ├── Push "step_started" to WebSocket
  │    ├── Delegate to StepRunner (via registry)
  │    ├── StepRunner yields progress events → push to WebSocket
  │    ├── On completion: update RunBookStepRun, push "step_completed"
  │    ├── If step is "human_checkpoint": push event, pause, wait for response
  │    └── On failure: apply on_failure policy (continue / stop / alert)
  └── Update RunBookRun.status = "completed" / "failed"
       Push "run_completed" to WebSocket
```

### Step Runner Registry

```python
STEP_RUNNER_REGISTRY = {
    "compliance_scan":      ComplianceStepRunner,
    "os_patching":          OSPatchingStepRunner,
    "os_hardening":         OSHardeningStepRunner,
    "human_checkpoint":     HumanCheckpointStepRunner,
    "install_agents":       InstallAgentsStepRunner,
    "create_ticket":        CreateTicketStepRunner,
    "notify_slack":         SlackNotificationStepRunner,
    "script_runner":        ScriptRunnerStepRunner,
}
```

### How Runners Wrap Existing Agents

```
OSPatchingStepRunner.run(context)
  └── calls chatbot.os_management.agent.execute_os_management_agent(
          user_input = "Apply latest security patches",
          session_id = run_id,
          customer   = run.customer,
          account    = run.account,
          cred_loader = ...,
          resource_id = context["instance_id"],
          region      = context["region"],
          platform    = step.config.get("platform", "linux"),
      )
  └── yields progress events from agent response
  └── returns structured output: {"patches_applied": 12, "reboot_required": false}

ComplianceStepRunner.run(context)
  └── calls compliance scanning for the specific resource
  └── returns {"violations_count": 3, "violations": [...]}

HumanCheckpointStepRunner.run(context)
  └── push "human_checkpoint" WebSocket event
  └── set run.human_checkpoint_pending = True
  └── set run.status = "paused_awaiting_human"
  └── PAUSE — generator yields nothing; execution resumes when /respond/ is called
```

---

## Phase 5 — CloudTrail Event Trigger

### How It Works

```
AWS CloudTrail (RunInstances event)
    → AWS EventBridge rule → HTTP POST to Codly webhook endpoint
    → POST /webhooks/runbook-trigger/{trigger_id}/
    → HMAC-SHA256 signature verified
    → Find all active RunBooks with matching trigger (cloudtrail_event, event_name=RunInstances)
    → For each RunBook: create RunBookRun with trigger_context = {instance_id, region, account_id}
    → Enqueue Celery task: execute_runbook_task.delay(run_id)
```

**Webhook endpoint**: No cookie auth. Uses HMAC signature in `X-Codly-Signature` header.  
**Celery task**: `runbooks.tasks.execute_runbook_task` — runs the executor asynchronously.

---

## Phase 6 — Celery Tasks

```python
# runbooks/tasks.py

@shared_task
def execute_runbook_task(run_id: str):
    """Execute a RunBook run asynchronously."""
    ...

@shared_task  
def trigger_scheduled_runbooks():
    """Called by Celery Beat — find all RunBooks with scheduled triggers due now."""
    ...
```

Celery Beat entry in settings:
```python
CELERY_BEAT_SCHEDULE["runbook_scheduled_check"] = {
    "task": "runbooks.tasks.trigger_scheduled_runbooks",
    "schedule": crontab(minute="*"),  # every minute, checks for due cron triggers
}
```

---

## EC2 Post-Deploy RunBook — Full Backend Flow

```
1. EventBridge fires → POST /webhooks/runbook-trigger/{trigger_id}/
   payload: {instance_id: "i-0abc", region: "us-east-1", event: "RunInstances"}

2. Webhook view:
   - Verifies HMAC signature
   - Finds RunBook by trigger_id
   - Creates RunBookRun (status=pending, trigger_context={...})
   - Enqueues execute_runbook_task.delay(run_id)

3. Admin opens WebSocket: ws/runbooks/run/{run_id}/
   - Receives "connected"

4. Executor runs Step 1 — Compliance Scan:
   - ComplianceStepRunner calls compliance agent for the instance
   - Streams progress to WS
   - Result: {violations_count: 3}
   - "step_completed" → WS

5. Step 2 — OS Patching (condition: always):
   - OSPatchingStepRunner calls os_management agent
   - Streams SSH output to WS
   - Result: {patches_applied: 12}

6. Step 3 — OS Hardening:
   - OSHardeningStepRunner calls os_hardening agent
   - Streams hardening steps to WS
   - Result: {hardening_applied: true, cis_score: 94}

7. Step 4 — Human Checkpoint:
   - Push "human_checkpoint" to WS:
     {"message": "Hardening complete. Proceed to install monitoring agents?",
      "options": ["Approve", "Reject"]}
   - run.status = "paused_awaiting_human"
   - Admin sees modal in UI, clicks "Approve"

8. Frontend POST /admin-api/runbooks/runs/{run_id}/respond/ {"choice": "Approve"}
   - Sets run.human_checkpoint_response
   - Resumes executor from Step 5

9. Step 5 — Install Monitoring Agents:
   - OSManagementStepRunner: install CloudWatch agent, Splunk/Elastic SIEM
   - Streams progress

10. Step 6 — Create ITSM Ticket:
    - CreateTicketStepRunner calls Freshservice/Jira API
    - Creates "EC2 Post-Deploy Complete" ticket with full run summary

11. RunBookRun.status = "completed"
    "run_completed" → WS
```

---

## File Structure to Create

```
Codly_Backend/
└── runbooks/                          ← NEW Django app
    ├── __init__.py
    ├── apps.py
    ├── admin.py
    ├── models.py                      ← RunBook, RunBookStep, RunBookTrigger, RunBookRun, RunBookStepRun
    ├── serializers.py
    ├── views.py                       ← admin-auth CRUD + execution views
    ├── urls.py
    ├── consumers.py                   ← WebSocket consumer
    ├── routing.py
    ├── tasks.py                       ← Celery tasks
    ├── executor/
    │   ├── __init__.py
    │   ├── engine.py                  ← Main executor loop
    │   ├── registry.py                ← step_type → runner mapping
    │   ├── base_runner.py             ← Abstract base StepRunner
    │   └── step_runners/
    │       ├── __init__.py
    │       ├── compliance_runner.py
    │       ├── os_patching_runner.py
    │       ├── os_hardening_runner.py
    │       ├── human_checkpoint_runner.py
    │       ├── install_agents_runner.py
    │       ├── create_ticket_runner.py
    │       └── notify_slack_runner.py
    ├── triggers/
    │   ├── __init__.py
    │   ├── cloudtrail_webhook.py      ← Webhook view (HMAC verified)
    │   └── scheduler.py              ← Scheduled trigger Celery task
    └── migrations/
```

---

## Integration Points with Existing Code

| RunBook Component | Existing Code It Calls |
|-------------------|----------------------|
| Compliance step runner | `compliance/` views / agent |
| OS Patching step runner | `chatbot/os_management/agent.py::execute_os_management_agent()` |
| OS Hardening step runner | `chatbot/os_hardening/agents.py` (needs async wrapper) |
| Create Ticket step runner | `ticket_management/` integrations (Freshservice/Jira) |
| Credential loading | `manage_user/credentials_management.py::create_cloud_cred_loader()` |
| Admin auth | `admin_portal/views.py::CookieJWTAdminAuthentication` |
| WebSocket pattern | Mirrored from `ai_ops/consumers.py` |
| Celery tasks | Registered in `codly_v2/celery.py` |

---

## What We Are NOT Building (Yet)

- Frontend RunBook builder canvas wiring (already has sample data — we wire real API after backend)
- Dynamic AI Workflows (Planner Engine — Codly 2.0 future phase)
- RunBook marketplace / templates
- Azure / GCP-triggered RunBooks (Phase 1 = AWS only)
- Scheduled trigger UI (Phase 1 = manual + CloudTrail only)

---

## Open Items (See RUNBOOK_BACKEND_QUESTIONS.md)

Questions need answers before we can implement specific pieces. See the questions doc.
