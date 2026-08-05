---
name: backend-pr-review
description: PR review checklist for Codly Backend. Distilled from docs/PR_REVIEW_GUIDELINES.md. Use when reviewing any PR or before submitting code for review.
---

# Codly Backend — PR Review Checklist

Full guidelines at `Codly_Backend/docs/PR_REVIEW_GUIDELINES.md`.

## Instant rejection — check these first

```
❌ Direct LLM import in feature code
   grep -r "from langchain_openai" .
   grep -r "import openai" .
   grep -r "from llm.langchain.llm_helper import LangChainModelFactory" .

❌ File over 1500 lines (CI will fail)
   find . -name "*.py" | xargs wc -l | sort -rn | head -20

❌ Hardcoded secrets / regions / account IDs / exchange rates
   grep -r "us-east-1" . --include="*.py"  # should come from config
   grep -r "sk-" . --include="*.py"        # API key

❌ Missing @authentication_classes or @permission_classes on any view
❌ DB query without customer/account filter
❌ Multi-line prompt string in Python (not in .md file)
❌ Cloud SDK call (boto3, azure-*) directly in views.py
```

## Security checks

- [ ] Every `Account.objects.get()` includes `customer=customer`
- [ ] User-supplied IDs validated against tenant before use
- [ ] No secrets in code, `.env.example`, or logs
- [ ] `logger.exception()` used (not `logger.error()`) for unexpected failures — captures stack trace
- [ ] Error responses to client are generic — no stack traces, no internal details

## LLM / Agent checks

- [ ] `SwarmAgents` used for all agents (single or multi-agent, not raw LangGraph)
- [ ] `model_category` specified on every agent (`"default"` | `"low"` | `"medium"` | `"high"`)
- [ ] `PIIMaskingMiddleware` applied to swarm
- [ ] Prompts loaded via `load_prompt()` — not inline strings
- [ ] Tools accept `runtime: ToolRuntime = None`
- [ ] Tools return dict (not string, not raw SDK response)

## Architecture checks

- [ ] New cloud feature has `base/` abstract class + `providers/` implementations
- [ ] Factory pattern used for provider selection (raises `ValueError` for unknown provider)
- [ ] `views.py` < 300 lines — routing only
- [ ] Agent/manager contains all business logic
- [ ] `select_related()` / `prefetch_related()` used where N+1 queries are possible

## Multi-cloud checks

- [ ] Feature works for all supported providers (AWS + Azure minimum)
- [ ] Provider-specific code in `providers/aws_manager.py`, `providers/azure_manager.py`
- [ ] Common logic in `base/` or `utils/`
- [ ] Provider-specific tools in `tools/aws/` and `tools/azure/`
- [ ] Provider-specific prompts in `prompts/AWS*.md` and `prompts/Azure*.md`

## Quality checks

- [ ] No file > 1500 lines (hard CI limit)
- [ ] Split large files to `_part2.py` or sub-modules before hitting 800 lines
- [ ] API input/output changes documented in `/docs/api/<FeatureName>/`
- [ ] New models have migrations created
- [ ] Tests added or updated (at minimum happy path + error path)

## Common anti-patterns

```python
# ❌ Cross-tenant query
Account.objects.get(id=account_id)

# ❌ Missing auth
@api_view(["POST"])
def my_view(request):  # no auth decorators

# ❌ Hardcoded region
boto3.client("ec2", region_name="us-east-1")

# ❌ Direct LLM
from langchain_openai import ChatOpenAI
model = ChatOpenAI()

# ❌ Inline prompt
system_prompt = """You are an expert analyst.
Please analyze the following..."""

# ❌ os.getenv for cloud creds
key = os.getenv("AWS_ACCESS_KEY_ID")

# ✅ All correct patterns in respective skills
```
