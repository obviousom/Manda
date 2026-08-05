#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISTRO_NAME="${WSL_DISTRO_NAME:-}"
DRY_RUN=false
WT_BIN="${WT_BIN:-}"
WSL_BIN="${WSL_BIN:-}"
WT_WSL_CMD="${WT_WSL_CMD:-wsl.exe}"

usage() {
    cat <<'EOF'
Usage:
  ./start_codly_dev_tabs.sh
  ./start_codly_dev_tabs.sh --dry-run
  ./start_codly_dev_tabs.sh --distro Ubuntu

Opens three Windows Terminal tabs from WSL:
  1. Dev tunnel with auto-retry and server wake-up
  2. Django backend on port 8000 with logs tee'd to /tmp/codly_backend_logs.txt
  3. Frontend via bun run dev
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --distro)
            [[ $# -lt 2 ]] && { echo "Missing value for --distro" >&2; exit 1; }
            DISTRO_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$DISTRO_NAME" ]]; then
    echo "WSL_DISTRO_NAME is not set. Run this from WSL or pass --distro." >&2
    exit 1
fi

if [[ -z "$WT_BIN" ]]; then
    WT_BIN="$(command -v wt.exe || true)"
fi
if [[ -z "$WT_BIN" && -x "/mnt/c/Users/$USER/AppData/Local/Microsoft/WindowsApps/wt.exe" ]]; then
    WT_BIN="/mnt/c/Users/$USER/AppData/Local/Microsoft/WindowsApps/wt.exe"
fi

if [[ -z "$WSL_BIN" ]]; then
    WSL_BIN="$(command -v wsl.exe || true)"
fi
if [[ -z "$WSL_BIN" && -x "/mnt/c/WINDOWS/system32/wsl.exe" ]]; then
    WSL_BIN="/mnt/c/WINDOWS/system32/wsl.exe"
fi
if [[ -z "$WSL_BIN" && -x "/mnt/c/Windows/System32/wsl.exe" ]]; then
    WSL_BIN="/mnt/c/Windows/System32/wsl.exe"
fi

if [[ -z "$WT_BIN" ]]; then
    echo "wt.exe not found. Install Windows Terminal or add it to PATH." >&2
    exit 1
fi

if [[ -z "$WSL_BIN" ]]; then
    echo "wsl.exe not found. Ensure WSL Windows interop is available." >&2
    exit 1
fi

shell_quote() {
    printf '%q' "$1"
}

tunnel_dir="$REPO_ROOT"
backend_dir="$REPO_ROOT/Codly_Backend"
frontend_dir="$REPO_ROOT/Codly-Frontend"

tunnel_cmd="./dev_tunnel_retry.sh"
backend_cmd="./run_codly_backend_dev.sh"
frontend_cmd="./run_codly_frontend_dev.sh"

WT_ARGS=(
    new-tab
    --title "Codly Tunnel"
    -- "$WT_WSL_CMD" --distribution "$DISTRO_NAME" --cd "$tunnel_dir" "$tunnel_cmd"
    ";"
    new-tab
    --title "Codly Backend"
    -- "$WT_WSL_CMD" --distribution "$DISTRO_NAME" --cd "$backend_dir" "$backend_cmd"
    ";"
    new-tab
    --title "Codly Frontend"
    -- "$WT_WSL_CMD" --distribution "$DISTRO_NAME" --cd "$frontend_dir" "$frontend_cmd"
)

if [[ "$DRY_RUN" == true ]]; then
    printf 'Distro: %s\n' "$DISTRO_NAME"
    printf 'Tunnel tab: %s\n' "$tunnel_cmd"
    printf 'Backend tab: %s\n' "$backend_cmd"
    printf 'Frontend tab: %s\n' "$frontend_cmd"
    printf '%s' "$WT_BIN"
    printf ' %q' "${WT_ARGS[@]}"
    printf '\n'
    exit 0
fi

"$WT_BIN" "${WT_ARGS[@]}"
