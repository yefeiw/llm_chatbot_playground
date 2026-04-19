#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
QDRANT_LOCK="$BACKEND_DIR/qdrant_data/.lock"

log() {
  printf '[seed] %s\n' "$*"
}

fail() {
  printf '[seed] ERROR: %s\n' "$*" >&2
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

require_command lsof
require_file "$BACKEND_DIR/.venv/bin/python" "Backend virtualenv is missing. Run: cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
has_openai_api_key || fail "OPENAI_API_KEY is missing. Set it in your shell or create backend/.env from backend/.env.example"

if [[ -e "$QDRANT_LOCK" ]] && lsof "$QDRANT_LOCK" >/dev/null 2>&1; then
  log "Local Qdrant is currently in use:"
  lsof "$QDRANT_LOCK" || true
  fail "Stop the backend/dev server before reseeding local Qdrant"
fi

log "Seeding mock catalog and rebuilding the local Qdrant index"
(
  cd "$BACKEND_DIR"
  .venv/bin/python seed.py
)
log "Seed complete"
