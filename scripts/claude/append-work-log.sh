#!/usr/bin/env bash
# Claude Code "Stop" hook. Fires once per finished Claude turn (not per tool
# call), same as claude-stop-notify.sh (runs alongside it, does not replace
# it). Reads the hook's JSON payload from stdin, pulls the last user prompt
# (task) and Claude's last text response (outcome) from the transcript, and
# appends them as a timestamped entry to today's pending work-log MD file.
#
# A separate 17:00 scheduled job (summarize-daily-log.sh, triggered via
# Windows Task Scheduler since WSL2 doesn't keep cron alive when idle) folds
# that MD into daily_summary.xlsx and deletes it. If work continues after
# 17:00, this hook just recreates the file (it was deleted), which is the
# "new MD file" behavior.
#
# Must never block or fail Claude Code: always exits 0.

set -u

PENDING_DIR="/mnt/c/Users/lenovo/Desktop/documentation and logging/daily-tracker/pending"
mkdir -p "$PENDING_DIR" 2>/dev/null

TODAY="$(date +%F)"
LOG_FILE="$PENDING_DIR/pending-log-${TODAY}.md"

INPUT="$(cat)"

# Prints TASK on line 1, SUMMARY on line 2 (each single-line, truncated).
EXTRACTED="$(printf '%s' "$INPUT" | python3 -c '
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    print("")
    sys.exit(0)

transcript_path = data.get("transcript_path", "")
task = ""
summary = ""

def text_blocks(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""

try:
    with open(transcript_path, "r") as f:
        lines = f.readlines()

    for line in reversed(lines):
        if task and summary:
            break
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue

        entry_type = entry.get("type")
        message = entry.get("message", {})
        content = message.get("content", "")

        if entry_type == "assistant" and not summary:
            text = text_blocks(content)
            if text.strip():
                summary = text

        if entry_type == "user" and not task:
            text = text_blocks(content)
            if text.strip():
                task = text
except Exception:
    pass

def clean(s, limit):
    return s.strip().replace("\n", " ")[:limit]

print(clean(task, 400))
print(clean(summary, 800))
' 2>/dev/null)"

TASK="$(printf '%s\n' "$EXTRACTED" | sed -n '1p')"
SUMMARY="$(printf '%s\n' "$EXTRACTED" | sed -n '2p')"

if [ -z "$TASK" ] && [ -z "$SUMMARY" ]; then
  exit 0
fi

TS="$(date '+%H:%M:%S')"
{
  echo "### ${TS}"
  echo "- **Task:** ${TASK}"
  echo "- **Done:** ${SUMMARY}"
  echo ""
} >> "$LOG_FILE"

exit 0
