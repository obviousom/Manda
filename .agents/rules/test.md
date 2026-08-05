---
trigger: model_decision
description: When making heavy changes to Codly_Backend . It's Fine to not refer this when troubelshooting something but while implementing . Please refer this
---

# Codly Backend - Development & Code Review Standards

## Purpose

This file guides GitHub Copilot for both **writing new code** and **reviewing pull requests** in the Codly multi-cloud AI automation platform.

**IMPORTANT** 
You need to always refer `/docs/PR_REVIEW_GUIDELINES.md` for comprehensive guideline while Code Review
- If you do any changes in view endpoint input or output ... Please make sure to give .md file for thes changes in `/docs/api/{Feature_Name}` folder with details of change. This will help developer to dump the doc in FrontendC Copliot for changes
YOU ARE NOT ALLOWED TO MAKE WRITE OPREATIONS IN DB ONLY READ
- 

IF YOU ARE CREATING A DOCUMENTED ie .md file for anything .... Can you please not dump into root folder ??? and put it in `/docs` folder and maybe create subfolders if needed. It will be easier to maintain and find things in future. 
---

## ⚠️ ABSOLUTE PROHIBITIONS (Immediate Rejection)

### 1. ❌ NO DIRECT LLM CALLS (CRITICAL)
- **FORBIDDEN**: `from langchain_openai import ChatOpenAI`
- **FORBIDDEN**: `from langchain_google_genai import ChatGoogleGenerativeAI`
- **FORBIDDEN**: `import openai` (direct API calls)
- **FORBIDDEN**: `from llm.langchain.llm_helper import LangChainModelFactory` (in feature code) 
- **FORBIDDEN**: `ReactSwarmAgents' 
- **REQUIRED**: ONLY use `SwarmAgents` or `ChatSession`
- **WHY**: Bypasses PII masking/unmasking, credential protection, centralized model config

### 2. ❌ NO FILES OVER 1500 LINES (BREAKS CI/CD)
- **HARD LIMIT**: 1500 lines per Python file (CI/CD pipeline WILL FAIL)
- **PROACTIVE SPLIT**: When approaching 800 lines
- **TARGET LIMITS**: Views < 300, Tools < 500, Managers < 1000
- **CHECK**: `wc -l <file>` before commit

### 3. ❌ NO HARDCODED VALUES
- **FORBIDDEN**: Hardcoded regions (`"us-east-1"`, `"eastus"`)
- **FORBIDDEN**: Hardcoded customer/account IDs (`123`, `456789012`)
- **FORBIDDEN**: Hardcoded credentials/API keys
- **FORBIDDEN**: Hardcoded exchange rates (`88.51`, `0.012`)
- **FORBIDDEN**: Hardcoded dates/years (`2025`, `"2024-12-01"`)
- **FORBIDDEN**: Hardcoded bucket/container names
- **FORBIDDEN**: Hardcoded email addresses
- **FORBIDDEN**: Hardcoded threshold values
- **REQUIRED**: Use `settings.py`, `account.region`, `datetime.now()`, etc.

### 4. ❌ NO CLOUD-SPECIFIC CODE WITHOUT ABSTRACTION
- **REQUIRED**: Every cloud feature MUST have `base/` abstract class with `@abstractmethod`
- **REQUIRED**: Every cloud feature MUST have `providers/` implementations (AWS, Azure)
- **REQUIRED**: Use factory pattern for provider selection
- **FORBIDDEN**: Cloud SDK calls directly in views or agents
- **FORBIDDEN**: Provider-specific logic outside `providers/` directory

### 5. ❌ NO MISSING AUTHENTICATION
- **REQUIRED**: ALL views MUST have `@authentication_classes` decorator
- **REQUIRED**: ALL views MUST have `@permission_classes` decorator
- **FRONTEND**: Use `CookieJWTAuthentication` + `CustomIsAuthenticated`
- **ADMIN**: Use `CookieJWTAdminAuthentication` + `CustomIsAdminAuthenticated`
- **DUAL**: Use both authentication classes with type checking

### 6. ❌ NO PROMPTS IN CODE
- **REQUIRED**: ALL prompts MUST be in `.md` files in `prompts/` directory
- **REQUIRED**: Load prompts using `load_prompt()` from `llm.utils.prompt_loader`
- **FORBIDDEN**: Multi-line string prompts in Python code
- **FORBIDDEN**: F-strings or `.format()` for entire prompts

### 7. ❌ NO UNMASKED PII TO LLMs
- **REQUIRED**: ALL LLM calls MUST use `SwarmAgents`,  or `ChatSession` (auto-masks)
- **FORBIDDEN**: Sending raw customer data to LLMs without masking
- **FORBIDDEN**: Direct LLM API calls (cannot mask PII)

---

## ✅ MANDATORY REQUIREMENTS

### Model Category Specification
- **REQUIRED**: ALL agents MUST specify `category` parameter
- **OPTIONS**: `"low"`, `"default"/"medium"`, `"high"`
- **low**: Simple classification, yes/no decisions, basic queries
- **medium**: Standard analysis, cost breakdowns, resource listing
- **high**: Complex reasoning, multi-step workflows, code generation, deep analysis
- **FORBIDDEN**: Omitting category (will use wrong model tier)

### Error Handling
- **REQUIRED**: ALL cloud API calls MUST have `try/except` with `ClientError`
- **REQUIRED**: Use `logger.exception()` for unexpected errors
- **REQUIRED**: Return user-friendly error messages
- **FORBIDDEN**: Exposing internal error details to users
- **FORBIDDEN**: Silent failures (must log errors)

### Multi-Tenant Isolation
- **REQUIRED**: ALL database queries MUST filter by `customer` or `account`
- **REQUIRED**: Validate user has access to requested resource
- **FORBIDDEN**: `.objects.all()` without customer filter
- **FORBIDDEN**: Trusting user-provided IDs without validation
- **FORBIDDEN**: Cross-tenant data exposure

### Credential Management
- **REQUIRED**: Use `create_cloud_cred_loader()` for all cloud credentials
- **REQUIRED**: Call `.load_db_credentials()` before `.get_env_values()`
- **REQUIRED**: Pass credentials to cloud SDKs explicitly
- **FORBIDDEN**: `os.getenv()` for cloud credentials
- **FORBIDDEN**: Hardcoded credentials anywhere
- **FORBIDDEN**: Credentials in logs

---

## 🏗️ ARCHITECTURE REQUIREMENTS

### Multi-Cloud Feature Structure (MANDATORY)
```
feature_name/
├── __init__.py
├── views.py                    # API endpoints (< 300 lines)
├── agent.py                    # Agent orchestration
├── base/
│   ├── __init__.py
│   └── feature_manager.py      # Abstract base class with @abstractmethod
├── providers/
│   ├── __init__.py
│   ├── aws_manager.py          # AWS implementation
│   └── azure_manager.py        # Azure implementation (can be stub)
├── tools/
│   ├── __init__.py
│   ├── common_tools.py         # Provider-agnostic tools
│   ├── aws_tools.py            # AWS-specific tools
│   └── azure_tools.py          # Azure-specific tools (can be stub)
├── prompts/
│   ├── AWSFeature.md           # AWS-specific prompts
│   └── AzureFeature.md         # Azure-specific prompts (can be stub)
└── utils/
    ├── __init__.py
    └── helpers.py
```

### Abstract Base Class Requirements
- **REQUIRED**: Inherit from `ABC`
- **REQUIRED**: Use `@abstractmethod` for all cloud-specific methods
- **REQUIRED**: Accept `credentials_loader`, `customer`, `account` in `__init__`
- **REQUIRED**: Define consistent interface for all providers
- **FORBIDDEN**: Implementation details in base class

### Provider Implementation Requirements
- **REQUIRED**: Inherit from abstract base class
- **REQUIRED**: Implement ALL abstract methods
- **ALLOWED**: Stub implementations with `raise NotImplementedError("Azure support coming soon")`
- **REQUIRED**: Initialize cloud SDK client in `__init__`
- **REQUIRED**: Use `self.credentials_loader.get_env_values()` for credentials

### Factory Pattern Requirements
- **REQUIRED**: Provider selection based on `account.cloud_provider`
- **REQUIRED**: Raise `ValueError` for unsupported providers
- **REQUIRED**: Return provider-specific manager instance
- **LOCATION**: In `agent.py` or `views.py`

---

## 🔐 AUTHENTICATION RULES

### Two Separate Authentication Systems
**Frontend/Customer APIs**:
- **CLASSES**: `CookieJWTAuthentication`, `CustomIsAuthenticated`
- **ACCESS**: `request.user` is `User` instance
- **ACCESS**: `request.user.customer` for customer context
- **SCOPE**: Customer can only access their own data

**Admin Portal APIs**:
- **CLASSES**: `CookieJWTAdminAuthentication`, `CustomIsAdminAuthenticated`
- **ACCESS**: `request.user` is `AdminUser` instance
- **ACCESS**: Can access any customer's data via `customer_id` parameter
- **SCOPE**: Admin has cross-customer access

**Dual Access APIs**:
- **CLASSES**: Both auth classes in list
- **REQUIRED**: Type checking with `isinstance(request.user, AdminUser)`
- **LOGIC**: Separate code paths for admin vs customer

### Cookie Management
- **REQUIRED**: Set `httponly=True` for all auth cookies
- **REQUIRED**: Set `secure=True` in production
- **REQUIRED**: Set `samesite='Lax'` or `'Strict'`
- **FORBIDDEN**: Storing sensitive data in cookies

---

## Security Critical Patterns

### Credential Management

**When writing**: ALWAYS use credentials_management module:

```python
from manage_user.credentials_management import create_cloud_cred_loader

# Step 1: Create loader
cred_loader = create_cloud_cred_loader(
    cloud_provider=account.cloud_provider,
    user=request.user,
    account=account,
    customer=customer
)

# Step 2: Load credentials (MANDATORY before using)
cred_loader.load_db_credentials()

# Step 3: Get environment variables
env_vars = cred_loader.get_env_values()
# Returns: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.

# Step 4: Use with cloud SDKs
client = boto3.client('ec2',
    aws_access_key_id=env_vars['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=env_vars['AWS_SECRET_ACCESS_KEY']
)
```

**Never**:
```python
# ❌ FORBIDDEN - Direct credentials
client = boto3.client('ec2',
    aws_access_key_id='AKIAIOSFODNN7EXAMPLE',
    aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
)

# ❌ FORBIDDEN - Environment variables directly
import os
key = os.getenv('AWS_ACCESS_KEY_ID')
```

### Multi-Tenant Isolation (CRITICAL)

**When writing**: EVERY database query MUST filter by customer/account:

```python
# ✅ CORRECT - Filtered by customer
def get_customer_scans(customer):
    scans = ComplianceScan.objects.filter(customer=customer)
    return scans

# ✅ CORRECT - Validate ownership
def get_scan_detail(scan_id, customer):
    try:
        scan = ComplianceScan.objects.get(id=scan_id, customer=customer)
    except ComplianceScan.DoesNotExist:
        raise PermissionDenied("Scan not found")
    return scan

# ❌ FORBIDDEN - No customer filter
def get_all_scans():
    return ComplianceScan.objects.all()  # Data leak!

# ❌ FORBIDDEN - Trust user input without validation
def get_scan(scan_id):
    return ComplianceScan.objects.get(id=scan_id)  # Any customer's scan!
```

**When reviewing**: Flag any query without customer/account filter

### Centralized Storage (CRITICAL)

**When writing**: ALWAYS use `StorageConfig` for all file uploads, downloads, and URL generation:

```python
from common.StorageConfig import StorageConfig

# ✅ CORRECT - Use StorageConfig for all storage operations
storage = StorageConfig(customer)  # Loads provider from DB automatically

# Upload bytes content and get presigned URL
result = storage.upload(
    content=b"file content",
    key="compliance/deviations/123/proof.pdf",
    ttl_hours=1,
    content_type="application/pdf"
)
presigned_url = result['presigned_url']  # Time-limited download URL
storage_key = result['key']              # Store THIS in DB, not the URL

# Upload from file-like object (Django request.FILES)
result = storage.upload_fileobj(
    fileobj=request.FILES['upload'],
    key="reports/2024_report.xlsx",
    ttl_hours=24,
    content_type="application/vnd.openxmlformats-officedocument.spreadsheet+xml"
)

# Upload from disk
result = storage.upload_file(
    filepath="/tmp/diagram.png",
    key="diagrams/architecture.png",
    ttl_hours=24,
    content_type="image/png"
)

# Generate presigned URL at READ time (never store URLs in DB)
storage_key = deviation.proof_storage_key  # Store keys, NOT URLs
presigned_url = StorageConfig(customer).generate_presigned_url(
    key=storage_key,
    ttl_hours=1
)

# Delete from storage
StorageConfig(customer).delete(key=storage_key)
```


**Never**:
```python
# ❌ FORBIDDEN - Raw boto3 uploads
s3 = boto3.client('s3', ...)
s3.upload_fileobj(file, bucket, key)
presigned_url = s3.generate_presigned_url(...)
# Store presigned_url in DB  ← DEAD URL after expiry!