# Contributing to SoundHub

Thanks for wanting to help! SoundHub is a tokenized marketplace for finished
sounds — presets, loops, stems and packs — with a web app, a DAW parsing
engine, Solidity contracts and a Max for Live device. Any contribution is
welcome: code, tests, docs, M4L patches, or design feedback.

## Project layout

| Path | What lives there |
|---|---|
| `backend/` | FastAPI app — auth, repos/commits, DAW parsers, catalog & recommendations |
| `frontend/` | React 18 + TypeScript + Vite web app |
| `contracts/` | Hardhat + Solidity: SND token, marketplace escrow, release NFTs, DAO, faucet |
| `m4l/` | Max for Live device (`.amxd`), built from `soundhub-device.js` via `build_amxd.py` |
| `scripts/` | Dev tooling (screenshots, demo GIF) |

## Getting started

Follow the [Quick start](README.md#quick-start) in the README. It boots the
backend and frontend locally with a demo user (`demo` / `demo123`).

## Running checks

```bash
# Backend
cd backend
.venv/bin/python -m pytest tests/ -q

# Contracts
cd contracts
npm test            # hardhat: compile + 12 contract tests

# Frontend
cd frontend
npm run build       # tsc + vite build
```

CI runs all three on every push/PR — keep them green.

## M4L device

The `.amxd` is generated from `m4l/soundhub-device.js`:

```bash
cd m4l
python3 build_amxd.py   # writes ./SoundHub.amxd
```

Don't hand-edit the `.amxd` binary; edit the JS source and rebuild.

## Code style

- Python: PEP 8, type hints on public functions.
- TypeScript: strict (project already uses `tsc -b`).
- Solidity: follow the existing contract conventions (OpenZeppelin v5,
  NatSpec on public functions).
- Keep changes small and focused; explain the *why* in the PR description.

## Opening a PR

1. Open an issue first for anything non-trivial, or pick an open one.
2. Branch from `main`, keep the change scoped.
3. Run the checks above.
4. Open a PR — the template has a short checklist.

## License

By contributing you agree that your work is licensed under the
[MIT License](LICENSE).
