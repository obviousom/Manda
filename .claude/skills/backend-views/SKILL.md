---
name: backend-views
description: How to write views.py correctly in Codly Backend. Covers auth decorators, thin routing pattern, request validation, credential loading, delegation to agents/managers, and response format. Use when writing or reviewing any view function.
---

# Codly — views.py Pattern

Views are **routing-only**. No business logic, no cloud SDK calls, no LLM calls

## Standard frontend view

```python
import logging
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status
from manage_user.models import Customer, Account
from manage_user.authentication import CookieJWTAuthentication
from common.authentication import CustomIsAuthenticated
from manage_user.credentials_management import create_cloud_cred_loader
from .agent import create_agents

logger = logging.getLogger(__name__)


@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([CustomIsAuthenticated])
def my_feature_view(request):
    # 1. Extract + validate input
    account_id = request.data.get("account_id")
    user_input = request.data.get("user_input", "").strip()
    session_id = request.data.get("session_id")

    if not account_id or not user_input:
        return Response({"error": "account_id and user_input are required"}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Resolve customer + account with ownership check
    customer = request.user.customer
    try:
        account = Account.objects.get(id=account_id, customer=customer)
    except Account.DoesNotExist:
        return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

    # 3. Load credentials
    cred_loader = create_cloud_cred_loader(
        account.cloud_provider,
        user=request.user,
        account=account,
        customer=customer,
    )
    cred_loader.load_db_credentials()

    # 4. Delegate to agent
    try:
        result = create_agents(
            user_input=user_input,
            session_id=session_id,
            customer=customer,
            account=account,
            cred_loader=cred_loader,
            cloud_provider=account.cloud_provider,
        )
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception("my_feature_view failed")
        return Response({"error": "An error occurred. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

## Admin portal view

```python
from admin_portal.views import CookieJWTAdminAuthentication, CustomIsAdminAuthenticated

@api_view(["POST"])
@authentication_classes([CookieJWTAdminAuthentication])
@permission_classes([CustomIsAdminAuthenticated])
def admin_only_view(request):
    ...
```

## Dual-access view (both frontend users and admin)

```python
from manage_user.models import AdminUser

@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication, CookieJWTAdminAuthentication])
@permission_classes([CustomIsAuthenticated])
def dual_access_view(request):
    if isinstance(request.user, AdminUser):
        # admin path — can access any customer
        customer_id = request.query_params.get("customer_id")
        customer = Customer.objects.get(id=customer_id)
    else:
        # end-user path — scoped to their customer
        customer = request.user.customer
    ...
```

## Auth class reference

| Surface | Cookie | Auth class | Permission class |
|---|---|---|---|
| Frontend users | `access_token` httponly | `CookieJWTAuthentication` | `CustomIsAuthenticated` |
| Admin portal | `auth-token` httponly | `CookieJWTAdminAuthentication` | `CustomIsAdminAuthenticated` |

Imports:
```python
from manage_user.authentication import CookieJWTAuthentication
from common.authentication import CustomIsAuthenticated
from admin_portal.views import CookieJWTAdminAuthentication, CustomIsAdminAuthenticated
```

## GET view with query params

```python
@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([CustomIsAuthenticated])
def list_view(request):
    customer = request.user.customer
    account_id = request.query_params.get("account_id")

    qs = MyModel.objects.filter(customer=customer)
    if account_id:
        qs = qs.filter(account_id=account_id)

    data = list(qs.values("id", "name", "created_at"))
    return Response({"results": data, "count": len(data)})
```

## Rules

- Views < 300 lines — split to `views_part2.py` if needed
- No direct cloud SDK calls (boto3, azure, gcp) in views
- No LLM calls in views
- Every query filtered by `customer` or `account`  
- Always use `try/except` around agent/manager calls, log with `logger.exception()`
- Return meaningful errors, never expose stack traces to client
- API doc changes → add `.md` file to `/docs/api/<FeatureName>/`
