# Codly 2.0 — Admin Portal RunBook Builder UI Design

> **Version**: 2.0 Draft  
> **Date**: April 2026  
> **Status**: Design Specification  
> **Covers**: Admin Portal RunBook Builder (Process Workflows)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Naming Conventions & Terminology](#2-naming-conventions)
3. [Navigation & Entry Point](#3-navigation--entry-point)
4. [RunBook List Page](#4-runbook-list-page)
5. [RunBook Canvas Editor](#5-runbook-canvas-editor)
6. [Node Picker Panel ("+")](#6-node-picker-panel)
7. [Node Configuration Panels](#7-node-configuration-panels)
8. [Trigger Configuration](#8-trigger-configuration)
9. [Human Checkpoint Node](#9-human-checkpoint-node)
10. [Execution History (Runs Tab)](#10-execution-history--runs-tab)
11. [Evaluations & Testing Tab](#11-evaluations--testing-tab)
12. [Shared Components](#12-shared-components)
13. [Color & Visual Language](#13-color--visual-language)
14. [Responsive Behavior](#14-responsive-behavior)

---

## 1. Overview

The **Admin Portal RunBook Builder** is a visual canvas-based editor for creating pre-configured, reusable automation workflows called **RunBooks**. 

- **Who uses it**: Admins, Platform Engineers, DevOps leads
- **What they do**: Design step-by-step automation workflows with triggers, logic, human checkpoints, and integrations
- **Workflow type**: Process Workflows (deterministic, pre-built, reusable)
- **UI style**: Visual canvas editor inspired by n8n
- **Purpose**: Create once, reuse many times — triggered by events, schedules, tickets, or manual execution

### Key Differences from Codly Frontend AI Planner

| Aspect | RunBook Builder | AI Planner |
|--------|-----------------|-----------|
| **Audience** | Admins, engineers | End users |
| **Workflow creation** | Manual design in UI | Auto-generated from user intent |
| **Reusability** | Designed to reuse | One-time execution |
| **Triggers** | Event/schedule/webhook | User request |
| **Canvas** | Persistent, saveable | Temporary, for review only |

---

## 2. Naming Conventions & Terminology

These are the official names to use everywhere in the RunBook builder UI.

### Node / Step Types

| Old / Generic Name | Codly Name | Icon |
|-------------------|------------|------|
| ~~AI~~ | **Codly Agent** | 🤖 Bot icon |
| ~~Action in an app~~ | **Integration Action** | 🔗 Link icon |
| ~~Data transformation~~ | **Transform** | ⚡ Zap icon |
| ~~Flow~~ | **Logic** | 🔀 Merge icon |
| ~~Core~~ | **Utility** | 🔧 Wrench icon |
| ~~Human review~~ | **Human Checkpoint** | 👤 UserCheck icon |
| ~~Trigger~~ | **Trigger** | ⚡ Lightning icon |

### Agent Types

| What n8n calls | Codly 2.0 Name | Description |
|---------------|---------------|-------------|
| ~~Third-party agent~~ | **Partner Skill** | Pre-built skills from verified partners (Splunk, Nessus, etc.) — amber star icon |
| ~~AI node~~ | **Codly Agent** | Native Codly agents (OS, Compliance, FinOps, etc.) — blue bot icon |
| ~~Webhook~~ | **Inbound Trigger** | Incoming webhook from external system |
| ~~HTTP Request~~ | **Outbound Call** | Call external API |
| ~~Code node~~ | **Script Runner** | Execute custom script on cloud |

### RunBook Terminology

| Term | Meaning |
|------|---------|
| **RunBook** | A complete pre-configured automation workflow (the overall thing) |
| **Step** | One node/action inside a RunBook |
| **Run** | One execution of a RunBook |
| **Trigger** | What starts the RunBook (event, schedule, webhook, manual, ticket) |
| **Checkpoint** | Human approval point within the RunBook |

---

## 3. Navigation & Entry Point

### Left Sidebar Addition

**Location**: Admin Portal → Left Sidebar → "RunBooks" (new menu item)

```
LEFT SIDEBAR (Admin Portal)
├── Dashboard
├── Customers
├── User Management
├── Compliance
├── FinOps Hub
├── ─────────────── (separator)
├── 🗂️  RunBooks          ← NEW — Codly 2.0
│   ├── All RunBooks
│   ├── + Create RunBook
│   └── Templates
├── ─────────────────────
├── Agent Management
├── AI Platforms
└── Settings
```

**Route**: `/dashboard/runbooks`

---

## 4. RunBook List Page

**Route**: `/dashboard/runbooks`

The landing page showing all RunBooks the admin has created or has access to.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RunBooks                                              [+ Create RunBook]    │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  ┌──────────────────┐  Filter: [All ▼] [Customer ▼] [Cloud ▼] [Status ▼]   │
│  │ 🔍 Search RunBooks│                                                       │
│  └──────────────────┘                                                        │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  NAME                    CUSTOMER    TRIGGERS   LAST RUN    STATUS     │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │  EC2 Post-Deploy Runbook  Acme Corp  2 triggers  2h ago    ✅ Active   │ │
│  │  [AWS] [Security]                                 ✅ 47 runs           │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │  Nightly Compliance Sweep Codly      1 trigger   6h ago    ✅ Active   │ │
│  │  [AWS] [Azure] [Compliance]                       ✅ 12 runs           │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │  SG Violation Response    Acme Corp  1 trigger   —         ⏸ Paused   │ │
│  │  [AWS] [Security] [P1]               Never run              0 runs     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  FROM MARKETPLACE                                                            │
│  ┌───────────────────────────────────────────────────────────────────┐      │
│  │  💡 Browse 24 ready-to-use RunBook templates in the Marketplace → │      │
│  └───────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Column Details

- **NAME**: RunBook title, with tags (AWS, Azure, Security, Compliance, etc.)
- **CUSTOMER**: Which customer this RunBook belongs to (Acme Corp, Codly, etc.)
- **TRIGGERS**: How many triggers are configured (e.g., "2 triggers")
- **LAST RUN**: When it last executed (e.g., "2h ago" or "Never")
- **STATUS**: Active ✅ | Paused ⏸ | Draft ✏️
- **RUN COUNT**: Total successful runs

### Row Actions (on hover)

- **Edit** → Opens canvas editor
- **Run Now** → Execute immediately
- **Duplicate** → Clone this RunBook with a new name
- **View Runs** → Jump to the Runs tab
- **Pause/Resume** → Toggle active/paused state
- **Delete** → Remove RunBook (soft delete with restore option)

### Filters

- **All / Active / Paused / Draft** — status filter
- **Customer** — filter by which customer owns it
- **Cloud Provider** — AWS, Azure, GCP
- **Category / Tags** — custom tags (Security, Compliance, etc.)

---

## 5. RunBook Canvas Editor

**Route**: `/dashboard/runbooks/{id}/edit`

This is the main visual editor. Inspired by n8n's workflow editor.

### Overall Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ← RunBooks  /  EC2 Post-Deploy Runbook                    [Run Now] [Save] │
│  ─────────────────────────────────────────────────────────────────────────  │
│  [Customer: Acme Corp] [Account: prod-aws-01] [Permission: Operator]        │
│  ────────────────────────────────┬──────────────────────────────────────────│
│              TABS                │
│  [ Editor ] [ Runs ] [ Evaluate ]│
│  ────────────────────────────────┘
│                                                                              │
│  ┌─────────────────────────────────────────────────────── CANVAS ─────────┐ │
│  │                                           (dot-grid background)         │ │
│  │                                                                         │ │
│  │   ⚡[EC2 Created]───→[🤖 Compliance]───→[🔀 IF violations>0]           │ │
│  │                                              │YES          │NO          │ │
│  │                                    [🤖 OS Patching]  [🔗 Slack: OK]    │ │
│  │                                         │                               │ │
│  │                                    [🤖 OS Hardening]                   │ │
│  │                                         │                               │ │
│  │                                    [👤 Human Check]                    │ │
│  │                                         │APPROVED                      │ │
│  │                                    [🤖 Install Agents]                 │ │
│  │                                         │                               │ │
│  │                                    [🔗 Create Ticket]                  │ │
│  │                                                                         │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  BOTTOM BAR:  [⊡ Fit] [🔍+] [🔍-] [↩ Undo] [↪ Redo]    [▶ Execute RunBook]│
│  MINI-MAP (bottom right corner, collapsible)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Canvas Interactions

| Action | How | Result |
|--------|-----|--------|
| **Pan** | Click and drag empty canvas | Move viewport around |
| **Zoom** | Scroll wheel or bottom toolbar +/- | Zoom in/out |
| **Select node** | Click on a node | Shows selection highlight |
| **Move node** | Drag a node | Reposition on canvas |
| **Connect nodes** | Drag from output port to input port | Create edge between steps |
| **Add a step** | Click `+` button between nodes or in toolbar | Opens Node Picker panel |
| **Delete node** | Select → Delete key or right-click → Delete | Remove step |
| **Duplicate node** | Right-click → Duplicate | Copy step with same config |
| **Multi-select** | Shift+Click or drag select box | Select multiple nodes |
| **Quick config** | Double-click a node | Open config panel for that step |
| **View step output** | Click step, then "View Output" | See what the step returned |

### Node Visual Design

```
Single node appearance:

┌─────────────────────────────┐
│  🤖  Compliance Agent        │  ← icon + agent name
│  ─────────────────────────  │
│  CIS Benchmark Scan          │  ← sub-label (what it does)
│  Account: prod-aws-01        │  ← configured context
└──────┬──────────────────────┘
  INPUT PORT (left)       OUTPUT PORT (right) ──→

Node states:
- Default:    White card, grey border
- Selected:   Blue border, subtle shadow
- Running:    Pulsing blue left border, spinner icon
- Success:    Green left border, ✅ in corner
- Failed:     Red left border, ❌ in corner
- Skipped:    Grey, diagonal stripes
- Waiting:    Yellow left border, 👤 icon (human checkpoint)
```

### Connection Lines

- **Default**: Grey animated dashed line
- **On hover**: Highlighted blue, shows `+` button to insert node between
- **Conditional branches**: Labelled `YES` / `NO` or `TRUE` / `FALSE` in small pill badge on line
- **Parallel branches**: Lines fan out, can merge back together

---

## 6. Node Picker Panel ("+")

When the user clicks `+` (between nodes, from a node output, or toolbar), the right panel slides in.

**This is the Codly version of n8n's "What happens next?" panel.**

```
RIGHT PANEL — "What's the next step?"
┌──────────────────────────────────────────┐
│  What's the next step?                 ✕ │
│  ──────────────────────────────────────  │
│  🔍 Search steps...                      │
│  ──────────────────────────────────────  │
│                                          │
│  🤖  CODLY AGENTS          →             │
│      Run Codly's built-in cloud agents   │
│                                          │
│  🔗  INTEGRATION ACTION    →             │
│      Notify Slack, create Jira ticket,   │
│      call external API, update ITSM      │
│                                          │
│  🔀  LOGIC                 →             │
│      Branch, loop, merge, wait, set var  │
│                                          │
│  👤  HUMAN CHECKPOINT      →             │
│      Pause and require human approval    │
│      before continuing                   │
│                                          │
│  🔧  UTILITY               →             │
│      Transform data, filter list,        │
│      run script, HTTP call               │
│                                          │
│  ⭐  PARTNER SKILLS        →             │
│      Splunk, Nessus, Grafana, Datadog,   │
│      GitHub, PagerDuty                   │
│                                          │
│  ──────────────────────────────────────  │
│  Recently used:                          │
│  [🤖 Compliance] [🔗 Slack] [👤 Review]  │
└──────────────────────────────────────────┘
```

### Sub-panel: Codly Agents

Clicking "CODLY AGENTS →" shows available agents organized by function:

```
← Back to categories

🤖 CODLY AGENTS
──────────────────────────────────────────
🔍 Search agents...

CLOUD OPERATIONS
  ├── OS Management Agent
  │    Patch status, SSH checks, services
  ├── OS Hardening Agent
  │    CIS benchmarks, security config
  ├── Compliance Agent
  │    CIS/SOC2/PCI compliance scans
  ├── Inventory Agent
  │    Discover EC2, VMs, S3, storage
  └── Log Analytics Agent
       CloudTrail, VPC Flow Logs, ALB

COST & FINANCE
  ├── FinOps Agent
  │    Cost breakdown, anomalies
  └── Waste Analysis Agent
       Idle resources, rightsizing

OPERATIONS
  ├── CLI Execution Agent
  │    Run AWS CLI / Azure CLI commands
  ├── DB Management Agent
  │    Safe database inspection & queries
  └── Network Validation Agent
       Connectivity, security group checks

SUPPORT
  └── Ticket Management Agent
       Create, update, resolve ITSM tickets
```

### Sub-panel: Integration Action

```
← Back to categories

🔗 INTEGRATION ACTION
──────────────────────────────────────────
NOTIFICATIONS
  ├── Slack — Send message to channel
  ├── Microsoft Teams — Post to channel
  ├── Email — Send via SES/SMTP
  ├── PagerDuty — Create/resolve incident
  └── SMS (Twilio) — Text alert

ITSM
  ├── Freshservice — Create/update ticket
  ├── Jira — Create/update issue
  ├── Zendesk — Create/update ticket
  └── ServiceNow — Create/update record

STORAGE & DATA
  ├── S3 — Upload report/file
  ├── Google Sheets — Append row
  └── Confluence — Create/update page

CUSTOM
  └── HTTP Webhook — POST to external URL
```

### Sub-panel: Logic

```
← Back to categories

🔀 LOGIC
──────────────────────────────────────────

IF / Else          Branch on condition
Loop               Iterate over a list
Wait               Pause for N minutes
Merge              Join parallel branches
Set Variable       Store a value for later
Error Handler      Catch failures gracefully
```

### Sub-panel: Partner Skills

```
← Back to categories

⭐ PARTNER SKILLS
──────────────────────────────────────────
Note: These are verified skills built by
our integration partners.

SECURITY
  ├── Nessus Vulnerability Scan
  │    Run and parse Nessus scan results
  ├── Qualys Security Scan
  │    Trigger and collect Qualys scans
  └── CrowdStrike EDR Check
       Query CrowdStrike for endpoint status

OBSERVABILITY
  ├── Grafana — Query dashboards/alerts
  ├── Datadog — Query metrics/events
  └── Splunk — Run SPL searches

DEVOPS
  ├── GitHub — Trigger Actions, read PRs
  ├── ArgoCD — Check deployment status
  └── Terraform — Read/plan state files

[Browse Marketplace for more →]
```

---

## 7. Node Configuration Panels

When a node is double-clicked or selected, a right panel opens with configuration specific to that node type.

### Codly Agent Node Config

```
┌───────────────────────────────────────────┐
│  🤖 Compliance Agent                  [✕] │
│  ─────────────────────────────────────    │
│  GENERAL                                  │
│  Name:  [Compliance Scan Step 1     ]     │
│                                           │
│  AGENT SETTINGS                           │
│  Agent: [Compliance Agent          ▼]     │
│  Provider: Auto (uses account cloud)      │
│  Account: [Use RunBook account      ▼]    │
│                                           │
│  TASK INSTRUCTION                         │
│  ┌─────────────────────────────────────┐  │
│  │ Run a full CIS Level 1 compliance   │  │
│  │ scan. Return violations as a list.  │  │
│  └─────────────────────────────────────┘  │
│  (Uses variables from previous steps:)    │
│  [{{instance_id}}]  [{{region}}]          │
│                                           │
│  OUTPUT VARIABLE NAME                     │
│  [ compliance_result             ]        │
│  (Available to next steps as this name)   │
│                                           │
│  ERROR HANDLING                           │
│  On failure: [Continue ▼]                 │
│  Timeout:    [5 minutes ▼]                │
│                                           │
│  [Cancel]              [Save Step]        │
└───────────────────────────────────────────┘
```

### IF / Else Logic Node Config

```
┌───────────────────────────────────────────┐
│  🔀 IF / Else                         [✕] │
│  ─────────────────────────────────────    │
│  CONDITION                                │
│  Variable:  [compliance_result.count ▼]   │
│  Operator:  [Greater than          ▼]     │
│  Value:     [0                       ]    │
│                                           │
│  ADD MORE CONDITIONS                      │
│  [+ Add AND condition]                    │
│  [+ Add OR condition ]                    │
│                                           │
│  BRANCH LABELS                            │
│  YES branch label: [Violations Found]     │
│  NO branch label:  [All Clear      ]      │
│                                           │
│  [Cancel]              [Save Step]        │
└───────────────────────────────────────────┘
```

### Integration Action — Slack Config

```
┌───────────────────────────────────────────┐
│  🔗 Slack — Send Message              [✕] │
│  ─────────────────────────────────────    │
│  CHANNEL                                  │
│  [ #security-alerts               ▼]      │
│                                           │
│  MESSAGE                                  │
│  ┌─────────────────────────────────────┐  │
│  │ ✅ RunBook Complete: {{runbook_name}}│  │
│  │ Account: {{account_name}}           │  │
│  │ Violations found: {{count}}         │  │
│  │ View run: {{run_url}}               │  │
│  └─────────────────────────────────────┘  │
│  [Insert variable ▼]                      │
│                                           │
│  SEND AS                                  │
│  [○ Notification  ● Rich Message]         │
│                                           │
│  COLOR (for rich message)                 │
│  [● Red  ○ Green  ○ Yellow  ○ Blue]       │
│                                           │
│  [Cancel]              [Save Step]        │
└───────────────────────────────────────────┘
```

---

## 8. Trigger Configuration

Triggers are the first node (leftmost, entry point). Clicking the Trigger node opens the config panel.

```
┌───────────────────────────────────────────┐
│  ⚡ Trigger Configuration             [✕] │
│  ─────────────────────────────────────    │
│  TRIGGER TYPE                             │
│  ┌──────────────────────────────────────┐ │
│  │ ○ Scheduled (Cron)                   │ │
│  │ ● CloudTrail Event          ← active │ │
│  │ ○ Ticket Created / Updated           │ │
│  │ ○ Metric / Alert Threshold           │ │
│  │ ○ Cost Anomaly                       │ │
│  │ ○ Manual Only                        │ │
│  │ ○ Inbound Webhook                    │ │
│  │ ○ After Dynamic Workflow Completes   │ │
│  └──────────────────────────────────────┘ │
│                                           │
│  CLOUDTRAIL EVENT SETTINGS                │
│  Event name: [RunInstances         ]      │
│  Resource type: [EC2 Instance      ▼]     │
│  Account filter: [Any account      ▼]     │
│                                           │
│  INITIAL CONTEXT (passed to first step)   │
│  ┌──────────────────────────────────────┐ │
│  │ instance_id → from event.instanceId  │ │
│  │ region → from event.region           │ │
│  │ [+ Add mapping]                      │ │
│  └──────────────────────────────────────┘ │
│                                           │
│  [Cancel]              [Save Trigger]     │
└───────────────────────────────────────────┘
```

### Trigger Types

#### Scheduled (Cron)

```
Cron expression: [0 2 * * *              ]
                  ↓ Human-readable preview
                 "Every day at 2:00 AM"

Timezone: [Asia/Kolkata (IST) ▼]

[Common schedules: Daily at midnight | Every hour | Every Monday | Custom]
```

#### CloudTrail Event

Triggered by AWS API events:
- Event name: RunInstances, TerminateInstances, ModifySecurityGroup, etc.
- Resource type: EC2, S3, RDS, etc.
- Account filter: Which AWS account(s)

#### Ticket Created / Updated

Triggered by ITSM ticket events:
```
ITSM Provider: [Freshservice ▼]
Ticket type: [Incident ▼]
Trigger on: [● Created  ○ Updated  ○ Both]
Keywords (any match): [server down] [cpu high] [+ Add]
Priority filter: [P1 ▼] [P2 ▼] [+ Add]
```

#### Metric / Alert Threshold

Triggered by CloudWatch alarm or external monitoring:
```
Metric: [CPU Utilization ▼]
Threshold: [Greater than] [80]%
Duration: [5 minutes ▼]
```

#### Cost Anomaly

Triggered by Codly's cost anomaly detection:
```
Threshold increase: [20]%
Min daily cost: [$50 ▼]
Cloud provider: [Any ▼]
```

#### Manual Only

No automatic trigger — only runs when clicked "Run Now" on the list page.

#### Inbound Webhook

Accepts HTTP POST from external systems:
```
Webhook URL: https://codly.io/webhooks/rbk_abc123xyz
Expected payload: [JSON ▼]
```

#### After Dynamic Workflow Completes

Triggered after a user's AI Planner mission completes. See Frontend section.

---

## 9. Human Checkpoint Node

The Human Checkpoint pauses execution and waits for human approval before proceeding.

### Node on Canvas

```
┌──────────────────────────────────────┐
│  👤  Human Checkpoint                 │
│  ──────────────────────────────────  │
│  Approve: Install Monitoring  │
│  Via: Slack #devops-alerts   │
│  Timeout: 2 hours            │
└──────┬──────┬────────────────┘
       │      │
   APPROVED  REJECTED/TIMEOUT
```

### Config Panel

```
┌───────────────────────────────────────────┐
│  👤 Human Checkpoint                  [✕] │
│  ─────────────────────────────────────    │
│  CHECKPOINT TITLE                         │
│  [Approve: Install Monitoring Agents  ]   │
│                                           │
│  MESSAGE TO REVIEWER                      │
│  ┌─────────────────────────────────────┐  │
│  │ Compliance scan complete.           │  │
│  │ {{compliance_result.count}} violations│ │
│  │ found on {{instance_id}}.           │  │
│  │                                     │  │
│  │ Continue with OS patching and       │  │
│  │ agent installation?                 │  │
│  └─────────────────────────────────────┘  │
│                                           │
│  APPROVAL OPTIONS                         │
│  [Approve]  label: [Proceed            ]  │
│  [Reject]   label: [Skip this instance ]  │
│  [+ Add custom option]                    │
│                                           │
│  NOTIFY VIA                               │
│  ☑ Slack channel: [#devops-approvals  ]   │
│  ☑ Email: [{{assigned_user.email}}    ]   │
│  ☐ Teams                                  │
│  ☐ PagerDuty                              │
│                                           │
│  TIMEOUT                                  │
│  Wait: [2 hours ▼] then: [Auto-Reject ▼]  │
│                                           │
│  ON APPROVED → (connects to next step)    │
│  ON REJECTED → [Stop RunBook ▼]           │
│                                           │
│  [Cancel]              [Save Step]        │
└───────────────────────────────────────────┘
```

### Approval Notification (Slack)

What the approver sees:

```
🟡 Codly | RunBook Approval Required

RunBook: EC2 Post-Deploy Runbook
Customer: Acme Corp / prod-aws-01
Checkpoint: Approve: Install Monitoring Agents

Compliance scan complete.
12 violations found on i-0abc123def.
Continue with OS patching and agent installation?

[✅ Proceed]   [⏭️ Skip this instance]

⏱️ Expires in 2 hours
View full run → https://app.codly.io/runbooks/runs/abc123
```

---

## 10. Execution History (Runs Tab)

**Route**: `/dashboard/runbooks/{id}/runs`

Shows all past executions of this RunBook.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ← RunBooks  /  EC2 Post-Deploy Runbook                                     │
│  [ Editor ] [● Runs ] [ Evaluate ]                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  FILTERS:  [Status: All ▼]  [Account: All ▼]  [Date: Last 7 days ▼]        │
│  [Export CSV]                                                     47 runs    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  RUN ID    TRIGGERED BY          STARTED         DURATION  STATUS   │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │  run_047   EC2: i-0abc (RunInst) Today 14:22     3m 41s    ✅ Done   │   │
│  │  run_046   Manual — admin@x.com  Today 11:05     2m 15s    ✅ Done   │   │
│  │  run_045   EC2: i-0def (RunInst) Yesterday 22:01 0m 12s    ❌ Failed │   │
│  │  run_044   EC2: i-0ghi (RunInst) Yesterday 18:44 —         ⏸ Paused │   │
│  │            ↳ 👤 Awaiting approval at step 5                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Clicking a Run — Run Detail View

Same canvas, read-only, showing each step's execution status:

```
┌───────────────── RUN #047 ──────────────────┐
│  EC2 Post-Deploy Runbook · i-0abc123         │
│  Started: Today 14:22 · Duration: 3m 41s    │
│  Triggered by: CloudTrail RunInstances event │
│  ─────────────────────────────────────────── │
│                                              │
│  STEP TIMELINE                               │
│                                              │
│  ✅ Trigger          0s     EC2 i-0abc123    │
│  ✅ Compliance Scan  1m 2s  12 violations    │
│  ✅ IF Violations    0s     → YES branch     │
│  ✅ OS Patching      1m 5s  42 patches       │
│  ✅ OS Hardening     45s    8 rules applied  │
│  👤 Human Checkpoint —     APPROVED by dev  │
│  ✅ Install Agents   28s   4 agents done     │
│  ✅ Create Ticket    3s    TICKET-1024       │
│  ✅ Slack Alert      2s    Sent to #devops  │
│                                              │
│  [View Step Output] [Download Report PDF]   │
└──────────────────────────────────────────────┘
```

---

## 11. Evaluations & Testing Tab

**Route**: `/dashboard/runbooks/{id}/evaluate`

Test the RunBook with simulated data before going live.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [ Editor ] [ Runs ] [● Evaluate ]                                          │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  TEST YOUR RUNBOOK SAFELY                                                    │
│  Run with simulated data — no real cloud calls will be made.                 │
│                                                                              │
│  TEST SCENARIO                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  Scenario name: [EC2 creation with violations              ]           │ │
│  │  Mock trigger event:                                                   │ │
│  │  {                                                                     │ │
│  │    "instance_id": "i-0testABC",                                        │ │
│  │    "region": "us-east-1",                                              │ │
│  │    "event": "RunInstances"                                             │ │
│  │  }                                                                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  MOCK AGENT RESPONSES                                                        │
│  Step 1 (Compliance Agent): [Use real API ▼ / Mock with sample data]        │
│  Step 3 (OS Patching):      [Use real API ▼ / Mock with sample data]        │
│                                                                              │
│  [▶ Run Evaluation]                                                          │
│                                                                              │
│  PAST EVALUATIONS  ───────────────────────────────────────────────          │
│  eval_003 · All steps passed · Yesterday 16:30                              │
│  eval_002 · Step 3 failed (timeout) · 3 days ago                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Shared Components

### Variable Picker

When configuring steps that use dynamic variables (from previous step outputs):

```
TYPE: {{   ← triggers picker dropdown

┌──────────────────────────────────┐
│  Insert Variable                 │
│  ────────────────────────────    │
│  FROM TRIGGER                    │
│  {{instance_id}}                 │
│  {{region}}                      │
│  {{event_name}}                  │
│                                  │
│  FROM STEP 1 (Compliance)        │
│  {{compliance_result.count}}     │
│  {{compliance_result.violations}}│
│  {{compliance_result.score}}     │
│                                  │
│  FROM STEP 2 (OS Patching)       │
│  {{patching_result.success}}     │
│  {{patching_result.patch_count}} │
│                                  │
│  GLOBAL                          │
│  {{account_name}}                │
│  {{customer_name}}               │
│  {{run_url}}                     │
│  {{current_datetime}}            │
└──────────────────────────────────┘
```

### Step Status Badge

```
⬜ Not started (grey)
⏳ Running (blue, pulsing)
✅ Completed (green)
❌ Failed (red)
⏸ Paused (yellow — human checkpoint)
⏭ Skipped (grey, diagonal)
🔁 Retrying (orange)
```

### Permission Level Badge

Visible throughout the editor:

```
🔍 Read-Only     (grey badge) — only read/inspect actions
⚙️ Operator      (blue badge) — safe change actions
⚡ Power User    (orange badge) — full execution including destructive actions
```

---

## 13. Color & Visual Language

### Node Colors by Category

| Category | Border Color | Icon Background |
|----------|-------------|-----------------|
| Codly Agents | `#3B82F6` (Blue) | Light blue |
| Partner Skills | `#F59E0B` (Amber) | Light amber — star badge |
| Integration Actions | `#8B5CF6` (Purple) | Light purple |
| Logic nodes | `#6B7280` (Grey) | Light grey |
| Human Checkpoint | `#EAB308` (Yellow) | Light yellow, dashed border |
| Trigger | `#10B981` (Green) | Solid green |
| Error/Failed state | `#EF4444` (Red) | — |
| Running state | `#3B82F6` (Blue) | Pulsing animation |
| Success state | `#10B981` (Green) | — |

### RunBook Status Colors

| Status | Color | Icon |
|--------|-------|------|
| Active | Green | ✅ |
| Paused | Yellow | ⏸ |
| Draft | Grey | ✏️ |
| Running | Blue (pulsing) | ⏳ |
| Error | Red | ❌ |

### Node Type Icons

| Node Type | Icon |
|-----------|------|
| Codly Agent | 🤖 |
| Partner Skill | ⭐ |
| Integration Action | 🔗 |
| Logic | 🔀 |
| Human Checkpoint | 👤 |
| Trigger | ⚡ |
| Utility | 🔧 |

---

## 14. Responsive Behavior

### Desktop (> 1280px)

- Full canvas visible with nodes and edges
- Right config panel open side-by-side
- Bottom toolbar visible
- Mini-map in corner
- Smooth panning and zooming

### Tablet (1024–1280px)

- Canvas fills screen
- Right config panel overlays on demand
- Bottom toolbar still visible
- Mini-map optional

### Mobile (< 1024px)

- **Canvas editor disabled** on mobile
- Switch to "Step List" view instead — linear list of steps, not canvas
- Config panels open as full-screen modals
- Editing disabled; read-only mode only
- Can view run history and results

---

## API Integration (Backend Reference)

For backend developers implementing these APIs:

- **GET** `/api/runbooks/` — List all RunBooks
- **POST** `/api/runbooks/` — Create new RunBook
- **GET** `/api/runbooks/{id}/` — Get RunBook details (canvas JSON)
- **PUT** `/api/runbooks/{id}/` — Save RunBook canvas
- **POST** `/api/runbooks/{id}/run/` — Execute RunBook manually
- **GET** `/api/runbooks/{id}/runs/` — List past executions
- **GET** `/api/runbooks/{id}/runs/{run_id}/` — Get run details
- **POST** `/api/runbooks/{id}/evaluate/` — Test with mock data
- **POST** `/api/runbooks/{id}/templates/` — Save as marketplace template

---

## Summary

The Admin Portal RunBook Builder provides a powerful, intuitive visual editor for creating reusable automation workflows. With support for triggers, multi-step orchestration, human checkpoints, and dozens of integrations, it enables platform engineers to design complex automation without code.

Key design principles:
- **Visual first** — canvas-based like n8n
- **Reusable** — designed once, triggered many times
- **Safe** — human checkpoints for critical decisions
- **Transparent** — full execution history and run details
- **Tested** — evaluation mode before going live

---

*Component library: shadcn/ui. Icons: Lucide React. Canvas library: ReactFlow (recommended).*
