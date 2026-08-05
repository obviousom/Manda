#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUNNEL_SCRIPT="${TUNNEL_SCRIPT:-$REPO_ROOT/tunnel.sh}"
START_DEV_SERVER_URL="${START_DEV_SERVER_URL:-https://dev4gjvlr5.execute-api.ap-south-1.amazonaws.com/default/start_dev_server}"
RETRY_WAIT_SECONDS="${RETRY_WAIT_SECONDS:-10}"
CURL_BIN="${CURL_BIN:-curl}"

if ! [[ "$RETRY_WAIT_SECONDS" =~ ^[0-9]+$ ]]; then
    echo "[x] RETRY_WAIT_SECONDS must be a non-negative integer." >&2
    exit 1
fi

attempt=1

while true; do
    echo "[*] Tunnel attempt $attempt"

    status=0
    "$TUNNEL_SCRIPT" --env dev --non-interactive || status=$?
    if [[ $status -eq 0 ]]; then
        exit 0
    fi
    if [[ $status -eq 130 || $status -eq 143 ]]; then
        exit "$status"
    fi

    if [[ $status -ne 2 ]]; then
        echo "[x] Tunnel failed with exit code $status. Not retrying." >&2
        exit "$status"
    fi

    echo "[!] Dev tunnel startup failed. Hitting start-dev-server URL..."
    if ! "$CURL_BIN" --fail --silent --show-error "$START_DEV_SERVER_URL"; then
        echo "[!] Wake-up request failed, but retrying tunnel anyway." >&2
    fi

    echo "[*] Waiting ${RETRY_WAIT_SECONDS}s before retry..."
    sleep "$RETRY_WAIT_SECONDS"
    attempt=$((attempt + 1))
done
