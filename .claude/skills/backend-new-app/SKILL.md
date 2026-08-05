---
name: backend-new-app
description: How to scaffold a new Django app in Codly Backend. Covers file structure, models, views, urls, admin, migrations, and registration. Use when creating a brand-new Django app (new module).
---

# Codly — New Django App Scaffold

## 1. Create the app

```bash
cd Codly_Backend
uv run python manage.py startapp <app_name>
```

## 2. Mandatory file structure

```
<app_name>/
├── __init__.py
├── apps.py
├── admin.py
├── models.py
├── views.py              # Thin routing only — see codly:backend-views
├── urls.py
├── serializers.py        # DRF serializers if needed
├── migrations/
│   └── __init__.py
├── tests.py
└── docs/                 # API docs go here, not repo root
```

If the app has cloud features (AWS/Azure/GCP):

```
<app_name>/
├── agent.py              # Agent orchestration
├── base/
│   └── <feature>_manager.py   # Abstract base class
├── providers/
│   ├── aws_manager.py
│   └── azure_manager.py
├── tools/
│   ├── aws_tools.py
│   └── azure_tools.py
└── prompts/
    ├── AWS<Feature>.md
    └── Azure<Feature>.md
```

See `codly:backend-new-feature` for the multi-cloud feature pattern.

## 3. Register the app

In `Codly_AI_Langraph/settings.py` → `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "<app_name>",
]
```

## 4. urls.py skeleton

```python
from django.urls import path
from . import views

urlpatterns = [
    path("my-endpoint/", views.my_view, name="my_view"),
]
```

Register in root `Codly_AI_Langraph/urls.py`:

```python
path("<app_name>/", include("<app_name>.urls")),
```

## 5. models.py rules

- **Every model tied to a customer/account MUST have ForeignKey to `Customer` or `Account`**
- Use `utf8mb4` compatible field types (already default in Django with MySQL utf8mb4 charset)
- Add `class Meta` with `ordering` and `verbose_name`

```python
from django.db import models
from manage_user.models import Customer, Account

class MyModel(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="my_models")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="my_models", null=True, blank=True)
    name = models.CharField(max_length=255)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "My Model"
        verbose_name_plural = "My Models"

    def __str__(self):
        return self.name
```

## 6. admin.py skeleton

```python
from django.contrib import admin
from .models import MyModel

@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    list_display = ["name", "customer", "created_at"]
    list_filter = ["customer"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]
```

## 7. Migrations

```bash
uv run python manage.py makemigrations <app_name>
uv run python manage.py migrate
```

## 8. Checklist

- [ ] App in `INSTALLED_APPS`
- [ ] URLs registered in root `urls.py`
- [ ] Every model has `customer` FK (multi-tenant isolation)
- [ ] Auth decorators on every view
- [ ] No file > 1500 lines
- [ ] Migration created and tested locally
- [ ] API docs added to `/docs/api/<FeatureName>/` if endpoints changed
