---
name: manda-repo-maintenance
description: How the Manda umbrella repo is organised and how to maintain it - where files go, how to add or change a Claude skill, the one-worktree-per-repo rule, the _junk folder, and the documentation-and-logging work-log folder. Use when adding a skill, creating or removing a worktree, saving a report/plan/log, or tidying the Manda root.
---

# Manda repo maintenance

Manda is the umbrella repo for Codly. `Codly_Backend`, `Codly-Frontend`, `Codly-Website` are git submodules; everything else here is shared Claude context, docs and ops.

## Layout

```
Manda/
├── CLAUDE.md                     # repo map + hard rules. Short. No secrets.
├── CLAUDE.local.md               # GITIGNORED. Credentials and personal notes.
├── .claude/
│   ├── settings.json             # hooks (graphify, Stop notifier, work log)
│   └── skills/<name>/SKILL.md    # CROSS-REPO skills only
├── Codly_Backend/ Codly-Frontend/ Codly-Website/   # submodules - keep names/paths
├── documentation-and-logging/    # work log + working docs (see below)
├── ops/
│   ├── dev/                      # tunnel + dev launcher scripts, .desktop file
│   ├── claude-hooks/             # Stop-hook scripts (notify, work log)
│   ├── tools/                    # small repo tools (e.g. pyarmour size check)
│   └── server-console/
├── .worktrees/                   # GITIGNORED. At most ONE worktree per repo
└── _junk/                        # GITIGNORED. Anything stray goes here
```

## Where things go

| Thing | Location |
|---|---|
| Per-feature TODO / flow doc | `documentation-and-logging/expectation/feature - <name>.MD` |
| Daily work log / tracker | `documentation-and-logging/daily-tracker/` (`pending/` is gitignored, written by the Stop hook) |
| PR screenshot evidence | `documentation-and-logging/pr-evidence/<issue>-<topic>/` |
| Reports, audits, xlsx, pdf | `documentation-and-logging/reports/` |
| Design / implementation plans | `documentation-and-logging/plans/` |
| Architecture docs | `documentation-and-logging/architecture/` |
| Test docs + screenshots | `documentation-and-logging/testing/` |
| Notebook (books > chapters > pages) | `documentation-and-logging/notebook/notebook.html` (see `notebook` skill) |
| Scripts | `ops/` - never at repo root |
| Anything unclassified, logs, SQL dumps, scratch | `_junk/` |

Never leave files at the Manda root. If unsure, put it in `_junk/` and mention it.

## Adding a Claude skill

1. Decide scope - **one skill, one home**:
   - Applies to several repos or to process (PRs, servers, notebook) -> `Manda/.claude/skills/<name>/`
   - Only about one repo's code -> that repo's `.claude/skills/<name>/` (versions with the code)
   - Personal style -> `~/.claude/skills/`
   Before creating, `ls` all three and check no skill with that name or purpose exists. Duplicates drift (`backend-auth` already did).
2. Create `<scope>/.claude/skills/<kebab-name>/SKILL.md` with frontmatter:
   ```
   ---
   name: <kebab-name>          # must equal the folder name
   description: <what it covers + WHEN to use it. This line decides when it triggers - be specific>
   ---
   ```
3. Body: short, imperative, concrete paths/commands. Link to files instead of pasting large content; put long references in `references/` beside `SKILL.md`.
4. Register it: add a row to the Skills table in the relevant `CLAUDE.md` (trigger -> skill) and, for Codly skills, to the `codly` index skill.
5. Check: `name` matches folder, no secrets, no duplicate elsewhere:
   `find . -path ./.worktrees -prune -o -name SKILL.md -print | xargs -n1 dirname | xargs -n1 basename | sort | uniq -d`
6. Changing a skill = edit the one home copy. Never copy a skill between repos.
7. Do not commit unless asked.

## Worktree rule (one per repo)

- Keep at most **one** worktree each for Codly_Backend and Codly-Frontend, in `.worktrees/`, for the current task. Remove it when the branch is merged.
- Create: `git -C Codly_Backend worktree add ../.worktrees/<repo>-<topic> -b <branch-name> origin/<base>` (branch naming per `codly-workflow`).
- Remove: confirm clean and pushed (`git -C <wt> status`, `git -C <wt> log @{u}..`), then `git worktree remove <path>`; `git worktree prune` afterwards.
- If the repo is ever moved on disk, run `git worktree repair <path>` for each worktree.
- Never `rm -rf` a worktree directory without checking for unpushed work first.

## Submodules

- Update a pointer: `git add Codly_Backend` after checking out the wanted commit, one commit "chore: bump submodule pointers".
- `.gitmodules` `branch =` should name a stable branch (main/staging), not a feature branch.

## Hard rules

- Never commit or push unless asked. Never force-push or rewrite history.
- No credentials in tracked files - use `CLAUDE.local.md` or `.env` (gitignored).
- No `*:Zone.Identifier` files (Windows download markers) - they are gitignored.
