---
name: codly
description: Index skill for Codly Backend. Lists all available Codly skills and when to use them. Invoke this when unsure which specific skill to use.
---

# Codly Skills Index

All skills live in `.claude/skills/codly/`. Use the `Skill` tool to load them.

| Skill name | Trigger / use when |
|---|---|
| `backend-swarm-agent` | All agent work (single or multi-agent), writing `agent.py`, `SwarmAgents` usage |
| `backend-new-app` | Scaffolding a new Django app from scratch |
| `backend-new-feature` | Adding new cloud-integrated feature (AWS/Azure/GCP) to existing app |
| `backend-views` | Writing `views.py`, auth decorators, response patterns |
| `backend-tools` | Writing `@tool` functions, `ToolRuntime` context injection |
| `backend-auth` | Auth classes, permissions, `create_cloud_cred_loader`, ownership checks |
| `backend-models` | Django models, multi-tenant queries, migrations, caching |
| `backend-prompts` | Writing/loading prompts, `load_prompt()`, variable injection |
| `backend-celery` | Background tasks, Celery `@shared_task`, WebSocket progress |
| `backend-ticket-management` | Ticket model, `TicketProviderFactory`, agents, monitoring |
| `backend-compliance` | Compliance scans, `ComplianceScan` model, WebSocket progress |
| `backend-inventory` | Inventory agents, `Suggestion` model, VM/RDS views |
| `backend-finops` | FinOps/cost analytics, multi-cloud cost agents, report generation |
| `backend-log-analytics` | Log analysis agents, CloudTrail/VPC/ALB/Azure Monitor |
| `backend-os-hardening` | CIS/STIG scan and execution, SSH remote execution |
| `backend-runbooks` | RunBook engine — step runners, executor loop, triggers, WebSocket live runs |
| `backend-storage` | `StorageConfig` S3/Azure Blob upload/download |
| `backend-agent-hub` | User-defined agents, MCP agents, marketplace |
| `backend-pr-review` | PR review checklist, common anti-patterns, rejection criteria |
