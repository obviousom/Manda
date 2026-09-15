# Feature: RunBooks

## Context

RunBooks app (`Codly_Backend/runbooks/`) — multi-step automation flows triggered by AWS events (e.g. EC2 create), executed via `agent_hub_agent`, `ai_ops_action`, `script_runner`, `wait_delay`, `human_checkpoint`, `notify_email_ses` step types. Cross-customer cloning via `install_runbook_template()`.

## RunBooks Built/Modified This Session

| RunBook | Customer | Env | ID | Steps | Status | Notes |
|---|---|---|---|---|---|---|
| Codly.ai POC Deployment RunBook | Codly | Staging | `dc111fb7-bb0e-4d70-9e79-3f0b33f75158` | 33 | — | DB image fixed to `codly_db:prod_05_march-20260827-114721`; removed bad `Environment=POC` tag instruction (was blocking OS suggestion) |
| Codly.ai POC Deployment RunBook (clone) | — | Local dev (`om_26_june`) | `cb366650-8238-453d-b865-8ed891139a13` | 32 | — | Same as above, correct DB image from start |
| Post Ec2 workflow for deployment (clone) | Acme | Prod | `084f894d-634b-4c7a-82ee-73939da2e35b` | 10 | active | Cloned from Codly `c731b3ec-4a56-4dc2-b8ad-23c44366b9c4`; confirmed real completed run `6edea1bb-...` against Acme Account id=46 |
| EC2 Post-Deploy: Storage, IAM, Patch & Backup | Codly | Prod | `b0d45fc3-b0d4-4169-a346-4268215d0c5c` | 15 | draft | New build: create_ec2 trigger → wait → AZ check → EBS create+attach → wait → IAM role create+attach → wait → AWS CLI v2 install → internet check → Patching Agent → Install Antivirus → backup → email vishal@allysense.ai. Account = Codly id=1 |
| EC2 Post-Deploy: Storage, IAM, Patch & Backup (clone) | Acme | Prod | `c28b1d2f-fecc-413d-afc5-d09556324682` | 15 | draft | Cloned via `install_runbook_template()`, agent_hub_agent steps remapped to Acme-owned copies. Attached to ALL Acme AWS accounts: id=46 "AWS Test Account", id=49 "Log Archive", id=50 "Log Archive" (id=47 Azure skipped — not AWS) |

## Known Bugs Found (this feature area)

- **#2069** — AI Ops "OS" suggestion queries nonexistent AMI tag convention (`inventory/agents.py::inline_cli_suggestion_agent`). Broader fragility real; specific tested repro's proximate cause was self-inflicted `Environment=POC` RunBook instruction (removed). Issue not yet updated with this nuance.
- **#2073** — `script_runner` steps target wrong resource: `ai_ops_action.py` never normalized CloudFormation-style resource type strings (`AWS::EC2::Instance`) to the canonical `"ec2_instance"` key `RunContext.get_resource_id()` matches on. Fix written, committed to branch `fix/runbooks-ai-ops-action-resource-type-mismatch/staging/2026-09-08/2073` (commit `c98fa1c9`) — **NOT pushed, no PR yet** (paused on "stop").

## Open Questions / TODO

- [ ] Push #2073 fix branch + open PR (codly-workflow: PR from template, add screenshot evidence + reasoning after)
- [ ] Decide whether to add correction comment to #2069 (proximate cause was self-inflicted, not purely platform bug) — not yet requested by user
- [ ] Activate `c28b1d2f-...` (Acme clone) and `b0d45fc3-...` (Codly source) in admin portal — currently draft
- [ ] Test current flow end-to-end (this session's task — see below)

## Test Log

(append results here as flow gets tested)
