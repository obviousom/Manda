---
name: backend-compliance
description: Compliance scan patterns for Codly Backend — ComplianceScan model, scan lifecycle, WebSocket progress, agent architecture (AWS/Azure/GCP), framework/point structure. Use when working on compliance/ app.
---

# Codly — Compliance

App: `compliance/`

## Key models

```python
from compliance.models import (
    ComplianceScan,
    CompliancePointScanResult,
    ComplianceFramework,
    ComplianceCategory,
    ComplianceService,
    ComplianceResourceType,
    ComplianceObjective,
    CompliancePoint,
    ComplianceDeviation,
)
```

### ComplianceScan — scan run

```python
scan.scan_id              # UUID, unique scan identifier
scan.account_id           # int — related Account.id
scan.customer_id          # str — related Customer.id
scan.cloud_provider       # "AWS" | "AZURE" | "GCP"
scan.status               # "pending" | "in_progress" | "completed" | "failed"
scan.total_points         # Total CIS/STIG points to check
scan.completed_points     # Points checked so far
scan.failed_points        # Points that errored
scan.skipped_points       # Points with no resources (skipped)
scan.progress_percentage  # 0.0 – 100.0
scan.compliance_frameworks.all()  # ManyToMany to ComplianceFramework
scan.created_at, scan.completed_at
```

### Querying scans (always filter by customer)

```python
from compliance.models import ComplianceScan

# Latest scan for an account
scan = ComplianceScan.objects.filter(
    customer_id=str(customer.id),
    account_id=account.id,
).order_by("-created_at").first()

# All completed scans
scans = ComplianceScan.objects.filter(
    customer_id=str(customer.id),
    status="completed",
).select_related()

# Specific scan by UUID (validate customer ownership)
scan = ComplianceScan.objects.get(
    scan_id=scan_id,
    customer_id=str(customer.id),
)
```

## Scan lifecycle

```
pending → in_progress → completed
                      ↘ completed_with_errors
                      ↘ failed
```

Status updates via `update_scan_status()` utility + WebSocket:

```python
from compliance.compliance_dashboard.utils import (
    update_scan_status,
    send_websocket_update,
    send_point_event,
    send_resource_event,
)

# Update scan status
update_scan_status(scan, status="in_progress", completed=10, total=100)

# Send live progress to frontend WebSocket
send_websocket_update(
    scan_id=str(scan.scan_id),
    event_type="progress",
    data={"progress": 45, "message": "Scanning IAM policies..."},
)

# Send point-level event
send_point_event(scan_id=str(scan.scan_id), point_id=point.id, status="completed")
```

WebSocket endpoint: `ws/compliance/scan/<scan_id>/`

## Architecture

```
compliance/
├── views.py                     # Thin routing — start scan, get results
├── models.py                    # ComplianceScan, CompliancePoint, etc.
└── compliance_dashboard/
    ├── scan_view.py             # Main scan orchestration
    ├── scan_view_2.py           # Part 2 (>1500 line split)
    ├── utils.py                 # send_websocket_update, update_scan_status
    ├── controls_service.py      # Framework/point lookup service
    ├── tasks.py                 # Celery tasks for async scan execution
    ├── aws_compliance/
    │   ├── agents.py            # AWS compliance agent swarm
    │   ├── agents_part2.py
    │   ├── tools.py             # AWS CLI tool wrappers
    │   └── helper_functions.py  # Resource list collection, CLI execution
    ├── azure_compliance/
    │   ├── agents/              # Multi-file agent split
    │   │   ├── analyzer_agent.py
    │   │   ├── scanner_agent.py
    │   │   ├── resource_list_collector_agent.py
    │   │   └── remediation_agent.py
    │   ├── tools.py
    │   └── helper_functions.py
    └── gcp_compliance/
        ├── agents.py
        ├── tools.py
        └── helper_functions.py
```

## ComplianceFramework hierarchy

```
ComplianceFramework (e.g., "CIS AWS Foundations Benchmark v1.4")
└── ComplianceCategory (e.g., "Identity and Access Management")
    └── ComplianceObjective (e.g., "Ensure MFA is enabled for root account")
        └── CompliancePoint (individual check — has CLI command, expected result)
```

## Starting a scan programmatically

```python
from compliance.compliance_dashboard.scan_view import start_scan

result = start_scan(
    customer=customer,
    account=account,
    user=request.user,
    region="us-east-1",
    framework_ids=[1, 2],   # ComplianceFramework PKs
    scan_type="full",        # "full" | "resource_specific"
)
# Returns {"scan_id": "...", "status": "pending"}
```

## CompliancePointScanResult

Per-point result for each scan:

```python
point_result = CompliancePointScanResult.objects.filter(
    scan=scan,
    status="failed",
).select_related("scan")

point_result.point_id     # CompliancePoint PK
point_result.point_name   # Human-readable name
point_result.status       # "pending" | "scanning" | "completed" | "failed" | "skipped"
point_result.cli_command  # CLI command executed
```
