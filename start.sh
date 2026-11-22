#!/usr/bin/env bash
# Docker and Compose v2 are the only host dependencies (macOS/Linux/WSL).
set -euo pipefail
cd "$(dirname "$0")"
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
    export RETAIL_CREDENTIAL_VOLUME="$project-google-credentials"
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
helper=
env_tmp=
cleanup() {
    if [[ -n "$helper" ]]; then docker rm -f "$helper" >/dev/null 2>&1 || true; fi
    if [[ -n "$env_tmp" ]]; then rm -f "$env_tmp"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Only selected config files cross the Docker API. No repository/host bind mount,
# Docker socket mount, or permanent Desktop file-sharing change is needed.
copy_env_back() {
    umask 077
    env_tmp="$(mktemp "$RETAIL_ENV_FILE.tmp.XXXXXX")"
    docker cp "$helper:/tmp/deployment.env" "$env_tmp"
    chmod 600 "$env_tmp"
    mv "$env_tmp" "$RETAIL_ENV_FILE"
    env_tmp=
}
setup=(--output /tmp/deployment.env)
mounts=(--user 0:0)
if [[ "$mode" == live ]]; then
    mounts+=(-v "$RETAIL_CREDENTIAL_VOLUME:/google-runtime")
    setup+=(--live --credentials /tmp/provider.env --google-credentials /tmp/google-input.json
        --google-output /google-runtime/google.json --google-owner 10001)
fi
helper="$project-config-$$"
docker create --name "$helper" --network none "${mounts[@]}" \
    --entrypoint python "$RETAIL_API_IMAGE" /app/scripts/setup_docker.py "${setup[@]}" >/dev/null
if [[ -f "$RETAIL_ENV_FILE" ]]; then docker cp "$RETAIL_ENV_FILE" "$helper:/tmp/deployment.env"; fi
if [[ "$mode" == live ]]; then
    docker cp "$credentials" "$helper:/tmp/provider.env"
    docker cp "$google" "$helper:/tmp/google-input.json"
fi
docker start -a "$helper"
[[ "$(docker inspect --format '{{.State.ExitCode}}' "$helper")" == 0 ]] || { echo 'Configuration setup failed.' >&2; exit 1; }
copy_env_back
docker rm "$helper" >/dev/null
helper=
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
helper="$project-bootstrap-$$"
docker create --name "$helper" --network "${project}_default" --user 0:0 \
    --entrypoint python "$RETAIL_API_IMAGE" /app/scripts/bootstrap_webui.py \
    --env-file /tmp/deployment.env --webui-url http://webui:8080 --compose-local --reports >/dev/null
docker cp "$RETAIL_ENV_FILE" "$helper:/tmp/deployment.env"
docker start -a "$helper"
[[ "$(docker inspect --format '{{.State.ExitCode}}' "$helper")" == 0 ]] || { echo 'WebUI setup failed.' >&2; exit 1; }
copy_env_back
docker rm "$helper" >/dev/null
helper=
# Load the WebUI identity mapping and newly registered native routes.
"${compose[@]}" up -d --force-recreate --wait --wait-timeout 300 api webui
echo "Ready ($mode): http://localhost:$RETAIL_WEBUI_PORT"
echo "Login: WEBUI_ADMIN_EMAIL / WEBUI_ADMIN_PASSWORD in $RETAIL_ENV_FILE (keep private)."
echo "Stop: ./start.sh --project $project --stop"
