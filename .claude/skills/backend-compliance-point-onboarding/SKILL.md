---
name: backend-compliance-point-onboarding
description: How to add a new compliance point to staging through the API and the Compliance Tester agent, review and fix the AI-generated CLI, commit it, and verify it with a real scan. Use when asked to add, import or test a new compliance policy/point (for example a vendor policy pasted as text), or when working with compliance_tester_app sessions.
---

# Compliance Point Onboarding (API + Tester)

No code change and no migration. A point is data: create the row through the API, let the Tester generate the scan script and remediation, review them by hand, commit, then prove it with a scan. Proven on point 1803 (Pentoo IAM), 2026-10-09.

Staging writes follow the `server-access` skill: read-only unless the user approves each write. Never put passwords in this file or in a PR.

## 0. Before creating anything

1. **Look for duplicates and siblings.** Log in to staging and `GET /api/compliance-tester/points/?search=<word>`. It searches title and description of **active** points only; an inactive duplicate is invisible to it. Sibling points are the best template (script style, frameworks, categories).
2. **Reformat the title** to start with "Ensure ..." (older points do) and make it a pass condition.
3. **Check lookup values exist:** `GET /api/compliance-tester/lookup-data/?cloud_provider=AWS` lists categories, services, resource types and frameworks. Reuse names; do not create near-duplicates.
4. **Source columns with no field** (vendor policy id, "audit_event") go in `note`.

## 1. Create the point

`POST /compliance/compliance_dashboard/points/create/` (admin only). Body: `compliance_point`, `description`, `cloud_provider`, `severity`, `remediation_type`, `category: []`, `service: []`, `resource_type: []`, `note`, `steps_to_remediate`, `recommendations`, `customer_ids: [id]`. Omit `eligible_account_ids` for all of the customer's accounts.

Gotchas:
- The endpoint forces `is_customPoint=true` and **overwrites frameworks with Corporate Governance**. Set the real frameworks later through a tester commit.
- `point_id` is assigned by `save()`; read it from the response.
- Leave `deployement_phase` empty unless the point must run in resource-specific scan, Smart Scan and the "points filtered during deployment" list. Those three filter on exactly `during_deployment`; a null hides the point from them. Siblings leave it empty.

## 2. Tester session

Prefix `/api/compliance-tester/`. **Every tester endpoint uses `request.user.customer`.** A super-admin or MSP user has `customer = None`, so sessions fail with "Account not found" and the accounts list is empty. Use a customer-bound user. Setting `customer` on a user is a staging DB write: ask first, record the old value, revert afterwards, and call `cacheops.invalidate_model(User)` (the ORM cache serves the stale row after a queryset `.update()`).

Also: `GET accounts/` returns 500 for a customer-bound user (`views.py` reads `acc.region`, `Account` has no such field). Skip it; take the account id from `/manage_user/protected/`.

Flow:
1. `POST sessions/` with `{name, point_ids, cloud_provider, account_id}`.
2. `POST sessions/{id}/analyze-all/`. On staging via localhost it runs **synchronously** (the dev check matches "localhost"), so start it in the background and poll `GET sessions/{id}/`. Three steps: metadata, scan script, remediation.
3. **Review every generated field.** See section 3.
4. Accept = `POST sessions/{id}/staged/` with `{point_id, analysis_step, approved_fields}`. Use your corrected values.
5. Optional: `POST sessions/{id}/run-scan-tester/` with `{point_ids, human_hint}` (see section 4).
6. `POST sessions/{id}/commit/`. Commit applies exactly what is staged.
7. **Verify the committed point** (`GET points/{id}/`) and the audit log (`GET audit/{id}/`). On 1803 the first commit wrote the agent's severity and a dangerous remediation script over the values I had staged (the scan tester run likely re-staged them). If the point is wrong, open a new session, stage only the corrected fields, and commit again. Do not run analysis or the scan tester in that session. Each audit entry can be rolled back.

## 3. What to check in the generated CLI

The AI output is a draft. Known failure patterns:
- **Wrong region.** Global services (IAM, Route 53, CloudFront, Organizations) record CloudTrail events only in `us-east-1`. A `<region>` placeholder silently passes elsewhere.
- **No window, no pagination.** `--max-results 50` checks only the newest 50 events. Use a `--start-time` window and let the CLI paginate.
- **Guessing event names by prefix.** Misses `Set*`, `Tag*`, `Enable*`, `Change*`. Prefer `readOnly`.
- **CloudTrail `lookup-events` is slow on read-heavy sources.** Filtering `EventSource=iam.amazonaws.com` pages through every List/Get call (over 280 s for one day on the test account). Use `AttributeKey=ReadOnly,AttributeValue=false` and filter the source in `jq`: 33 s for 30 days.
- **Missing `resource_fetching_cli` and `mapping_dict`.** Without them the scanner has no resource list. Account-level checks use `aws sts get-caller-identity --query '[{AccountNumber:Account}]' --output json` with `placeholder_list ['<account-id>']` and `mapping_dict {'AccountNumber': '<account-id>'}` (see point 316). System-filled placeholders: `ACCOUNT_ID, REGION, SUBSCRIPTION_ID, PROJECT_ID, LOCATION`.
- **Output contract.** The last line must be `true` (compliant) or `false`. The script must contain `echo "true"` or `echo "false"`.
- **Dangerous remediation.** Never accept an automated script that changes IAM or blocks a principal. Detection points use `remediation_type: manual`, `remediation_enabled: false`, a no-op script ending in `echo "true"`, and numbered human steps.
- **Severity drift.** Keep the source policy's severity.
- Match the style of siblings and point 316; check the metadata the agent adds (categories, frameworks) against siblings.

## 4. Testing

- The scan tester creates a compliant and a non-compliant resource, runs the script on each (Test A then Test B), retries up to 3 times, and stages what it fixes. It uses **CLI tools only**, so it cannot set a request header or user agent. For audit-event points it created unrelated resources and Test B failed correctly.
- For a user-agent check, create the trigger yourself: `AWS_EXECUTION_ENV=<marker> aws iam create-user ...` puts `exec-env/<marker>` into the CloudTrail user agent. Use a harmless, uniquely named object and delete it after.
- For **per-resource** points (for example IAM roles), create the compliant, non-compliant and out-of-scope resources yourself, then run the scan tester with a `human_hint` that names them and says "do not create new resources; discover them with execute_cli and register them". It then passes cleanly (point 1804: Test A `true`, Test B `false`). The scan tester re-stages fields, so **re-stage your reviewed values right before commit** and verify the committed point.
- Before trusting a script, run it locally (read calls only) on every test resource, plus a wildcard case (`iam:Attach*`) and an out-of-scope case.
- Take the detection logic from the nearest sibling (point 1801 detects Okta roles by trust-policy provider name or SAML metadata; point 1724 has the policy-management action list) instead of the agent's version, which can be syntactically broken (point 1804: a literal `(aws_placeholder)` in the script).
- CloudTrail `lookup-events` lags a few minutes. Poll the script locally (read calls only) until it flips.
- An **account-wide** check has one resource, the account. It cannot be compliant while the trigger event is inside the window. Prove the compliant direction on another account, or before creating the event.
- Rerun a real scan from the dashboard on the test account and read `GET /compliance/compliance_dashboard/results/{scan_id}/points/{point_id}/` (status, resources, metrics).
- Real-world detection (for example a real Pentoo host) is unproven by a synthetic marker. Say so.

## 5. Cleanup and reporting

- Delete the test objects you made in the cloud account, including the unrelated ones the scan tester created.
- Revert any user or `customer` change and invalidate the cache.
- List every staging DB, cache and AWS change made, with its state.
- This flow changes data only. Do not commit or push anything.
- Report honestly: what was proven, what was a synthetic test, what is still open (deployment phase, frameworks, promotion to beta and prod).

## Reference

- Point model: `compliance/models.py` (`CompliancePoint`). Create view: `compliance/compliance_dashboard/compliance_point_views.py`.
- Tester: `compliance_tester_app/` (`views.py`, `views_staging.py`, `managers/session_manager.py`, `agents/aws_scan_tester_agent.py`, `validators.py`).
- Templates: point 316 (CloudTrail script, account-level), points 1786 to 1788 and 1799 (audit-event family).
- Related skills: `backend-compliance`, `server-access`.
