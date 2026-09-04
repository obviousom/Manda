# Claude Code -> Microsoft Teams notifications

Sends a Teams channel message whenever Claude Code finishes a task in this
monorepo. Centralized here so every app in the parent folder shares one
implementation instead of duplicating it.

Message includes your prompt (`task`, truncated to 200 chars) and Claude's
last text response (`summary`, truncated to 300 chars) — pulled straight
from the transcript, not re-summarized by another LLM call.

## Architecture

```
Claude Code finishes a turn
  -> Stop hook (.claude/settings.json, repo root)
  -> scripts/claude/claude-stop-notify.sh   (reads hook JSON from stdin, pulls last user prompt + Claude's last response text)
  -> scripts/claude/notify-teams.sh         (builds payload, POSTs to TEAMS_WEBHOOK_URL)
  -> Microsoft Teams Workflow webhook
  -> Teams channel message
```

`notify-teams.sh` is the reusable core (repo/branch/commit detection, webhook
POST, secret handling). `claude-stop-notify.sh` is a thin adapter that turns
Claude Code's Stop-hook JSON into arguments for it. Any other tool in this
monorepo can call `notify-teams.sh` directly the same way.

## Setup: create the Teams Workflow

Microsoft retired Office 365 Connectors; use a **Workflow** (Power Automate)
instead:

1. In Teams, open the channel you want notifications in.
2. Channel `...` menu -> **Workflows**.
3. Search the template **"Post to a channel when a webhook request is
   received"** (trigger: *When a Teams webhook request is received*).
4. Create it, name it (e.g. "Claude Code Notifications"), pick the target
   team/channel.
5. When prompted for a sample payload to infer the schema, paste:
   ```json
   {
     "title": "Claude Code Task Completed",
     "status": "completed",
     "emoji": "✅",
     "repository": "Manda",
     "branch": "main",
     "commit": "b7db151 final",
     "timestamp": "2026-09-04 10:23:00 UTC",
     "task": "short description of what was asked",
     "summary": "short version of what Claude actually did/said"
   }
   ```
6. In the flow's "Post message in a channel" step, compose the message text
   using the dynamic fields above, e.g.:
   ```
   {emoji} Claude Code Task {status}

   Repository: {repository}
   Branch: {branch}
   Status: {status}

   Time: {timestamp}
   Task: {task}
   Summary: {summary}
   Latest commit: {commit}
   ```
   `task` and `summary` are omitted from the payload (not sent as empty
   strings) when the transcript has neither a matching user prompt nor an
   assistant text block — set the flow step to tolerate a missing field.
7. Save. Copy the generated **HTTP POST URL** — that's your webhook URL.

## Environment variable

```
TEAMS_WEBHOOK_URL
```

Never commit the real value. `.env.example` (repo root) documents the
variable with a placeholder; `.env` (gitignored) holds the real one.

### Local setup

**WSL / Linux shell:**
```bash
cp /home/lenovo/Manda/.env.example /home/lenovo/Manda/.env
# edit .env, set TEAMS_WEBHOOK_URL to the real URL from the Teams workflow
```

**Windows:** if you also run Claude Code from Windows against this same
checkout, set a user environment variable named `TEAMS_WEBHOOK_URL` (System
Properties -> Environment Variables), or keep using the WSL `.env` file if
Claude Code always runs inside WSL.

## Testing

```bash
cd /home/lenovo/Manda
TEAMS_WEBHOOK_URL="<paste only in your shell, never in a file you commit>" \
  ./scripts/claude/notify-teams.sh --status completed --task "manual test" --summary "webhook wiring verified"
```

Or, once `.env` is populated:

```bash
cd /home/lenovo/Manda
./scripts/claude/notify-teams.sh --status completed --task "manual test" --summary "webhook wiring verified"
```

If `TEAMS_WEBHOOK_URL` isn't set anywhere, the script prints:
```
notify-teams: TEAMS_WEBHOOK_URL is not configured.
Add it locally to your environment/.env and rerun the test.
```
and exits 0 — it never fails the caller.

## Claude Code hook

Configured in `.claude/settings.json` (repo root) under `hooks.Stop`:

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/claude/claude-stop-notify.sh",
        "timeout": 15
      }
    ]
  }
]
```

`Stop` fires once when Claude finishes responding to a turn — not on every
tool call. `$CLAUDE_PROJECT_DIR` is set by Claude Code to the project root
(this repo), so the script resolves the right repo/branch/commit even if
Claude's tools were working inside a subdirectory (e.g. `Codly_Backend/`).

This is wired at the monorepo root only. If you separately open Claude Code
directly inside `Codly_Backend/` or `Codly-Frontend/` as their own project
(they're git submodules with their own `.claude/` config), add the same
`Stop` block to that project's `.claude/settings.local.json`, pointing at
`../scripts/claude/claude-stop-notify.sh`.

## Limitation: no reliable failure signal

Installed version: Claude Code 2.1.260 (checked via `claude --version` and
the hook event names present in the CLI binary).

Claude Code's `Stop` hook does not carry a success/failure status — it just
means "Claude stopped generating." There is no exit-code or error field
exposed to hooks that reliably distinguishes "task succeeded" from "task hit
an error." Because of that:

- Every Stop-hook notification currently sends `status: completed`.
- `notify-teams.sh --status failed` exists and works (build your own trigger
  for it — e.g. a wrapper script around a specific long-running command) but
  nothing in this setup calls it automatically, since guessing at failure
  from hook data would be unreliable and misleading.
- `SessionEnd` hook (fires on session exit) only reports *why the session
  ended* (`clear`, `logout`, `prompt_input_exit`, `other`) — `other` covers
  normal terminal closes as much as crashes, so it's not a trustworthy
  failure signal either. Not wired up for that reason.

## Security

- `TEAMS_WEBHOOK_URL` is a bearer credential — anyone with it can post to
  your Teams channel. Never put it in source, committed config, or chat.
- It's gitignored via `.env`; `.env.example` only ever holds a placeholder.
- `notify-teams.sh` never echoes/logs the URL, only the resulting HTTP
  status code on failure.
- All notification calls are best-effort: any failure (missing var, network
  error, non-2xx response) is swallowed and the script exits `0`, so it can
  never fail a Claude Code task or block it for more than the 10s curl
  timeout (15s hook timeout).
