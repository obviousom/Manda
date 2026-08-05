# Compliance Tester Redesign — 2026-06-22

## Context

The compliance tester (`/admin/compliance/tester`) is an AI-assisted tool for reviewing and improving `CompliancePoint` records before committing them to production. It has three sub-pages:

- **Dashboard** (`/tester`) — session list + stats
- **Session** (`/tester/session/[id]`) — point-by-point AI review with 3-step analysis
- **Guidelines** (`/tester/guidelines`) — admin configures per-field AI instructions

**Problems being fixed:**
1. Guidelines page has no cloud-provider context — one flat list for all clouds, but AWS/Azure/GCP scripts differ completely
2. Session page analysis steps feel like a flat dump, not a guided process
3. Scripts section shows raw code with zero context — no summary, no edge cases, no limitations, no placeholder detail
4. Nothing is markdown-rendered — prose fields show as plain text walls
5. `rb_summary` field is often empty — not surfaced in UI at all; needs AI fallback
6. AI reasoning/confidence is buried — humans can't make informed decisions

---

## Design

### A. Backend: `FieldGuideline` — Add `cloud_provider`

**File:** `Codly_Backend/compliance_tester_app/models.py`

**Change:** Add `cloud_provider` to `FieldGuideline`. Unique constraint changes from `field_name` alone to `(field_name, cloud_provider)`.

```python
cloud_provider = models.CharField(
    max_length=10,
    choices=[('AWS', 'AWS'), ('AZURE', 'AZURE'), ('GCP', 'GCP')],
    null=True,
    blank=True,
    help_text="null = applies to all clouds. Set to restrict guideline to one provider.",
)
```

**Migration:** New migration. Existing rows keep `cloud_provider=null` (global).

**Unique constraint update:**
```python
class Meta:
    db_table = "compliance_tester_field_guideline"
    ordering = ["analysis_step", "field_name"]
    unique_together = [("field_name", "cloud_provider")]  # replaces unique=True on field_name
```

**Serializer update:** `bulk-save` endpoint accepts optional `cloud_provider` per item. GET endpoint accepts `?cloud_provider=AWS` filter + returns null (global) rows when querying specific cloud (union: global + cloud-specific, cloud-specific wins on conflict).

---

### B. Guidelines Page Redesign

**File:** `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/guidelines/page.tsx`

#### Cloud Provider Tabs

Top of page, below header:
```
[ AWS ]  [ Azure ]  [ GCP ]  [ Global (All Clouds) ]
```

- Switching tab: re-fetches `?cloud_provider=AWS` (merged with global)
- Saving: sends `cloud_provider` in payload per item
- Default tab: `AWS`
- Tab shows count badge: `AWS (12/19 configured)`

#### Script Fields — Cloud-Specific Labels

When tab = AWS: field label = "Scan CLI — AWS CLI"  
When tab = AZURE: field label = "Scan CLI — Azure CLI / ARM"  
When tab = GCP: field label = "Scan CLI — gcloud CLI"

Field `aws_cli_with_placeholders` is renamed in display only. Key stays same in DB.

#### Field Row Enhancements

Each field row gains:
- **Cloud badge** showing which cloud this guideline applies to (or "Global")
- **Inheritance indicator**: if field has no cloud-specific guideline, shows "Using global guideline" in dim text
- **Markdown preview toggle** on textarea fields — small "Preview" button renders the guideline text as markdown inline

#### Valid Values UX Fix

Current: add one-by-one with input+button.  
Fix: also accept comma-separated paste. On blur, split by comma and add all.

---

### C. Session Page — Analysis Steps Redesign

**File:** `Codly-Frontend/src/app/admin/(dashboard)/compliance/tester/session/[id]/page.tsx`

#### Per-Point Vertical Stepper

Each point gets a 3-step vertical stepper replacing the current flat tab UI:

```
┌──────────────────────────────────────────────────────────┐
│  Point #1234 · S3 Bucket Server-Side Encryption          │
│  [AWS] [critical] [Encryption · Storage]                 │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ① Metadata Analysis          ✅ Done (4 suggestions)    │
│  │  ↳ [Expand to review]                                 │
│                                                          │
│  ② Scan Script Review         🔄 In Progress             │
│  │  ↳ Cloud: AWS CLI                                     │
│  │  ↳ [Expand to review]                                 │
│                                                          │
│  ③ Remediation Review         ⏳ Pending                 │
│     ↳ [Locked until step 2 done]                         │
│                                                          │
│  [Approve All Steps]  [Request Changes]  [Skip Point]    │
└──────────────────────────────────────────────────────────┘
```

Step labels are cloud-aware:
- Step 2 label: "Scan Script Review — AWS CLI" / "Azure CLI" / "gcloud CLI"
- Step 3 label: "Remediation Review — Auto" or "Remediation Review — Manual Steps"

Steps are NOT strictly locked in sequence — user can jump to any step, but incomplete steps show warning badge.

#### Step Expand Panel — Metadata Step

Shows a diff table per suggested field:

```
Field         | Current Value          | AI Suggestion         | Confidence | Reasoning
description   | "Ensure S3 buckets..." | "Ensure all Amazon..." | HIGH ●●●   | "Current is too brief..."
severity      | high                   | critical               | MED ●●○    | "PII exposure = critical..."
```

Per-row actions: `[✓ Accept]` `[✗ Reject]` `[✎ Edit]`

Accepted rows turn green. Rejected rows turn dim. Edited rows show inline textarea.

#### Step Expand Panel — Scan Script Step

This is the main redesign area. Shows full script detail:

```
┌─ Scan CLI Script ───────────────────────────── [AWS CLI] [Copy] ─┐
│                                                                    │
│  ### What this script checks                                       │
│  <rb_summary if exists, else AI-generated 1-liner from reasoning> │
│                                                                    │
│  ### Script                                                        │
│  ```bash                                                           │
│  aws s3api get-bucket-encryption \                                 │
│    --bucket <BUCKET_NAME> \                                        │
│    --region <REGION>                                               │
│  ```                                                               │
│                                                                    │
│  ### Placeholders                                                  │
│  | Name          | Description              | Mapped From    |    │
│  |---------------|--------------------------|----------------|    │
│  | BUCKET_NAME   | S3 bucket name           | resource.Name  |    │
│  | REGION        | AWS region               | resource.region|    │
│                                                                    │
│  ### Compliance Logic                                              │
│  Output contains `true`  → Compliant                              │
│  Output contains `false` → Non-compliant                          │
│  Otherwise               → Unknown (logged, not remediated)       │
│                                                                    │
│  ### Edge Cases & Limitations (AI-analyzed)                       │
│  - Requires `s3:GetEncryptionConfiguration` IAM permission        │
│  - Returns `NoSuchBucket` error if bucket was deleted mid-scan    │
│  - Access Denied treated as non-compliant (conservative default)  │
│  - SSE-KMS and SSE-S3 both return `true` — no distinction made   │
│                                                                    │
│  ### AI Suggestions for this Script                               │
│  <diff view: current script vs suggested script if any>           │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- `rb_summary` → "What this script checks" (fallback: AI generates from script + description)
- `aws_cli_with_placeholders` → Script block (syntax highlighted)
- `placeholder_list` + `mapping_dict` → Placeholders table
- Edge cases → AI-generated, stored in `scan_script_reasoning` on `PointSessionState`
- AI diff → `scan_script_suggestion` on `PointSessionState`

**Resource Fetching CLI** shown below scan script in collapsible panel with same format.

#### Step Expand Panel — Remediation Step

```
┌─ Remediation ──────────────────────────────── [AUTO] ────────────┐
│                                                                    │
│  ### Remediation Script                                            │
│  ```bash                                                           │
│  aws s3api put-bucket-encryption ...                               │
│  ```                                                               │
│                                                                    │
│  ### What this remediation does                                    │
│  <rb_summary — REQUIRED here, AI fills if empty>                  │
│                                                                    │
│  ### Risk Assessment                                               │
│  <remediation_risk field, markdown rendered>                       │
│  ⚠ If empty: AI generates risk assessment from script analysis    │
│                                                                    │
│  ### Manual Steps (for manual remediation type)                   │
│  1. Navigate to S3 console                                         │
│  2. Select bucket → Properties → Encryption                       │
│  3. Enable SSE-S3 or SSE-KMS                                       │
│                                                                    │
│  ### Edge Cases (AI-analyzed)                                      │
│  - Cannot revert encryption once enabled                          │
│  - Script requires `s3:PutEncryptionConfiguration` permission     │
│                                                                    │
│  ### Recommendations                                               │
│  <recommendations field, markdown rendered>                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

`rb_summary` is the **summary of remediation script** — shown here, not in scan step.

#### Overall Point Review Header

Above the stepper, per point:
```
AI Confidence Summary:  HIGH ██████░░  6/10 fields   MED ██░░░░  2/10   LOW ░░░░░░  2/10
Changes proposed: 4 fields  |  No-change fields: 16  |  Your decisions: 3 approved, 1 pending
```

---

### D. Markdown Rendering

**Rule:** All prose fields rendered as markdown throughout session page:
- `description` 
- `recommendations`
- `rb_summary`
- `remediation_risk`
- `steps_to_remediate` (rendered as ordered list)
- AI reasoning text
- Edge cases text

Use existing markdown renderer in the codebase (check for `react-markdown` or `ReactMarkdown` import). If not present, add `react-markdown` + `remark-gfm`.

---

### E. Script Section — AI Edge Case Generation

**Where it's stored:** `PointSessionState.scan_script_reasoning` (already JSON field). Add `edge_cases` key to the reasoning JSON.

**When generated:** During `analyzePoint` backend call for `scan_script` step. AI prompt receives:
- The script content
- `cloud_provider` of the session
- Loaded guidelines for `aws_cli_with_placeholders` field filtered by `cloud_provider`
- The compliance point description

**AI output structure for scan_script step:**
```json
{
  "summary": "Checks whether S3 bucket server-side encryption is enabled",
  "edge_cases": [
    "Requires s3:GetEncryptionConfiguration IAM permission",
    "Returns NoSuchBucket if bucket deleted mid-scan",
    "Access Denied treated conservatively as non-compliant"
  ],
  "script_issues": ["Missing --region flag causes cross-region confusion"],
  "suggested_script": "aws s3api get-bucket-encryption --bucket <BUCKET_NAME> --region <REGION>",
  "placeholder_issues": ["REGION placeholder missing from placeholder_list"]
}
```

Remediation step gets same treatment: `remediation_reasoning` stores `edge_cases`, `risk_summary`, `permissions_required`.

---

## Files Changed

| File | Change Type |
|------|-------------|
| `compliance_tester_app/models.py` | Add `cloud_provider` to `FieldGuideline`, update unique constraint |
| `compliance_tester_app/migrations/000X_guideline_cloud_provider.py` | New migration |
| `compliance_tester_app/serializers.py` | Update guideline serializer, bulk-save logic |
| `compliance_tester_app/views.py` | Update GET filter: return global + cloud-specific merged |
| `compliance_tester_app/agents/suggestion_agent.py` | Update prompts: cloud-aware, output edge_cases + summary |
| `tester/guidelines/page.tsx` | Cloud provider tabs, per-cloud guideline slots, markdown preview |
| `tester/session/[id]/page.tsx` | Vertical stepper, script detail panels, markdown rendering, AI detail view |
| `tester/lib/mock-data.ts` | Add `cloud_provider` to `FieldGuideline` type |

---

## What's NOT Changing

- Backend scan execution logic (`compliance/compliance_dashboard/`) — untouched
- `CompliancePoint` model — untouched
- `TesterSession`, `PointSessionState`, `StagedChange` models — untouched (reasoning JSON is already flexible)
- Session dashboard (`/tester/page.tsx`) — untouched
- API route structure — no new endpoints, only parameter additions

---

## Implementation Order

1. Backend: `FieldGuideline` model + migration + serializer + view filter
2. Frontend: Guidelines page — cloud tabs + per-cloud save/load
3. Frontend: Session page — script detail panels (scan + remediation) with markdown
4. Frontend: Session page — vertical stepper per point
5. Backend: `suggestion_agent.py` — update prompt to output `edge_cases` + `summary` + cloud-aware
6. Frontend: Wire edge_cases + summary from `PointSessionState.scan_script_reasoning` into script panels
