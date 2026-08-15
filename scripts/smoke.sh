#!/usr/bin/env bash
# `make smoke` — minimal pre-release smoke check.
#
#   1. backend /api/health answers
#   2. demo seed exists (/api/demo/review returns a share token)
#   3. frontend is served on :5173 (vite dev)
#   4. end-to-end API journey passes (pytest tests/test_e2e.py)
#
# Exit non-zero on any failure — run before every demo/deploy.
set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

API_PID=""
WEB_PID=""
cleanup() {
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "=== SoundHub smoke check ==="

# --- backend ---
if ! curl -fsS "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
  echo "→ starting backend on :${API_PORT}"
  (cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT") &
  API_PID=$!
  for _ in $(seq 1 60); do
    curl -fsS "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi
curl -fsS "http://localhost:${API_PORT}/api/health" >/dev/null && echo "✓ backend health" || { echo "✗ backend not healthy" >&2; exit 1; }

# --- demo seed ---
DEMO=$(curl -fsS "http://localhost:${API_PORT}/api/demo/review")
echo "$DEMO" | grep -q '"share_token"' && [ -n "$(echo "$DEMO" | sed -n 's/.*"share_token":"\([^"]*\)".*/\1/p')" ] \
  && echo "✓ demo review seeded ($(echo "$DEMO" | sed -n 's/.*"name":"\([^"]*\)".*/\1/p'))" \
  || { echo "✗ demo seed missing" >&2; exit 1; }

# --- frontend ---
if ! curl -fsS -m 2 "http://localhost:${WEB_PORT}/" >/dev/null 2>&1; then
  echo "→ starting frontend on :${WEB_PORT}"
  (cd frontend && npm run dev -- --port "$WEB_PORT" --strictPort >/dev/null 2>&1) &
  WEB_PID=$!
  for _ in $(seq 1 90); do
    curl -fsS -m 2 "http://localhost:${WEB_PORT}/" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi
curl -fsS -m 2 "http://localhost:${WEB_PORT}/" >/dev/null && echo "✓ frontend served on :${WEB_PORT}" || { echo "✗ frontend not served" >&2; exit 1; }

# --- e2e journey ---
echo "→ running end-to-end journey (pytest tests/test_e2e.py)"
(cd backend && .venv/bin/python -m pytest tests/test_e2e.py -q) || { echo "✗ e2e failed" >&2; exit 1; }

echo "=== smoke OK — ready to demo/deploy ==="
