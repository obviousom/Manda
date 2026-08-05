#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/codly_desktop_launcher.log"
DISTRO_NAME="${CODLY_WSL_DISTRO:-${WSL_DISTRO_NAME:-Ubuntu}}"

export PATH="$PATH:/mnt/c/Users/$USER/AppData/Local/Microsoft/WindowsApps:/mnt/c/Windows/System32:/mnt/c/WINDOWS/system32"

{
    echo "[$(date -Is)] Launching Codly desktop starter"
    cd "$REPO_ROOT"
    ./start_codly_dev_tabs.sh --distro "$DISTRO_NAME"
} >> "$LOG_FILE" 2>&1
