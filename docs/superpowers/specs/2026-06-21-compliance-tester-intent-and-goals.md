# Compliance Tester — Intent, Goals & Vision

**Date:** 2026-06-21  
**Status:** Living document — update as vision evolves

---

## Why We're Building This

Compliance point validation was a manual, brain-draining process. Engineers would:
1. Copy a CompliancePoint's metadata, CLI script, placeholders into ChatGPT
2. Ask it to review/suggest improvements
3. Manually copy output back, paste into DB, repeat for next point

This is:
- **Slow** — one point at a time, one person at a time
- **Untracked** — no audit of what changed, who changed it, why
- **Inconsistent** — no shared rules, everyone interprets "good" differently
- **Not scalable** — we have hundreds of points across AWS, Azure, GCP

**The core insight:** The human is the expert on what the final output should look like. The AI is the data-entry person with a brain. Flip the roles — AI does the grunt work, human just approves.

---

## What We're Building

An **AI-assisted Compliance Point Review Tool** — internally called **Compliance Tester**.

It works like this:
1. Human selects a batch of CompliancePoints (by service, framework, or individual search)
2. AI analyzes every field of each point against pre-configured guidelines
3. AI suggests what should change (and why)
4. Human reviews suggestions one by one: **Approve / Request Changes / Keep Existing**
5. All approved changes are staged
6. Human commits the batch in one shot
7. Every change is permanently audited: who, what field, old value, new value, when — with rollback

---

## Goals

### Primary Goals
- **Eliminate manual copy-paste** from compliance review workflow
- **Enforce consistency** through per-field guidelines that all AI suggestions must follow
- **Create audit trail** for every field change on every CompliancePoint
- **Enable rollback** — any field can be reverted to any prior value
- **Support batch operations** — review whole services at once, not one point at a time

### Secondary Goals
- **Validate CLI scripts** — catch broken `aws_cli_with_placeholders` before they run in scans
- **Auto-discover resources** for points where `resource_fetching_cli` is missing
- **Keep humans in control** — AI never applies changes without human approval
- **Multi-cloud** — AWS first, then Azure, GCP

### Non-Goals (explicit)
- AI does NOT auto-apply changes without human approval (ever)
- This is NOT a customer-facing feature
- NOT replacing the existing compliance scanner — it's a metadata review tool, not a scan runner

---

## Success Metrics

| Metric | Target |
|---|---|
| Time to review one CompliancePoint | < 2 minutes (down from 10-15 min manual) |
| Points reviewed per session | 20-50 (batch mode) |
| Fields with audit coverage | 100% after rollout |
| Rollback capability | Any field, any time |
| Consistency score | All active points pass guideline validation |

---

## Users

**Primary:** Internal Codly team (compliance engineers, DevOps)  
**Secondary:** Future: customer admins who want to customize their own compliance points

---

## Principles

1. **Human approves, AI suggests** — never the other way around
2. **Guidelines first** — before any session, field guidelines must be configured
3. **Audit everything** — no silent writes to CompliancePoint fields ever
4. **Batch-friendly** — designed for bulk review, not one-off edits
5. **Cloud-agnostic design** — backend structured for AWS/Azure/GCP from day one
