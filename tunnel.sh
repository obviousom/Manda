#!/usr/bin/env bash
# ============================================================
# AWS SSM Port Forwarding Tunnel (WSL/Linux)
# Usage:
#   ./tunnel.sh
#   ./tunnel.sh --env dev --non-interactive
# ============================================================

set -u

AWS_REGION="ap-south-1"
AWS_PROFILE="ssm-port"

DEV_INSTANCE="i-070fa60ad49785f8d"
BETA_INSTANCE="i-0e5d43cddb36a407c"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; WHITE='\033[1;37m'; GRAY='\033[0;37m'; NC='\033[0m'

info()    { echo -e "${CYAN}[*] $1${NC}"; }
success() { echo -e "${GREEN}[+] $1${NC}"; }
warn()    { echo -e "${YELLOW}[!] $1${NC}"; }
err()     { echo -e "${RED}[x] $1${NC}"; }

PIDS=()
ALL_PORTS=()
EXTRA_PORT_INPUTS=()
INTERACTIVE=true
SKIP_CLEAR=false
ENV_CHOICE=""
PROBE_SECONDS=3
CLEANED_UP=false

usage() {
    cat <<'EOF'
Usage:
  ./tunnel.sh
  ./tunnel.sh --env dev --non-interactive
  ./tunnel.sh --env beta --extra-port 9000:9001

Options:
  --env <dev|beta|1|2>   Select the target environment.
  --extra-port <value>   Add one extra port. Accepts 5432 or 9000:9001.
  --extra-ports "<list>" Add multiple extra ports separated by spaces.
  --probe-seconds <n>    Seconds to wait before checking tunnel health.
  --non-interactive      Skip prompts and keep running until interrupted.
  --no-clear             Do not clear the terminal.
  -h, --help             Show this help message.

Exit codes:
  0  Success.
  1  Configuration or AWS authentication error.
  2  Tunnel startup failed after the initial health check.
EOF
}

cleanup() {
    if [[ "$CLEANED_UP" == true ]]; then
        return
    fi
    CLEANED_UP=true

    if [[ ${#PIDS[@]} -eq 0 ]]; then
        return
    fi

    echo ""
    info "Stopping all tunnels..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    success "All tunnels stopped. Bye!"
}

handle_int() {
    cleanup
    exit 130
}

handle_term() {
    cleanup
    exit 143
}

trap cleanup EXIT
trap handle_int INT
trap handle_term TERM

normalize_env_choice() {
    case "$1" in
        1|dev|DEV) echo "1" ;;
        2|beta|BETA) echo "2" ;;
        *) return 1 ;;
    esac
}

print_header() {
    if [[ "$SKIP_CLEAR" == false ]]; then
        clear
    fi
    echo -e "${CYAN}==========================================${NC}"
    echo -e "${CYAN}   AWS SSM Port Forwarding Tunnel${NC}"
    echo -e "${CYAN}==========================================${NC}"
    echo ""
}

append_extra_ports() {
    local input="$1"
    local part

    [[ -z "$input" ]] && return

    for part in $input; do
        if [[ "$part" =~ ^([0-9]+):([0-9]+)$ ]]; then
            ALL_PORTS+=("${BASH_REMATCH[1]}:${BASH_REMATCH[2]}:Custom")
            success "Added: localhost:${BASH_REMATCH[1]} -> remote:${BASH_REMATCH[2]}"
        elif [[ "$part" =~ ^[0-9]+$ ]]; then
            ALL_PORTS+=("$part:$part:Custom")
            success "Added: localhost:$part -> remote:$part"
        else
            warn "Skipping invalid entry: $part"
        fi
    done
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            [[ $# -lt 2 ]] && { err "Missing value for --env"; exit 1; }
            ENV_CHOICE="$2"
            shift 2
            ;;
        --extra-port)
            [[ $# -lt 2 ]] && { err "Missing value for --extra-port"; exit 1; }
            EXTRA_PORT_INPUTS+=("$2")
            shift 2
            ;;
        --extra-ports)
            [[ $# -lt 2 ]] && { err "Missing value for --extra-ports"; exit 1; }
            EXTRA_PORT_INPUTS+=("$2")
            shift 2
            ;;
        --probe-seconds)
            [[ $# -lt 2 ]] && { err "Missing value for --probe-seconds"; exit 1; }
            PROBE_SECONDS="$2"
            shift 2
            ;;
        --non-interactive)
            INTERACTIVE=false
            SKIP_CLEAR=true
            shift
            ;;
        --no-clear)
            SKIP_CLEAR=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            err "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if ! [[ "$PROBE_SECONDS" =~ ^[0-9]+$ ]]; then
    err "--probe-seconds must be a non-negative integer."
    exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
    err "AWS CLI not found. Install AWS CLI v2 first."
    exit 1
fi

if ! aws sts get-caller-identity --profile "$AWS_PROFILE" >/dev/null 2>&1; then
    err "AWS profile '$AWS_PROFILE' is not configured or invalid."
    echo "Run: aws configure --profile $AWS_PROFILE"
    exit 1
fi

if [[ -n "$ENV_CHOICE" ]]; then
    if ! ENV_CHOICE="$(normalize_env_choice "$ENV_CHOICE")"; then
        err "Invalid environment: $ENV_CHOICE"
        usage
        exit 1
    fi
fi

if [[ -z "$ENV_CHOICE" ]]; then
    if [[ "$INTERACTIVE" == false || ! -t 0 ]]; then
        err "Provide --env when running non-interactively."
        exit 1
    fi

    print_header
    echo -e "${WHITE}Select environment:${NC}"
    echo -e "  ${YELLOW}[1] Dev   ($DEV_INSTANCE)${NC}"
    echo -e "  ${YELLOW}[2] Beta  ($BETA_INSTANCE)${NC}"
    echo ""

    while true; do
        read -rp "Enter choice (1 or 2): " ENV_CHOICE
        [[ "$ENV_CHOICE" == "1" || "$ENV_CHOICE" == "2" ]] && break
        warn "Invalid choice, enter 1 or 2"
    done
fi

if [[ "$ENV_CHOICE" == "1" ]]; then
    ENV_NAME="dev"
    INSTANCE_ID="$DEV_INSTANCE"
    DEFAULT_PORTS=("8080:80:HTTP" "3306:3306:MySQL" "6379:6379:Redis")
else
    ENV_NAME="beta"
    INSTANCE_ID="$BETA_INSTANCE"
    DEFAULT_PORTS=("8093:8093:App")
fi

echo ""
success "Selected: $ENV_NAME ($INSTANCE_ID)"
echo ""

info "Default ports for $ENV_NAME:"
for entry in "${DEFAULT_PORTS[@]}"; do
    IFS=':' read -r local remote name <<< "$entry"
    echo -e "    ${GRAY}$name: localhost:$local -> remote:$remote${NC}"
done
echo ""

ALL_PORTS=("${DEFAULT_PORTS[@]}")

if [[ ${#EXTRA_PORT_INPUTS[@]} -gt 0 ]]; then
    for input in "${EXTRA_PORT_INPUTS[@]}"; do
        append_extra_ports "$input"
    done
elif [[ "$INTERACTIVE" == true ]]; then
    info "Add extra ports? (press Enter to skip)"
    echo -e "    ${GRAY}Format: localPort:remotePort (e.g. 9000:9001) or just port (e.g. 5432)${NC}"
    echo -e "    ${GRAY}Multiple ports separated by space${NC}"
    echo ""

    read -rp "Extra ports: " extra_input
    append_extra_ports "$extra_input"
fi

echo ""
print_header
info "Starting SSM tunnels for $ENV_NAME..."
echo ""

for entry in "${ALL_PORTS[@]}"; do
    IFS=':' read -r local remote name <<< "$entry"
    info "Forwarding $name: localhost:$local -> $INSTANCE_ID:$remote"

    aws ssm start-session \
        --target "$INSTANCE_ID" \
        --document-name AWS-StartPortForwardingSession \
        --parameters "{\"portNumber\":[\"$remote\"],\"localPortNumber\":[\"$local\"]}" \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" >/tmp/ssm_${ENV_NAME}_${local}.log 2>&1 &

    PIDS+=("$!")
    sleep 0.5
done

sleep "$PROBE_SECONDS"

echo ""
echo -e "${WHITE}Tunnel status:${NC}"

any_failed=false
for i in "${!ALL_PORTS[@]}"; do
    entry="${ALL_PORTS[$i]}"
    pid="${PIDS[$i]}"

    IFS=':' read -r local remote name <<< "$entry"
    if kill -0 "$pid" 2>/dev/null; then
        printf "  ${GREEN}%-10s localhost:%-5s -> %s:%-5s [RUNNING]${NC}\n" "$name" "$local" "$ENV_NAME" "$remote"
    else
        any_failed=true
        printf "  ${RED}%-10s localhost:%-5s -> %s:%-5s [FAILED]${NC}\n" "$name" "$local" "$ENV_NAME" "$remote"
        if [[ -f "/tmp/ssm_${ENV_NAME}_${local}.log" ]]; then
            sed -n '1,4p' "/tmp/ssm_${ENV_NAME}_${local}.log" | sed 's/^/      /'
        fi
    fi
done

echo ""
echo -e "${WHITE}Local endpoints:${NC}"
for entry in "${ALL_PORTS[@]}"; do
    IFS=':' read -r local remote name <<< "$entry"
    if [[ "$name" == "HTTP" || ("$ENV_NAME" == "beta" && "$local" == "8093") ]]; then
        echo -e "  ${GRAY}http://localhost:$local${NC}"
    else
        echo -e "  ${GRAY}localhost:$local${NC}"
    fi
done

if [[ "$any_failed" == true ]]; then
    err "One or more tunnels failed during startup."
    exit 2
fi

echo ""
if [[ "$INTERACTIVE" == true ]]; then
    warn "Press Enter to stop all tunnels and exit..."
    read -r _
    exit 0
fi

warn "Tunnels are running. Press Ctrl+C to stop."
wait "${PIDS[@]}"
