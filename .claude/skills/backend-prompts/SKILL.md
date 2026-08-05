---
name: backend-prompts
description: How to write and load agent prompts in Codly Backend. Covers load_prompt(), .md file conventions, variable injection, per-provider prompt files, and UTC injection. Use when creating or modifying agent prompts.
---

# Codly — Prompts

All agent prompts live in `.md` files. Never inline multi-line prompts in Python.

## Loading prompts

```python
from llm.utils.prompt_loader import load_prompt

# Path relative to Codly_Backend/
prompt = load_prompt("chatbot/finops/cost_analytics/prompts/AWSCostAnalysis.md")
```

## Variable injection

`load_prompt()` returns a string. Inject variables with `.replace()`:

```python
prompt = load_prompt("chatbot/myfeature/prompts/AWSFeature.md")
prompt = prompt.replace("{{CUSTOMER_NAME}}", customer.name)
prompt = prompt.replace("{{ACCOUNT_ID}}", account.provider_account_id or "")
prompt = prompt.replace("{{CLOUD_PROVIDER}}", cloud_provider)
```

Use `{{VARIABLE_NAME}}` convention in `.md` files for placeholder variables.

## UTC time injection

Some agents need current UTC time. Use the utility:

```python
from chatbot.finops.cost_analytics.prompt_injection import inject_utc_into_prompt

prompt = load_prompt("chatbot/myfeature/prompts/AWSFeature.md")
prompt = inject_utc_into_prompt(prompt)  # appends current UTC datetime
```

## Prompt file location convention

```
<app_name>/<feature>/
└── prompts/
    ├── AWS<Feature>.md       # AWS-specific agent prompt
    ├── Azure<Feature>.md     # Azure-specific agent prompt
    ├── GCP<Feature>.md       # GCP-specific (if needed)
    └── Supervisor.md         # Supervisor/router agent prompt
```

Named after provider + feature, e.g.:
- `AWSCostAnalysis.md`
- `AzureLogAnalytics.md`
- `ComplianceSupervisor.md`

## Writing effective prompt files

Structure:

```markdown
# <Agent Name>

## Role
You are an expert <domain> specialist for the Codly platform...

## Context
- Customer: {{CUSTOMER_NAME}}
- Cloud Provider: {{CLOUD_PROVIDER}}
- Current UTC Time: {{UTC_TIME}}

## Capabilities
You have access to the following tools:
- `tool_name`: What it does and when to use it
- ...

## Instructions
1. Always verify...
2. When the user asks about X, use Y tool...
3. ...

## Response Format
Always respond with:
- Summary of findings
- Data in structured format
- Recommended next steps
```

## Multi-agent prompts — handoff instructions

Supervisor agents need explicit handoff instructions:

```markdown
## Agent Routing
You coordinate a team of specialist agents. Route tasks as follows:
- **cost_analyzer**: Initial cost breakdown, service totals, period queries
- **detail_analyzer**: Drill-down into specific services, anomaly detail
- **resource_analyzer**: Resource-level cost attribution

When handing off, pass a concise task summary including:
- Original user intent
- Cloud provider
- Resolved time period
- Key findings so far
- Exact action expected from the target agent
```

## Rules

- No multi-line prompt strings in Python files
- Store in `prompts/` subdirectory of the feature
- One `.md` file per provider per agent (when prompts differ by provider)
- Shared prompts (provider-agnostic) can be a single file
- After modifying a prompt, test with a real invocation — LLM behavior changes are not caught by unit tests
