# Compliance Tester — Backend Architecture & Plan

**Date:** 2026-06-21  
**Status:** Planning — implementation starts after Phase 1 frontend approved

---

## Overview

New Django app: `compliance_tester`  
Lives in: `Codly_Backend/compliance_tester/`  
Port: 8093 (same Daphne server, new URL prefix `/api/compliance-tester/`)  
Cloud support: AWS first, Azure + GCP in Phase 3  
LLM: Azure Foundry (configured via admin settings, not hardcoded)

---

## Phase 2 — Core Backend

### New Django App Structure

```
compliance_tester/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── serializers.py
├── agents/
│   ├── __init__.py
│   ├── suggestion_agent.py      # main AI agent per point
│   └── prompts/
│       ├── analyze_point.md     # system prompt for field analysis
│       └── re_suggest_field.md  # prompt for re-suggestion on feedback
├── managers/
│   ├── __init__.py
│   ├── session_manager.py       # session CRUD, stage/commit logic
│   └── audit_manager.py         # audit writes, rollback logic
└── migrations/
```

---

### Models

```python
# compliance_tester/models.py

class FieldGuideline(models.Model):
    """Per-field instructions for AI analysis. Configured by team before sessions."""
    field_name = models.CharField(max_length=100, unique=True)
    guideline_text = models.TextField()
    valid_values = models.JSONField(default=list, blank=True)  # for enum fields
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "compliance_tester_field_guideline"


class TesterSession(models.Model):
    """A batch review session."""
    STATUS_CHOICES = [
        ("active", "Active"),
        ("committed", "Committed"),
        ("discarded", "Discarded"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    point_ids = models.JSONField(default=list)            # list of point_id ints
    cloud_provider = models.CharField(max_length=10, default="AWS")
    committed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "compliance_tester_session"


class PointSessionState(models.Model):
    """Per-point status within a session."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("analyzing", "Analyzing"),
        ("ready", "Ready for Review"),
        ("approved", "Approved"),
        ("needs_change", "Needs Change"),
        ("skipped", "Skipped"),
    ]
    session = models.ForeignKey(TesterSession, on_delete=models.CASCADE, related_name="point_states")
    point_id = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    ai_suggestion = models.JSONField(null=True, blank=True)   # suggested field values
    ai_reasoning = models.JSONField(null=True, blank=True)    # field → reason dict
    ai_confidence = models.JSONField(null=True, blank=True)   # field → high/medium/low
    human_feedback = models.TextField(blank=True)              # for Request Changes input
    analyzed_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "compliance_tester_point_state"
        unique_together = [("session", "point_id")]


class StagedChange(models.Model):
    """A human-approved field change, not yet committed to CompliancePoint."""
    session = models.ForeignKey(TesterSession, on_delete=models.CASCADE, related_name="staged_changes")
    point_id = models.IntegerField()
    field_name = models.CharField(max_length=100)
    old_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "compliance_tester_staged_change"
        unique_together = [("session", "point_id", "field_name")]


class PointAuditLog(models.Model):
    """Permanent record of every field change ever committed. Rollback source."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point_id = models.IntegerField(db_index=True)
    field_name = models.CharField(max_length=100)
    old_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    session = models.ForeignKey(TesterSession, on_delete=models.SET_NULL, null=True)
    rolled_back = models.BooleanField(default=False)
    rolled_back_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="rollbacks"
    )
    rolled_back_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "compliance_tester_audit_log"
        indexes = [
            models.Index(fields=["point_id", "changed_at"]),
            models.Index(fields=["session", "point_id"]),
        ]
```

---

### API Endpoints

All under `/api/compliance-tester/`. All require auth (`CookieJWTAuthentication + CustomIsAuthenticated`).

#### Guidelines
| Method | URL | Action |
|---|---|---|
| GET | `/guidelines/` | List all field guidelines |
| PUT | `/guidelines/<field_name>/` | Update guideline for a field |
| GET | `/guidelines/fields/` | List all valid CompliancePoint field names |

#### Sessions
| Method | URL | Action |
|---|---|---|
| GET | `/sessions/` | List sessions (paginated, by customer/account) |
| POST | `/sessions/` | Create new session (body: name, point_ids, cloud_provider) |
| GET | `/sessions/<id>/` | Get session detail + point states |
| DELETE | `/sessions/<id>/` | Discard session |

#### Point State & AI
| Method | URL | Action |
|---|---|---|
| POST | `/sessions/<id>/analyze/<point_id>/` | Trigger AI analysis for one point |
| POST | `/sessions/<id>/analyze-all/` | Queue AI analysis for all pending points (Celery) |
| POST | `/sessions/<id>/re-suggest/<point_id>/` | Re-suggest with human feedback |

#### Staging & Commit
| Method | URL | Action |
|---|---|---|
| POST | `/sessions/<id>/stage/` | Stage approved changes for a point (body: point_id, approved_fields dict) |
| DELETE | `/sessions/<id>/stage/<point_id>/` | Remove staged changes for a point |
| GET | `/sessions/<id>/staged/` | List all staged changes (full diff) |
| POST | `/sessions/<id>/commit/` | Commit all staged changes → writes to CompliancePoint, creates PointAuditLog entries |

#### Audit & Rollback
| Method | URL | Action |
|---|---|---|
| GET | `/audit/<point_id>/` | Full audit log for a point |
| POST | `/audit/<entry_id>/rollback/` | Rollback a specific audit entry |

#### Point Lookup (proxies compliance app)
| Method | URL | Action |
|---|---|---|
| GET | `/points/` | List CompliancePoints (filter: service, framework, category, cloud, search) |
| GET | `/points/<point_id>/` | Get single CompliancePoint (all fields) |

---

### AI Agent Design

**File:** `compliance_tester/agents/suggestion_agent.py`  
**Uses:** `MaskedReactAgentBuilder` or `ChatSession` from `llm.open_ai`  
**Model:** Azure Foundry (model name from DB config, not hardcoded)

**Input to agent per point:**
```python
{
    "point": { ...all CompliancePoint fields... },
    "guidelines": { ...field_name: guideline_text... },  # only active guidelines
    "cloud_provider": "AWS",
}
```

**Output format (structured):**
```python
{
    "suggested_fields": {
        "severity": "high",
        "description": "...",
        "categories": ["IAM", "Encryption"],
        # only fields the AI wants to change
    },
    "reasoning": {
        "severity": "Current value 'medium' is incorrect for this type of control...",
        "description": "Description lacks clarity about what resource is checked...",
    },
    "confidence": {
        "severity": "high",
        "description": "medium",
    },
    "no_changes_needed": ["aws_cli_with_placeholders", "placeholder_list"],  # fields AI agrees with
}
```

**Prompt file:** `compliance_tester/agents/prompts/analyze_point.md`  
Contains: system instructions, how to use guidelines, output JSON schema, examples.

**Celery task for batch analysis:**
```python
@shared_task(queue="agent_test")
def analyze_session_points(session_id: str) -> None:
    # fetch all pending points in session
    # for each: call suggestion_agent, save to PointSessionState
    # update TesterSession progress via WebSocket
```

---

### Commit Logic (session_manager.py)

```python
def commit_session(session_id, committed_by_user):
    session = TesterSession.objects.get(id=session_id)
    staged = StagedChange.objects.filter(session=session)

    # group by point_id
    changes_by_point = defaultdict(list)
    for change in staged:
        changes_by_point[change.point_id].append(change)

    with transaction.atomic():
        for point_id, changes in changes_by_point.items():
            point = CompliancePoint.objects.get(point_id=point_id)
            for change in changes:
                old_val = getattr(point, change.field_name, None)
                # handle M2M vs regular fields
                _apply_field_change(point, change.field_name, change.new_value)
                PointAuditLog.objects.create(
                    point_id=point_id,
                    field_name=change.field_name,
                    old_value=old_val,
                    new_value=change.new_value,
                    changed_by=committed_by_user,
                    session=session,
                )
            point.save()

        session.status = "committed"
        session.committed_at = now()
        session.save()
```

---

### Multi-Tenant Isolation

Every query filtered by `customer` + `account`. `TesterSession` has both FK.  
`PointAuditLog` traces back to session which traces to customer/account.  
`FieldGuideline` — customer-level (each customer can have their own guidelines). Add `customer` FK.

---

## Phase 3 — AI Enhancement + Scanning Integration

### Script Validation
- Feed `aws_cli_with_placeholders` to agent with AWS CLI reference
- Validate: placeholders match `placeholder_list`, command syntax correct, command makes sense for the point's `resource_types`
- Suggest fixed script if broken

### Resource Auto-Discovery
- For points with missing `resource_fetching_cli`: agent generates a resource-fetch command
- Human approves the generated CLI → staged same as any other field change
- Uses existing `compliance/validate_resource/agent.py` patterns

### Azure Foundry Model Config
- New model: `TesterModelConfig` (per-customer)
  - `model_name`, `azure_endpoint`, `api_key` (encrypted), `max_tokens`, `temperature`
- Agent reads config from DB, not env vars
- UI: settings page at `/compliance/tester/settings/` for admins

### Azure + GCP Support
- `cloud_provider` field on `TesterSession` drives which CLI validation rules apply
- `FieldGuideline` can be cloud-specific: add `cloud_provider` filter (null = all clouds)

---

## Phase 4 — Advanced Features

- **Bulk re-suggest:** after human sets "Request Changes" on many points, fire them all in one batch
- **Auto-approve by confidence:** setting to auto-approve fields where AI confidence = "high" and guideline match = exact (requires human opt-in)
- **Export/Import guidelines:** share guideline sets across customers
- **Compliance Point creation:** agent creates brand new points from scratch based on a service description
- **Webhook on commit:** notify downstream systems when a batch is committed

---

## Hard Rules (carry-forward from CLAUDE.md)

1. No direct LLM imports — use `llm.open_ai.ChatSession` or `llm.agents.swarm.SwarmAgents`
2. No file > 1500 lines — split at 800
3. No hardcoded model names, endpoints, or API keys
4. Auth on every view — `@authentication_classes` + `@permission_classes`
5. Prompts in `.md` files only
6. All DB queries filtered by `customer` or `account`
7. No DB writes during debugging/inspection
