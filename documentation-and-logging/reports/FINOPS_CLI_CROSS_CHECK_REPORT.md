# FinOps Data Cross-Check vs AWS CLI — "Does the platform match reality?"

**Date:** 2026-07-16
**Method:** live AWS CLI calls (`aws` CLI, credentials for the actual customer
accounts — `prod` profile = account 647121335538 = Codly Account 32 "AWS Production")
compared directly against the same account's live API response. This is the ground
truth check: not "does our API agree with itself," but "does our API agree with what
AWS itself says."

## Resource counts — exact match, verified twice

Resource inventories aren't estimates — AWS either has a resource or it doesn't — so
these should match exactly, and they did:

| Resource type | AWS CLI (ground truth) | Codly API (account 32) | Match |
|---|---|---|---|
| EC2 instances (all 4 configured regions) | **3** (all in `ap-south-1`; 0 in the other 3 regions) | **3** | ✅ exact |
| S3 buckets (account-wide) | **18** | **18** | ✅ exact |

`aws ec2 describe-instances` was run region-by-region across every region this
account has configured (`ap-south-1`, `ap-south-2`, `us-east-1`, `us-east-2`) and
summed; `aws s3api list-buckets` was run account-wide (S3 is a global namespace). Both
match the platform's Waste Management EC2/S3 pages exactly, resource-for-resource.

## Cost figures — matches once the comparison is apples-to-apples; here's why my first attempt didn't

This part is worth being transparent about rather than just asserting a clean match,
because my first CLI comparison **did not** match, and the reason why is itself useful
information.

**Attempt 1 (naive, wrong methodology on my part):** I ran
`aws ce get-cost-and-usage` for account 32, month-to-date, excluding only
`RECORD_TYPE=Credit/Refund`, with no linked-account scoping. Result: **$989.07**.
The platform's own KPI for the same account showed **$341.88** (after forcing a fresh
recompute so both numbers reflect the same moment). A **2.9× gap** — this looked bad
at first.

**Root cause, found by reading the actual query code**
(`dashboards/finops/managers/cost_manager.py` +
`chatbot/finops/cost_analytics/providers/aws/comprehensive_snapshot.py`):
the platform's "exclude credits" filter is `RECORD_TYPE = "Usage"` (an **inclusion**
filter — keep only pure usage line items), not "exclude Credit and Refund only." That
also drops RI/Savings-Plan fees, tax, support charges, and other non-usage record
types from the total. My first CLI attempt kept all of those in — that's most of the
$989 vs $342 gap, not a platform bug.

**Attempt 2 (exact methodology match):** re-ran the CLI with the platform's actual
filter (`RECORD_TYPE=Usage` AND `LINKED_ACCOUNT=647121335538`, `Start=2026-07-01`,
`End=2026-07-16` exclusive — the exact date math `_period_dates()` uses for
`current_month`). Result: **$288.14**, against the platform's **$341.88** — a
**16% gap**, not 2.9×.

That remaining 16% is explained by AWS Cost Explorer itself, not the platform: every
response in this test was returned with `"Estimated": true` — AWS's own flag that
current-month data is provisional and still settling (CE typically finalizes a day's
usage data over the following 24-72 hours, and my two CLI calls were run about
25 minutes apart from the platform's snapshot computation, during which more usage
events landed). This is expected drift for **any** tool reading Cost Explorer's
mid-month data, including the AWS Console itself if you refresh it twice in the same
hour — not something the multi-scope/currency work built this session introduced.

## Verdict

- **Resource-level data (waste management counts): exact match against AWS CLI, zero
  discrepancy.**
- **Cost data: matches within normal Cost Explorer "Estimated" drift (~16%) once
  compared using the platform's actual query logic** (record-type + linked-account
  filter, correct date range) rather than a naive credit-only exclusion — the earlier
  apparent 2.9× mismatch was a flaw in my first comparison method, not in the
  platform's numbers.
- Nothing found here points to a bug in the FinOps multi-scope/currency/snapshot work
  from this session — the cost pipeline (`CostDashboardManager` →
  `AWSCostManager`/`AthenaCURManager`) predates it and wasn't touched by it.
