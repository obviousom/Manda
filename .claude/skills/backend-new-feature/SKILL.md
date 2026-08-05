---
name: backend-new-feature
description: How to add a new cloud-integrated feature to Codly Backend. Covers mandatory multi-cloud structure (base/providers/tools/prompts), factory pattern, and provider implementation. Use when adding any new AWS/Azure/GCP feature.
---

# Codly — New Cloud Feature Structure

**Every** cloud-integrated feature must follow this layout. No exceptions — CI checks for it.

## Directory layout

```
<app_name>/<feature_name>/
├── views.py                        # Thin routing only — <300 lines
├── agent.py                        # SwarmAgents orchestration + provider factory
├── urls.py                         # URL patterns for this feature
├── base/
│   └── <feature>_manager.py        # Abstract base class with @abstractmethod
├── providers/
│   ├── __init__.py
│   ├── aws_manager.py              # AWS implementation
│   └── azure_manager.py           # Azure implementation
├── tools/
│   ├── __init__.py
│   ├── aws/
│   │   └── aws_tools.py           # @tool decorated AWS functions
│   └── azure/
│       └── azure_tools.py         # @tool decorated Azure functions
└── prompts/
    ├── AWS<Feature>.md             # AWS agent system prompt
    └── Azure<Feature>.md          # Azure agent system prompt
```

Real example: `chatbot/finops/cost_analytics/`

## 1. Abstract base class

```python
# base/<feature>_manager.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseFeatureManager(ABC):

    def __init__(self, credentials_loader):
        self.credentials_loader = credentials_loader
        env_vars = credentials_loader.get_env_values()
        self._setup_client(env_vars)

    @abstractmethod
    def _setup_client(self, env_vars: dict) -> None:
        """Initialize cloud SDK client from env_vars."""
        ...

    @abstractmethod
    def get_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch feature data."""
        ...

    @abstractmethod
    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw cloud data."""
        ...
```

## 2. Provider implementation (AWS)

```python
# providers/aws_manager.py
import boto3
from .base.<feature>_manager import BaseFeatureManager

class AWSFeatureManager(BaseFeatureManager):

    def _setup_client(self, env_vars: dict) -> None:
        self.client = boto3.client(
            "service-name",
            aws_access_key_id=env_vars["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=env_vars["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=env_vars.get("AWS_SESSION_TOKEN"),
            region_name=env_vars.get("AWS_DEFAULT_REGION", "us-east-1"),
        )

    def get_data(self, **kwargs):
        try:
            response = self.client.some_operation(**kwargs)
            return response
        except Exception as e:
            logger.exception("AWS operation failed")
            raise

    def process_data(self, data):
        # transform raw response
        return data
```

## 3. Factory pattern in agent.py

```python
# agent.py
from .providers.aws_manager import AWSFeatureManager
from .providers.azure_manager import AzureFeatureManager

def _get_provider_manager(cloud_provider: str, cred_loader):
    if cloud_provider == "AWS":
        return AWSFeatureManager(cred_loader)
    elif cloud_provider == "AZURE":
        return AzureFeatureManager(cred_loader)
    else:
        raise ValueError(f"Unsupported cloud provider: {cloud_provider}")

def create_agents(user_input, session_id, customer, account, cred_loader, cloud_provider):
    manager = _get_provider_manager(cloud_provider, cred_loader)

    context = {
        "manager": manager,
        "customer": customer,
        "account": account,
        "cloud_provider": cloud_provider,
    }
    # ... build SwarmAgents with context
```

## 4. Tools — provider-specific

```python
# tools/aws/aws_tools.py
from langchain.tools import tool, ToolRuntime

@tool
def get_feature_data(
    param1: str,
    param2: int = 10,
    runtime: ToolRuntime = None,
) -> dict:
    """
    Get feature data for given parameters.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (default 10)
        runtime: Injected by SwarmAgents — do not pass manually
    
    Returns:
        dict with keys: data, total_count, metadata
    """
    context = runtime.context
    manager = context["manager"]
    try:
        return manager.get_data(param=param1, limit=param2)
    except Exception as e:
        logger.exception("get_feature_data failed")
        return {"error": str(e)}
```

## 5. Prompts

- One `.md` file per provider per agent role
- Store in `prompts/` directory
- Name: `AWS<FeatureName>.md`, `Azure<FeatureName>.md`
- Load with `load_prompt("chatbot/<app>/<feature>/prompts/AWS<Feature>.md")`

## 6. views.py pattern

```python
@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([CustomIsAuthenticated])
def feature_view(request):
    data = request.data
    account_id = data.get("account_id")
    user_input = data.get("user_input")
    session_id = data.get("session_id")

    customer = request.user.customer
    account = Account.objects.get(id=account_id, customer=customer)  # always filter by customer

    cred_loader = create_cloud_cred_loader(
        account.cloud_provider,
        user=request.user,
        account=account,
        customer=customer,
    )
    cred_loader.load_db_credentials()

    result = create_agents(
        user_input=user_input,
        session_id=session_id,
        customer=customer,
        account=account,
        cred_loader=cred_loader,
        cloud_provider=account.cloud_provider,
    )
    return Response(result)
```

## Checklist

- [ ] `base/` abstract class with `@abstractmethod`
- [ ] `providers/aws_manager.py` and `providers/azure_manager.py` both exist
- [ ] Factory function raises `ValueError` for unknown providers
- [ ] Prompts in `prompts/*.md`, never inline
- [ ] `@tool` functions accept `runtime: ToolRuntime = None`
- [ ] `views.py` < 300 lines, no business logic
- [ ] All DB queries filter by `customer` or `account`
