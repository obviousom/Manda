#!/usr/bin/env bash
# Claude Code "Stop" hook entrypoint. Fires once per finished Claude turn
# (not per tool call). Reads the hook's JSON payload from stdin, pulls the
# last user prompt (task) and Claude's last text response (summary) from the
# transcript, and forwards both to notify-teams.sh.
#
# Must never block or fail Claude Code: always exits 0.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

print(clean(task, 200))
print(clean(summary, 300))
' 2>/dev/null)"

TASK="$(printf '%s\n' "$EXTRACTED" | sed -n '1p')"
SUMMARY="$(printf '%s\n' "$EXTRACTED" | sed -n '2p')"

"$SCRIPT_DIR/notify-teams.sh" --status completed --task "$TASK" --summary "$SUMMARY" >/dev/null 2>&1

exit 0
