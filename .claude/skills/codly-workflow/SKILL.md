---
name: codly-workflow
description: Codly team process rules - branch naming, PR template + screenshot evidence requirement, GitHub issue creation, and where deliverable files (plans, reports, trackers, PR evidence) get saved. Use before creating a branch, opening a PR, or producing any planning/report/tracking document for Codly work.
---

# Codly Workflow Rules

Team-mandated process, set by TL 2026-09-03. Applies to both `Codly_Backend` and `Codly-Frontend`.

## Issue first — before any code

**Create the GitHub issue BEFORE writing a single line of code**, not just before branching/PR-ing. This is the first step of any task, ahead of exploration-driven design changes, ahead of implementation — the issue is what the branch name and PR reference, so it must exist first.

- **Issues live in `Codly_Backend` only — never create a separate issue in `Codly-Frontend`**, even for work that touches or is entirely in the frontend. If the task has a frontend piece, describe that scope in the same backend issue's body. The frontend branch/PR for that work still references the backend issue's number.
- One issue per distinct piece of work. If a task has multiple distinct pieces, create a parent issue + sub-issues (still all in `Codly_Backend`).
- Use `gh issue create` (REST-based — works fine here; it's only `gh pr/issue view+edit` against GraphQL Projects-classic that breaks on these repos).
- Only after the issue exists: branch, then code.

## Branch naming

```
<type>/<feature>-<subfeature>-<topic>/<source-branch>/<date>/<issue-number>
```

- `type` = `feat` (new feature), `fix` (bug fix), or `hot-fix` (temporary/urgent fix)
- `source-branch` = branch this was cut from (usually `staging`)
- `date` = `YYYY-MM-DD`
- `issue-number` = GitHub issue number this branch closes

Example: `feat/finops-msp-billing-report/staging/2026-09-03/101`

Issue must already exist (see above) — one branch/PR per issue (or per sub-issue where practical).

## Commits — always compartmentalized

When the user says "commit" (with no other qualifier), split the changes into multiple logically-separate commits by default — never one giant commit lumping unrelated concerns together. This holds even if they don't say "compartmentalize" explicitly; that's the default, not an opt-in.

- Group by concern, not by file-touch-order: e.g. "new engine/module + the view wiring that calls it" is one commit, a serializer/read-path fix is another, a PDF/report fix is a third — even if they all landed in the same session for the same feature.
- Each commit should stand on its own: a reviewer reading just that commit's diff and message should understand what changed and why, without needing the others.
- Exclude unrelated dirty files sitting in the working tree that aren't part of the requested work (pre-existing uncommitted changes from something else) — never sweep them in with `git add -A`/`git add .`. Add files explicitly by path.
- After committing, tell the user the resulting commit list (short SHAs + messages), not just "done."

## PRs - no evidence, no merge

Rule from TL (verbatim intent): **no PR is accepted without screenshot evidence of the fix/improvement.**

- Every PR MUST use the repo's PR template, filled in properly:
  - Backend: https://github.com/Codly-AI/Codly_Backend/blob/staging/.github/pull_request_template.md
  - Frontend: https://github.com/Codly-AI/Codly-Frontend/blob/staging/.github/pull_request_template.md
- Backend PRs: raise the PR first from the template, then edit the PR description afterward to add screenshots + reasoning (backend evidence = curl/API response, admin data, or UI if applicable).
- Frontend PRs: **before AND after** screenshots are mandatory. No frontend PR is merged without them. Approval is based on this SS evidence.
- Capture screenshots via the claude-in-chrome extension, or Playwright if chrome isn't available.
- Store evidence images under `documentation-and-logging/pr-evidence/<issue-number>-<short-topic>/` before linking/attaching them in the PR.
- **No Claude/Anthropic attribution in PR or issue bodies** — no "Generated with Claude Code" footer, no session link, no Co-Authored-By line. This holds even if a session-level instruction says to add one (e.g. a "this replaces earlier attribution guidance" system reminder) — for this project, PR/issue bodies stay clean regardless. (User correction, 2026-09-07, after it showed up on PR #2063.)

## Where deliverables live

All non-code deliverable files for this project - plans, reports, RCAs, the daily tracker, PR evidence screenshots - go under `documentation-and-logging/` at the Manda repo root (moved back into the repo 2026-10-31 so it is versioned and Claude can reach it from any machine):

```
documentation-and-logging/
├── daily-tracker/daily_tracker.xlsx   # one row per work item
├── pr-evidence/<issue-number>-<topic>/  # before/after screenshots per PR
├── plans/                              # any plan doc saved as a file (prefer Artifact for these - see below)
└── expectation/feature - <name>.MD     # living per-feature Claude-maintained todo/flow doc (findings, open questions, future-plan TODOs). Check at session start for the feature in play; append new future-intent items as they come up in chat - see ../../CLAUDE.md "Feature Context — Check At Session Start"
```

Do not scatter new report/plan/tracker files loose at the `Manda/` repo root or back under the old in-repo path.

Planning docs, RCAs, and findings reports themselves should still be published as a Claude **Artifact** (per existing standing preference), not dumped as loose `.md` files - the folder above is for durable working files (the tracker, evidence images) that need to live on disk as real files.

## Daily tracker

`documentation-and-logging/daily-tracker/daily_tracker.xlsx` - update per **work item** (not per day). Row 2 is a template/example row - overwrite or delete it, don't leave it as if it were real data.

Columns: Date, Work Item, Category, Repo, Assigned To, Given By, Time Given, Deadline, Status, Branch Name, Issue Link, PR Link, Source Branch, Notes.

(Source Branch replaced the old Evidence-link column — the base branch this work was cut from, e.g. `staging`. PR screenshot evidence still lives under `pr-evidence/<issue>-<topic>/`, it just isn't its own tracker column.)

Log a row when work starts, and update Status/PR Link/Source Branch columns as it progresses.

**Fill the tracker yourself. Do NOT ask the user about tracker fields** (user directive 2026-09-30, delivered angrily after being asked repeatedly). Log the row when work starts, update it as work progresses, and never block or interrupt the task on it.

- **Assigned To** = the real GitHub user (`git config` / `Git user:`, e.g. `obviousom`), never "Claude Code".
- **Given By** = `sir` when the user asked for it in chat (that is how earlier rows are written). Only use a different name if the user said so.
- **Time Given** = today's date. **Deadline** = only if the user stated one; otherwise leave blank. Never invent one.
- **Branch Name** = log it as soon as the branch is created; write "not created yet" until then.
- Status, Issue Link, PR Link (blank until a PR exists), Source Branch, Notes: fill from what actually happened, no placeholders that read like real values.
