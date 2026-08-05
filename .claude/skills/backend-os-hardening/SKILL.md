---
name: backend-os-hardening
description: OS Hardening patterns for Codly Backend — CIS/STIG scan and execution flows, SSH-based remote execution, WebSocket progress, scanner/executor architecture. Use when working on chatbot/os_hardening/.
---

# Codly — OS Hardening

App: `chatbot/os_hardening/`

## Architecture

```
chatbot/os_hardening/
├── views.py          # Thin routing — start scan, execute hardening
├── agents.py         # Main agent orchestration
├── scanner/          # CIS/STIG scan logic
├── executor/         # Remediation execution
├── configuration/    # Hardening configuration management
├── tools.py          # @tool functions for hardening
└── utils.py          # Helpers
```

## Flows

### Scan flow — read-only assessment

```
POST /chatbot/os-hardening/scan/
→ views.py → agents.py → scanner/
→ SSH into instance → run CIS/STIG checks
→ WebSocket: ws/scan-hardening/ (live progress)
→ Returns: list of pass/fail checks
```

### Execute flow — apply remediations

```
POST /chatbot/os-hardening/execute/
→ views.py → agents.py → executor/
→ SSH into instance → apply fixes
→ WebSocket: ws/execute-hardening/ (live progress)
→ Returns: list of applied/failed remediations
```

## SSH execution via common/executor

Remote VM execution uses SSH via `common/executor/cloud_script.py`:

```python
from common.executor.cloud_script import CloudScriptExecutor

executor = CloudScriptExecutor(
    instance_id=instance_id,
    region=region,
    customer=customer,
    account=account,
    cred_loader=cred_loader,
)
result = executor.execute(script="sudo cat /etc/passwd")
```

Handles both AWS SSM Session Manager and direct SSH.

## WebSocket progress

```python
# Scan progress
from chatbot.os_hardening.utils import send_hardening_progress

send_hardening_progress(
    session_id=session_id,
    progress=45,
    current_check="Checking SSH configuration",
    total_checks=120,
    status="scanning",
)
```

WebSocket endpoints:
- `ws/scan-hardening/` — scan progress consumer
- `ws/execute-hardening/` — execution progress consumer

## Tool context

OS hardening tools need SSH credentials in context:

```python
context = {
    "instance_id": instance_id,
    "region": region,
    "os_type": "linux",   # "linux" | "windows"
    "cred_loader": cred_loader,
    "customer": customer,
    "account": account,
    "session_id": session_id,
}
```

## Access level required

OS hardening requires **power_user** access level (write operations):

```python
cred_loader = create_cloud_cred_loader(
    "AWS",
    user=request.user,
    account=account,
    customer=customer,
    access_level=AccessLevel.POWER_USER,
)
```
