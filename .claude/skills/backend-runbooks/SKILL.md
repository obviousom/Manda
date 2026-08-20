---
name: backend-runbooks
description: RunBook automation patterns for Codly Backend — admin-authored multi-step workflows (RunBook/RunBookStep/RunBookTrigger/RunBookRun/RunBookStepRun models), the executor engine, step runner registry (cloud_agnostic vs providers/<cloud>), human checkpoints, WebSocket live execution, triggers, and template install. Use when working on runbooks/ app.
---

# Codly — RunBooks

App: `runbooks/` (mounted at `/admin-api/runbooks/`). Separate customer-facing surface: `chatbot/views/runbook_views.py` (mounted at `/chatbot/runbooks/`, consumed by the AIOps chat, not the admin portal).

A RunBook is an admin-designed sequence of steps (agents/integrations) run manually, on AI Ops resource creation, or (future) on schedule/webhook/ticket.

## Architecture

```
runbooks/
├── models.py                      # RunBook, RunBookStep, RunBookTrigger, RunBookRun, RunBookStepRun
├── views.py                       # 17 REST endpoints, admin-scoped (CookieJWTAuthentication)
├── serializers.py                 # DRF serializers (list/detail/run)
├── urls.py                        # mounted at /admin-api/runbooks/
├── consumers.py                   # RunBookRunConsumer — ws/runbooks/run/<uuid>/
├── routing.py
├── tasks.py                       # Celery: execute_runbook_task, resume_runbook_task
├── triggers/                      # PACKAGE — the only live trigger module (see Known gap #1)
│   ├── base.py                    #   _enqueue, _matching_runbooks, enqueue_resume
│   ├── manual.py                  #   fire_manual()
│   └── ai_ops_resource.py         #   fire_ai_ops_runbook(), fire_ai_ops_resource_created(), fire_ai_ops_ec2_created()
├── services/
│   └── template_install.py        # clone a template RunBook into a customer, remapping agent_hub PKs
├── executor/
│   ├── base_runner.py             # BaseStepRunner, RunContext, StepResult, HumanInterventionRequired
│   ├── registry.py                # register_step_runner() decorator + get_step_runner() lookup
│   ├── engine.py                  # execute_run() — the orchestration loop
│   ├── context_collector/         # pre-run LLM pass that parses freeform dynamic_context
│   └── step_runners/
│       ├── <step_type>.py         # THIN REDIRECTS ONLY — `from ....cloud_agnostic.X import *`
│       │                          #   or `from ....providers.aws.X import *`. Never put logic here.
│       ├── cloud_agnostic/        # real impls: notify_slack, notify_teams, notify_email_ses,
│       │                          #   create_ticket, agent_hub_agent, human_checkpoint, wait_delay
│       └── providers/
│           ├── aws/               # real impls: os_patching, os_hardening, install_agents, script_runner
│           ├── azure/             # placeholder, __all__ = [] — planned Q4 2026
│           └── gcp/                # placeholder, __all__ = [] — planned Q4 2026
└── management/commands/
    ├── seed_runbooks.py           # demo EC2 Post-Deploy RunBook seeder
    └── export_codly_runbooks_seed.py
```

Frontend (`Codly-Frontend/src/admin/`):
`components/runbooks/{RunBooksDashboard,RunBookBuilder}.tsx`, `stores/runbooks-store.ts`,
`hooks/runbooks/useRunBooks.ts` (TanStack Query), `lib/api/runbooks.ts`, `types/runbooks.d.ts`,
page at `app/admin/(dashboard)/runbooks/`. Builder's step catalog is driven live by `useAvailableSteps()`
(hits `GET /available-steps/`) — not static sample data.

## Step runner contract

Every step type is a `BaseStepRunner` subclass registered via decorator:

```python
from runbooks.executor.base_runner import BaseStepRunner, RunContext, StepResult
from runbooks.executor.registry import register_step_runner

@register_step_runner("my_step_type", cloud_providers=["AWS"])  # omit cloud_providers = multi-cloud
class MyStepRunner(BaseStepRunner):
    """First line of docstring becomes the catalog description."""

    display_name = "My Step"
    category = "agent"  # "agent" | "integration" | "utility"
    config_schema = {"some_field": {"type": "string", "description": "..."}}

    def run(self, ctx: RunContext) -> StepResult:
        instance_id = ctx.get_resource_id()   # shared_context["instance_id" or "resource_id"]
        region = ctx.get_region()
        if not instance_id:
            return StepResult(success=False, error="No instance_id in context")
        # ... do work, call ctx.emit("step_progress", message=...) for live UI updates ...
        return StepResult(success=True, output={...}, text="human-readable summary")
```

Register the real implementation under `cloud_agnostic/` (works for every `RunBook.cloud`) or
`providers/<cloud>/` (single-cloud only), then add a **redirect shim** at the flat
`executor/step_runners/<name>.py` path so `registry.py`'s static import list keeps working:

```python
# executor/step_runners/my_step_type.py
"""My Step step runner - redirect for backward compatibility."""
from runbooks.executor.step_runners.cloud_agnostic.my_step_type import *  # noqa: F401, F403
```

To raise a human checkpoint mid-step instead of failing:

```python
from runbooks.executor.base_runner import HumanInterventionRequired
raise HumanInterventionRequired(
    "Confirm before deleting the snapshot?",
    options=["Approve", "Reject", "Skip"],
    payload={"snapshot_id": snap_id},
    checkpoint_type="human",  # "human" | "error" | "input"
)
```

## Executor engine (`executor/engine.py`)

`execute_run(run_id, resume_response=None)` — synchronous, called from a Celery task, idempotent
on `run.current_step_order`. Per step, in order:

1. Skip if `step.condition` (`{field, op, value}` against `run.context`) evaluates false.
2. Create a `RunBookStepRun`, emit `step_started`.
3. Resolve runner via `get_step_runner(step.step_type, cloud_provider=run.account.cloud_provider)`.
4. Run it. On `HumanInterventionRequired` → pause (`paused_awaiting_human`), emit `human_checkpoint`, return.
5. On failure, `step.on_failure` decides: `continue` (next step), `stop` (fail whole run),
   `pause` (default — same `human_checkpoint` shape as above, options `Retry/Skip/Abort`).
6. On success, merge `result.output` into `run.context` under `step_{order}_{type}`, hoist
   `instance_id`/`region`/`violations_count` to top-level context keys, append to `run_narrative`.

Pre-run: if the trigger context includes `dynamic_context` (freeform admin text), the
`context_collector` runs a cheap (`model_category="low"`) SwarmAgents pass with a 30s hard
timeout in a background thread to extract structured fields before step 1 — failures here are
swallowed and the run proceeds with just the trigger context.

Resume path (`respond/` endpoint or WS `human_response`): `resume_response.choice` of
`Approve`/anything → advance past the paused step; `Retry`/`Proceed` → re-run the same step
(optionally with `custom_instruction` merged into context as
`retry_instruction_step_{order}` / `human_input_step_{order}`); `Reject`/`Abort`/`Cancel` → cancel the run.

## WebSocket protocol

`ws/runbooks/run/<uuid>/`, channel group `runbook_run_<uuid>`.

Outbound: `connected`, `snapshot` (full run + `runbook_steps` plan, sent on connect),
`run_started`, `context_collection_started/completed/failed`, `step_started`, `step_progress`,
`step_completed`, `step_failed`, `step_skipped`, `human_checkpoint`, `run_resumed`,
`run_completed`, `run_failed`, `run_cancelled`.

Inbound: `{"type": "human_response", "choice", "note", "custom_instruction"}`,
`{"type": "cancel"}`, `{"type": "ping"}`.

Tenant check happens in `consumers.py::_load_snapshot` (only if the connecting user is
authenticated — anonymous WS connections are accepted, since the run UUID itself is the secret).

## Triggers

```python
from runbooks.triggers import fire_manual, fire_ai_ops_runbook, fire_ai_ops_resource_created, enqueue_resume
```

- `fire_manual(runbook, account, started_by, context)` — admin clicks "Run Now".
- `fire_ai_ops_runbook(runbook, customer, account, use_case_name, resource_id, region, ...)` —
  launch **one specific** runbook (user clicked a specific suggestion card). Does NOT do trigger
  matching/fan-out.
- `fire_ai_ops_resource_created(customer, account, use_case_name, resource_id, region, resource_type, ...)` —
  matches ALL active `RunBookTrigger(trigger_type="ai_ops_resource_created")` rows whose `config`
  is a subset match (`{}` = matches everything; `{"use_case_name": "create_ec2"}` = any EC2 creation)
  and fires a run per match. Use this for background/automatic firing, not for a user-driven click
  (that's `fire_ai_ops_runbook`, precisely to avoid firing unrelated runbooks — see the comment in
  `chatbot/views/runbook_views.py` around the AIOps suggestion-card flow).
- `enqueue_resume(run_id, response)` — used by both `POST .../respond/` and the WS handler.

All enqueue via Celery in prod, a background thread in `DEBUG` (`triggers/base.py::_enqueue`).

## Auth & multi-tenant scoping

Admin endpoints (`runbooks/views.py`) use `CookieJWTAuthentication` + `CustomIsAuthenticated`
(not the `Admin*` classes CLAUDE.md's top-level table implies — same pattern as `admin_portal`,
see `backend-auth`). Customer scoping handles two user-model paths:
`manage_user.User` (has `.customer_id` / `.is_admin`) vs legacy `django.contrib.auth.models.User`
(looked up via `AdminProfile`). Always scope querysets through `_scoped_runbook_qs(request.user)` /
`_scoped_run_qs(request.user)` — never query `RunBook.objects` / `RunBookRun.objects` directly in a view.

Customer-facing endpoints (`chatbot/views/runbook_views.py`, mounted under `/chatbot/runbooks/`)
use plain `manage_user.User.customer_id` — no `AdminProfile` involved.

## Templates

`RunBook.is_template=True` rows (owned by the `Codly` customer) are admin-curated content other
customers can install. `services/template_install.install_runbook_template()` deep-clones steps/
triggers AND remaps any `agent_hub_agent` step's embedded `agent_definition_id` /
`marketplace_instance_id` to a customer-owned copy (matched by natural key `(customer, name)`,
created if missing). `runbook_duplicate` (plain copy within the same customer) intentionally
does NOT remap — the source PKs are already valid there.

## Known gaps (verified in code, not yet fixed)

1. **Two import-shadowed dead files.** `runbooks/triggers.py` (250-line flat module) sits next to
   the `runbooks/triggers/` package of the same name — Python resolves `runbooks.triggers` to the
   package, so the flat file is unreachable dead code with its own drifted copies of
   `fire_ai_ops_resource_created`/`fire_ai_ops_ec2_created`. Same pattern in `chatbot/`:
   `chatbot/runbook_views.py` (June, dead) vs `chatbot/views/runbook_views.py` (Aug, the one
   `chatbot/urls.py` actually imports). Safe to delete both dead files — grep confirms zero live
   importers of either.
2. **AWS-only step runners aren't cloud-scoped at registration.** `os_patching`, `os_hardening`,
   `install_agents`, `script_runner` live under `providers/aws/` but their
   `@register_step_runner(...)` calls omit `cloud_providers=["AWS"]`, so `get_step_runner()`
   treats them as universal. A `RunBook.cloud="AZURE"` or `"GCP"` runbook (both valid choices,
   and `providers/azure|gcp/` are explicit empty placeholders) can add one of these steps and it
   will silently attempt AWS-shaped execution at run time instead of failing fast at config time
   via `available-steps/`'s `cloud_provider` filter or `get_step_runner`'s `ValueError`.
3. **`os_hardening` step is an intentional Phase-1 demo wrapper**, not the real hardening agent —
   its own docstring says it treats `chatbot/os_hardening/` as an opaque blackbox and only applies
   2-3 hardening points via the OS Management agent.

## Quick reference

```bash
# Seed the demo runbook
cd Codly_Backend && uv run python manage.py seed_runbooks --customer-id <id> --account-id <id>

# Django shell — inspect AI-Ops-triggered runs
uv run python manage.py shell -c "
from runbooks.models import RunBookRun
for r in RunBookRun.objects.filter(triggered_by='ai_ops_resource_created').order_by('-created_at')[:5]:
    print(r.id, r.runbook.name, r.status)
"
```

Endpoint testing: use the `X-Dev-Test` headers from the top-level CLAUDE.md. Key endpoints —
`POST /admin-api/runbooks/<uuid>/run/` (body: `account_id`, `region`, optional `dynamic_context`/`context`),
`POST /admin-api/runbooks/runs/<uuid>/respond/` (body: `choice`, optional `note`/`custom_instruction`),
`GET /admin-api/runbooks/available-steps/?cloud_provider=AWS`.
