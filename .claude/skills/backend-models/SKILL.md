---
name: backend-models
description: Django model patterns for Codly Backend. Covers multi-tenant isolation rules, key models reference, query patterns, migrations, and caching. Use when writing models, DB queries, or migrations.
---

# Codly — Models & Database

## Key models quick reference

| Model | App | Purpose |
|---|---|---|
| `Customer` | `manage_user` | Top-level tenant. Has cloud credential fields. |
| `Account` | `manage_user` | Cloud account/subscription. Has IAM role ARNs. |
| `User` | `manage_user` | End user. Has `is_power`, `is_admin` flags. |
| `AdminUser` | `django.contrib.auth` | Internal Codly admin (separate auth). |
| `LargeLanguageModel` | `llm` | Per-customer LLM config (provider, model, secret key). |
| `Session` | `chatbot` | AI conversation session. |
| `ConversationHistory` | `chatbot` | Per-message chat history. |
| `Ticket` | `ticket_management` | IT ticket with status, priority, severity. |
| `TicketIntegration` | `ticket_management` | Freshservice/Jira/Zendesk config per customer. |
| `ComplianceScan` | `compliance` | Compliance scan run. |
| `CompliancePoint` | `compliance` | Individual CIS/STIG check point. |

## Imports

```python
from manage_user.models import Customer, Account, User, AdminUser
from chatbot.models.models import Session, ConversationHistory
from ticket_management.models import Ticket, TicketIntegration
from compliance.models import ComplianceScan, CompliancePoint
from llm.models import LargeLanguageModel
```

## Multi-tenant isolation — MANDATORY

Every query MUST filter by `customer` or `account`. No exceptions.

```python
# ✅ Correct
resource = MyModel.objects.get(id=resource_id, customer=customer)
resources = MyModel.objects.filter(account=account)
scan = ComplianceScan.objects.get(scan_id=scan_id, customer_id=str(customer.id))

# ❌ Wrong — cross-tenant leak
resource = MyModel.objects.get(id=resource_id)
```

## Writing new models

```python
from django.db import models
from manage_user.models import Customer, Account

class MyFeatureRecord(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="my_feature_records"
    )
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="my_feature_records",
        null=True, blank=True,
    )
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=[
        ("pending", "Pending"),
        ("active", "Active"),
        ("done", "Done"),
    ], default="pending")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "My Feature Record"

    def __str__(self):
        return f"{self.name} ({self.customer})"
```

## Query patterns

```python
# Select related to avoid N+1
accounts = Account.objects.filter(customer=customer).select_related("customer")
tickets = Ticket.objects.filter(customer=customer).prefetch_related("tasks")

# Existence check (efficient)
if MyModel.objects.filter(id=obj_id, customer=customer).exists():
    ...

# Get or create with tenant scope
obj, created = MyModel.objects.get_or_create(
    customer=customer,
    name=name,
    defaults={"status": "pending"},
)

# Bulk operations
MyModel.objects.filter(customer=customer, status="pending").update(status="active")
```

## Migrations

```bash
# After model changes:
uv run python manage.py makemigrations <app_name>

# Apply:
uv run python manage.py migrate

# Check pending:
uv run python manage.py showmigrations
```

Never edit migration files manually after they've been applied to any environment.

## Django ORM caching

Expensive queries cached via `django.core.cache`:

```python
from django.core.cache import cache

CACHE_TTL = 60 * 30  # 30 minutes
cache_key = f"{settings.ENV}_cache_mymodel_{customer.id}"

data = cache.get(cache_key)
if data is None:
    data = list(MyModel.objects.filter(customer=customer).values())
    cache.set(cache_key, data, CACHE_TTL)
```

Key pattern: `{env}_cache_{model}_{hash_or_id}` — see `common/CachingUtils.py` for helpers.

## Account model fields

```python
account.cloud_provider         # "AWS" | "AZURE" | "GCP"
account.provider_account_id    # AWS account ID / Azure subscription ID
account.read_only_iam_role_arn # ARN for read-only STS assume role
account.power_user_iam_role_arn# ARN for power-user STS assume role
account.customer               # FK to Customer
```

## Customer credential fields

Customer model has raw credential fields (legacy), but credentials should be loaded via `create_cloud_cred_loader()` — not accessed directly.
