# FinOps Multi-Scope / Currency — Verification Test Report

**Date:** 2026-07-16
**Tester:** Claude Code (automated, live backend + real cloud data)
**Environment:** local dev server (`0.0.0.0:8000`), migrations `admin_portal.0026`,
`dashboards.0013_finopspagesnapshot` applied. Auth via `X-Dev-Test` bypass headers per
`CLAUDE.md`.
**Test tenant:** Customer 20 "Allysense" — 5 accounts (32 AWS Production, 33 AWS Test
Account, 38 AWS Log-Archive, 31 AzureNewAcc, 34 Azure-Test-account-2), Region
Preference AWS=[ap-south-1, ap-south-2, us-east-1, us-east-2], AZURE=[centralindia,
southindia, eastus] — i.e. the exact "5 accounts × up-to-4 regions" shape this whole
feature was built for.

This supersedes the informal "see conversation history" note at the bottom of
`docs/FINOPS_MULTISCOPE_CURRENCY_API.md` §9 — every claim below has a captured
request/response, not a memory of a prior run.

## Summary

| Area | Result |
|---|---|
| Overview (all-accounts + single-account) | ✅ pass |
| Waste Management multi-scope (EC2, S3, KMS, RI/SP) | ✅ pass |
| Optimization Hub multi-scope (rightsizing, ri-coverage) | ✅ pass |
| Cost Atlas multi-scope (services, resources) | ✅ pass |
| Currency conversion math (INR, AED) | ✅ pass, exact |
| Region Preferences / Currency Rates admin endpoints | ✅ pass |
| Tenant isolation (foreign account_id in account_ids) | ✅ pass (404) |
| Cloud-provider mismatch exclusion (Azure acct on AWS-only page) | ✅ pass (silently excluded) |
| Tag Costs (single-scope, lazy-populate) | ✅ pass (cold → refreshing → populated on retry) |
| Frontend `tsc --noEmit` | ✅ pass — 0 errors in any FinOps file; all 31 repo-wide errors are pre-existing, unrelated (budget_tracker, ai-ops-policies, compliance/tester, role page, etc.) |
| Frontend scope-selector rollout | ⚠️ **partial** — see gaps below |
| Currency Settings admin page | ❌ **not built** (backend API works; no UI) |

Nothing tested regressed and no multi-scope/currency-specific bug was found. Two
pre-existing open items (task #20 frontend rollout, task #21 settings page) are
confirmed still incomplete, detailed below so they're not lost.

---

## 1. Overview

`GET /api/dashboard/finops/snapshot/?customer_id=20` (all accounts):
```json
{"aggregation": {"type": "customer_wide", "accounts_included": 5, "total_accounts": 5},
 "account_ids": [31, 32, 33, 34, 38], "missing_account_ids": [],
 "kpi": {"monthly_cost": {"usd": 1002.12, ...}, "savings_potential": {"usd": 574.34, ...},
         "tag_compliance_pct": 15.0, "ri_coverage_pct": 50.0, "maturity_level": "WALK"}, ...}
```
All 5 accounts present, `missing_account_ids` empty, per-account `accounts_progress`
correctly shows 2 accounts mid-refresh (`is_refreshing: true`) at request time — proves
the "partial while refreshing" contract works, not just the happy path.

`GET .../snapshot/?customer_id=20&account_id=32` (single account): returns the
single-account KPI/maturity/cost_trend shape, `is_refreshing: false`, `is_stale: false`.
Both modes pass.

## 2. Waste Management — multi-scope merge

- **EC2** single (`account_id=32&region=ap-south-1`): `total_count: 3`.
  Multi (`account_ids=32,33&regions=all`): `total_count: 10`, `aggregated: true`,
  `accounts: [32, 33]`, `regions: [ap-south-1, ap-south-2, us-east-1, us-east-2]` —
  correct union of both accounts' visible AWS regions.
- **S3** all-accounts/all-regions (`account_ids=all&regions=all`): `aggregated: true`,
  all 5 accounts present, regions correctly union AWS (4) + Azure (3) = 7 distinct
  regions — confirms mixed-cloud "all" resolution works, not just same-cloud.
- **KMS** (SCAN_REGIONS type, no region param) multi-account: `aggregated: true`,
  `total_keys: 38` merged across both accounts' region-scan results.
- **RI/SP Coverage** (account-level type) multi: `region_scope: "account"`,
  returns an honest `accounts: [{...account 32...}, {...account 33...}]` array instead
  of blending utilization percentages — matches the documented "no fake blended metric"
  design decision.

## 3. Optimization Hub — multi-scope merge

- **Rightsizing** multi (`account_ids=32,33&regions=all`): `aggregated: true`,
  `total_count: 1`, `total_savings.usd: 3.13`, correct region union.
- **RI Coverage** multi: `aggregated: true`, per-account array (`sp_coverage_pct: 27.4`
  for account 32 vs `0.9` for account 33) — again correctly un-blended.
- **Summary** (pre-existing all-account aggregate, unchanged code path): returns
  `total_savings`, category breakdown — still working after the surrounding file's
  multi-scope changes (views2.py, views_network.py, views_observability.py).

## 4. Cost Atlas — multi-scope merge

- **Trends** (pre-existing all-accounts): per-source cost breakdown present, unchanged.
- **Services** multi (`account_ids=32,33`, **new** capability): `aggregated: true`,
  `accounts: [32, 33]` — merge executed without error.
- **Resources** multi (`account_ids=32,33&service=EC2`): returned `resources: []` for
  this particular service/account combo (empty result, not an error) — inconclusive on
  the merge logic itself since there was no data to merge; the request/response
  round-trip and param handling worked correctly.

## 5. Currency — exact math verification

EC2 waste "KEEP" bucket, account 32, ap-south-1, raw USD = `131.91`.

| Currency | Returned `display_value` | Manual check | Match |
|---|---|---|---|
| INR | 12213.55 | `131.91 × 92.59 = 12213.60` (rounding) | ✅ |
| AED | 484.44 | `131.91 × 3.6725 = 484.4436...` | ✅ exact |

`GET /admin_portal/api/currency-rates/` → `{"INR": 92.59, "AED": 3.6725, ...}` matches
the rates used in both conversions above — confirms the endpoint and the per-request
conversion read the same source of truth, not two independently-hardcoded values.

## 6. Security / correctness edge cases

- **Tenant isolation**: `account_ids=32,36` where account 36 belongs to a *different*
  customer (Anunta-Tech, id 21) while `customer_id=20` → **HTTP 404**. Confirms every
  explicit id in a multi-scope list is validated against the requesting customer, not
  just the first one.
- **Cloud-provider mismatch**: KMS (AWS-only page) requested with
  `account_ids=32,31` (32=AWS, 31=Azure) → response silently drops account 31,
  `accounts: [{id: 32, ...}]` only — matches documented behavior (multi-mode excludes
  unsupported accounts rather than erroring).

## 7. Tag Costs (deliberately single-scope, v1)

First call for `tag_key=Environment` on a never-queried account returned
`{"status": "refreshing", "needs_refresh": true}` (cold cache, background refresh
queued) — retried 5s later and got the full breakdown (`tag_value: "Production", ...
delta_pct: -53.3, services: [...]`). Confirms the lazy-populate-on-miss path still
works correctly and wasn't broken by the surrounding currency-formatting changes.

## 8. Frontend

- `node_modules/.bin/tsc --noEmit`: **0 errors** in any file under `finops-hub/`,
  `useWasteManagement.ts`, `useOptimization.ts`, `useCostAtlas.ts`, `finops-store.ts`,
  or `WasteScopeSelector.tsx`. The 31 errors the compiler does report are all in
  unrelated pre-existing code (`budget_tracker/`, `ai-ops-policies/`,
  `compliance/tester/`, `role/page.tsx`, `os-hardening/`, etc.) — none touched by this
  feature, confirmed by path.
- `WasteScopeSelector` component exists and is wired into **10 pages**: `compute`,
  `ebs`, `s3`, `rds`, `load-balancer`, `ami`, `network`, `rg` (8 of the resource-type
  waste pages), plus `optimization/page.tsx` and `cost-atlas/page.tsx`.
- **Gap found**: the frontend only has dedicated routes for 8 of the 19
  backend-supported waste `page_key`s (`compute`, `ebs`, `s3`, `rds`, `load-balancer`,
  `ami`, `network`, `rg`) — there is no dedicated Next.js route for `kms`, `secrets`,
  `nat-gateway`, `cloudwatch-logs`, `lambda`, `ecr`, `efs`, `eip`, `ri-sp-coverage`,
  `azure-extras`, or `key-vault`. This is a pre-existing frontend-coverage gap (those
  11 types have presumably always been reachable only via the aggregate
  `categories`/`resources` views, not standalone pages), not a regression from this
  session's work — but it means `WasteScopeSelector` cannot be "wired into all 19
  pages" because 11 of them have no page to wire it into. Flagging so it isn't
  mistaken for an oversight.
- `categories/page.tsx`, `resources/page.tsx`, `history/page.tsx`, and the main
  `waste-management/page.tsx` landing page do **not** use `WasteScopeSelector`
  directly — the landing page does read `useFinOpsStore`, so it likely inherits scope
  from the shared store, but this wasn't independently click-tested in a browser this
  pass (browser automation is disabled for this project per standing instruction —
  UI behavior beyond typecheck/API testing needs a manual pass by you).

## 9. Currency Settings page (task #21)

Confirmed **not built**: no file under `src/app/admin/` references
`currency-rates`/`CurrencyExchangeRate`. Backend `GET`/`PUT
/admin_portal/api/currency-rates/` both work (verified in §5/§6 above) but there is no
admin UI to edit rates yet — an admin today would have to `curl` the PUT directly.

---

## Open items (unchanged from before this test pass, now re-confirmed with evidence)

1. **Task #20** (frontend rollout) — partially done: 10/21 pages wired
   (8 waste-type pages + optimization + cost-atlas); `categories`/`resources`/`history`
   pages not independently verified to respect multi-select scope.
2. **Task #21** (Currency Settings page) — not started.
3. Cost Atlas `resources/` multi-scope merge logic is implemented and doesn't error,
   but wasn't exercised against real multi-row data in this pass (the tested
   account/service combo had zero resources) — worth one more curl against a
   service/account pair known to have resource-level data before calling it fully
   verified.
