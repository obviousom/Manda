#!/usr/bin/env bash

set -euo pipefail

HOST="${TUNNEL_WAIT_HOST:-127.0.0.1}"
PORTS=(${TUNNEL_WAIT_PORTS:-3306 6379})
TIMEOUT_SECONDS="${TUNNEL_WAIT_TIMEOUT_SECONDS:-180}"
SLEEP_SECONDS="${TUNNEL_WAIT_SLEEP_SECONDS:-2}"

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ && "$SLEEP_SECONDS" =~ ^[0-9]+$ ]]; then
    echo "[x] Timeout values must be non-negative integers." >&2
    exit 1
fi

if [[ ${#PORTS[@]} -eq 0 ]]; then
    echo "[x] No ports configured to wait for." >&2
    exit 1
fi

wait_for_port() {
    local host="$1"
    local port="$2"
    local start_ts now elapsed

    start_ts="$(date +%s)"
    echo "[*] Waiting for ${host}:${port}..."

    while true; do
        if command -v nc >/dev/null 2>&1; then
            if nc -z "$host" "$port" >/dev/null 2>&1; then
                break
            fi
        elif (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
            break
        fi

        now="$(date +%s)"
        elapsed=$((now - start_ts))
        if (( elapsed >= TIMEOUT_SECONDS )); then
            echo "[x] Timed out waiting for ${host}:${port} after ${TIMEOUT_SECONDS}s." >&2
            return 1
        fi
        sleep "$SLEEP_SECONDS"
    done

    echo "[+] ${host}:${port} is ready."
}

for port in "${PORTS[@]}"; do
    wait_for_port "$HOST" "$port"
done
