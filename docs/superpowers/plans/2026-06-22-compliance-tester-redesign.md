# Compliance Tester Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the compliance tester to be cloud-provider-aware, with rich per-step script detail panels (summary, edge cases, placeholders, AI diff), proper markdown rendering, and a vertical stepper UX for point review.

**Architecture:** Backend adds `cloud_provider` to `FieldGuideline` and updates the suggestion agent to output `edge_cases` + `script_summary`. Frontend replaces the flat guidelines list with cloud-tab UI and rebuilds the session page script panels and step stepper.

**Tech Stack:** Django 6, DRF, Next.js 14 (App Router), TypeScript, Tailwind, `react-markdown` + `remark-gfm` (already in `package.json`), Sonner toasts, shadcn/ui components.

## Global Constraints

- No direct LLM imports — use only `from llm.agents.swarm import SwarmAgents, AgentConfig` and `from llm.utils.prompt_loader import load_prompt`
- Auth on every view: `@authentication_classes([CookieJWTAuthentication])` + `@permission_classes([CustomIsAuthenticated])`
- No file > 1500 lines — split if growing past 800 lines
- All prompts in `.md` files under `compliance_tester_app/agents/prompts/`
- Multi-tenant: every DB query filtered by `customer`
- No DB writes in read-only views
- Frontend API base: use existing `apiFetch` or raw `fetch` with `credentials: "include"` (pattern from existing tester files)
- Existing hardcoded `API_BASE = "https://devapi3.codly.ai/"` in tester pages — keep same pattern for new calls

---

## File Map

### Backend (new/modified)
| File | Action | Responsibility |
|------|--------|---------------|
| `compliance_tester_app/models.py` | Modify | Add `cloud_provider` to `FieldGuideline`, update unique constraint |
| `compliance_tester_app/migrations/0003_guideline_cloud_provider.py` | Create | Migration for new field + constraint |
| `compliance_tester_app/serializers.py` | Modify | Add `cloud_provider` to `serialize_guideline` |
| `compliance_tester_app/views.py` | Modify | `guidelines_list_view`: filter by `cloud_provider`, merge global; `guidelines_bulk_save_view`: accept `cloud_provider`; `guideline_detail_view`: lookup by `(field_name, cloud_provider)` |
| `compliance_tester_app/agents/suggestion_agent.py` | Modify | Pass `cloud_provider` to guidelines fetch; update `_build_agent` to inject cloud context |
| `compliance_tester_app/agents/prompts/analyze_scan_script.md` | Modify | Add `edge_cases`, `script_summary`, `permissions_required` to output JSON |
| `compliance_tester_app/agents/prompts/analyze_remediation.md` | Modify | Add `edge_cases`, `risk_summary`, `permissions_required` to output JSON |

### Frontend (new/modified)
| File | Action | Responsibility |
|------|--------|---------------|
| `tester/lib/mock-data.ts` | Modify | Add `cloud_provider` to `FieldGuideline` type |
| `tester/lib/api.ts` | Modify | Add `cloud_provider` param to guideline fetch/save calls |
| `tester/guidelines/page.tsx` | Modify | Cloud provider tabs, per-cloud load/save, markdown preview toggle |
| `tester/session/[id]/page.tsx` | Modify | Vertical stepper, script detail panels with markdown, AI edge cases display |
| `tester/session/[id]/components/ScriptPanel.tsx` | Create | Reusable script detail panel (summary, code block, placeholders table, edge cases, AI diff) |
| `tester/session/[id]/components/StepStepper.tsx` | Create | 3-step vertical stepper per point with status badges |
| `tester/session/[id]/components/FieldDiffTable.tsx` | Create | Old vs new field diff table with per-row accept/reject/edit actions |

---

## Task 1: Backend — Add `cloud_provider` to `FieldGuideline`

**Files:**
- Modify: `Codly_Backend/compliance_tester_app/models.py`
- Create: `Codly_Backend/compliance_tester_app/migrations/0003_guideline_cloud_provider.py`

**Interfaces:**
- Produces: `FieldGuideline.cloud_provider` (nullable CharField, max_length=10)
- Produces: unique constraint `("field_name", "cloud_provider")` replaces `unique=True` on `field_name`

- [ ] **Step 1: Modify `FieldGuideline` model**

In `compliance_tester_app/models.py`, find the `FieldGuideline` class and make these changes:

```python
class FieldGuideline(models.Model):
    ANALYSIS_STEP_CHOICES = [
        ("metadata", "Metadata"),
        ("scan_script", "Scan Script"),
        ("remediation", "Remediation"),
    ]

    CLOUD_PROVIDER_CHOICES = [
        ("AWS", "AWS"),
        ("AZURE", "AZURE"),
        ("GCP", "GCP"),
    ]

    field_name = models.CharField(max_length=100)  # remove unique=True
    cloud_provider = models.CharField(
        max_length=10,
        choices=CLOUD_PROVIDER_CHOICES,
        null=True,
        blank=True,
        help_text="null = applies to all clouds (global). Set to restrict to one provider.",
    )
    analysis_step = models.CharField(
        max_length=20,
        choices=ANALYSIS_STEP_CHOICES,
        help_text="Which AI step this guideline belongs to",
    )
    guideline_text = models.TextField()
    valid_values = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed values for enum-like fields",
    )
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guideline_updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "compliance_tester_field_guideline"
        ordering = ["analysis_step", "field_name"]
        unique_together = [("field_name", "cloud_provider")]

    def __str__(self):
        cloud = self.cloud_provider or "global"
        return f"{self.field_name} [{cloud}] ({self.analysis_step})"
```

- [ ] **Step 2: Generate migration**

```bash
cd Codly_Backend
uv run python manage.py makemigrations compliance_tester_app --name guideline_cloud_provider
```

Expected: creates `compliance_tester_app/migrations/0003_guideline_cloud_provider.py`

- [ ] **Step 3: Verify migration content makes sense**

```bash
uv run python manage.py sqlmigrate compliance_tester_app 0003
```

Expected output includes: `ADD COLUMN cloud_provider`, `DROP CONSTRAINT` on old unique, `ADD CONSTRAINT` on `(field_name, cloud_provider)`.

- [ ] **Step 4: Run migration**

```bash
uv run python manage.py migrate compliance_tester_app
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd Codly_Backend
rtk git add compliance_tester_app/models.py compliance_tester_app/migrations/0003_guideline_cloud_provider.py
rtk git commit -m "feat(compliance-tester): add cloud_provider to FieldGuideline model"
```

---

## Task 2: Backend — Update Serializer + Views for cloud_provider

**Files:**
- Modify: `Codly_Backend/compliance_tester_app/serializers.py`
- Modify: `Codly_Backend/compliance_tester_app/views.py`

**Interfaces:**
- Consumes: `FieldGuideline.cloud_provider` from Task 1
- Produces: `GET /api/compliance-tester/guidelines/?cloud_provider=AWS` returns global (null) + AWS rows merged, AWS-specific wins on conflict
- Produces: `POST /api/compliance-tester/guidelines/bulk-save/` accepts optional `cloud_provider` per item
- Produces: `serialize_guideline` includes `cloud_provider` key

- [ ] **Step 1: Update `serialize_guideline`**

In `compliance_tester_app/serializers.py`, update:

```python
def serialize_guideline(g: FieldGuideline) -> dict:
    return {
        "id": g.id,
        "field_name": g.field_name,
        "cloud_provider": g.cloud_provider,  # new
        "analysis_step": g.analysis_step,
        "guideline_text": g.guideline_text,
        "valid_values": g.valid_values,
        "is_active": g.is_active,
        "updated_by": g.updated_by_id,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
```

- [ ] **Step 2: Update `guidelines_list_view` GET logic**

In `compliance_tester_app/views.py`, find `guidelines_list_view` and replace the GET block:

```python
@api_view(["GET", "POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([CustomIsAuthenticated])
def guidelines_list_view(request):
    if request.method == "GET":
        step = request.query_params.get("analysis_step")
        cloud_provider = request.query_params.get("cloud_provider")  # new

        # Always fetch global (null) rows
        qs_global = FieldGuideline.objects.filter(is_active=True, cloud_provider__isnull=True)
        if step:
            qs_global = qs_global.filter(analysis_step=step)

        if cloud_provider:
            # Fetch cloud-specific rows
            qs_cloud = FieldGuideline.objects.filter(
                is_active=True, cloud_provider=cloud_provider.upper()
            )
            if step:
                qs_cloud = qs_cloud.filter(analysis_step=step)

            # Merge: cloud-specific wins over global on same field_name
            cloud_map = {g.field_name: g for g in qs_cloud}
            merged = []
            for g in qs_global:
                if g.field_name not in cloud_map:
                    merged.append(g)
            merged.extend(cloud_map.values())
            results = sorted(merged, key=lambda g: (g.analysis_step, g.field_name))
        else:
            results = list(qs_global.order_by("analysis_step", "field_name"))

        return JsonResponse({
            "results": [serialize_guideline(g) for g in results],
            "count": len(results),
        })
    # ... POST block unchanged below
```

- [ ] **Step 3: Update `guidelines_bulk_save_view` to accept `cloud_provider`**

Find `guidelines_bulk_save_view` and update the upsert logic:

```python
@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([CustomIsAuthenticated])
def guidelines_bulk_save_view(request):
    items = request.data.get("guidelines", [])
    if not items:
        return JsonResponse({"error": "guidelines list required"}, status=status.HTTP_400_BAD_REQUEST)

    saved = []
    errors = []

    for item in items:
        field_name = (item.get("field_name") or "").strip()
        analysis_step = (item.get("analysis_step") or "").strip()
        guideline_text = (item.get("guideline_text") or "").strip()
        valid_values = item.get("valid_values", [])
        cloud_provider = (item.get("cloud_provider") or "").strip().upper() or None  # new

        if not field_name or not guideline_text or not analysis_step:
            errors.append({"field_name": field_name, "error": "field_name, guideline_text, analysis_step required"})
            continue

        obj, created = FieldGuideline.objects.update_or_create(
            field_name=field_name,
            cloud_provider=cloud_provider,  # new — part of unique lookup
            defaults={
                "analysis_step": analysis_step,
                "guideline_text": guideline_text,
                "valid_values": valid_values if isinstance(valid_values, list) else [],
                "is_active": True,
                "updated_by": request.user,
            },
        )
        FieldGuidelineHistory.objects.create(
            guideline=obj,
            field_name=field_name,
            new_guideline_text=guideline_text,
            new_valid_values=valid_values,
            new_is_active=True,
            changed_by=request.user,
        )
        saved.append(field_name)

    return JsonResponse({"saved": saved, "errors": errors, "count": len(saved)})
```

- [ ] **Step 4: Test via curl**

```bash
curl -s -X GET "https://devapi3.codly.ai/api/compliance-tester/guidelines/?cloud_provider=AWS" \
  -H "Cookie: <your-cookie>" | python3 -m json.tool | head -30
```

Expected: JSON with `results` array, each item has `cloud_provider` key.

- [ ] **Step 5: Commit**

```bash
cd Codly_Backend
rtk git add compliance_tester_app/serializers.py compliance_tester_app/views.py
rtk git commit -m "feat(compliance-tester): cloud_provider filter on guideline list + bulk-save"
```

---

## Task 3: Backend — Update Suggestion Agent for cloud-aware guidelines + edge_cases output

**Files:**
- Modify: `Codly_Backend/compliance_tester_app/agents/suggestion_agent.py`
- Modify: `Codly_Backend/compliance_tester_app/agents/prompts/analyze_scan_script.md`
- Modify: `Codly_Backend/compliance_tester_app/agents/prompts/analyze_remediation.md`

**Interfaces:**
- Consumes: `point.cloud_provider` (str, e.g. "AWS")
- Produces: `scan_script` step response now includes `script_summary`, `edge_cases`, `permissions_required` keys
- Produces: `remediation` step response now includes `edge_cases`, `risk_summary`, `permissions_required` keys

- [ ] **Step 1: Update `_get_guidelines_for_step` to accept cloud_provider**

In `suggestion_agent.py`, replace:

```python
def _get_guidelines_for_step(step: str, cloud_provider: str = None) -> dict:
    """Return guidelines for step. Cloud-specific wins over global on conflict."""
    # Global guidelines (cloud_provider=null)
    global_qs = FieldGuideline.objects.filter(
        analysis_step=step, is_active=True, cloud_provider__isnull=True
    )
    result = {g.field_name: g.guideline_text for g in global_qs}

    # Cloud-specific guidelines override global
    if cloud_provider:
        cloud_qs = FieldGuideline.objects.filter(
            analysis_step=step, is_active=True, cloud_provider=cloud_provider.upper()
        )
        for g in cloud_qs:
            result[g.field_name] = g.guideline_text

    return result
```

- [ ] **Step 2: Update `analyze_point_step` to pass cloud_provider**

Replace the existing `analyze_point_step` signature and body:

```python
def analyze_point_step(point, step: str, customer) -> dict:
    """
    Run AI analysis for one step on one CompliancePoint.

    Returns:
        {
            "suggested_fields": {...},
            "reasoning": {...},
            "confidence": {...},
            "no_changes_needed": [...],
            "script_summary": str,        # scan_script step only
            "edge_cases": list[str],      # scan_script + remediation steps
            "permissions_required": list[str],  # scan_script + remediation steps
            "risk_summary": str,          # remediation step only
            "error": None or str,
        }
    """
    if step not in _STEP_PROMPT_MAP:
        return {"error": f"Unknown step: {step}", "suggested_fields": {}}

    cloud_provider = getattr(point, "cloud_provider", None)
    guidelines = _get_guidelines_for_step(step, cloud_provider=cloud_provider)
    guidelines_text = _format_guidelines(guidelines)
    fields = _STEP_FIELDS[step]
    point_data = _build_point_context(point, fields)

    swarm, agent_name = _build_agent(step, guidelines_text, customer)

    user_input = (
        f"Analyze this CompliancePoint's {step} fields and suggest improvements.\n\n"
        f"Point ID: {point.point_id}\n"
        f"Compliance Check: {point.compliance_point}\n"
        f"Description: {point.description}\n"
        f"Cloud Provider: {cloud_provider or 'AWS'}\n\n"
        f"Current field values:\n{json.dumps(point_data, indent=2, default=str)}"
    )

    try:
        result = swarm.invoke(
            user_input=user_input,
            session_id=None,
            thread_id_override=f"tester_analyze:{point.point_id}:{step}:{int(time.time())}",
            context={"customer": customer},
            load_history=False,
            save_history=False,
            metadata={
                "feature": "compliance_tester",
                "point_id": point.point_id,
                "step": step,
                "cloud_provider": cloud_provider,
            },
        )
        raw = result.get("output") or result.get("message") or ""
        parsed = _parse_agent_response(raw)
        return {
            "suggested_fields": parsed.get("suggested_fields", {}),
            "reasoning": parsed.get("reasoning", {}),
            "confidence": parsed.get("confidence", {}),
            "no_changes_needed": parsed.get("no_changes_needed", []),
            "script_summary": parsed.get("script_summary", ""),
            "edge_cases": parsed.get("edge_cases", []),
            "permissions_required": parsed.get("permissions_required", []),
            "risk_summary": parsed.get("risk_summary", ""),
            "error": None,
        }
    except Exception as exc:
        logger.exception("analyze_point_step failed: point=%s step=%s", point.point_id, step)
        return {"error": str(exc), "suggested_fields": {}}
```

- [ ] **Step 3: Update `analyze_scan_script.md` prompt**

Replace content of `compliance_tester_app/agents/prompts/analyze_scan_script.md`:

```markdown
# Compliance Point — Scan Script Analysis Agent

You are an expert cloud security engineer reviewing CompliancePoint scan script fields.

## Your Task

Analyze the provided CompliancePoint and suggest improvements to its **scan script fields** only:
- `aws_cli_with_placeholders` — the CLI command used to check compliance (must use `<PLACEHOLDER>` syntax)
- `placeholder_list` — JSON array of `{"name": "<PH_NAME>", "description": "..."}` objects
- `mapping_dict` — JSON object mapping placeholder names to resource attribute keys for auto-fill
- `resource_fetching_cli` — CLI command to discover and list resources of this type

The cloud provider is given in the input. Use the correct CLI tool:
- AWS → `aws` CLI
- AZURE → `az` CLI
- GCP → `gcloud` CLI

## Guidelines

Apply the following field-specific guidelines when making suggestions:
{guidelines}

## Rules

1. Placeholders must use `<UPPERCASE_NAME>` syntax.
2. Every placeholder in the command must appear in `placeholder_list`.
3. `mapping_dict` keys must match placeholder names exactly (without angle brackets).
4. `resource_fetching_cli` should return a JSON list of resources with their identifiers.
5. Do not suggest commands that write data — scan commands are read-only.
6. Only suggest if you are confident the command is correct for this compliance check.
7. Confidence: "high" = certain, "medium" = likely correct, "low" = uncertain.

## Output Format

Respond ONLY with valid JSON:

```json
{
  "script_summary": "One sentence: what this scan command checks and what output means compliant vs non-compliant.",
  "edge_cases": [
    "Requires s3:GetEncryptionConfiguration IAM permission",
    "Returns NoSuchBucket error if bucket deleted mid-scan — treated as non-compliant",
    "SSE-KMS and SSE-S3 both return true — no encryption-type distinction"
  ],
  "permissions_required": [
    "s3:GetEncryptionConfiguration"
  ],
  "suggested_fields": {
    "aws_cli_with_placeholders": "aws s3api get-bucket-public-access-block --bucket <BUCKET_NAME> --region <REGION>"
  },
  "reasoning": {
    "aws_cli_with_placeholders": "Current command uses wrong API"
  },
  "confidence": {
    "aws_cli_with_placeholders": "high"
  },
  "no_changes_needed": ["placeholder_list", "resource_fetching_cli"]
}
```

`script_summary`, `edge_cases`, and `permissions_required` are ALWAYS required even if no field changes are suggested.
Only include fields you want to change in `suggested_fields`.
```

- [ ] **Step 4: Update `analyze_remediation.md` prompt**

```bash
cat Codly_Backend/compliance_tester_app/agents/prompts/analyze_remediation.md
```

Read current content, then add to the output JSON section:

```json
{
  "risk_summary": "One sentence: what risk does running this remediation script carry (data loss, downtime, permission escalation, irreversibility).",
  "edge_cases": [
    "Cannot revert encryption once enabled on RDS — creates new encrypted instance",
    "Requires s3:PutEncryptionConfiguration permission"
  ],
  "permissions_required": [
    "s3:PutEncryptionConfiguration"
  ],
  "suggested_fields": { ... },
  "reasoning": { ... },
  "confidence": { ... },
  "no_changes_needed": [...]
}
```

Add to the rules section: "`risk_summary`, `edge_cases`, and `permissions_required` are ALWAYS required."

- [ ] **Step 5: Commit**

```bash
cd Codly_Backend
rtk git add compliance_tester_app/agents/suggestion_agent.py \
  compliance_tester_app/agents/prompts/analyze_scan_script.md \
  compliance_tester_app/agents/prompts/analyze_remediation.md
rtk git commit -m "feat(compliance-tester): cloud-aware guidelines + edge_cases in AI output"
```

---

## Task 4: Frontend — Update Types and API helpers

**Files:**
- Modify: `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/lib/mock-data.ts`
- Modify: `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/lib/api.ts`

**Interfaces:**
- Produces: `FieldGuideline.cloud_provider?: "AWS" | "AZURE" | "GCP" | null`
- Produces: `PointStateAPI.scan_script_step.script_summary: string`
- Produces: `PointStateAPI.scan_script_step.edge_cases: string[]`
- Produces: `PointStateAPI.scan_script_step.permissions_required: string[]`
- Produces: `PointStateAPI.remediation_step.risk_summary: string`
- Produces: `PointStateAPI.remediation_step.edge_cases: string[]`
- Produces: `fetchGuidelines(cloudProvider?: string)` function

- [ ] **Step 1: Update `FieldGuideline` type in `mock-data.ts`**

Find the `FieldGuideline` interface and add `cloud_provider`:

```typescript
export interface FieldGuideline {
  field_name: string;
  cloud_provider?: "AWS" | "AZURE" | "GCP" | null;
  guideline_text: string;
  valid_values?: string[];
  updated_at: string;
}
```

- [ ] **Step 2: Check what `PointStateAPI` looks like in `api.ts`**

```bash
grep -n "PointStateAPI\|scan_script_step\|remediation_step" \
  Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/lib/api.ts | head -30
```

- [ ] **Step 3: Update `PointStateAPI` in `api.ts` to include new fields**

Find the `PointStateAPI` type and extend `scan_script_step` and `remediation_step`:

```typescript
export interface PointStateAPI {
  point_id: number;
  status: string;
  metadata_step: {
    status: string;
    suggestion: Record<string, unknown> | null;
    reasoning: Record<string, string> | null;
    confidence: Record<string, string> | null;
    analyzed_at: string | null;
  };
  scan_script_step: {
    status: string;
    suggestion: Record<string, unknown> | null;
    reasoning: Record<string, string> | null;
    confidence: Record<string, string> | null;
    analyzed_at: string | null;
    script_summary?: string;        // new
    edge_cases?: string[];          // new
    permissions_required?: string[]; // new
  };
  remediation_step: {
    status: string;
    suggestion: Record<string, unknown> | null;
    reasoning: Record<string, string> | null;
    confidence: Record<string, string> | null;
    analyzed_at: string | null;
    risk_summary?: string;           // new
    edge_cases?: string[];           // new
    permissions_required?: string[]; // new
  };
  human_feedback: string;
  reviewed_at: string | null;
}
```

- [ ] **Step 4: Add `fetchGuidelines` function to `api.ts`**

```typescript
const _API_BASE = "https://devapi3.codly.ai/";

export async function fetchGuidelines(cloudProvider?: string): Promise<{ results: FieldGuidelineAPI[]; count: number }> {
  const q = cloudProvider ? `?cloud_provider=${cloudProvider}` : "";
  const url = `${_API_BASE}api/compliance-tester/guidelines/${q}`;
  const res = await fetch(url, { credentials: "include", cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface FieldGuidelineAPI {
  id: number;
  field_name: string;
  cloud_provider: string | null;
  analysis_step: string;
  guideline_text: string;
  valid_values: string[];
  is_active: boolean;
  updated_at: string;
}
```

- [ ] **Step 5: Commit**

```bash
cd Codly-Frontend
rtk git add src/app/admin/\(dashboard\)/compliance/tester/lib/mock-data.ts \
  src/app/admin/\(dashboard\)/compliance/tester/lib/api.ts
rtk git commit -m "feat(compliance-tester): types + api helpers for cloud_provider and edge_cases"
```

---

## Task 5: Frontend — Guidelines Page Cloud Provider Tabs

**Files:**
- Modify: `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/guidelines/page.tsx`

**Interfaces:**
- Consumes: `fetchGuidelines(cloudProvider)` from Task 4
- Consumes: `FieldGuideline.cloud_provider` from Task 4

- [ ] **Step 1: Add cloud provider tab state and fetch logic**

At top of `GuidelinesPage` component, add:

```typescript
const CLOUD_TABS = ["AWS", "AZURE", "GCP"] as const;
type CloudTab = typeof CLOUD_TABS[number];

const [activeCloud, setActiveCloud] = useState<CloudTab>("AWS");
```

Replace the `useEffect` that loads guidelines:

```typescript
useEffect(() => {
  fetchGuidelinesRaw(`?cloud_provider=${activeCloud}`)
    .then((data) => {
      const apiGuidelines = data.results ?? [];
      const merged = FIELD_META.map((f) => {
        const existing = apiGuidelines.find((g: any) => g.field_name === f.key);
        return existing ?? {
          field_name: f.key,
          cloud_provider: activeCloud,
          guideline_text: "",
          updated_at: new Date().toISOString(),
        };
      });
      setGuidelines(merged);
    })
    .catch(() => {
      const loaded = loadGuidelines();
      const merged = FIELD_META.map((f) => {
        const existing = loaded.find((g) => g.field_name === f.key);
        return existing ?? {
          field_name: f.key,
          cloud_provider: activeCloud,
          guideline_text: "",
          updated_at: new Date().toISOString(),
        };
      });
      setGuidelines(merged);
    });
}, [activeCloud]);
```

- [ ] **Step 2: Update `handleSave` to send `cloud_provider`**

```typescript
async function handleSave() {
  setSaving(true);
  const toSave = guidelines
    .filter((g) => g.guideline_text.trim())
    .map((g) => {
      const field = FIELD_META.find((f) => f.key === g.field_name);
      const step = GROUP_TO_STEP[field?.group ?? "metadata"] ?? "metadata";
      return {
        field_name: g.field_name,
        cloud_provider: activeCloud,  // new
        analysis_step: step,
        guideline_text: g.guideline_text.trim(),
        valid_values: g.valid_values ?? [],
      };
    });
  // ... rest unchanged
}
```

- [ ] **Step 3: Render cloud provider tabs in JSX**

In the header section, after the group tabs `div`, add cloud tabs above them:

```tsx
{/* Cloud Provider Tabs */}
<div className="max-w-4xl mx-auto mt-3 flex gap-1 border-b border-border pb-3">
  {CLOUD_TABS.map((cloud) => {
    const cloudConfigured = guidelines.filter(
      (g) => g.guideline_text.trim() && g.cloud_provider === cloud
    ).length;
    return (
      <button
        key={cloud}
        onClick={() => setActiveCloud(cloud)}
        className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
          activeCloud === cloud
            ? "bg-blue-600 text-white"
            : "text-muted-foreground hover:bg-muted"
        }`}
      >
        {cloud}
        <span className={`text-xs px-1.5 py-0.5 rounded-full ${
          activeCloud === cloud ? "bg-white/20 text-white" : "bg-muted text-muted-foreground"
        }`}>
          {cloudConfigured}
        </span>
      </button>
    );
  })}
  <span className="ml-2 text-xs text-muted-foreground self-center">
    Showing guidelines for {activeCloud} · Global guidelines apply to all clouds
  </span>
</div>
```

- [ ] **Step 4: Add inheritance indicator to `GuidelineRow`**

In `GuidelineRow`, add a prop `isGlobal?: boolean` and show a dim badge when guideline came from global (null cloud_provider):

```tsx
function GuidelineRow({ field, guideline, onChange, onAddValue, onRemoveValue, isGlobal }: {
  // ... existing props
  isGlobal?: boolean;
}) {
  // In the header div, after the field key/type badges:
  {isGlobal && (
    <span className="text-xs text-muted-foreground/60 italic">
      Using global guideline
    </span>
  )}
```

Pass `isGlobal={guideline.cloud_provider === null}` from the parent map call.

- [ ] **Step 5: Add markdown preview toggle to textarea fields**

In `GuidelineRow`, add preview state and toggle:

```tsx
const [showPreview, setShowPreview] = useState(false);

// Replace the Textarea block with:
<div>
  <div className="flex items-center justify-between mb-1">
    <Label className="text-xs text-muted-foreground">
      AI Guideline — what rules should AI follow for this field?
    </Label>
    <button
      type="button"
      onClick={() => setShowPreview((v) => !v)}
      className="text-xs text-muted-foreground hover:text-foreground transition-colors"
    >
      {showPreview ? "Edit" : "Preview"}
    </button>
  </div>
  {showPreview ? (
    <div className="text-sm prose prose-sm dark:prose-invert max-w-none min-h-[72px] border rounded-md px-3 py-2 bg-muted/30">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {guideline.guideline_text || "_No guideline text yet_"}
      </ReactMarkdown>
    </div>
  ) : (
    <Textarea
      value={guideline.guideline_text}
      onChange={(e) => onChange(e.target.value)}
      placeholder={`e.g. "${field.label} must be..."`}
      className="text-sm min-h-[72px] resize-y"
    />
  )}
</div>
```

Add imports at top of file:
```typescript
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
```

- [ ] **Step 6: Verify page loads with tabs**

```bash
cd Codly-Frontend && bun run dev
```

Navigate to `/admin/compliance/tester/guidelines`. Verify: 3 cloud tabs render, switching tabs re-fetches guidelines, save button sends `cloud_provider` in payload (check Network tab).

- [ ] **Step 7: Commit**

```bash
cd Codly-Frontend
rtk git add src/app/admin/\(dashboard\)/compliance/tester/guidelines/page.tsx
rtk git commit -m "feat(compliance-tester): cloud provider tabs on guidelines page"
```

---

## Task 6: Frontend — `ScriptPanel` Component

**Files:**
- Create: `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/session/[id]/components/ScriptPanel.tsx`

**Interfaces:**
- Consumes: nothing from prior tasks yet (standalone display component)
- Produces:
  ```typescript
  interface ScriptPanelProps {
    title: string;                    // "Scan CLI Script" | "Resource Fetching CLI" | "Remediation Script"
    cloudProvider: "AWS" | "AZURE" | "GCP";
    script: string;                   // raw script text with <PLACEHOLDER> syntax
    scriptSummary?: string;           // what the script does (from AI or rb_summary)
    placeholderList?: Array<{ name: string; description: string }>;
    mappingDict?: Record<string, string>;
    edgeCases?: string[];
    permissionsRequired?: string[];
    riskSummary?: string;             // remediation only
    suggestedScript?: string;         // AI-suggested replacement
    scriptReasoning?: string;         // why AI suggests the change
    complianceLogic?: boolean;        // show true/false compliance logic box
    isRemediation?: boolean;          // changes some labels
  }
  ```

- [ ] **Step 1: Create `ScriptPanel.tsx`**

```bash
mkdir -p Codly-Frontend/src/app/admin/\(dashboard\)/compliance/tester/session/\[id\]/components
```

```typescript
// ScriptPanel.tsx
"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, ChevronDown, ChevronRight, AlertTriangle, Info, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/admin/lib/utils";
import { Badge } from "@/admin/components/ui/badge";

const CLOUD_LABELS: Record<string, string> = {
  AWS: "AWS CLI",
  AZURE: "Azure CLI",
  GCP: "gcloud CLI",
};

export interface ScriptPanelProps {
  title: string;
  cloudProvider: "AWS" | "AZURE" | "GCP";
  script: string;
  scriptSummary?: string;
  placeholderList?: Array<{ name: string; description: string }>;
  mappingDict?: Record<string, string>;
  edgeCases?: string[];
  permissionsRequired?: string[];
  riskSummary?: string;
  suggestedScript?: string;
  scriptReasoning?: string;
  complianceLogic?: boolean;
  isRemediation?: boolean;
}

export function ScriptPanel({
  title,
  cloudProvider,
  script,
  scriptSummary,
  placeholderList,
  mappingDict,
  edgeCases,
  permissionsRequired,
  riskSummary,
  suggestedScript,
  scriptReasoning,
  complianceLogic = false,
  isRemediation = false,
}: ScriptPanelProps) {
  const [showDiff, setShowDiff] = useState(false);
  const cloudLabel = CLOUD_LABELS[cloudProvider] ?? cloudProvider;
  const hasScript = !!script?.trim();
  const hasSuggestion = !!suggestedScript && suggestedScript !== script;

  function copyScript(text: string) {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  }

  if (!hasScript) {
    return (
      <div className="rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">
        No {title.toLowerCase()} configured.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">{title}</span>
          <Badge variant="outline" className="text-xs font-mono">{cloudLabel}</Badge>
          {isRemediation && (
            <Badge variant="outline" className="text-xs bg-orange-50 text-orange-700 dark:bg-orange-900/20 dark:text-orange-300 border-orange-200">
              MODIFIES RESOURCES
            </Badge>
          )}
        </div>
        <button
          onClick={() => copyScript(script)}
          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
        >
          <Copy className="h-3 w-3" />
          Copy
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Summary */}
        {scriptSummary && (
          <div className="flex gap-2 text-sm">
            <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
            <p className="text-muted-foreground">{scriptSummary}</p>
          </div>
        )}

        {/* Script block */}
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5">Script</p>
          <pre className="bg-gray-950 dark:bg-gray-950 text-green-400 text-xs rounded-lg p-4 overflow-x-auto font-mono leading-relaxed whitespace-pre-wrap">
            {script}
          </pre>
        </div>

        {/* Compliance logic */}
        {complianceLogic && !isRemediation && (
          <div className="rounded-lg border border-border bg-muted/20 p-3 text-xs font-mono space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Compliance Logic</p>
            <div className="flex gap-3">
              <span className="text-green-600 dark:text-green-400">output contains "true"</span>
              <span className="text-muted-foreground">→ Compliant</span>
            </div>
            <div className="flex gap-3">
              <span className="text-red-500">output contains "false"</span>
              <span className="text-muted-foreground">→ Non-compliant</span>
            </div>
            <div className="flex gap-3">
              <span className="text-yellow-500">otherwise</span>
              <span className="text-muted-foreground">→ Unknown (logged, not remediated)</span>
            </div>
          </div>
        )}

        {/* Placeholders table */}
        {placeholderList && placeholderList.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5">Placeholders</p>
            <div className="rounded-lg border border-border overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-muted-foreground">Name</th>
                    <th className="text-left px-3 py-2 font-medium text-muted-foreground">Description</th>
                    <th className="text-left px-3 py-2 font-medium text-muted-foreground">Mapped From</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {placeholderList.map((ph) => {
                    const cleanName = ph.name.replace(/[<>]/g, "");
                    const mapped = mappingDict?.[cleanName] ?? "—";
                    return (
                      <tr key={ph.name}>
                        <td className="px-3 py-2 font-mono text-blue-600 dark:text-blue-400">{ph.name}</td>
                        <td className="px-3 py-2 text-muted-foreground">{ph.description}</td>
                        <td className="px-3 py-2 font-mono text-muted-foreground">{mapped}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Permissions required */}
        {permissionsRequired && permissionsRequired.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5">Permissions Required</p>
            <div className="flex flex-wrap gap-1.5">
              {permissionsRequired.map((p) => (
                <span key={p} className="text-xs font-mono px-2 py-0.5 rounded bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Risk summary (remediation only) */}
        {riskSummary && (
          <div className="flex gap-2 rounded-lg border border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-900/10 p-3">
            <AlertTriangle className="h-4 w-4 text-orange-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-orange-700 dark:text-orange-300 mb-0.5">Risk</p>
              <p className="text-xs text-orange-700 dark:text-orange-300">{riskSummary}</p>
            </div>
          </div>
        )}

        {/* Edge cases */}
        {edgeCases && edgeCases.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5">
              Edge Cases & Limitations
            </p>
            <ul className="space-y-1.5">
              {edgeCases.map((ec, i) => (
                <li key={i} className="flex gap-2 text-xs text-muted-foreground">
                  <span className="text-yellow-500 shrink-0">⚠</span>
                  <span>{ec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* AI diff */}
        {hasSuggestion && (
          <div>
            <button
              type="button"
              onClick={() => setShowDiff((v) => !v)}
              className="flex items-center gap-1.5 text-xs font-medium text-teal-600 dark:text-teal-400 hover:text-teal-500 transition-colors"
            >
              {showDiff ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              AI suggests script improvement
            </button>
            {showDiff && (
              <div className="mt-2 space-y-2">
                {scriptReasoning && (
                  <p className="text-xs text-muted-foreground italic">{scriptReasoning}</p>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Current</p>
                    <pre className="bg-red-950/20 border border-red-800/30 text-red-400 text-xs rounded p-3 overflow-x-auto font-mono whitespace-pre-wrap">
                      {script}
                    </pre>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Suggested</p>
                    <pre className="bg-green-950/20 border border-green-800/30 text-green-400 text-xs rounded p-3 overflow-x-auto font-mono whitespace-pre-wrap">
                      {suggestedScript}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify no TypeScript errors**

```bash
cd Codly-Frontend
rtk tsc --noEmit 2>&1 | grep -i "ScriptPanel\|error" | head -20
```

Expected: no errors related to ScriptPanel.

- [ ] **Step 3: Commit**

```bash
rtk git add src/app/admin/\(dashboard\)/compliance/tester/session/\[id\]/components/ScriptPanel.tsx
rtk git commit -m "feat(compliance-tester): ScriptPanel component with edge cases + AI diff"
```

---

## Task 7: Frontend — `FieldDiffTable` Component

**Files:**
- Create: `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/session/[id]/components/FieldDiffTable.tsx`

**Interfaces:**
- Produces:
  ```typescript
  interface FieldDiffTableProps {
    suggestedFields: Record<string, unknown>;
    reasoning: Record<string, string>;
    confidence: Record<string, "high" | "medium" | "low">;
    noChangesNeeded: string[];
    currentPoint: Record<string, unknown>;
    onAccept: (field: string, value: unknown) => void;
    onReject: (field: string) => void;
    onEdit: (field: string, value: unknown) => void;
    acceptedFields: Set<string>;
    rejectedFields: Set<string>;
  }
  ```

- [ ] **Step 1: Create `FieldDiffTable.tsx`**

```typescript
// FieldDiffTable.tsx
"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, Pencil, Check, X } from "lucide-react";
import { cn } from "@/admin/lib/utils";
import { Textarea } from "@/admin/components/ui/textarea";
import { Button } from "@/admin/components/ui/button";

const CONFIDENCE_COLORS = {
  high: "text-green-600 dark:text-green-400",
  medium: "text-yellow-600 dark:text-yellow-400",
  low: "text-red-500",
};

const CONFIDENCE_DOTS = {
  high: "●●●",
  medium: "●●○",
  low: "●○○",
};

function renderValue(val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (Array.isArray(val)) return val.join(", ");
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

export interface FieldDiffTableProps {
  suggestedFields: Record<string, unknown>;
  reasoning: Record<string, string>;
  confidence: Record<string, "high" | "medium" | "low">;
  noChangesNeeded: string[];
  currentPoint: Record<string, unknown>;
  onAccept: (field: string, value: unknown) => void;
  onReject: (field: string) => void;
  onEdit: (field: string, value: unknown) => void;
  acceptedFields: Set<string>;
  rejectedFields: Set<string>;
}

export function FieldDiffTable({
  suggestedFields,
  reasoning,
  confidence,
  noChangesNeeded,
  currentPoint,
  onAccept,
  onReject,
  onEdit,
  acceptedFields,
  rejectedFields,
}: FieldDiffTableProps) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");

  const changedFields = Object.keys(suggestedFields);

  if (changedFields.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-6">
        AI found no changes needed for this step.
        {noChangesNeeded.length > 0 && (
          <p className="text-xs mt-1 text-muted-foreground/60">
            Reviewed: {noChangesNeeded.join(", ")}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 border-b border-border">
          <tr>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide w-[160px]">Field</th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Current</th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">AI Suggestion</th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide w-[80px]">Confidence</th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide w-[100px]">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {changedFields.map((field) => {
            const accepted = acceptedFields.has(field);
            const rejected = rejectedFields.has(field);
            const conf = confidence[field] as "high" | "medium" | "low" | undefined ?? "medium";
            const currentVal = renderValue(currentPoint[field]);
            const suggestedVal = renderValue(suggestedFields[field]);
            const isEditing = editingField === field;

            return (
              <tr
                key={field}
                className={cn(
                  "transition-colors",
                  accepted && "bg-green-50/50 dark:bg-green-900/10",
                  rejected && "bg-muted/30 opacity-60",
                )}
              >
                {/* Field name */}
                <td className="px-4 py-3 align-top">
                  <span className="font-mono text-xs font-semibold">{field}</span>
                  {reasoning[field] && (
                    <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{reasoning[field]}</p>
                  )}
                </td>

                {/* Current value */}
                <td className="px-4 py-3 align-top">
                  <span className="text-xs text-muted-foreground font-mono break-all">{currentVal || "—"}</span>
                </td>

                {/* Suggested value */}
                <td className="px-4 py-3 align-top">
                  {isEditing ? (
                    <div className="flex flex-col gap-1.5">
                      <Textarea
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="text-xs min-h-[60px] font-mono"
                      />
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          className="h-6 px-2 text-xs bg-teal-600 hover:bg-teal-700 text-white"
                          onClick={() => {
                            onEdit(field, editValue);
                            setEditingField(null);
                          }}
                        >
                          <Check className="h-3 w-3 mr-1" />
                          Apply
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-6 px-2 text-xs"
                          onClick={() => setEditingField(null)}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <span className={cn("text-xs font-mono break-all", accepted && "text-green-700 dark:text-green-300")}>
                      {suggestedVal}
                    </span>
                  )}
                </td>

                {/* Confidence */}
                <td className="px-4 py-3 align-top">
                  <span className={cn("text-xs font-mono", CONFIDENCE_COLORS[conf])}>
                    {CONFIDENCE_DOTS[conf]} {conf}
                  </span>
                </td>

                {/* Actions */}
                <td className="px-4 py-3 align-top">
                  {accepted ? (
                    <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400 font-medium">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Accepted
                    </span>
                  ) : rejected ? (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <XCircle className="h-3.5 w-3.5" />
                      Rejected
                    </span>
                  ) : (
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => onAccept(field, suggestedFields[field])}
                        className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400 hover:text-green-500 font-medium transition-colors"
                      >
                        <CheckCircle2 className="h-3 w-3" />
                        Accept
                      </button>
                      <button
                        onClick={() => onReject(field)}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive transition-colors"
                      >
                        <XCircle className="h-3 w-3" />
                        Reject
                      </button>
                      <button
                        onClick={() => {
                          setEditingField(field);
                          setEditValue(suggestedVal === "—" ? "" : suggestedVal);
                        }}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <Pencil className="h-3 w-3" />
                        Edit
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd Codly-Frontend
rtk tsc --noEmit 2>&1 | grep -i "FieldDiffTable\|error" | head -10
```

- [ ] **Step 3: Commit**

```bash
rtk git add src/app/admin/\(dashboard\)/compliance/tester/session/\[id\]/components/FieldDiffTable.tsx
rtk git commit -m "feat(compliance-tester): FieldDiffTable with accept/reject/edit per AI suggestion"
```

---

## Task 8: Frontend — `StepStepper` Component

**Files:**
- Create: `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/session/[id]/components/StepStepper.tsx`

**Interfaces:**
- Produces:
  ```typescript
  interface Step {
    id: "metadata" | "scan_script" | "remediation";
    label: string;
    subLabel: string;
    status: "pending" | "analyzing" | "done" | "error" | "skipped";
    suggestionCount: number;
  }
  interface StepStepperProps {
    steps: Step[];
    activeStep: Step["id"];
    onStepClick: (stepId: Step["id"]) => void;
  }
  ```

- [ ] **Step 1: Create `StepStepper.tsx`**

```typescript
// StepStepper.tsx
"use client";

import { CheckCircle2, AlertCircle, Clock, Loader2, SkipForward } from "lucide-react";
import { cn } from "@/admin/lib/utils";

export interface Step {
  id: "metadata" | "scan_script" | "remediation";
  label: string;
  subLabel: string;
  status: "pending" | "analyzing" | "done" | "error" | "skipped";
  suggestionCount: number;
}

export interface StepStepperProps {
  steps: Step[];
  activeStep: Step["id"];
  onStepClick: (stepId: Step["id"]) => void;
}

const STATUS_ICON = {
  pending: <Clock className="h-4 w-4 text-muted-foreground" />,
  analyzing: <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />,
  done: <CheckCircle2 className="h-4 w-4 text-green-500" />,
  error: <AlertCircle className="h-4 w-4 text-red-500" />,
  skipped: <SkipForward className="h-4 w-4 text-muted-foreground" />,
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  analyzing: "Analyzing...",
  done: "Done",
  error: "Error",
  skipped: "Skipped",
};

export function StepStepper({ steps, activeStep, onStepClick }: StepStepperProps) {
  return (
    <div className="flex flex-col gap-0">
      {steps.map((step, idx) => {
        const isActive = step.id === activeStep;
        const isLast = idx === steps.length - 1;

        return (
          <div key={step.id} className="flex gap-3">
            {/* Vertical line + circle */}
            <div className="flex flex-col items-center">
              <button
                type="button"
                onClick={() => onStepClick(step.id)}
                className={cn(
                  "w-8 h-8 rounded-full border-2 flex items-center justify-center shrink-0 transition-all",
                  isActive
                    ? "border-teal-500 bg-teal-500/10"
                    : step.status === "done"
                      ? "border-green-500 bg-green-500/10"
                      : step.status === "error"
                        ? "border-red-500 bg-red-500/10"
                        : "border-border bg-card hover:border-muted-foreground",
                )}
              >
                {STATUS_ICON[step.status]}
              </button>
              {!isLast && (
                <div className={cn(
                  "w-px flex-1 my-1 min-h-[24px]",
                  step.status === "done" ? "bg-green-500/40" : "bg-border",
                )} />
              )}
            </div>

            {/* Step content */}
            <button
              type="button"
              onClick={() => onStepClick(step.id)}
              className={cn(
                "flex-1 text-left pb-4 pt-1 transition-colors",
                isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <div className="flex items-center justify-between">
                <span className={cn("text-sm font-semibold", isActive && "text-teal-600 dark:text-teal-400")}>
                  {idx + 1}. {step.label}
                </span>
                <div className="flex items-center gap-1.5">
                  {step.suggestionCount > 0 && step.status === "done" && (
                    <span className="text-xs px-1.5 py-0.5 rounded-full bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300">
                      {step.suggestionCount} suggestions
                    </span>
                  )}
                  <span className={cn(
                    "text-xs",
                    step.status === "done" && "text-green-600 dark:text-green-400",
                    step.status === "analyzing" && "text-blue-500",
                    step.status === "error" && "text-red-500",
                  )}>
                    {STATUS_LABEL[step.status]}
                  </span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">{step.subLabel}</p>
            </button>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd Codly-Frontend
rtk tsc --noEmit 2>&1 | grep -i "StepStepper\|error" | head -10
```

- [ ] **Step 3: Commit**

```bash
rtk git add src/app/admin/\(dashboard\)/compliance/tester/session/\[id\]/components/StepStepper.tsx
rtk git commit -m "feat(compliance-tester): StepStepper vertical step indicator component"
```

---

## Task 9: Frontend — Wire Components into Session Page

**Files:**
- Modify: `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/session/[id]/page.tsx`

**Interfaces:**
- Consumes: `ScriptPanel` from Task 6
- Consumes: `FieldDiffTable` from Task 7
- Consumes: `StepStepper` from Task 8
- Consumes: `PointStateAPI` with `edge_cases`, `script_summary` from Task 4
- Consumes: `CompliancePointAPI` with `aws_cli_with_placeholders`, `placeholder_list`, `mapping_dict`, `rb_summary`, `remediation_risk`

- [ ] **Step 1: Add imports to session page**

At top of `page.tsx`, add:

```typescript
import { ScriptPanel } from "./components/ScriptPanel";
import { FieldDiffTable } from "./components/FieldDiffTable";
import { StepStepper, type Step } from "./components/StepStepper";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
```

- [ ] **Step 2: Add per-point accepted/rejected field state**

In the component, add state for tracking decisions per point per field:

```typescript
const [fieldActions, setFieldActions] = useState<
  Record<number, { accepted: Set<string>; rejected: Set<string>; edited: Record<string, unknown> }>
>({});

function getFieldActions(pointId: number) {
  return fieldActions[pointId] ?? { accepted: new Set(), rejected: new Set(), edited: {} };
}

function acceptField(pointId: number, field: string, value: unknown) {
  setFieldActions((prev) => {
    const curr = prev[pointId] ?? { accepted: new Set(), rejected: new Set(), edited: {} };
    const nextAccepted = new Set(curr.accepted);
    const nextRejected = new Set(curr.rejected);
    nextAccepted.add(field);
    nextRejected.delete(field);
    return { ...prev, [pointId]: { ...curr, accepted: nextAccepted, rejected: nextRejected } };
  });
}

function rejectField(pointId: number, field: string) {
  setFieldActions((prev) => {
    const curr = prev[pointId] ?? { accepted: new Set(), rejected: new Set(), edited: {} };
    const nextAccepted = new Set(curr.accepted);
    const nextRejected = new Set(curr.rejected);
    nextRejected.add(field);
    nextAccepted.delete(field);
    return { ...prev, [pointId]: { ...curr, accepted: nextAccepted, rejected: nextRejected } };
  });
}

function editField(pointId: number, field: string, value: unknown) {
  setFieldActions((prev) => {
    const curr = prev[pointId] ?? { accepted: new Set(), rejected: new Set(), edited: {} };
    const nextAccepted = new Set(curr.accepted);
    nextAccepted.add(field);
    return { ...prev, [pointId]: { ...curr, accepted: nextAccepted, edited: { ...curr.edited, [field]: value } } };
  });
}
```

- [ ] **Step 3: Add active step state per point**

```typescript
const [activeStepPerPoint, setActiveStepPerPoint] = useState<
  Record<number, "metadata" | "scan_script" | "remediation">
>({});

function getActiveStep(pointId: number): "metadata" | "scan_script" | "remediation" {
  return activeStepPerPoint[pointId] ?? "metadata";
}
```

- [ ] **Step 4: Build step array helper**

Add a helper that computes the 3 steps for a point from its `PointStateAPI`:

```typescript
function buildSteps(
  state: PointStateAPI,
  cloudProvider: string
): Step[] {
  const cloudLabel = cloudProvider === "AZURE" ? "Azure CLI" : cloudProvider === "GCP" ? "gcloud CLI" : "AWS CLI";
  const remType = (state as any)?.remediation_type ?? "";
  const remLabel = remType === "auto" ? "Auto Script" : remType === "manual" ? "Manual Steps" : "Remediation";

  return [
    {
      id: "metadata" as const,
      label: "Metadata Analysis",
      subLabel: "severity, description, categories, frameworks",
      status: state.metadata_step.status as Step["status"],
      suggestionCount: Object.keys(state.metadata_step.suggestion ?? {}).length,
    },
    {
      id: "scan_script" as const,
      label: `Scan Script Review`,
      subLabel: cloudLabel,
      status: state.scan_script_step.status as Step["status"],
      suggestionCount: Object.keys(state.scan_script_step.suggestion ?? {}).length,
    },
    {
      id: "remediation" as const,
      label: `Remediation Review`,
      subLabel: remLabel,
      status: state.remediation_step.status as Step["status"],
      suggestionCount: Object.keys(state.remediation_step.suggestion ?? {}).length,
    },
  ];
}
```

- [ ] **Step 5: Replace per-point render with stepper + panels**

Find the section in the render that renders each point (the main loop over `points` or `pointStates`) and replace the inner content with the stepper layout:

```tsx
{/* For each point in the session */}
{currentPoint && currentState && (() => {
  const pointId = currentPoint.point_id;
  const activeStep = getActiveStep(pointId);
  const steps = buildSteps(currentState, session?.cloud_provider ?? "AWS");
  const fa = getFieldActions(pointId);
  const cloud = (session?.cloud_provider ?? "AWS") as "AWS" | "AZURE" | "GCP";

  return (
    <div className="grid grid-cols-[220px_1fr] gap-6">
      {/* Left: Stepper */}
      <div className="pt-1">
        <StepStepper
          steps={steps}
          activeStep={activeStep}
          onStepClick={(stepId) =>
            setActiveStepPerPoint((prev) => ({ ...prev, [pointId]: stepId }))
          }
        />

        {/* Confidence summary */}
        {currentState.metadata_step.confidence && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
              AI Confidence
            </p>
            {(() => {
              const allConf = {
                ...currentState.metadata_step.confidence,
                ...currentState.scan_script_step.confidence,
                ...currentState.remediation_step.confidence,
              };
              const vals = Object.values(allConf) as string[];
              const high = vals.filter((v) => v === "high").length;
              const med = vals.filter((v) => v === "medium").length;
              const low = vals.filter((v) => v === "low").length;
              return (
                <div className="space-y-1 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-green-600 dark:text-green-400 w-10">HIGH</span>
                    <div className="flex-1 bg-muted rounded-full h-1.5 overflow-hidden">
                      <div className="bg-green-500 h-full rounded-full" style={{ width: `${vals.length ? (high/vals.length)*100 : 0}%` }} />
                    </div>
                    <span className="text-muted-foreground w-4">{high}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-yellow-600 dark:text-yellow-400 w-10">MED</span>
                    <div className="flex-1 bg-muted rounded-full h-1.5 overflow-hidden">
                      <div className="bg-yellow-500 h-full rounded-full" style={{ width: `${vals.length ? (med/vals.length)*100 : 0}%` }} />
                    </div>
                    <span className="text-muted-foreground w-4">{med}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-red-500 w-10">LOW</span>
                    <div className="flex-1 bg-muted rounded-full h-1.5 overflow-hidden">
                      <div className="bg-red-500 h-full rounded-full" style={{ width: `${vals.length ? (low/vals.length)*100 : 0}%` }} />
                    </div>
                    <span className="text-muted-foreground w-4">{low}</span>
                  </div>
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {/* Right: Active step content */}
      <div className="space-y-5">
        {/* METADATA STEP */}
        {activeStep === "metadata" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold">Metadata Analysis</h3>
            {currentState.metadata_step.status === "pending" && (
              <p className="text-sm text-muted-foreground">Not yet analyzed. Click Analyze to start.</p>
            )}
            {currentState.metadata_step.status === "analyzing" && (
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing metadata fields...
              </p>
            )}
            {currentState.metadata_step.status === "done" && (
              <FieldDiffTable
                suggestedFields={currentState.metadata_step.suggestion ?? {}}
                reasoning={currentState.metadata_step.reasoning ?? {}}
                confidence={currentState.metadata_step.confidence ?? {}}
                noChangesNeeded={[]}
                currentPoint={currentPoint as unknown as Record<string, unknown>}
                acceptedFields={fa.accepted}
                rejectedFields={fa.rejected}
                onAccept={(field, value) => acceptField(pointId, field, value)}
                onReject={(field) => rejectField(pointId, field)}
                onEdit={(field, value) => editField(pointId, field, value)}
              />
            )}
          </div>
        )}

        {/* SCAN SCRIPT STEP */}
        {activeStep === "scan_script" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold">Scan Script Review</h3>

            {/* Script detail panel */}
            <ScriptPanel
              title="Scan CLI Script"
              cloudProvider={cloud}
              script={currentPoint.aws_cli_with_placeholders ?? ""}
              scriptSummary={currentState.scan_script_step.script_summary}
              placeholderList={
                Array.isArray(currentPoint.placeholder_list)
                  ? currentPoint.placeholder_list.map((p: any) =>
                      typeof p === "string" ? { name: p, description: "" } : p
                    )
                  : []
              }
              mappingDict={currentPoint.mapping_dict as Record<string, string> ?? {}}
              edgeCases={currentState.scan_script_step.edge_cases}
              permissionsRequired={currentState.scan_script_step.permissions_required}
              suggestedScript={
                (currentState.scan_script_step.suggestion as any)?.aws_cli_with_placeholders
              }
              scriptReasoning={
                currentState.scan_script_step.reasoning?.aws_cli_with_placeholders
              }
              complianceLogic
            />

            {/* Resource fetching CLI */}
            {currentPoint.resource_fetching_cli && (
              <ScriptPanel
                title="Resource Fetching CLI"
                cloudProvider={cloud}
                script={currentPoint.resource_fetching_cli}
                scriptSummary="Fetches all resources of this type to be scanned."
              />
            )}

            {/* Field diff for script fields */}
            {currentState.scan_script_step.status === "done" && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Script Field Changes
                </h4>
                <FieldDiffTable
                  suggestedFields={currentState.scan_script_step.suggestion ?? {}}
                  reasoning={currentState.scan_script_step.reasoning ?? {}}
                  confidence={currentState.scan_script_step.confidence ?? {}}
                  noChangesNeeded={[]}
                  currentPoint={currentPoint as unknown as Record<string, unknown>}
                  acceptedFields={fa.accepted}
                  rejectedFields={fa.rejected}
                  onAccept={(field, value) => acceptField(pointId, field, value)}
                  onReject={(field) => rejectField(pointId, field)}
                  onEdit={(field, value) => editField(pointId, field, value)}
                />
              </div>
            )}
          </div>
        )}

        {/* REMEDIATION STEP */}
        {activeStep === "remediation" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold">Remediation Review</h3>

            {/* Remediation script panel */}
            <ScriptPanel
              title="Remediation Script"
              cloudProvider={cloud}
              script={currentPoint.remediate_bashscript ?? ""}
              scriptSummary={currentPoint.rb_summary ?? currentState.remediation_step.risk_summary}
              edgeCases={currentState.remediation_step.edge_cases}
              permissionsRequired={currentState.remediation_step.permissions_required}
              riskSummary={currentState.remediation_step.risk_summary ?? currentPoint.remediation_risk}
              isRemediation
            />

            {/* Manual steps */}
            {Array.isArray(currentPoint.steps_to_remediate) && currentPoint.steps_to_remediate.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Manual Steps</p>
                <ol className="space-y-1.5">
                  {currentPoint.steps_to_remediate.map((step: string, i: number) => (
                    <li key={i} className="flex gap-2 text-sm">
                      <span className="shrink-0 w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs font-semibold">
                        {i + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Recommendations (markdown) */}
            {currentPoint.recommendations && (
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Recommendations</p>
                <div className="prose prose-sm dark:prose-invert max-w-none text-sm border rounded-lg p-4 bg-muted/20">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {currentPoint.recommendations}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Remediation field diff */}
            {currentState.remediation_step.status === "done" && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Remediation Field Changes
                </h4>
                <FieldDiffTable
                  suggestedFields={currentState.remediation_step.suggestion ?? {}}
                  reasoning={currentState.remediation_step.reasoning ?? {}}
                  confidence={currentState.remediation_step.confidence ?? {}}
                  noChangesNeeded={[]}
                  currentPoint={currentPoint as unknown as Record<string, unknown>}
                  acceptedFields={fa.accepted}
                  rejectedFields={fa.rejected}
                  onAccept={(field, value) => acceptField(pointId, field, value)}
                  onReject={(field) => rejectField(pointId, field)}
                  onEdit={(field, value) => editField(pointId, field, value)}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
})()}
```

- [ ] **Step 6: Verify no TypeScript errors**

```bash
cd Codly-Frontend
rtk tsc --noEmit 2>&1 | grep "error TS" | head -20
```

Fix any type errors. Common ones:
- `Loader2` not imported → add to lucide-react imports
- `currentPoint.rb_summary` not on type → cast via `(currentPoint as any).rb_summary`

- [ ] **Step 7: Run dev server and smoke test**

```bash
cd Codly-Frontend && bun run dev
```

Navigate to `/admin/compliance/tester/session/<any-session-id>`. Verify:
- Stepper renders 3 steps on left
- Clicking a step shows correct panel on right
- Script panel renders with code block, badges
- FieldDiffTable accept/reject buttons work (green/dim rows)

- [ ] **Step 8: Commit**

```bash
rtk git add src/app/admin/\(dashboard\)/compliance/tester/session/\[id\]/page.tsx
rtk git commit -m "feat(compliance-tester): wire stepper + script panels + field diff into session page"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| Cloud provider tabs on guidelines | Task 5 |
| `cloud_provider` on `FieldGuideline` model | Task 1 |
| Per-cloud guideline save/load | Tasks 2, 5 |
| Markdown preview on guidelines | Task 5 |
| Suggestion agent cloud-aware | Task 3 |
| `edge_cases` + `script_summary` in AI output | Task 3 |
| `analyze_scan_script.md` prompt updated | Task 3 |
| `analyze_remediation.md` prompt updated | Task 3 |
| `ScriptPanel` component | Task 6 |
| `FieldDiffTable` component | Task 7 |
| `StepStepper` component | Task 8 |
| Session page wired | Task 9 |
| `PointStateAPI` types extended | Task 4 |
| `rb_summary` in remediation panel | Task 9 step 5 |
| `remediation_risk` in remediation panel | Task 9 step 5 |
| Compliance logic box in scan panel | Task 6 (complianceLogic prop) |
| Placeholders table in script panel | Task 6 |
| Permissions required badges | Task 6 |
| Risk badge on remediation panel | Task 6 |
| Confidence summary bar | Task 9 step 5 |
| Markdown rendering for recommendations | Task 9 step 5 |
| Manual steps ordered list | Task 9 step 5 |

All spec requirements covered. No gaps found.
