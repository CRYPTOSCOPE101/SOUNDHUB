.PHONY: dev smoke test build e2e

# Run the full stack (backend :8000 + frontend :5173). Ctrl-C stops both.
dev:
	bash scripts/dev.sh

# Minimal pre-release smoke: backend health, demo seed, frontend served, e2e flow.
smoke:
	bash scripts/smoke.sh

# Backend tests + frontend typecheck/build.
test:
	cd backend && .venv/bin/python -m pytest tests/ -q
	cd frontend && npm run build

# Frontend production build.
build:
	cd frontend && npm run build

# Full end-to-end API journey only.
e2e:
	cd backend && .venv/bin/python -m pytest tests/test_e2e.py -q
