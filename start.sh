#!/usr/bin/env bash
# Docker and Compose v2 are the only host dependencies (macOS/Linux/WSL).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
project=retail-demo
mode=fixture
credentials=
google=
action=start
tone=
reviewer=operator
export RETAIL_API_PORT="${RETAIL_API_PORT:-8000}"
export RETAIL_WEBUI_PORT="${RETAIL_WEBUI_PORT:-3000}"
while (($#)); do
    case "$1" in
        --live) mode=live; shift ;;
        --project|--env-file|--google-credentials|--api-port|--webui-port|--tone|--reviewer)
            [[ $# -ge 2 && -n "$2" ]] || { echo "Missing value for $1" >&2; exit 2; }
            case "$1" in
                --project) project="$2" ;;
                --env-file) credentials="$2" ;;
                --google-credentials) google="$2" ;;
                --api-port) RETAIL_API_PORT="$2" ;;
                --webui-port) RETAIL_WEBUI_PORT="$2" ;;
                --tone) action=tone; tone="$2" ;;
                --reviewer) reviewer="$2" ;;
            esac
            shift 2 ;;
        --stop) action=stop; shift ;;
        -h|--help)
            echo 'Usage: ./start.sh [--live --project retail-live --env-file .env.providers --google-credentials /path/google.json]'
            echo '  --project NAME  --api-port 8000  --webui-port 3000'
            echo '  --stop | --tone tone.txt --reviewer operator (use the same project/live flags)'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { echo 'Invalid Compose project name' >&2; exit 2; }
for port in "$RETAIL_API_PORT" "$RETAIL_WEBUI_PORT"; do
    [[ "$port" =~ ^[0-9]{1,5}$ ]] && ((10#$port > 0 && 10#$port <= 65535)) || { echo 'Invalid port' >&2; exit 2; }
done
command -v docker >/dev/null || { echo 'Install and start Docker with Compose v2 first.' >&2; exit 1; }
docker compose version >/dev/null
echo 'Checking Docker (up to 20 seconds)...'
docker info >/dev/null 2>&1 &
daemon_pid=$!
for ((attempt=0; attempt<20; attempt++)); do
    kill -0 "$daemon_pid" 2>/dev/null || break
    sleep 1
done
if kill -0 "$daemon_pid" 2>/dev/null; then
    kill "$daemon_pid" 2>/dev/null || true
    wait "$daemon_pid" 2>/dev/null || true
    echo 'Docker is not responding. Start/recover Docker Desktop, then retry.' >&2
    exit 1
fi
wait "$daemon_pid" || { echo 'Start Docker first.' >&2; exit 1; }
export RETAIL_ENV_FILE=".env.docker-$project"
export RETAIL_API_IMAGE="retail-assistant-api:local"
# The generated file owns these stable values, even if a host shell has others.
unset POSTGRES_PASSWORD WEBUI_SECRET_KEY RETAIL_MODE
compose=(docker compose -p "$project" --env-file "$RETAIL_ENV_FILE" -f compose.yaml -f compose.webui-reports.yaml)
if [[ "$mode" == live ]]; then
    if [[ "$action" == start ]]; then
        [[ -f "$credentials" && -f "$google" ]] || { echo 'Live startup needs --env-file and --google-credentials files.' >&2; exit 2; }
    fi
    # For stop/tone Compose still needs a valid interpolation value, without mounting it.
    export RETAIL_GOOGLE_CREDENTIALS="$ROOT/.local/docker-$project/google.json"
    compose+=(-f compose.live.yaml)
elif [[ -n "$credentials" || -n "$google" ]]; then
    echo 'Credential files require --live.' >&2; exit 2
fi
if [[ "$action" == stop ]]; then
    "${compose[@]}" stop
    exit 0
fi
if [[ "$action" == tone ]]; then
    [[ -f "$tone" ]] || { echo 'Tone file is missing.' >&2; exit 2; }
    "${compose[@]}" exec -T api retail-admin persona --file /dev/stdin --reviewer "$reviewer" < "$tone"
    exit 0
fi
echo 'Building the Docker runtime (first launch downloads dependencies)...'
docker build -t "$RETAIL_API_IMAGE" .
setup=(--output "/workspace/$RETAIL_ENV_FILE")
mounts=(-v "$ROOT:/workspace")
if [[ "$mode" == live ]]; then
    source_env="$(cd "$(dirname "$credentials")" && pwd)/$(basename "$credentials")"
    source_google="$(cd "$(dirname "$google")" && pwd)/$(basename "$google")"
    mounts+=(-v "$source_env:/run/provider.env:ro" -v "$source_google:/run/google-input.json:ro")
    setup+=(--live --credentials /run/provider.env --google-credentials /run/google-input.json
        --google-output "/workspace/.local/docker-$project/google.json")
fi
docker run --rm --network none --user "$(id -u):$(id -g)" "${mounts[@]}" \
    --entrypoint python "$RETAIL_API_IMAGE" /app/scripts/setup_docker.py "${setup[@]}"
echo 'Starting PostgreSQL, API and WebUI...'
"${compose[@]}" up --build -d --wait --wait-timeout 300
echo 'Configuring the dedicated WebUI and report pages...'
# WebUI can become healthy before its auth endpoints finish initialization.
ready=false
for ((attempt=0; attempt<30; attempt++)); do
    if "${compose[@]}" exec -T api python -c \
        'import urllib.request; urllib.request.urlopen("http://webui:8080/api/config", timeout=3)' >/dev/null 2>&1; then
        ready=true; break
    fi
    sleep 2
done
[[ "$ready" == true ]] || { echo 'WebUI is not ready; rerun start.sh to retry setup.' >&2; exit 1; }
"${compose[@]}" run --rm --no-deps --user "$(id -u):$(id -g)" -v "$ROOT:/workspace" \
    --entrypoint python api /app/scripts/bootstrap_webui.py \
    --env-file "/workspace/$RETAIL_ENV_FILE" --webui-url http://webui:8080 --compose-local --reports
# Load the WebUI identity mapping and newly registered native routes.
"${compose[@]}" up -d --force-recreate --wait --wait-timeout 300 api webui
echo "Ready ($mode): http://localhost:$RETAIL_WEBUI_PORT"
echo "Login: WEBUI_ADMIN_EMAIL / WEBUI_ADMIN_PASSWORD in $RETAIL_ENV_FILE (keep private)."
echo "Stop: ./start.sh --project $project --stop"
