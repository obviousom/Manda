---
name: backend-inventory
description: Inventory management patterns for Codly Backend — Suggestion model, agent types, CLI suggestion agents, VM/RDS views, and inventory sync. Use when working on inventory/ app or adding resource query features.
---

# Codly — Inventory Management

App: `inventory/`

## Key models

```python
from inventory.models import Suggestion, SuggestionType
```

### Suggestion model

Suggestions are natural-language queries users can run against cloud resources. Pre-seeded per customer.

```python
suggestion.value              # The query text shown to user
suggestion.description        # What this suggestion does
suggestion.type               # FK to SuggestionType (category)
suggestion.cloud_provider     # "AWS" | "AZURE" | "GCP" | None (all)
suggestion.cli_execution_required   # bool — needs remote CLI execution
suggestion.include_chat_history     # bool — pass conversation history to agent
suggestion.customer           # FK to Customer (None = global suggestion)
suggestion.is_creatable       # bool — show "Create" button in AI Ops form
```

### Querying suggestions

```python
from inventory.models import Suggestion, SuggestionType

# All suggestions for a customer (own + global)
suggestions = Suggestion.objects.filter(
    models.Q(customer=customer) | models.Q(customer__isnull=True)
).filter(cloud_provider__in=[account.cloud_provider, None])

# By type
type_obj = SuggestionType.objects.get(type="EC2")
suggestions = Suggestion.objects.filter(type=type_obj, customer=customer)
```

## Agent architecture

```
inventory/
├── views.py             # Thin routing — list resources, run suggestions
├── views_vm.py          # VM-specific views (EC2, Azure VM)
├── views_rds.py         # RDS/database views
├── agents.py            # All agent functions
├── workflow.py          # LangGraph workflow for inventory queries
├── agent_extractors.py  # LLM-based metadata extraction
├── db_utils.py          # Environment tag helpers
└── inventory_utils.py   # Utility functions
```

## Agent types in agents.py

```python
from inventory.agents import (
    descriptive_cli_suggestion_agent,   # Run CLI command, describe results
    inline_cli_suggestion_agent,        # Run CLI, return inline result
    recommendations_analyzer_agent,     # Analyze resource and give recommendations
    chat_history_agent,                 # Use conversation history for context
    get_instance_types_from_aws,        # AWS instance type lookup
)
```

### descriptive_cli_suggestion_agent

Most common pattern — runs a CLI suggestion against cloud resources:

```python
from inventory.agents import descriptive_cli_suggestion_agent

result = descriptive_cli_suggestion_agent(
    user_input=user_query,
    session_id=session_id,
    customer=customer,
    account=account,
    cred_loader=cred_loader,
    suggestion=suggestion,
    region=region,
)
```

### recommendations_analyzer_agent

Analyze a specific resource and get optimization recommendations:

```python
from inventory.agents import recommendations_analyzer_agent

result = recommendations_analyzer_agent(
    resource_id=instance_id,
    resource_type="EC2",
    session_id=session_id,
    customer=customer,
    account=account,
    cred_loader=cred_loader,
)
```

## VM views pattern

```python
# GET /inventory/vms/?account_id=1&region=us-east-1
@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([CustomIsAuthenticated])
def get_vms(request):
    account_id = request.query_params.get("account_id")
    region = request.query_params.get("region")

    customer = request.user.customer
    account = Account.objects.get(id=account_id, customer=customer)

    cred_loader = create_cloud_cred_loader("AWS", user=request.user, account=account, customer=customer)
    cred_loader.load_db_credentials()
    env_vars = cred_loader.get_env_values()

    # Use boto3 directly here since this is data fetching, not agent work
    import boto3
    ec2 = boto3.client("ec2",
        aws_access_key_id=env_vars["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env_vars["AWS_SECRET_ACCESS_KEY"],
        aws_session_token=env_vars.get("AWS_SESSION_TOKEN"),
        region_name=region,
    )
    response = ec2.describe_instances()
    return Response({"instances": response["Reservations"]})
```

See `inventory/views_vm.py` and `inventory/views_rds.py` for full real-world examples.

## Environment tag helpers

```python
from inventory.db_utils import get_environment_tag_key, get_environment_tag_info

# Get the tag key used for environments for this customer
tag_key = get_environment_tag_key(customer=customer)  # e.g., "Environment"
tag_info = get_environment_tag_info(customer=customer)
```

## Azure VM suggestion service

```python
from inventory.azure_vm_suggestion_service import AzureVMSuggestionService

service = AzureVMSuggestionService(customer=customer, account=account, cred_loader=cred_loader)
suggestions = service.get_suggestions(vm_id="vm-resource-id")
```

## LangGraph workflow

For complex multi-step inventory queries:

```python
from inventory.workflow import create_graph

graph = create_graph(customer=customer, account=account, cred_loader=cred_loader)
result = graph.invoke({"user_input": user_query, "session_id": session_id})
```
