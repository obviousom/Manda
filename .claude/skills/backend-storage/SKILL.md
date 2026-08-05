---
name: backend-storage
description: File storage patterns for Codly Backend — StorageConfig unified S3/Azure Blob upload/download. Use when uploading files, reports, or attachments to cloud storage.
---

# Codly — File Storage

## StorageConfig — unified S3 / Azure Blob

```python
from common.StorageConfig import StorageConfig

storage = StorageConfig(
    customer=customer,
    account=account,
    cred_loader=cred_loader,
)
```

## Upload file

```python
# Upload bytes/file object
url = storage.upload_file(
    file_data=pdf_bytes,           # bytes or file-like object
    file_name="report_2024_01.pdf",
    content_type="application/pdf",
    folder="reports/finops/",      # optional folder prefix
)
# Returns public/presigned URL
```

## Download file

```python
data = storage.download_file(
    file_name="report_2024_01.pdf",
    folder="reports/finops/",
)
# Returns bytes
```

## Upload from local path

```python
with open(local_path, "rb") as f:
    url = storage.upload_file(
        file_data=f,
        file_name=os.path.basename(local_path),
    )
```

## Storage config by provider

StorageConfig auto-detects provider from `account.cloud_provider`:
- **AWS** → S3 bucket (configured per customer/account)
- **Azure** → Azure Blob Storage container

Credentials loaded from `cred_loader` — no hardcoded bucket names.

## Common use cases

```python
# Save compliance PDF report
url = storage.upload_file(
    file_data=pdf_bytes,
    file_name=f"compliance_report_{scan.scan_id}.pdf",
    folder="compliance/reports/",
    content_type="application/pdf",
)

# Save cost analysis CSV export
url = storage.upload_file(
    file_data=csv_data.encode("utf-8"),
    file_name=f"cost_report_{session_id}.csv",
    folder="finops/exports/",
    content_type="text/csv",
)
```

Return the URL to the user/agent via the response dict.
