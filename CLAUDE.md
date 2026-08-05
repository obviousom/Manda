# CLAUDE.md

Guidance for Claude Code in this repository.

\---
Address me as "sir" with dry wit; keep language simple and direct rather than overly formal or British (Jarvis-style tone).
Talk like Jarvis from Iron man

## Project Overview

**Codly** — multi-cloud AI automation platform. FinOps, Compliance, OS Hardening, Inventory, Log Analytics, IT Ticket Management across AWS, Azure, GCP.

**Monorepo:**

* `Codly\_Backend/` — Django 6 + LangGraph (port 8000)
* `Codly-Frontend/` — Next.js SPA (port 3003)

\---

## Dev Commands

```bash
# Backend
cd Codly_Backend
uv run python manage.py runserver 0.0.0.0:8000  | tee /tmp/codly\_backend\_logs.txt


# Frontend
cd Codly-Frontend \&\& bun run dev          # port 3004

# Migrations
uv run python manage.py makemigrations <app>
uv run python manage.py migrate
uv run python manage.py showmigrations
```

\---

## Endpoint Testing (Auth Bypass)

Bypass JWT for local dev testing via `X-Dev-Test` header. Secret: `codly-dev-test-2024`. Default user\_id: `36`.

```bash
# GET — no payload
curl -s "http://localhost:8000/api/<path>/" \\
  -H "X-Dev-Test: codly-dev-test-2024" \\
  -H "X-Dev-Test-User-Id: 36"

# POST — with payload
curl -s -X POST "http://localhost:8000/api/<path>/" \\
  -H "X-Dev-Test: codly-dev-test-2024" \\
  -H "X-Dev-Test-User-Id: 36" \\
  -H "Content-Type: application/json" \\
  -d '{"key": "value"}'

# Admin user
curl -s "http://localhost:8000/api/<path>/" \\
  -H "X-Dev-Test: codly-dev-test-2024" \\
  -H "X-Dev-Test-Admin: true"
```

**Rule:** Always use these headers when testing endpoints. If endpoint needs a request body, ask user for payload before calling.

\---

## Skills — Load Before Working

Load with `Skill` tool. **Load the relevant skill before writing any code.**

|Trigger|Skill|
|-|-|
|All agents (single or multi) / `SwarmAgents` / `agent.py`|`backend-swarm-agent`|
|New Django app from scratch|`backend-new-app`|
|New cloud feature (AWS/Azure/GCP) in existing app|`backend-new-feature`|
|Writing `views.py` / auth decorators|`backend-views`|
|Writing `@tool` functions / `ToolRuntime`|`backend-tools`|
|Auth, permissions, `create\_cloud\_cred\_loader`|`backend-auth`|
|Django models / DB queries / migrations|`backend-models`|
|Writing or loading agent prompts / `load\_prompt()`|`backend-prompts`|
|Background tasks / Celery / WebSocket progress|`backend-celery`|
|`ticket\_management/` — tickets, integrations, agents|`backend-ticket-management`|
|`compliance/` — scans, frameworks, points|`backend-compliance`|
|`inventory/` — suggestions, VM/RDS views|`backend-inventory`|
|`chatbot/finops/` — cost analytics, reports|`backend-finops`|
|`chatbot/log\_analytics/` — CloudTrail, VPC, ALB|`backend-log-analytics`|
|`chatbot/os\_hardening/` — CIS/STIG, SSH execution|`backend-os-hardening`|
|File upload/download S3/Blob|`backend-storage`|
|`agent\_hub/` — user-defined / MCP agents|`backend-agent-hub`|
|PR review / code audit|`backend-pr-review`|

Skills live in `.claude/skills/`.

\---

## Graphify — Use Before Exploring Code

`graphify-out/graph.json` exists for `Codly\_Backend`. **Always query graphify before reading source files.**

```bash
cd Codly\_Backend

# Where is X, what calls Y
graphify query "<question>"

# Relationship between two symbols
graphify path "<A>" "<B>"

# Deep explanation of a concept
graphify explain "<concept>"

# After modifying code
graphify update .
```

If `graphify-out/wiki/index.md` exists, use it for navigation before raw file browsing.  
Read `graphify-out/GRAPH\_REPORT.md` only for broad architecture review.

\---

## Hard Rules (CI will fail on violations)

1. **No direct LLM imports** — never `from langchain\_openai import ...`, `import openai`, or `from llm.langchain.llm\_helper import LangChainModelFactory` in feature code
2. **No file > 1500 lines** — split before reaching 800 lines
3. **No hardcoded values** — regions, IDs, keys, rates must come from config/DB
4. **Multi-cloud mandatory** — every cloud feature needs `base/` + `providers/`
5. **Auth on every view** — `@authentication\_classes` + `@permission\_classes` always
6. **Prompts in `.md` files** — no inline multi-line strings
7. **Multi-tenant isolation** — every DB query filtered by `customer` or `account`
8. **No DB writes in debugging/review** — read-only only when inspecting
9. You can check backend logs for debugging at `/tmp/codly\_backend\_logs.txt` , use tail and grep
10. NEVER EVER COMMIT OR PUSH ANYTHING YOURSELF IF NOT ASKED

\---

## Pull Requests

* Never add Claude/Anthropic as co-author — no `Co-Authored-By: Claude` line, no attribution to Claude in commits or PRs
* PR description must be 100-200 words — concise summary + test plan, no filler
* Before pushing `Codly\_Backend/` changes, run the PyArmor obfuscation check locally (mirrors `.github/workflows/pr-pyarmor-check.yml`):
  ```bash
  cd Codly_Backend
  pyarmor gen . \
    --exclude './.git' --exclude './.github' --exclude './.agents' --exclude './.claude' \
    --exclude './_deprecated' --exclude './.scannerwork' --exclude './.venv' --exclude './dist' \
    --exclude '*__pycache__' --exclude '*.pyc'
  ```
  Confirm `dist/` is created and contains obfuscated `.py` files before pushing.
* Before pushing `Codly\_Backend/` changes, check every modified `.py` file's line count against Hard Rule #2 (split before 800 lines, hard cap 1500) and split any file that crosses it. This check is Python-only — skip it for frontend/TS files.

\---

## Key Imports Reference

```python
# Auth
from manage\_user.authentication
from manage\_user.credentials\_management import create\_cloud\_cred\_loader

# LLM — ONLY these
from llm.agents.swarm import SwarmAgents, AgentConfig
from llm.utils.prompt\_loader import load\_prompt

# Background tasks
from common.background\_tasks import run\_in\_background, run\_in\_background\_by\_path
from celery import shared\_task

# Storage
from common.StorageConfig import StorageConfig

# Models
from manage\_user.models import Customer, Account, User, AdminUser
from chatbot.models.models import Session, ConversationHistory
```

\---

## Docs \& API

* PR review guidelines: `Codly\_Backend/docs/PR\_REVIEW\_GUIDELINES.md`
* SwarmAgents docs: `Codly\_Backend/docs/SwarmAgents\_Documentation.md`
* API docs: `Codly\_Backend/docs/api/<FeatureName>/` — update when endpoints change
* New docs go in `/docs/`, never at repo root
import CookieJWTAuthentication
from common.authentication import CustomIsAuthenticated
from admin\_portal.views import CookieJWTAdminAuthentication, CustomIsAdminAuthenticated

# Credentials

Frontend - saurabh@allysense.ai 
Password - Saurabh@123

