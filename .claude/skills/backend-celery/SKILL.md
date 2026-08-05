---
name: backend-celery
description: Background task patterns for Codly Backend — run_in_background (thread pool), @shared_task (Celery), and WebSocket real-time updates. Use when adding background processing or real-time progress notifications.
---

# Codly — Background Tasks & WebSockets

## Decision: which mechanism to use

| Task duration | Mechanism | When |
|---|---|---|
| < 30 seconds | `run_in_background()` | Quick async fire-and-forget |
| > 30 seconds | `@shared_task` (Celery) | Long-running, retryable, schedulable |
| Real-time progress | `send_websocket_update()` | Live scan/execution progress |

## run_in_background

Thread pool (4 workers default). Fire-and-forget — no result tracking.

```python
from common.background_tasks import run_in_background

def my_view(request):
    # Don't await — returns immediately
    run_in_background(process_data, customer_id, account_id)
    return Response({"status": "processing started"})

def process_data(customer_id, account_id):
    # runs in background thread
    ...
```

Also available by dotted path (useful for avoiding circular imports):

```python
from common.background_tasks import run_in_background_by_path

run_in_background_by_path("myapp.tasks.process_data", customer_id, account_id)
```

## Celery @shared_task

For long-running work (compliance scans, report generation, syncs).

```python
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_my_task(self, customer_id: int, account_id: int):
    try:
        from manage_user.models import Customer, Account
        customer = Customer.objects.get(id=customer_id)
        account = Account.objects.get(id=account_id, customer=customer)
        # ... do work
    except Exception as exc:
        logger.exception("run_my_task failed: customer=%s", customer_id)
        raise self.retry(exc=exc, countdown=60)
```

Register task in `Codly_AI_Langraph/celery.py` autodiscovery (happens automatically if task is in `tasks.py` of a registered app).

Queues:
- `default` — general tasks
- `agent_test` — agent testing tasks

```python
@shared_task(queue="default")
def my_task():
    ...
```

## Trigger Celery task from view

```python
from .tasks import run_my_task

# Async (non-blocking)
task = run_my_task.delay(customer.id, account.id)
return Response({"task_id": str(task.id)})

# With specific queue
run_my_task.apply_async(args=[customer.id, account.id], queue="default")
```

## WebSocket progress updates

Used by compliance scans and OS hardening for live progress UI.

```python
from compliance.compliance_dashboard.utils import send_websocket_update

# Send update to WebSocket consumer
send_websocket_update(
    scan_id=str(scan.scan_id),
    event_type="progress",
    data={
        "progress": 45,
        "status": "scanning",
        "message": "Checking IAM policies...",
    }
)
```

WebSocket endpoints (consumers in `chatbot/routing.py`):

| WS endpoint | Purpose |
|---|---|
| `ws/compliance/scan/<scan_id>/` | Live compliance scan progress |
| `ws/scan-hardening/` | OS hardening scan progress |
| `ws/execute-hardening/` | OS hardening execution |

## Scheduled tasks (Celery Beat)

Defined in `Codly_AI_Langraph/settings.py` under `CELERY_BEAT_SCHEDULE`:

```python
CELERY_BEAT_SCHEDULE = {
    "check-new-tickets": {
        "task": "ticket_management.tasks.check_for_new_tickets",
        "schedule": 300,  # every 5 minutes
    },
}
```

Current scheduled tasks:
- `ticket_management.tasks.check_for_new_tickets` — every 300s
- `ticket_management.tasks.check_existing_ticket` — every 300s
- `ticket_management.tasks.check_monitoring` — every 300s

## Running workers

```bash
# Worker (processes tasks)
celery -A Codly_AI_Langraph worker -Q default,agent_test -l info

# Beat scheduler (triggers scheduled tasks)
celery -A Codly_AI_Langraph beat -l info
```
