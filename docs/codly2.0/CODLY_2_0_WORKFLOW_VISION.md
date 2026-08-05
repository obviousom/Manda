# Codly 2.0 — AI-Powered Workflow Platform
## Complete Vision, Architecture & Go-To-Market Document

> **Version**: 2.0 Draft  
> **Date**: April 2026  
> **Status**: Strategic Planning Document  

---

## Table of Contents

1. [The Big Picture — What We're Building](#1-the-big-picture)
2. [What Codly Already Has (Current State)](#2-current-state)
3. [The Two Workflow Types](#3-the-two-workflow-types)
4. [Process Workflows (Runbooks)](#4-process-workflows-runbooks)
5. [Dynamic AI Workflows (Planner Engine)](#5-dynamic-ai-workflows-planner-engine)
6. [How the Two Connect](#6-how-the-two-connect)
7. [Marketplace & Agent Catalog](#7-marketplace--agent-catalog)
8. [Inspired by n8n — What We Add](#8-inspired-by-n8n--what-we-add)
9. [How We Sell This](#9-how-we-sell-this)
10. [Data Model](#10-data-model)
11. [API Contracts](#11-api-contracts)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Key Differentiators vs. n8n, Zapier, etc.](#13-key-differentiators)

---

## 1. The Big Picture

**Codly 2.0 = AI-Orchestrated Cloud Operations Platform**

Where traditional tools (n8n, Zapier, Terraform) make you build pipelines manually, Codly 2.0 lets AI _plan, build, and execute_ those pipelines for you — with full awareness of your cloud infrastructure, compliance posture, tickets, and costs.

Think of it as:

> **"AWS Lambda triggers + Terraform workflows + AI agents + ITSM integration + CLI execution engine — in one platform"**

### The Core Shift

| Traditional Automation | Codly 2.0 |
|------------------------|-----------|
| User writes a pipeline | User describes intent, AI builds the pipeline |
| Static, brittle workflows | Self-healing, adaptive workflows |
| One job at a time (chat) | Multi-agent parallel execution |
| No cloud awareness | Deep cloud context (inventory, compliance, cost) |
| Separate tools (n8n + Terraform + Ansible) | One unified platform |

---

## 2. Current State

### 2.1 What We Already Have (Do Not Rebuild)

Codly already has a significant foundation that becomes the building blocks for 2.0:

#### Existing Agents (chatbot/)
| Agent | What It Does | Cloud Support |
|-------|-------------|---------------|
| **OS Management Agent** | SSH read-only inspection, patch status, CPU/disk/memory | AWS, Azure |
| **OS Hardening Agent** | Security configuration, CIS benchmarks, hardening policies | AWS, Azure |
| **Log Analytics Agent** | CloudTrail, VPC Flow Logs, ALB logs, CloudWatch | AWS, Azure, GCP |
| **DB Management Agent** | Secure DB queries, schema inspection, performance | AWS RDS, Azure |
| **FinOps Cost Agent** | Cost breakdown, anomaly detection, optimization tips | AWS, Azure, GCP |
| **Inventory Management Agent** | EC2/VM/S3 discovery, tagging, metadata | AWS, Azure |
| **Compliance Agent** | CIS/SOC2/PCI compliance scans, deviation tracking | AWS, Azure |

#### Existing AI Ops Architecture (ai_ops/ + chatbot/ai_ops/)
- `AIWorkflow` model — pre-defined agent configs in DB
- `WorkflowTrigger` model — manual/scheduled/event/webhook
- `WorkflowRun` model — full execution record, WebSocket streaming
- **SwarmAgents** framework — multi-agent handoff (Analyze → Supervisor → Param Collect → CLI Execute)
- **WorkerHandoffConfig / WorkerChainConfig** — chaining workers
- Agent Registry (`register_agent` decorator)
- Read-Only Supervisor Agent (uses OS + Log + FinOps workers in parallel)
- PII masking middleware for all LLM calls

#### Existing Ticket Management (ticket_management/)
- Integrations: **Freshservice**, **Jira**, **Zendesk**, **ManageEngine**
- Auto-monitoring triggers from ticket keywords
- AI workers chained to ticket context
- Ticket → AI Ops parameter collection chain

#### Existing Workers in Ticket Management
| Worker | What It Does |
|--------|-------------|
| `ai_ops.py` | AI Ops parameter collection from ticket context |
| `os_management.py` | OS monitoring for ticket-triggered checks |
| `cloudtrail_log_analytics.py` | Log investigation for incidents |
| `cost_optimization.py` | Cost impact analysis for service requests |
| `finops_cost.py` | FinOps data for ticket context |
| `finops_waste.py` | Waste identification linked to tickets |
| `db_management.py` | DB diagnostics for DB-related tickets |

---

## 3. The Two Workflow Types

This is the **core architectural idea** of Codly 2.0. There are **two fundamentally different types of workflows**, and they work together.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CODLY 2.0 WORKFLOW SYSTEM                     │
│                                                                       │
│   ┌──────────────────────────┐    ┌──────────────────────────────┐  │
│   │   TYPE 1: PROCESS        │    │   TYPE 2: DYNAMIC AI         │  │
│   │   WORKFLOW               │    │   WORKFLOW                   │  │
│   │   (Pre-defined Runbook)  │    │   (Planner-Generated)        │  │
│   │                          │    │                              │  │
│   │  • Configured in advance │    │  • Generated at runtime      │  │
│   │  • Always runs same way  │    │  • AI plans the steps        │  │
│   │  • Event-triggered       │    │  • User describes intent     │  │
│   │  • Consistent & audited  │    │  • Flexible & dynamic        │  │
│   └──────────┬───────────────┘    └──────────────┬───────────────┘  │
│              │                                   │                   │
│              │           CAN TRIGGER EACH OTHER  │                   │
│              └────────────────┬──────────────────┘                   │
│                               │                                      │
│                               ▼                                      │
│                    EXECUTION ENGINE (Workers + CLI)                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Process Workflows (Runbooks)

### 4.1 What Is a Process Workflow?

A **Process Workflow** is a **pre-configured, deterministic sequence of operations** that runs automatically every time a specific trigger fires.

- Defined by admins/engineers upfront
- Contains fixed steps in a fixed order
- Can have conditional branching (if/else based on results)
- Runs identically every single time
- Fully auditable — every execution is logged

**Analogy**: Think of it like a standard operating procedure (SOP) document — converted into an automated agent chain.

### 4.2 Real-World Use Cases

#### Use Case 1: EC2 Instance Post-Deployment Runbook
```
TRIGGER: EC2 instance created (CloudTrail event: RunInstances)
         ↓
STEP 1:  Wait for instance to be in "running" state
         ↓
STEP 2:  Compliance Agent — Scan EC2 for CIS baseline compliance
         ↓
STEP 3:  OS Management Agent — Apply latest OS patches
         ↓
STEP 4:  OS Hardening Agent — Run hardening playbook (CIS Level 1)
         ↓
STEP 5:  OS Management Agent — Install antivirus (CrowdStrike/Defender)
         ↓
STEP 6:  OS Management Agent — Install monitoring agent (CloudWatch/Datadog)
         ↓
STEP 7:  OS Management Agent — Install SIEM agent (Splunk/Elastic)
         ↓
STEP 8:  Notification — Slack/Email with full run report
         ↓
STEP 9:  Ticket — Auto-create success ticket in Jira/Freshservice
```

#### Use Case 2: Security Group Open Port Alert
```
TRIGGER: CloudTrail event — security group rule added with 0.0.0.0/0
         ↓
STEP 1:  Log Analytics Agent — Pull all recent API calls related to this SG
         ↓
STEP 2:  Compliance Agent — Check if this violates any policies
         ↓
STEP 3:  [IF VIOLATION] → Notify SOC team via PagerDuty/Slack
STEP 3:  [IF CRITICAL] → Auto-remediate — Remove the open rule via CLI
         ↓
STEP 4:  Ticket — Auto-create P1 Incident in ITSM
         ↓
STEP 5:  Audit log saved with full evidence
```

#### Use Case 3: Incident Ticket Raised (ITSM-Triggered)
```
TRIGGER: New ticket created in Freshservice/Jira with keyword "server down"
         ↓
STEP 1:  Ticket Worker — Parse ticket for server info (instance ID, region)
         ↓
STEP 2:  OS Management Agent — Check server health (CPU, disk, memory, services)
         ↓
STEP 3:  Log Analytics Agent — Check CloudTrail/CloudWatch for errors (last 2 hours)
         ↓
STEP 4:  [IF ROOT CAUSE FOUND] → Update ticket with diagnosis + fix recommendation
STEP 4:  [IF NOT FOUND] → Escalate with collected diagnostics to L2 team
         ↓
STEP 5:  Notification — Summary to ticket assignee via Slack
```

#### Use Case 4: Cost Anomaly Detected
```
TRIGGER: Scheduled — Daily at 09:00 IST (like the n8n AWS Cost Optimization Agent)
         ↓
STEP 1:  FinOps Agent — Scan all accounts for cost spikes (>20% day-over-day)
         ↓
STEP 2:  [FOR EACH ANOMALY] → Inventory Agent — Identify the resource
         ↓
STEP 3:  Log Analytics Agent — Check if usage spike is legitimate
         ↓
STEP 4:  [IF WASTE] → Generate rightsizing recommendation
         ↓
STEP 5:  Report — Send daily cost digest to finance/DevOps Slack channel
         ↓
STEP 6:  Ticket — Create cost optimization ticket if savings > $500/month
```

#### Use Case 5: Nightly Security & Compliance Sweep
```
TRIGGER: Scheduled — Every night at 02:00 AM
         ↓
STEP 1:  Inventory Agent — List all EC2/VMs across all accounts
         ↓
STEP 2:  [PARALLEL] Compliance Agent — Run compliance scans for all resources
STEP 2:  [PARALLEL] OS Management Agent — Check patch status for all servers
         ↓
STEP 3:  Summarize — Count violations, unpatched servers
         ↓
STEP 4:  [IF NEW VIOLATIONS] → Create tickets for each violation
         ↓
STEP 5:  Weekly report email to CISO/IT Manager
```

### 4.3 Process Workflow Architecture

```
ProcessWorkflow
├── id
├── name (e.g., "EC2 Post-Deployment Runbook")
├── description
├── customer / account
├── is_active
├── triggers[]            ← what fires this workflow
│   ├── SCHEDULED (cron)
│   ├── EVENT (CloudTrail event name)
│   ├── TICKET (ITSM keyword match)
│   ├── ALERT (monitoring alert)
│   └── MANUAL
├── steps[]               ← the ordered sequence
│   ├── step_order (1, 2, 3...)
│   ├── agent_key ("compliance_agent", "os_management_agent"...)
│   ├── worker_key (optional sub-worker)
│   ├── config {}         ← agent-specific params
│   ├── condition {}      ← run if prev_result matches
│   └── on_failure: (continue | stop | alert)
├── notification_config{}  ← Slack/email/PagerDuty on complete/fail
└── timeout_minutes
```

### 4.4 Supported Triggers for Process Workflows

| Trigger Type | Example | How We Detect |
|-------------|---------|--------------|
| **CloudTrail Event** | `RunInstances`, `AuthorizeSecurityGroupIngress` | CloudWatch Events / EventBridge |
| **Scheduled (Cron)** | Every night at 2AM | Celery Beat |
| **Ticket Created** | New P1 Incident in Freshservice | Ticket monitoring webhook |
| **Metric Threshold** | CPU > 90% for 5 mins | CloudWatch Alarm → webhook |
| **Cost Anomaly** | Daily spend > $X | FinOps agent scheduled check |
| **Manual** | User clicks "Run" in UI | REST API call |
| **Webhook** | External system push | `POST /api/workflows/{id}/trigger/` |
| **Change Request** | ITSM change approved | Freshservice/Jira webhook |

---

## 5. Dynamic AI Workflows (Planner Engine)

### 5.1 What Is a Dynamic Workflow?

A **Dynamic AI Workflow** is created **on the fly** by a Planner Agent based on the user's natural language description. The user doesn't design steps — the AI does.

- User describes what they want in plain English
- The **Planner Agent** breaks this into a multi-step plan
- Each step becomes a real agent/worker execution
- Can chain dozens of operations that interact with live cloud infra
- After completion, can **trigger a linked Process Workflow**

**Analogy**: Think of it like talking to a senior DevOps engineer who can simultaneously plan AND execute everything you describe.

### 5.2 The Planner Agent — How It Works

```
USER INPUT:
"Create an EC2 t3.medium in us-east-1, open port 443 on a new
security group, install Python 3.11 and nginx, then verify
the server is reachable"

                    ↓

PLANNER AGENT:
{
  "plan": [
    {
      "step": 1,
      "action": "Collect parameters for EC2 creation",
      "agent": "param_collection_agent",
      "needs_confirmation": true
    },
    {
      "step": 2,
      "action": "Create EC2 instance via AWS CLI",
      "agent": "cli_execution_agent",
      "command": "aws ec2 run-instances --image-id ami-xxx..."
    },
    {
      "step": 3,
      "action": "Create security group and allow port 443",
      "agent": "cli_execution_agent",
      "depends_on": [2]
    },
    {
      "step": 4,
      "action": "Install Python 3.11 via SSM Run Command",
      "agent": "os_management_agent",
      "depends_on": [2, 3]
    },
    {
      "step": 5,
      "action": "Install nginx via SSM Run Command",
      "agent": "os_management_agent",
      "depends_on": [4]
    },
    {
      "step": 6,
      "action": "Verify HTTP connectivity to new instance",
      "agent": "network_validation_agent",
      "depends_on": [5]
    }
  ],
  "estimated_duration": "8 minutes",
  "requires_permission": "operator",
  "post_workflow": "ec2_post_deployment_runbook"  ← triggers Process Workflow
}

USER REVIEWS PLAN → APPROVES → EXECUTION BEGINS
```

### 5.3 Human-in-the-Loop (HITL)

The Dynamic Workflow supports **human checkpoints** at critical steps:

```
PLANNER → "I'm about to delete 3 EC2 instances. Here's what I found:
           - i-0abc: stopped for 45 days, no traffic
           - i-0def: dev instance, no production traffic
           - i-0ghi: tagged 'temporary', 60 days old
           
           Total savings: $340/month
           
           Approve deletion? [Yes to all | Yes to selected | Cancel]"

USER: "Yes to i-0abc and i-0def only"

PLANNER → Executes deletion of selected instances only
         → Updates plan and continues remaining steps
```

### 5.4 Dynamic Workflow Execution Flow

```
┌──────────────────────────────────────────────────────────────┐
│                   DYNAMIC WORKFLOW ENGINE                      │
│                                                              │
│  User Input                                                  │
│      ↓                                                       │
│  ┌─────────────────────────────┐                            │
│  │      PLANNER AGENT          │  ← High-category LLM       │
│  │  (Goal decomposition)       │    (complex reasoning)     │
│  │  • Breaks goal into steps   │                            │
│  │  • Estimates dependencies   │                            │
│  │  • Identifies required      │                            │
│  │    agents/workers           │                            │
│  │  • Sets permission level    │                            │
│  │  • Detects post-workflow    │                            │
│  └──────────────┬──────────────┘                            │
│                 ↓                                            │
│  ┌─────────────────────────────┐                            │
│  │   PLAN REVIEW (UI)          │  ← User sees the plan      │
│  │  • Show step-by-step plan   │    before execution        │
│  │  • Show estimated time      │                            │
│  │  • Show permission required │                            │
│  │  • Approve / Modify / Cancel│                            │
│  └──────────────┬──────────────┘                            │
│                 ↓                                            │
│  ┌─────────────────────────────┐                            │
│  │   EXECUTION ORCHESTRATOR    │                            │
│  │  • Runs steps in order      │                            │
│  │  • Handles parallelism      │                            │
│  │  • WebSocket streaming      │                            │
│  │  • HITL interruptions       │                            │
│  │  • Error recovery           │                            │
│  └──────────────┬──────────────┘                            │
│                 ↓                                            │
│  ┌─────────────────────────────┐                            │
│  │  POST-EXECUTION              │                            │
│  │  • Generate summary report  │                            │
│  │  • Trigger Process Workflow │  ← Key connection!         │
│  │  • Create ticket if needed  │                            │
│  │  • Save as new template     │                            │
│  └─────────────────────────────┘                            │
└──────────────────────────────────────────────────────────────┘
```

### 5.5 Example Dynamic Workflow Interactions

**Example 1 — Infrastructure Provisioning**
> "I need a 3-tier architecture for our new app: load balancer, 2 web servers (t3.medium), and an RDS MySQL db.small. All in us-east-1, in a new VPC."

Planner creates: VPC → Subnets → Security Groups → RDS → EC2 x2 → ALB → Route53

**Example 2 — Incident Investigation**
> "Our production server i-0abc123 is slow. Find out why and fix it if safe to do so."

Planner creates: Check CPU/memory → CloudTrail logs → Application logs → Root cause analysis → [If safe] Apply fix → Verify → Update ticket

**Example 3 — Cost Reduction**
> "We're spending too much on dev environment. Identify what can be stopped/deleted without breaking anything."

Planner creates: Inventory scan → Check last-used dates → Check CloudWatch metrics → Check tags → Generate list with confidence scores → HITL review → Execute approved actions

**Example 4 — Compliance Remediation**
> "Our last compliance scan had 47 failures. Fix all the CIS Level 1 ones that are auto-fixable."

Planner creates: Get compliance failures → Filter L1 auto-fixable → Group by resource → Apply fixes in batches → Re-scan → Generate remediation report

---

## 6. How the Two Connect

This is the **magic** of Codly 2.0: the two workflow types work together seamlessly.

### 6.1 Dynamic Workflow Triggers Process Workflow

When a Dynamic Workflow creates or modifies infrastructure, it can **automatically trigger** the appropriate Process Workflow:

```
DYNAMIC WORKFLOW: "Create EC2 for our new microservice"
  ↓
  Step 1: Collect parameters          ✓ Done
  Step 2: Create EC2 instance         ✓ Done → instance: i-0newABC
  Step 3: Verify connectivity         ✓ Done
  
  DYNAMIC WORKFLOW COMPLETE
  ↓
  [POST-EXECUTION TRIGGER]
  → Detected: new EC2 created
  → Looking for linked Process Workflow...
  → Found: "EC2 Post-Deployment Runbook"
  → Triggering with context: {instance_id: "i-0newABC", region: "us-east-1"}
  ↓
PROCESS WORKFLOW STARTS AUTOMATICALLY:
  Step 1: Compliance scan             ← runs automatically
  Step 2: OS patching                 ← runs automatically
  Step 3: Hardening                   ← runs automatically
  Step 4: Install monitoring agents   ← runs automatically
  ...
```

### 6.2 Process Workflow Triggers Dynamic Workflow

A Process Workflow can spawn a Dynamic Workflow when it encounters something unexpected:

```
PROCESS WORKFLOW: "Nightly Compliance Sweep"
  Step 3: [23 CRITICAL VIOLATIONS FOUND]
  ↓
  → This exceeds threshold (>10 critical)
  → Spawning Dynamic Workflow for investigation...
  
DYNAMIC WORKFLOW (spawned):
  Planner: "I found 23 critical violations. Let me analyze root cause..."
  → Groups violations by pattern
  → Identifies 18 are same missing patch
  → Generates batch fix plan
  → HITL: "18 violations can be fixed by applying patch X. Approve?"
  → User approves → Executes
  → Reports back to parent Process Workflow
  
PROCESS WORKFLOW: Continues with updated violation count: 5 remaining
```

### 6.3 Connection via Trigger Config

In the data model, a `ProcessWorkflow` can be linked to specific events:

```python
# Process Workflow config example
{
  "name": "EC2 Post-Deployment Runbook",
  "triggers": [
    {
      "type": "event",
      "event_source": "cloudtrail",
      "event_name": "RunInstances"
    },
    {
      "type": "codly_internal",
      "source": "dynamic_workflow_completion",
      "resource_type": "ec2_instance",
      "action": "created"
    }
  ]
}
```

---

## 7. Marketplace & Agent Catalog

### 7.1 What the Marketplace Is

The **Marketplace** is where customers discover, install, and use:
- **Pre-built Process Workflow Templates** (runbooks)
- **Pre-built Dynamic Workflow Recipes** (intent templates)
- **Third-Party Integration Agents** (Splunk, Nessus, Grafana, etc.)
- **Community-contributed workflows**

### 7.2 What We Already Sell Today (Package as Products)

Everything in Codly today can be productized and sold as Marketplace items:

#### Tier 1: Built-in Agents (Included with Codly Platform)
| Agent/Feature | Value Proposition |
|--------------|-------------------|
| **OS Management Agent** | "No more SSH-ing into 200 servers. Ask in plain English." |
| **Log Analytics Agent** | "CloudTrail investigation in seconds, not hours" |
| **Compliance Agent** | "CIS/SOC2/PCI compliance in one click" |
| **FinOps Agent** | "Find cloud waste before your CFO does" |
| **Inventory Agent** | "Always-current map of your entire cloud footprint" |
| **OS Hardening Agent** | "Automated CIS hardening — no Ansible playbooks needed" |
| **DB Management Agent** | "Safe DB access without giving developers production creds" |
| **Ticket Management** | "ITSM integration — tickets automatically investigated" |

#### Tier 2: Process Workflow Templates (Marketplace Items)
| Template | Category | Price Model |
|---------|----------|-------------|
| EC2 Post-Deployment Runbook | Security | Included Pro |
| Nightly Compliance Sweep | Compliance | Included Pro |
| Incident Auto-Triage | ITSM | Included Pro |
| Security Group Violation Response | Security | Included Enterprise |
| Cost Anomaly Weekly Digest | FinOps | Included Pro |
| RDS Backup Verification | Database | Included Pro |
| AWS Account Onboarding | Setup | Free |
| Multi-Account Cost Consolidation | FinOps | Enterprise |
| SOC2 Evidence Collection | Compliance | Enterprise |

#### Tier 3: Integration Agents (Marketplace Premium)
| Integration | What It Does | Pricing |
|------------|-------------|---------|
| **GitHub Integration Agent** | Trigger workflows from GitHub Actions/PRs | Partner |
| **Splunk Log Agent** | Pull Splunk searches into Codly workflows | Partner |
| **Nessus Security Scan Agent** | Run Nessus scans, parse results, create tickets | Partner |
| **Grafana Monitoring Agent** | Use Grafana alerts as workflow triggers | Partner |
| **Datadog Agent** | Ingest Datadog events and metrics | Partner |
| **PagerDuty Agent** | Two-way sync with PagerDuty incidents | Partner |
| **Terraform Agent** | Read/plan Terraform state files | Built by Codly |
| **Ansible Agent** | Generate and run Ansible playbooks | Built by Codly |
| **Kubernetes Agent** | K8s cluster inspection and management | Built by Codly |
| **ArgoCD Agent** | GitOps deployment tracking | Partner |

### 7.3 Marketplace Architecture

```
MARKETPLACE
├── Templates (Process Workflows)
│   ├── Official (built by Codly team)
│   ├── Partner (verified third-party)
│   └── Community (user-submitted, reviewed)
│
├── Integration Agents
│   ├── Official integrations (AWS, Azure, GCP — free)
│   ├── Partner integrations (Splunk, Nessus — paid/subscription)
│   └── Custom (user builds their own)
│
└── Dynamic Workflow Recipes
    ├── "Quick Infrastructure Setup" prompts
    ├── "Security Investigation" prompt packs
    └── "Cost Optimization" prompt packs
```

### 7.4 How Customers Use the Marketplace

1. Browse templates by category (Security, FinOps, Compliance, ITSM)
2. Preview what the workflow does (step-by-step view)
3. One-click install into their workspace
4. Configure triggers and parameters
5. Schedule or activate immediately

---

## 8. Inspired by n8n — What We Add

n8n has 9,447 workflow templates and 400+ integrations across: AI, IT Ops, Sales, Marketing, Support, Document Ops. Here's what we should adopt:

### 8.1 Node Types to Add (inspired by n8n)

#### Flow Control Nodes (n8n has: Branch, Merge, Loop, Split, Wait)
Codly needs these in Process Workflows:

| Node Type | Description | Codly 2.0 Use Case |
|-----------|-------------|-------------------|
| **IF/Else Branch** | Split workflow based on condition | If compliance_score < 70: alert else continue |
| **Merge** | Wait for parallel branches to complete | Wait for all security checks before proceeding |
| **Loop** | Iterate over a list | For each EC2 instance: run patch check |
| **Wait** | Pause for N minutes/hours | Wait 5 min after EC2 launch before checking |
| **Set Variable** | Store intermediate result | Save instance_id for use in later steps |
| **Error Handler** | Catch step failures | If patching fails: notify + continue to next |

#### Data Transformation Nodes
| Node Type | Description |
|-----------|-------------|
| **Filter** | Remove items from list based on condition |
| **Aggregate** | Sum costs, count violations, group by tag |
| **Transform** | Map one data structure to another |
| **Deduplicate** | Remove duplicate resources from scan |

#### Notification Nodes (n8n has 30+ communication integrations)
| Integration | Use Case |
|------------|---------|
| **Slack** | Send workflow results, alerts, daily digests |
| **Microsoft Teams** | Enterprise notifications |
| **Email (SMTP/SES)** | Compliance reports, cost digests |
| **PagerDuty** | P1 incident escalation |
| **Telegram** | Developer alerts |
| **SMS (Twilio)** | Critical alert escalation |
| **Webhook** | Send results to any external system |

#### Human Review Node (n8n feature — critical for cloud ops)
- Pause workflow and send approval request to Slack/Teams
- Workflow resumes only after human approves
- With timeout: auto-reject or auto-approve after N hours
- Required for destructive actions (delete, stop, modify)

#### Action in External App Nodes
| Integration | What We Enable |
|------------|----------------|
| **Jira** | Create/update issues from workflow results |
| **Freshservice** | Auto-create, update, resolve incidents |
| **ServiceNow** | ITSM integration for enterprise |
| **Confluence** | Auto-generate runbook documentation |
| **Notion** | Push reports to Notion pages |
| **Google Sheets** | Export cost/compliance data |

### 8.2 Triggers to Add (inspired by n8n trigger types)

| Trigger | Description |
|---------|-------------|
| **Webhook** | External POST to `POST /api/workflows/{id}/trigger/` |
| **Polling** | Check external API every N minutes |
| **File Change** | S3 object created/deleted |
| **Database Change** | RDS record updated (CDC) |
| **Email Received** | Process email content (e.g., vendor alerts) |
| **Form Submit** | User fills a Codly form to kick off a workflow |
| **API Response** | Wait for external API to return a value |

### 8.3 Workflow Editor UI (inspired by n8n canvas)

What we build for the Process Workflow designer:

```
┌─────────────────────────────────────────────────────────────┐
│  CODLY WORKFLOW EDITOR                          [Run] [Save] │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  [TRIGGER]──→[COMPLIANCE SCAN]──→[IF: violations > 0]        │
│                                         │                    │
│                                  ┌──── YES ────┐             │
│                                  ↓              ↓            │
│                          [NOTIFY SLACK]  [CREATE TICKET]     │
│                                  ↓              ↓            │
│                                  └──────┬───────┘            │
│                                         ↓                    │
│                                 [OS PATCHING]                │
│                                         ↓                    │
│                                 [SEND REPORT]                │
│                                                               │
│  [+ Add Step]  [← Back]  [⚙ Configure]  [▶ Test Run]        │
└─────────────────────────────────────────────────────────────┘
```

### 8.4 Execution History & Observability (n8n has Executions tab)

Codly 2.0 needs:
- Per-run execution log (every step, every output)
- Step-level success/failure indicators
- Retry failed steps individually
- Download run report as PDF
- Compare two runs side-by-side
- Search runs by resource ID, trigger type, date

### 8.5 Workflow Versioning (n8n has Version History)

- Every workflow change creates a new version
- Can rollback to any previous version
- Diff view between versions
- "Deployed" vs "Draft" versions

### 8.6 Evaluations / Testing (n8n has Evaluations tab)

- Test a workflow with mock data without running real agents
- Define expected outputs and assert them
- Run evaluation suite before publishing workflow
- Track evaluation results over time

---

## 9. How We Sell This

### 9.1 The Core Pitch

> "Codly is the only platform where you can describe what you want in plain English and AI will plan it, execute it on your cloud, and document it — automatically."

### 9.2 Pricing Tiers

| Tier | Target | Price | What's Included |
|------|--------|-------|----------------|
| **Starter** | Small teams (< 10 users) | $299/month | 5 accounts, basic agents, 100 workflow runs/month |
| **Professional** | Mid-market DevOps teams | $999/month | 20 accounts, all agents, 1000 runs/month, Marketplace templates |
| **Enterprise** | Large enterprises | Custom | Unlimited accounts, custom agents, SLA, SSO, audit log |
| **Marketplace** | Any tier | Per-workflow | Premium templates and partner integrations |

### 9.3 Sales Motion — What to Highlight

#### Pain Point 1: "Our team wastes hours on repetitive tasks"
- **Our solution**: Process Workflows automate the same things every time
- **Demo**: Show EC2 post-deployment runbook running in 8 minutes what took the team 45 minutes

#### Pain Point 2: "We can't keep up with compliance"
- **Our solution**: Nightly compliance sweeps with auto-remediation
- **Demo**: Show compliance score going from 67% → 94% in one automated run

#### Pain Point 3: "Our devs keep creating security risks"
- **Our solution**: Security Group Violation Response runs automatically
- **Demo**: Open port → Slack alert in 2 minutes, ticket created, violation documented

#### Pain Point 4: "We spend too much on cloud"
- **Our solution**: Dynamic workflow: "Find cloud waste and help me fix it"
- **Demo**: Show planner identifying $3,200/month of waste in 90 seconds

#### Pain Point 5: "Our ITSM tickets sit unresolved for hours"
- **Our solution**: Ticket → AI investigation → diagnosis → auto-update in minutes
- **Demo**: Create P1 ticket → show Codly auto-investigating and updating it

### 9.4 Competitive Positioning

| Platform | What They Do | Why Codly Wins |
|---------|-------------|----------------|
| **n8n / Zapier** | Generic workflow automation | No cloud intelligence, no AI reasoning, no CLI execution |
| **ServiceNow** | ITSM automation | Expensive, no AI, not cloud-native |
| **AWS Systems Manager** | AWS-only automation | Single cloud, no AI, no ITSM |
| **Ansible Tower** | Infrastructure automation | Code-first, no AI, steep learning curve |
| **Terraform** | Infrastructure-as-code | No AI, no reactive workflows, no ITSM |
| **Codly 2.0** | AI-Orchestrated Cloud Ops | AI plans + executes + integrates ITSM + cost + compliance |

### 9.5 Land-and-Expand Strategy

```
Week 1: "Try the AI chat" (existing chatbot)
   ↓ User loves it
Week 2: "Let's automate that daily task you just did" → Process Workflow
   ↓ Saves 2 hours/week
Week 4: "Here are 5 more runbooks from our marketplace"
   ↓ Team adopts multiple workflows
Month 2: "Your colleague in the security team wants this too" → Team license
   ↓ Expand to more teams
Month 4: "Let's connect your Jira and Splunk" → Partner integrations
   ↓ Deep integration = hard to replace
Month 6: "Let's add your other AWS accounts" → Enterprise upgrade
```

---

## 10. Data Model

### 10.1 Process Workflow Models

```python
class ProcessWorkflow(models.Model):
    """Pre-configured, deterministic automation runbook."""
    PERMISSION_CHOICES = [("read_only", "Read Only"), ("operator", "Operator"), ("power_user", "Power User")]
    SOURCE_CHOICES = [("custom", "Custom"), ("marketplace", "Marketplace"), ("community", "Community")]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    permission_level = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default="read_only")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="custom")
    marketplace_template_id = models.CharField(max_length=100, blank=True)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_draft = models.BooleanField(default=False)
    tags = models.JSONField(default=list)
    notification_config = models.JSONField(default=dict)  # Slack/email/PagerDuty config
    timeout_minutes = models.IntegerField(default=60)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProcessWorkflowTrigger(models.Model):
    """What fires the workflow."""
    TRIGGER_TYPE_CHOICES = [
        ("scheduled", "Scheduled (Cron)"),
        ("cloudtrail_event", "CloudTrail Event"),
        ("ticket_created", "Ticket Created"),
        ("ticket_updated", "Ticket Updated"),
        ("metric_threshold", "Metric Threshold"),
        ("cost_anomaly", "Cost Anomaly"),
        ("s3_event", "S3 Object Event"),
        ("manual", "Manual"),
        ("webhook", "External Webhook"),
        ("dynamic_workflow_completion", "Dynamic Workflow Completion"),
        ("change_request_approval", "Change Request Approved"),
    ]

    workflow = models.ForeignKey(ProcessWorkflow, on_delete=models.CASCADE, related_name="triggers")
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_TYPE_CHOICES)
    config = models.JSONField(default=dict)
    # For cloudtrail: {"event_name": "RunInstances", "resource_type": "ec2"}
    # For scheduled: {"cron": "0 2 * * *", "timezone": "Asia/Kolkata"}
    # For ticket: {"provider": "freshservice", "keywords": ["server down", "cpu high"]}
    # For webhook: {"secret": "...", "source_ip_allowlist": [...]}
    is_active = models.BooleanField(default=True)


class ProcessWorkflowStep(models.Model):
    """One step in the workflow."""
    AGENT_CHOICES = [
        ("compliance_agent", "Compliance Agent"),
        ("os_management_agent", "OS Management Agent"),
        ("os_hardening_agent", "OS Hardening Agent"),
        ("log_analytics_agent", "Log Analytics Agent"),
        ("finops_agent", "FinOps Agent"),
        ("inventory_agent", "Inventory Agent"),
        ("ticket_agent", "Ticket Management Agent"),
        ("db_management_agent", "DB Management Agent"),
        ("cli_execution_agent", "CLI Execution Agent"),
        ("notification_node", "Send Notification"),
        ("human_review_node", "Human Review"),
        ("if_else_node", "IF/Else Branch"),
        ("wait_node", "Wait / Delay"),
        ("loop_node", "Loop Over List"),
        ("merge_node", "Merge Branches"),
        ("transform_node", "Transform Data"),
        ("webhook_node", "Call External Webhook"),
    ]
    ON_FAILURE_CHOICES = [("continue", "Continue"), ("stop", "Stop Workflow"), ("alert", "Alert and Continue")]

    workflow = models.ForeignKey(ProcessWorkflow, on_delete=models.CASCADE, related_name="steps")
    step_order = models.IntegerField()
    agent_key = models.CharField(max_length=100, choices=AGENT_CHOICES)
    name = models.CharField(max_length=255)
    config = models.JSONField(default=dict)
    # Agent-specific config. For cli_execution_agent: {"command_template": "aws ec2 ..."}
    # For notification_node: {"channel": "slack", "channel_id": "C01ABC"}
    # For if_else_node: {"condition_field": "compliance_score", "operator": "<", "value": 70}
    condition = models.JSONField(default=dict)  # Run only if parent step output matches
    on_failure = models.CharField(max_length=20, choices=ON_FAILURE_CHOICES, default="stop")
    timeout_seconds = models.IntegerField(default=300)
    requires_human_approval = models.BooleanField(default=False)


class ProcessWorkflowRun(models.Model):
    """Execution record for a process workflow run."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("awaiting_approval", "Awaiting Human Approval"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    workflow = models.ForeignKey(ProcessWorkflow, on_delete=models.CASCADE, related_name="runs")
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    triggered_by = models.JSONField(default=dict)  # {"type": "cloudtrail", "event": "RunInstances", "resource": "i-0abc"}
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    current_step = models.IntegerField(default=0)
    context = models.JSONField(default=dict)  # Shared data passed between steps
    result = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ProcessWorkflowStepRun(models.Model):
    """Execution record for one step in a run."""
    run = models.ForeignKey(ProcessWorkflowRun, on_delete=models.CASCADE, related_name="step_runs")
    step = models.ForeignKey(ProcessWorkflowStep, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default="pending")
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    agent_messages = models.JSONField(default=list)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

### 10.2 Dynamic Workflow Models

```python
class DynamicWorkflow(models.Model):
    """An AI-planned workflow generated at runtime from user intent."""
    STATUS_CHOICES = [
        ("planning", "Planner Running"),
        ("plan_ready", "Plan Ready for Review"),
        ("approved", "Approved by User"),
        ("executing", "Executing"),
        ("awaiting_hitl", "Awaiting Human Input"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    user_intent = models.TextField()  # The original user prompt
    generated_plan = models.JSONField(default=list)  # Steps generated by planner
    approved_plan = models.JSONField(default=list)   # Plan after user modifications
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="planning")
    current_step = models.IntegerField(default=0)
    shared_context = models.JSONField(default=dict)  # Resources created/found during execution
    result = models.JSONField(default=dict)
    post_process_workflow = models.ForeignKey(
        ProcessWorkflow, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Process Workflow to trigger after completion"
    )
    save_as_template = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 10.3 Marketplace Models

```python
class MarketplaceTemplate(models.Model):
    """A shareable Process Workflow or Dynamic Workflow recipe in the marketplace."""
    CATEGORY_CHOICES = [
        ("security", "Security"), ("compliance", "Compliance"), ("finops", "FinOps"),
        ("itsm", "ITSM"), ("database", "Database"), ("deployment", "Deployment"),
        ("monitoring", "Monitoring"), ("other", "Other"),
    ]
    TYPE_CHOICES = [("process_workflow", "Process Workflow"), ("dynamic_recipe", "Dynamic Recipe")]

    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    template_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    author = models.CharField(max_length=100)  # "Codly", "Community", partner name
    is_official = models.BooleanField(default=False)
    is_partner = models.BooleanField(default=False)
    is_free = models.BooleanField(default=True)
    workflow_definition = models.JSONField()  # Serialized workflow steps & triggers
    supported_cloud_providers = models.JSONField(default=list)  # ["AWS", "AZURE", "GCP"]
    required_integrations = models.JSONField(default=list)  # ["jira", "slack"]
    install_count = models.IntegerField(default=0)
    rating = models.FloatField(default=0.0)
    tags = models.JSONField(default=list)
    version = models.CharField(max_length=20, default="1.0.0")
    changelog = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

---

## 11. API Contracts

### 11.1 Process Workflow APIs

```
# List all workflows for customer
GET /api/process-workflows/
Response: [{ id, name, trigger_count, last_run, status, step_count }]

# Create a workflow
POST /api/process-workflows/
Body: { name, description, permission_level, triggers[], steps[] }

# Get workflow details
GET /api/process-workflows/{id}/

# Update workflow
PATCH /api/process-workflows/{id}/

# Manually trigger a workflow
POST /api/process-workflows/{id}/trigger/
Body: { account_id, context: { instance_id, region, ... } }
Response: { run_id, session_id, websocket_channel }

# Get run history
GET /api/process-workflows/{id}/runs/
Response: [{ run_id, status, triggered_by, started_at, completed_at, duration_seconds }]

# Get run details (all steps)
GET /api/process-workflows/runs/{run_id}/
Response: { run, step_runs: [{ step_name, status, output, duration }] }

# Approve human review step
POST /api/process-workflows/runs/{run_id}/steps/{step_id}/approve/
Body: { decision: "approve" | "reject", notes }

# Cancel a running workflow
POST /api/process-workflows/runs/{run_id}/cancel/
```

### 11.2 Dynamic Workflow APIs

```
# Start planning from user intent
POST /api/dynamic-workflows/
Body: { account_id, user_intent, permission_level }
Response: { session_id, status: "planning", websocket_channel }
# WebSocket streams planning steps in real-time

# Get the generated plan (after planning completes)
GET /api/dynamic-workflows/{session_id}/plan/
Response: { plan: [{ step, action, agent, estimated_duration, requires_approval }], total_steps, estimated_minutes }

# Approve / modify plan
POST /api/dynamic-workflows/{session_id}/approve/
Body: { approved_steps: [1,2,3,4,5], skip_steps: [6], post_process_workflow_id: null }

# Cancel plan
POST /api/dynamic-workflows/{session_id}/cancel/

# HITL response (during execution)
POST /api/dynamic-workflows/{session_id}/respond/
Body: { selected_options: [...], user_message: "..." }

# Get execution status
GET /api/dynamic-workflows/{session_id}/status/
Response: { status, current_step, completed_steps, shared_context, result }
```

### 11.3 Marketplace APIs

```
# Browse marketplace
GET /api/marketplace/templates/
Query: ?category=security&cloud=AWS&type=process_workflow&search=compliance

# Get template details
GET /api/marketplace/templates/{id}/

# Install a template
POST /api/marketplace/templates/{id}/install/
Body: { account_id, configure: { trigger_config, notification_config } }
Response: { process_workflow_id, configured: true }

# Submit to marketplace (community)
POST /api/marketplace/submit/
Body: { process_workflow_id, is_public, tags, description }
```

---

## 12. Implementation Roadmap

### Phase 1 — Process Workflows MVP (Weeks 1-6)

**Goal**: Ship pre-configured runbooks with simple linear execution

- [ ] `ProcessWorkflow` + `ProcessWorkflowStep` + `ProcessWorkflowRun` models
- [ ] Manual trigger (REST API + UI button)
- [ ] Scheduled trigger (Celery Beat integration)
- [ ] Linear step execution (existing agents as steps)
- [ ] WebSocket streaming per step
- [ ] Basic notification node (Slack/email)
- [ ] Run history UI
- [ ] 3 built-in templates: EC2 Runbook, Compliance Sweep, Cost Digest
- [ ] Human review checkpoint (approve/reject via UI)

### Phase 2 — Workflow Editor + Triggers (Weeks 7-12)

**Goal**: Visual workflow editor + event-based triggers

- [ ] CloudTrail event trigger (via EventBridge/SQS)
- [ ] Ticket-based trigger (ITSM webhook)
- [ ] IF/Else branch node
- [ ] Loop node (iterate over resource list)
- [ ] Wait/delay node
- [ ] Transform data node
- [ ] Visual workflow editor (canvas UI similar to n8n)
- [ ] Workflow versioning
- [ ] Marketplace v1 (Codly official templates only)
- [ ] 10 official templates published

### Phase 3 — Dynamic Workflows / Planner (Weeks 13-20)

**Goal**: AI-generated workflows from user intent

- [ ] Planner Agent (high-category LLM, complex reasoning)
- [ ] Plan generation + display UI
- [ ] User plan approval/modification flow
- [ ] Plan → execution bridge
- [ ] HITL during execution
- [ ] "Save as template" feature
- [ ] Post-execution → trigger Process Workflow
- [ ] Dynamic Workflow + Process Workflow connection

### Phase 4 — Marketplace + Integrations (Weeks 21-30)

**Goal**: Open marketplace + partner integrations

- [ ] Community marketplace (user submissions)
- [ ] Partner agent SDK (for building integration agents)
- [ ] Splunk integration agent
- [ ] GitHub Actions integration
- [ ] Datadog integration
- [ ] Grafana integration
- [ ] Nessus integration
- [ ] ServiceNow integration
- [ ] Workflow import/export (JSON format)
- [ ] Evaluation/testing framework

### Phase 5 — Enterprise + Observability (Weeks 31-40)

**Goal**: Enterprise-grade reliability and compliance

- [ ] Cross-account Process Workflows
- [ ] Full audit log (every step, every decision)
- [ ] RBAC for workflows (who can create/edit/run)
- [ ] Workflow run analytics dashboard
- [ ] SLA tracking per workflow
- [ ] SOC2 evidence collection workflow
- [ ] Custom worker SDK
- [ ] White-label marketplace for enterprises
- [ ] Advanced retry strategies
- [ ] Parallel branch execution

---

## 13. Key Differentiators

### Why Codly 2.0 Wins vs n8n

| Feature | n8n | Codly 2.0 |
|---------|-----|-----------|
| Visual workflow editor | ✅ Best-in-class | ✅ Will have |
| Generic integrations (400+) | ✅ 400+ | Will grow over time |
| AI-planned workflows | ❌ None | ✅ **Core feature** |
| Cloud infrastructure awareness | ❌ None | ✅ Deep (inventory, compliance, cost) |
| ITSM integration | ❌ Basic | ✅ Native (Freshservice, Jira, Zendesk) |
| CLI execution on cloud | ❌ None | ✅ AWS CLI, Azure CLI, SSM |
| PII masking for AI | ❌ None | ✅ Built-in middleware |
| Compliance-aware operations | ❌ None | ✅ CIS/SOC2/PCI awareness |
| Cost optimization built-in | ❌ None | ✅ FinOps native |
| OS patching/hardening | ❌ None | ✅ Native workers |
| Multi-tenant isolation | ❌ None | ✅ Customer/Account-level |
| Human-in-the-loop for cloud | ❌ Basic | ✅ Approval flows with context |

### The Unfair Advantage

Codly has **domain-specific cloud intelligence** that generic workflow tools will never have:

1. **Pre-built cloud knowledge** — knows what an EC2, RDS, SG, VPC is without being told
2. **Compliance context** — knows CIS benchmarks, SOC2 controls, PCI requirements
3. **Cost intelligence** — knows what resources cost and how to optimize
4. **ITSM native** — tickets become first-class workflow triggers
5. **Security first** — PII masking, credential management, multi-tenant isolation built-in
6. **CLI execution** — can actually _change_ your infrastructure, not just notify

---

## Summary

Codly 2.0 is built on two pillars:

1. **Process Workflows (Runbooks)** — Define once, run forever. Pre-configured, event-triggered, deterministic sequences that handle your SOPs automatically.

2. **Dynamic AI Workflows (Planner Engine)** — Describe what you want, let AI figure out how to do it, review the plan, approve it, and watch it execute.

These two types **connect to each other**: dynamic workflows can provision infrastructure and automatically hand off to process workflows for hardening/compliance/monitoring setup.

The **Marketplace** packages everything into a catalog where customers discover, install, and share automation templates — giving Codly a network effect moat similar to what makes n8n valuable, but with deep cloud-specific intelligence that n8n can never replicate.

---

*Document generated from exploration of: n8n workflow editor, n8n templates library (9,447 templates, IT Ops focus), Codly Backend codebase (ai_ops/, chatbot/ai_ops/, ticket_management/, compliance/, finops/, chatbot/os_management/, chatbot/log_analytics/, chatbot/os_hardening/, chatbot/inventory_management/).*
