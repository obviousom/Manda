#!/usr/bin/env bash
# Runs once daily at 17:00, triggered by Windows Task Scheduler (task
# "CodlyDailySummary") via: wsl.exe -d Ubuntu -e <this script>. Plain WSL2
# cron isn't reliable here since the distro suspends when idle - Task
# Scheduler wakes it.
#
# Reads today's pending work-log MD (written by append-work-log.sh's Stop
# hook across the day's chat turns), asks Claude - headless, no tools, no
# project settings (so it can't recurse into this same Stop hook) - to
# synthesize it into the daily_summary.xlsx row shape, appends the row, then
# deletes the MD.
#
# Safety: the MD is only deleted after a successful, verified Excel append.
# Any failure (API error, bad JSON, Excel write failure) leaves the MD in
# place and logs it - the next scheduled run (or a manual rerun) retries it,
# nothing is silently lost.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRACKER_DIR="/mnt/c/Users/lenovo/Desktop/documentation and logging/daily-tracker"
PENDING_DIR="$TRACKER_DIR/pending"
SUMMARY_XLSX="$TRACKER_DIR/daily_summary.xlsx"
CRON_LOG="$PENDING_DIR/cron.log"
TODAY="$(date +%F)"
LOG_FILE="$PENDING_DIR/pending-log-${TODAY}.md"

mkdir -p "$PENDING_DIR"
log() { echo "$(date '+%F %T') $1" >> "$CRON_LOG"; }

if [ ! -s "$LOG_FILE" ]; then
  log "skip: no pending log for ${TODAY}"
  exit 0
fi

if [ ! -f "$SUMMARY_XLSX" ]; then
  log "FAILED: $SUMMARY_XLSX does not exist, MD kept for retry: $LOG_FILE"
  exit 1
fi

SCHEMA='{"type":"object","properties":{"summary":{"type":"string"},"key_outcomes":{"type":"string"},"issues_filed":{"type":"string"},"branches_prs":{"type":"string"},"notes":{"type":"string"}},"required":["summary","key_outcomes","issues_filed","branches_prs","notes"]}'

PROMPT="You are compiling a daily engineering work-log summary from raw session notes below. Each entry is one Claude Code chat turn from today (the task asked, and what got done). Merge ALL entries into ONE row for a tracking spreadsheet with these exact fields:
- summary: 1-3 sentence overview of what the day's work covered.
- key_outcomes: bullet list (one '-' per line) of concrete outcomes/fixes/results.
- issues_filed: comma-separated GitHub issue numbers/links mentioned, or an em dash if none.
- branches_prs: comma-separated branch names / PR links mentioned, or an em dash if none.
- notes: anything noteworthy not covered above (blockers, pending items, caveats), or an em dash if none.
Be factual - don't invent details not present in the notes below.

--- today's entries ---
$(cat "$LOG_FILE")"

RESULT_JSON="$(printf '%s' "$PROMPT" | claude --setting-sources "" --tools "" --permission-prompts none --effort low -p --model claude-haiku-4-5-20251001 --output-format json --json-schema "$SCHEMA" 2>>"$CRON_LOG")"

if [ -z "$RESULT_JSON" ]; then
  log "FAILED: empty response from claude -p, MD kept for retry: $LOG_FILE"
  exit 1
fi

if ! python3 "$SCRIPT_DIR/append-summary-row.py" "$SUMMARY_XLSX" "$TODAY" "$RESULT_JSON" >>"$CRON_LOG" 2>&1; then
  log "FAILED: excel append failed, MD kept for retry: $LOG_FILE"
  exit 1
fi

rm -f "$LOG_FILE"
log "OK: summarized + appended row for ${TODAY}, MD deleted"
exit 0
