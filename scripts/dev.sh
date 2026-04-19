#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-30}"
MONITOR_INTERVAL_SECONDS="${MONITOR_INTERVAL_SECONDS:-2}"
HEALTH_FAILURE_LIMIT="${HEALTH_FAILURE_LIMIT:-3}"

BACKEND_URL="http://$BACKEND_HOST:$BACKEND_PORT"
FRONTEND_URL="http://$FRONTEND_HOST:$FRONTEND_PORT"

BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '[dev] %s\n' "$*"
}

fail() {
  printf '[dev] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_file() {
  [[ -e "$1" ]] || fail "$2"
}

has_openai_api_key() {
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    return 0
  fi

  if [[ -f "$BACKEND_DIR/.env" ]] && grep -Eq '^[[:space:]]*OPENAI_API_KEY[[:space:]]*=' "$BACKEND_DIR/.env"; then
    return 0
  fi

  return 1
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM

  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "Stopping frontend process $FRONTEND_PID"
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Stopping backend process $BACKEND_PID"
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  wait "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true

  exit "$status"
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local pid="$3"
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))

  log "Waiting for $name at $url"
  until curl -fsS "$url" >/dev/null 2>&1; do
    if ! kill -0 "$pid" 2>/dev/null; then
      code="$(process_exit_code "$pid")"
      fail "$name process exited before it became ready with status $code"
    fi

    if (( SECONDS >= deadline )); then
      fail "$name did not become ready within ${HEALTH_TIMEOUT_SECONDS}s"
    fi
    sleep 1
  done
  log "$name is ready"
}

process_exit_code() {
  local pid="$1"
  local code=0
  wait "$pid" || code=$?
  printf '%s' "$code"
}

check_health() {
  local name="$1"
  local url="$2"
  local failures="$3"

  if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
    printf '0'
    return
  fi

  failures=$((failures + 1))
  printf '[dev] %s\n' "$name health check failed ($failures/$HEALTH_FAILURE_LIMIT)" >&2

  if (( failures >= HEALTH_FAILURE_LIMIT )); then
    fail "$name became unhealthy at $url"
  fi

  printf '%s' "$failures"
}

require_command curl
require_command npm
require_file "$BACKEND_DIR/.venv/bin/uvicorn" "Backend virtualenv is missing. Run: cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
require_file "$FRONTEND_DIR/node_modules" "Frontend dependencies are missing. Run: cd frontend && npm install"
has_openai_api_key || fail "OPENAI_API_KEY is missing. Set it in your shell or create backend/.env from backend/.env.example"

trap cleanup EXIT INT TERM

log "Starting backend at $BACKEND_URL"
(
  cd "$BACKEND_DIR"
  .venv/bin/uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

log "Starting frontend at $FRONTEND_URL"
(
  cd "$FRONTEND_DIR"
  VITE_API_BASE="$BACKEND_URL" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort
) &
FRONTEND_PID=$!

wait_for_url "backend" "$BACKEND_URL/health" "$BACKEND_PID"
wait_for_url "frontend" "$FRONTEND_URL" "$FRONTEND_PID"

log "Ready. Open $FRONTEND_URL"
log "Monitoring backend pid $BACKEND_PID and frontend pid $FRONTEND_PID. Press Ctrl-C to stop both."

backend_health_failures=0
frontend_health_failures=0

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    code="$(process_exit_code "$BACKEND_PID")"
    log "Backend exited with status $code"
    exit "$code"
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    code="$(process_exit_code "$FRONTEND_PID")"
    log "Frontend exited with status $code"
    exit "$code"
  fi

  backend_health_failures="$(check_health "backend" "$BACKEND_URL/health" "$backend_health_failures")"
  frontend_health_failures="$(check_health "frontend" "$FRONTEND_URL" "$frontend_health_failures")"

  sleep "$MONITOR_INTERVAL_SECONDS"
done
