#!/usr/bin/env bash
# `make dev` — run the full SoundHub stack locally:
#   backend  → http://localhost:8000  (uvicorn, /api/health)
#   frontend → http://localhost:5173  (vite dev, proxies /api → :8000)
# Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

cleanup() {
  echo
  echo "⏹ stopping soundhub…"
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "${WEB_PID:-}" ]] && kill "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "▶ backend  → http://localhost:${API_PORT} (uvicorn)"
(cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT") &
API_PID=$!

echo "▶ frontend → http://localhost:${WEB_PORT} (vite dev)"
(cd frontend && npm run dev -- --port "$WEB_PORT" --strictPort) &
WEB_PID=$!

# wait for the stack, then leave both running in the foreground
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
if ! curl -fsS "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
  echo "✗ backend failed to start — check backend/.venv and config" >&2
  exit 1
fi
echo "✓ backend healthy (demo review seeded at /api/demo/review)"
echo "✓ stack up — open http://localhost:${WEB_PORT} (sample review CTA → /r/:token)"

wait
