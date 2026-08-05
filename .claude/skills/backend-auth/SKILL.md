---
name: backend-auth
description: Auth patterns for Codly Backend — CookieJWT authentication, permission classes, create_cloud_cred_loader usage, STS credential flow, and multi-tenant ownership checks. Use when writing views or adding new endpoints.
---

# Codly — Auth & Credentials

## Authentication classes

| Surface | Auth class | Permission class | Cookie name |
|---|---|---|---|
| Frontend users | `CookieJWTAuthentication` | `CustomIsAuthenticated` | `access_token` |
| Admin portal | `CookieJWTAdminAuthentication` | `CustomIsAdminAuthenticated` | `auth-token` |

```python
# Frontend endpoint
from manage_user.authentication import CookieJWTAuthentication
from common.authentication import CustomIsAuthenticated

@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([CustomIsAuthenticated])
def my_view(request):
    user = request.user          # manage_user.models.User
    customer = user.customer     # Customer model instance
    ...

# Admin portal endpoint
from admin_portal.views import CookieJWTAdminAuthentication, CustomIsAdminAuthenticated

@api_view(["GET"])
@authentication_classes([CookieJWTAdminAuthentication])
@permission_classes([CustomIsAdminAuthenticated])
def admin_view(request):
    admin_user = request.user    # django.contrib.auth.models.User (AdminUser)
    ...
```

Both decorators are **mandatory** on every view. Views without them will be rejected in PR review.

## Multi-tenant ownership check

Always validate the user owns the resource they're accessing:

```python
customer = request.user.customer

# Correct — filters by customer
account = Account.objects.get(id=account_id, customer=customer)

# WRONG — cross-tenant leak risk
account = Account.objects.get(id=account_id)
```

For admin users accessing any customer:

```python
from manage_user.models import AdminUser, Customer

if isinstance(request.user, AdminUser):
    customer_id = request.data.get("customer_id")
    customer = Customer.objects.get(id=customer_id)
else:
    customer = request.user.customer
```

## Credential loading — create_cloud_cred_loader

Always use this factory. Never use `os.getenv()` for cloud credentials in feature code.

```python
from manage_user.credentials_management import create_cloud_cred_loader

# Standard pattern
cred_loader = create_cloud_cred_loader(
    account.cloud_provider,     # "AWS" | "AZURE" | "GCP"
    user=request.user,
    account=account,
    customer=customer,
)
cred_loader.load_db_credentials()   # STS AssumeRole → tokens cached in Redis (57 min)
env_vars = cred_loader.get_env_values()
```

`env_vars` dict keys by provider:

**AWS:**
```python
{
    "AWS_ACCESS_KEY_ID": "...",
    "AWS_SECRET_ACCESS_KEY": "...",
    "AWS_SESSION_TOKEN": "...",          # STS temp token
    "AWS_DEFAULT_REGION": "ap-south-1",
}
```

**Azure:**
```python
{
    "AZURE_CLIENT_ID": "...",
    "AZURE_CLIENT_SECRET": "...",
    "AZURE_TENANT_ID": "...",
    "AZURE_SUBSCRIPTION_ID": "...",
}
```

Pass `env_vars` or `cred_loader` directly to cloud SDK clients or tools via context dict.

## Access levels

```python
from manage_user.credentials_management import AccessLevel

# Read-only role (default for most features)
cred_loader = create_cloud_cred_loader(
    "AWS", user=user, account=account, customer=customer,
    access_level=AccessLevel.READ_ONLY,
)

# Power user (for write operations like OS hardening, tag management)
cred_loader = create_cloud_cred_loader(
    "AWS", user=user, account=account, customer=customer,
    access_level=AccessLevel.POWER_USER,
)
```

Each `Account` has two IAM roles:
- `account.read_only_iam_role_arn` — read-only
- `account.power_user_iam_role_arn` — write operations

## JWT config

- Algorithm: HS256
- Lifetime: 7 days (access + refresh)
- Cookie flags: `httponly=True`, `samesite='Lax'`, `secure=True` (production)

## User model hierarchy

```
AdminUser (django.contrib.auth.models.User)  ← admin portal login
└── AdminProfile  ← links AdminUser to Customer, admin_type=SERVICE|CUSTOMER

Customer  ← top-level tenant
└── User (manage_user.models.User)  ← end-user, has is_power, is_admin flags
    └── Account  ← cloud account/subscription
```

Checking user type:

```python
from manage_user.models import User, AdminUser

isinstance(request.user, AdminUser)   # True → admin portal user
isinstance(request.user, User)        # True → frontend user
request.user.is_power                 # True → power user (write access)
request.user.is_admin                 # True → customer admin
```
