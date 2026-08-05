---
name: backend-ticket-management
description: Ticket management patterns for Codly Backend — Ticket model, TicketIntegration, TicketProviderFactory, agent architecture, monitoring, and integration APIs. Use when working on ticket_management/ app.
---

# Codly — Ticket Management

App: `ticket_management/`

## Key models

```python
from ticket_management.models import (
    Ticket,
    TicketIntegration,
    TicketGlobalInstructions,
    TicketConversation,
    TicketTask,
)
```

### Ticket model fields

```python
ticket.ticket_id          # External provider ID (Freshservice, Jira, etc.)
ticket.customer           # FK to Customer
ticket.account            # FK to Account
ticket.ticket_type        # "Incident" | "Service"
ticket.status             # "New" | "Active" | "in_Progress" | "Resolved" | "Closed"
ticket.priority           # "P1" | "P2" | "P3" | "P4"
ticket.severity           # "Crucial" | "moderate" | "low" | "Unknown"
ticket.category           # "Utilization" | "Down" | "Security" | "Service_Request"
ticket.sub_category       # "CPU" | "Disk" | "Memory" | "DB" | "Network" | "URL" | ...
ticket.environment        # "Prod" | "Beta" | "Staging" | "UAT" | "Dev"
ticket.instance_id        # Cloud resource ID
ticket.region             # Cloud region
ticket.description        # Full ticket description
ticket.resolution_note    # Resolution text
ticket.created_at
ticket.updated_at
```

### Querying tickets (always filter by customer)

```python
from ticket_management.models import Ticket
from django.utils import timezone
from datetime import timedelta

# All open tickets for a customer
tickets = Ticket.objects.filter(
    customer=customer,
    status__in=["New", "Active", "in_Progress"],
).order_by("-created_at")

# Recent tickets for a resource
recent = Ticket.objects.filter(
    customer=customer,
    instance_id=instance_id,
    created_at__gte=timezone.now() - timedelta(hours=24),
)

# By category and priority
critical = Ticket.objects.filter(
    customer=customer,
    category="Down",
    priority="P1",
    status__in=["New", "Active"],
)
```

## TicketProviderFactory — send/update tickets

```python
from ticket_management.integrations.factory import TicketProviderFactory
from ticket_management.integrations.base import (
    BaseTicketProvider,
    CreateTicketPayload,
    UpdateTicketPayload,
    TicketStatus,
    TicketPriority,
    TicketFilterPayload,
)

# Get provider for customer (reads TicketIntegration from DB)
provider = TicketProviderFactory.create_provider(customer)

# List tickets
filter_params = TicketFilterPayload(
    status="Open",
    priority="P1",
    page=1,
    per_page=30,
)
result = provider.list_tickets(filter_params)
# result: {"tickets": [...], "total": 42, "page": 1}

# Get single ticket
ticket = provider.get_ticket(ticket_id="12345")

# Create ticket
payload = CreateTicketPayload(
    subject="Server Down - prod-web-01",
    description="Instance i-abc123 is not responding",
    priority=TicketPriority.P1,
    status=TicketStatus.OPEN,
    requester_email="alert@company.com",
    tags=["auto-generated", "down-alert"],
)
result = provider.create_ticket(payload)

# Update ticket
update = UpdateTicketPayload(
    ticket_id="12345",
    status=TicketStatus.RESOLVED,
    resolution_note="Issue resolved by restarting the service",
)
provider.update_ticket(update)

# Reply to ticket
provider.reply_to_ticket(
    ticket_id="12345",
    message="We've investigated the issue and restarted the service.",
    requester_id=30000084651,
)
```

Supported providers: `Freshservice`, `ServiceDeskPlus`. Others registered in `integrations/factory.py`.

## Agent architecture

```
ticket_management/
├── agents.py                    # create_ticket_management_agents() — main entry
├── common_agent/
│   └── agents.py               # Shared agents (analyzer, pre-check, reply handler)
├── AWS/
│   ├── Incident_Alert/
│   │   ├── Down_Alert/agents.py
│   │   └── Utilization_Alert/agents.py
│   └── Service_Request/agents.py
├── monitoring_agents/          # Monitoring agent
└── tasks.py                    # Celery scheduled tasks
```

## Invoking ticket agents

```python
from ticket_management.agents import create_ticket_management_agents

result = create_ticket_management_agents(
    id=session_id,
    ticket_id=ticket.ticket_id,
    user_input=ticket_description,
    customer=customer,
    initial_active_agent="ticket_analyzer",  # entry point
)
```

Context injected into tools:
```python
context = {
    "ticket_id": str(ticket_id),
    "ticket_session_id": str(session_id),
    "ticket_text": str(user_input),
    "ticket_provider": provider,      # TicketProviderFactory result
    "customer": customer,
}
```

## Monitoring flow

Celery tasks in `tasks.py` poll Freshservice every 5 minutes:
1. `check_for_new_tickets` — fetch new tickets, create local `Ticket` records
2. `check_existing_ticket` — process new tickets through agent swarm
3. `check_monitoring` — handle active monitoring (URL health, CPU/disk thresholds)

Monitoring modules:
- `monitoring.py` — `process_monitoring_for_ticket()`
- `monitoring_part2.py` — `handle_down_monitoring()`, `handle_security_monitoring()`, `handle_service_request_monitoring()`

## ticket_details_fetcher

Utility to fetch enriched ticket data from the provider:

```python
from ticket_management.ticket_details_fetcher import TicketDetailsFetcher

fetcher = TicketDetailsFetcher(customer=customer)
details = fetcher.get_ticket_details(ticket_id="12345")
```

## TicketIntegration config

Set up per customer in Django admin or API:

```python
from ticket_management.models import TicketIntegration

integration = TicketIntegration.objects.filter(customer=customer).first()
integration.provider        # "Freshservice" | "Jira" | "ServiceDeskPlus"
integration.base_URL        # Provider API base URL
integration.api_key         # API key (encrypted)
integration.active          # bool
integration.activation_word # List of keywords that trigger auto-processing
integration.auto_monitoring_enabled  # bool
```
