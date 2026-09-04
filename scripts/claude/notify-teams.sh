#!/usr/bin/env bash
# Send a best-effort Microsoft Teams notification via a Teams Workflow webhook.
#
# Reads the webhook URL from TEAMS_WEBHOOK_URL (env var, or a .env file at the
# monorepo root). Never prints the webhook URL. Never exits non-zero — a
# notification failure must not fail whatever called this script (e.g. a
# Claude Code hook).
#
# Usage:
#   notify-teams.sh [--status completed|failed] [--task "what was asked"] [--summary "what Claude did"]
#
# Manual test:
#   TEAMS_WEBHOOK_URL="https://..." ./scripts/claude/notify-teams.sh --status completed --task "manual test" --summary "verified webhook works"

set -u

STATUS="completed"
TASK=""
SUMMARY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --status)
      STATUS="${2:-completed}"
      shift 2
      ;;
    --task)
      TASK="${2:-}"
      shift 2
      ;;
    --summary)
      SUMMARY="${2:-}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Resolve the monorepo root Claude Code told us about; fall back to walking
# up from this script's own location so the script also works stand-alone.
REPO_ROOT="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$REPO_ROOT" ]; then
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  while [ "$DIR" != "/" ] && [ ! -d "$DIR/.git" ]; do
    DIR="$(dirname "$DIR")"
  done
  REPO_ROOT="$DIR"
fi

# Load TEAMS_WEBHOOK_URL from a root .env if it isn't already exported.
if [ -z "${TEAMS_WEBHOOK_URL:-}" ] && [ -f "$REPO_ROOT/.env" ]; then
  # shellcheck disable=SC1090
  set -a
  . "$REPO_ROOT/.env"
  set +a
fi

if [ -z "${TEAMS_WEBHOOK_URL:-}" ]; then
  echo "notify-teams: TEAMS_WEBHOOK_URL is not configured." >&2
  echo "Add it locally to your environment/.env and rerun the test." >&2
  exit 0
fi

REPO_NAME="$(basename "$REPO_ROOT" 2>/dev/null || echo "unknown")"
BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
COMMIT="$(git -C "$REPO_ROOT" log -1 --pretty=format:'%h %s' 2>/dev/null || echo "unknown")"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S %Z')"

if [ "$STATUS" = "failed" ]; then
  TITLE="Claude Code Task Failed"
  EMOJI="❌"
else
  STATUS="completed"
  TITLE="Claude Code Task Completed"
  EMOJI="✅"
fi

# The "Post to a channel when a webhook request is received" Workflow expects
# the POST body itself to be an Adaptive Card (wrapped in a Bot Framework
# "message" activity) — not an arbitrary flat JSON payload.
PAYLOAD="$(python3 - "$TITLE" "$STATUS" "$EMOJI" "$REPO_NAME" "$BRANCH" "$COMMIT" "$TIMESTAMP" "$TASK" "$SUMMARY" <<'PYEOF'
import json
import sys

title, status, emoji, repo, branch, commit, timestamp, task, summary = sys.argv[1:10]

facts = [
    {"title": "Repository", "value": repo},
    {"title": "Branch", "value": branch},
    {"title": "Status", "value": status},
    {"title": "Time", "value": timestamp},
    {"title": "Latest commit", "value": commit},
]

body = [
    {
        "type": "TextBlock",
        "text": f"{emoji} {title}",
        "weight": "Bolder",
        "size": "Medium",
        "wrap": True,
    },
    {"type": "FactSet", "facts": facts},
]
if task:
    body.append({
        "type": "TextBlock",
        "text": f"**Task:** {task[:200]}",
        "wrap": True,
    })
if summary:
    body.append({
        "type": "TextBlock",
        "text": f"**Summary:** {summary[:300]}",
        "wrap": True,
    })

card = {
    "type": "AdaptiveCard",
    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    "version": "1.4",
    "body": body,
}

payload = {
    "type": "message",
    "attachments": [
        {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": card,
        }
    ],
}
print(json.dumps(payload))
PYEOF
)"

HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD" \
  "$TEAMS_WEBHOOK_URL" 2>/dev/null)"

if [ "$HTTP_CODE" -ge 200 ] 2>/dev/null && [ "$HTTP_CODE" -lt 300 ] 2>/dev/null; then
  exit 0
fi

echo "notify-teams: Teams webhook call did not succeed (HTTP ${HTTP_CODE:-none})." >&2
exit 0
