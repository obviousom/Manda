# Compliance Tester — Design Spec

**Date:** 2026-06-21  
**Status:** Approved — ready for implementation  
**Author:** Dikshant Naik + Claude

---

## Context

Compliance point validation was done manually: engineers fed each point's metadata, CLI scripts, and placeholders into ChatGPT one by one and reviewed the output themselves. This is slow, unaudited, and doesn't scale.

**Goal:** Replace manual copy-paste with an AI-assisted review tool embedded in the Codly frontend. The AI suggests improvements to every field of a `CompliancePoint`. A human acts on each suggestion (Approve / Request Changes / Keep Existing). Approved changes are staged and bulk-committed at end of session. Every change is audited with before/after, who, when — and is rollback-able per field.

This is an **internal operations tool** — not customer-facing — but it lives inside `Codly-Frontend` at `/compliance/tester/` since the admin portal submodule has been removed from the monorepo.

---

## What We Are NOT Building in Phase 1

- Backend API (Phase 1 = frontend with mock/sample data only)
- Azure Foundry model integration (configured later)
- Actual AI calls (stubbed with mock suggestions in Phase 1)
- Scanning script execution (`aws_cli_with_placeholders` runner)
- Resource auto-discovery agent
- GCP/Azure cloud support (AWS first)

---

## Architecture

### Frontend Location
`Codly-Frontend` (Next.js, port 3003)  
UI library: shadcn/ui + Radix UI (already in use across compliance pages)  
State: TanStack Query for server data, Zustand/useState for session state  
Route prefix: `/compliance/tester/`

### Routes

| Route | Purpose |
|---|---|
| `/compliance/tester/` | Landing: stats, new session, resume sessions |
| `/compliance/tester/guidelines/` | Per-field guideline configuration |
| `/compliance/tester/session/[id]/` | Active testing session (A/B view toggle) |
| `/compliance/tester/session/[id]/commit` | Staged diff review + bulk commit |
| `/compliance/tester/history/` | Past sessions list |
| `/compliance/tester/point/[pointId]/audit` | Per-point field-level change history + rollback |

---

## Page-by-Page Design

### 1. Landing Page (`/compliance/tester/`)

**Stats bar** (top):
- Total CompliancePoints | Tested this month | Pending review | Approved changes staged

**New Session card:**
- Search field: by `point_id`, free text (searches `compliance_point` text), or service name
- Multi-select: choose specific points OR select an entire service (all points under it)
- Filter chips: Framework, Category, Cloud Provider, Severity
- "Start Session" button → creates session, routes to `/session/[id]/`

**Active Sessions list** (resumable sessions):
- Session name, started by, date, # points, progress bar, "Resume" button

**Link to History** → `/compliance/tester/history/`

---

### 2. Guidelines Page (`/compliance/tester/guidelines/`)

A pre-configuration page. Filled in by the team before running any testing sessions.

**Layout:** Table or card list of all `CompliancePoint` fields.

**Fields covered:**
- `compliance_point` (description text)
- `description`
- `categories` (M2M)
- `services` (M2M)
- `compliance_frameworks` (M2M)
- `resource_types` (M2M)
- `objectives` (M2M)
- `severity`
- `action`
- `aws_cli_with_placeholders`
- `resource_fetching_cli`
- `placeholder_list`
- `mapping_dict`
- `remediation_type`
- `remediate_bashscript`
- `steps_to_remediate`
- `recommendations`
- `cloud_provider`
- `is_active`

**Each row:**
- Field name (code) + type badge
- Guideline textarea: "What should the AI validate/enforce for this field?"
- Example: for `categories`: "Must be one of: IAM, Encryption, Network, Logging, Storage, Compute, Database, Cost. If empty, AI should suggest based on the point's description."
- Save button (per row, or global Save All)

**Phase 1:** Guidelines saved to `localStorage` under key `compliance_tester_guidelines`.  
**Phase 2:** Persisted in a new `ComplianceTesterGuideline` Django model.

---

### 3. Session Page — Two Views

The session page renders both views. A toggle in the top-right switches between them. This is specifically for Phase 1 so the team can compare and decide.

#### View A — Wizard (per point, step-by-step)

**Header:** Point [3] of [24] | point_id: 1042 | "AWS S3 Bucket Encryption" | badges (service, framework, severity)

**Step tabs:** `[1. Metadata] [2. Scripts] [3. Remediation] [4. Summary]`

**Step content (2-column layout):**
- Left: **Current Value** (read-only, grey background)
- Right: **AI Suggestion** (highlighted, editable if user wants to tweak before approving)

**Field rows within each step:**
- Field label
- Current value (left)
- Suggested value (right, with diff highlights for changed text)
- Per-field action: `✓ Approve` | `→ Keep` | `✏ Request Change`

**Request Change flow:**
- Text input appears: "What should the AI change?"
- "Re-suggest" → AI generates new suggestion for that field only

**Step footer:**
- "Approve All Fields on This Step" button
- "Next Step →"

**Final Step (Summary):**
- All approved/kept/changed decisions for this point
- "Stage This Point" → adds to commit queue, moves to next point
- "Skip Point" → skips without staging

**Bottom progress:** "3 approved, 1 skipped, 20 remaining"

---

#### View B — Card Queue

**Left sidebar (280px):**
- Scrollable list of all points in session
- Each item: point_id, short name, status icon (⏳ pending / ✅ approved / ⏭ skipped / 🔄 needs change)
- Search/filter within session queue
- Click any item to jump to it

**Right main area:**
- **Card header:** point_id | name | badges (service, framework, severity, cloud)
- **Tabs:** `Metadata | Scripts | Remediation | All`
- **Tab content:** 2-column diff (current vs suggested) — same as View A but all fields visible at once in the "All" tab
- **Card footer (sticky):**
  - `✓ Approve All` — stages all suggestions for this point
  - `→ Keep Existing` — skips point, no changes staged
  - `✏ Request Changes` — opens text area, user types feedback, "Re-suggest" fires

**Keyboard shortcuts:** `A` approve | `K` keep | `R` request change | `→ / ←` next/prev point

**Right sidebar (optional, collapsible):**
- Guidelines for fields currently visible (pulled from guidelines config)
- Shows relevant rule as tooltip/panel while reviewing

---

### 4. Commit Review Page (`/session/[id]/commit`)

**Header:** "Stage 1 Session — 18 points with changes ready to commit"

**Content:** Expandable list, one section per point:
- Point name + ID
- For each staged field: `field_name: "old value" → "new value"` (diff style)
- Unchecked points can be excluded from this commit

**Actions:**
- `Commit All Checked Changes` → calls backend bulk-update API (Phase 2)
- `Export as JSON` → download staged changes as file
- `Discard Session` → clears staged changes

**Phase 1:** Show the diff UI with mock data. "Commit" shows success toast (no actual API call).

---

### 5. History Page (`/compliance/tester/history/`)

Table of past sessions:
- Session ID, name, date, # points reviewed, # changes committed, committed by
- "View Audit Log" → `/point/[id]/audit`

---

### 6. Per-Point Audit Page (`/point/[pointId]/audit`)

**Header:** Point 1042 — "AWS S3 Bucket Encryption" audit log

**Timeline (newest first):**
- Each entry: field name | old value | new value | changed by | date/time | session ID
- Field values truncated with expand

**Per-entry actions:**
- `Rollback This Change` → reverts that field to old value (Phase 2: calls API)
- `View Session` → links to session history

---

## Data Shape (Frontend — Sample Data)

```typescript
// CompliancePoint (loaded from existing API or mock)
interface CompliancePointData {
  point_id: number;
  compliance_point: string;
  description: string;
  categories: string[];        // M2M names
  services: string[];          // M2M names
  compliance_frameworks: string[];
  resource_types: string[];
  objectives: string[];
  severity: "low" | "medium" | "high" | "critical";
  action: "auto_fix" | "suggest_fix" | "approval_required" | "never_auto_fix";
  cloud_provider: "AWS" | "AZURE" | "GCP";
  aws_cli_with_placeholders: string;
  resource_fetching_cli: string;
  placeholder_list: string[];
  mapping_dict: Record<string, string>;
  remediation_type: "auto" | "manual" | "unclassified";
  remediate_bashscript: string;
  steps_to_remediate: string[];
  recommendations: string;
  is_active: boolean;
}

// AI Suggestion (one per point, per session)
interface AISuggestion {
  point_id: number;
  suggested_fields: Partial<CompliancePointData>;
  reasoning: Record<string, string>;  // field → why AI suggested this
  confidence: Record<string, "high" | "medium" | "low">;
}

// Testing Session
interface TesterSession {
  id: string;
  name: string;
  created_at: string;
  created_by: string;
  point_ids: number[];
  point_statuses: Record<number, "pending" | "approved" | "skipped" | "needs_change">;
  staged_changes: StagedChange[];
  status: "active" | "committed" | "discarded";
}

// Staged change (one per field per point)
interface StagedChange {
  point_id: number;
  field_name: string;
  old_value: unknown;
  new_value: unknown;
  approved_by: string;
  approved_at: string;
}

// Audit entry (persisted after commit)
interface AuditEntry {
  id: string;
  point_id: number;
  field_name: string;
  old_value: unknown;
  new_value: unknown;
  changed_by: string;
  changed_at: string;
  session_id: string;
  rolled_back: boolean;
}

// Per-field guideline
interface FieldGuideline {
  field_name: string;
  guideline_text: string;
  valid_values?: string[];  // for enum fields
  updated_at: string;
}
```

---

## Phased Implementation Plan

### Phase 1 — Frontend Only (this sprint)
Build all pages with **mock/sample data**. No real API calls. Goal: UI approved, UX validated.

- [ ] Route scaffolding under `/compliance/tester/`
- [ ] Mock data file with 5-10 sample CompliancePoints + mock AI suggestions
- [ ] Landing page with stats, session creation drawer, sessions list
- [ ] Guidelines page (localStorage persistence)
- [ ] Session page View A (wizard)
- [ ] Session page View B (card queue)
- [ ] A/B toggle on session page
- [ ] Commit review page (mock diff)
- [ ] History page (mock sessions)
- [ ] Per-point audit page (mock timeline)

### Phase 2 — Django Backend
- New Django app: `compliance_tester`
- Models: `TesterSession`, `StagedChange`, `CommittedChange` (audit), `FieldGuideline`
- Views: CRUD for sessions, stage changes, commit batch, audit log, rollback
- Azure Foundry AI integration for suggestions
- Connect frontend to real API

### Phase 3 — AI + Scanning Integration
- Feed `FieldGuideline` records as system context to AI model
- Integrate existing compliance scanner for `aws_cli_with_placeholders` validation
- Resource auto-discovery agent
- Multi-cloud: Azure, GCP support

---

## Sample Mock Data (for Phase 1)

5 representative CompliancePoints covering: IAM, S3, EC2, RDS, CloudTrail.  
Mock AI suggestions for each — some fields identical (AI agrees), some changed (AI suggests update), some flagged as low confidence.

---

## Verification (Phase 1)

1. `cd Codly-Frontend && bun run dev`
2. Navigate to `/compliance/tester/`
3. Click "New Session" → search for points → start session
4. On session page: toggle between View A and View B
5. Approve/Keep/Request Changes on several cards
6. Navigate to commit page → see diff → "commit" (toast only)
7. Check guidelines page → set a guideline → refresh → verify localStorage persistence
8. Check audit page renders timeline with rollback buttons

---

## Open Questions (deferred to Phase 2)

- Which Azure Foundry model? (user to configure in settings)
- What fields are excluded from AI analysis? (user will specify later)
- Manual validation rules format? (user will provide exact instructions)
- Existing compliance scanner integration points for script validation?
