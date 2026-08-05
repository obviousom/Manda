```instructions
# Codly Backend - AI Coding Assistant Instructions

## Overview
This instruction file applies to all files under the `Codly_Backend/` directory.
It guides AI assistants on Codly Backend conventions, security requirements, cloud abstractions, authentication patterns, prompt handling, and multi-tenant isolation.

## Absolute Prohibitions
- No direct LLM API imports or SDK usage in feature code.
  - Forbidden: `import openai`, `from langchain_openai import ChatOpenAI`, `from langchain_google_genai import ChatGoogleGenerativeAI`, `from llm.langchain.llm_helper import LangChainModelFactory`.
  - Required: use `MaskedReactAgentBuilder`, `ReactSwarmAgents`, or `ChatSession` for any LLM invocation.
- No hardcoded secrets, credentials, account IDs, regions, bucket names, exchange rates, or dates.
- No cloud provider SDK calls directly in views or agent entrypoints.
- No prompt text embedded in Python source; use `.md` prompt files and `load_prompt()`.
- No unmasked PII sent to LLMs.
- No database write operations in code review or debugging work; only read access is permitted for inspection.

## Mandatory Requirements
- Use `create_cloud_cred_loader()` for all cloud credential handling.
- Always call `.load_db_credentials()` before `.get_env_values()`.
- Pass credentials explicitly to cloud SDK clients.
- Do not use `os.getenv()` for cloud credentials.
- All database queries must filter by `customer` or `account`.
- Validate user access and tenant ownership on every lookup.
- All views must use `@authentication_classes` and `@permission_classes`.
- For customer APIs, use `CookieJWTAuthentication` + `CustomIsAuthenticated`.
- For admin APIs, use `CookieJWTAdminAuthentication` + `CustomIsAdminAuthenticated`.
- For dual-access APIs, use both auth classes and branch by `isinstance(request.user, AdminUser)`.
- All cloud API calls require try/except handling and user-friendly errors.
- Use `logger.exception()` for unexpected failures.

## Architecture Patterns
- New cloud features should follow the multi-cloud structure:
  - `views.py` (thin routing layer)
  - `agent.py` (orchestrates business logic)
  - `base/feature_manager.py` (abstract base class)
  - `providers/aws_manager.py`, `providers/azure_manager.py`
  - `tools/` for provider-specific and common tools
  - `prompts/` for `.md` prompt templates
  - `utils/` for helper utilities
- Base classes must inherit from `ABC` and define `@abstractmethod` signatures.
- Provider implementations must inherit the base class, initialize SDK clients in `__init__`, and use `self.credentials_loader.get_env_values()`.
- Use a factory pattern to select provider implementation based on `account.cloud_provider`.
- Raise `ValueError` for unsupported providers.

## View Style
- Keep views thin and routing-only.
- Extract request data, validate context, load credentials, delegate to agent/manager, and return JSON.
- Do not include heavy business logic or cloud SDK calls in views.
- Avoid views longer than 300 lines.

## Prompt and Tool Rules
- Store prompts in `prompts/` Markdown files.
- Load prompts with `load_prompt()` from `llm.utils.prompt_loader`.
- Use `@tool` decorated functions for tool definitions.
- Tools should accept typed inputs, return structured data, and use closure-injected context.

## Performance and Maintainability
- Avoid files larger than 1500 lines.
- Split large modules before 800 lines.
- Optimize queries using `select_related()` and `prefetch_related()` where appropriate.
- Cache expensive static lookups when safe.

## Documentation
- When view input/output changes, add API documentation under `/docs/api/{Feature_Name}/`.
- Prefer adding documentation files inside `/docs`, not at the repository root.

## References
- Always check `/docs/PR_REVIEW_GUIDELINES.md` for review-specific policies.
```