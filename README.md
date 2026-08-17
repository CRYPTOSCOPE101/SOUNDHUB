
![SoundHub](frontend/public/logo.png)





<div align="center" style="margin: 20px 0px;">
<a href="https://github.com/soundXlab/SoundHub/actions/workflows/ci.yml">
  <img src="https://github.com/soundXlab/SoundHub/actions/workflows/ci.yml/badge.svg" />
</a>
<a href="https://github.com/soundXlab/SoundHub/actions/workflows/release.yml">
  <img src="https://github.com/soundXlab/SoundHub/actions/workflows/release.yml/badge.svg" />
</a>
<a href="https://github.com/soundXlab/SoundHub/releases">
  <img src="https://img.shields.io/github/v/release/soundXlab/SoundHub?label=Release" />
</a>
<a href="https://github.com/soundXlab/SoundHub/issues">
  <img src="https://img.shields.io/github/issues/soundXlab/SoundHub" />
</a>
<a href="https://github.com/soundXlab/SoundHub/stargazers">
  <img src="https://img.shields.io/github/stars/soundXlab/SoundHub?style=social" />
</a>
<a href="LICENSE">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" />
</a>
<a href="Whitepaper.pdf">
  <img src="https://img.shields.io/badge/Whitepaper-PDF-orange.svg" />
</a>
</div>

# 🎛 What is SoundHub?

SoundHub is a tokenized marketplace where music producers buy and sell finished presets, loops, stems, and sound packs with on-chain ownership and licensing

**Don't generate. Buy. — the marketplace lives inside your DAW.** Presets,
loops, stems and packs, paid for with SND — from the SoundHub panel in
Ableton Live (Max for Live prototype in `m4l/`) or the web app.

![SoundHub demo — landing walkthrough](screenshots/demo.gif)

![SoundHub demo — landing scroll](screenshots/landing-demo.gif)

![SoundHub main page](screenshots/main-light.png)
![SoundHub projects](screenshots/projects.png)
![SoundHub repo page](screenshots/repo-page.png)
![SoundHub branch selector](screenshots/repo-page-branches.png)

📄 Read the [Project description](DESCRIPTION.md) — what SoundHub is, live
features vs roadmap, and how it compares to existing tools.

📄 Read the [Litepaper](LITEPAPER.md) — vision, tokenized layer, tokenomics
and roadmap.

🎛 **SoundHub inside your DAW** — Max for Live prototype for Ableton Live
(`m4l/`) that embeds the marketplace (catalog, BPM-aware suggestions, buy &
load), pushes the current set as a versioned commit (native sidecar), and
pulls open review comments into the DAW. The same loop works in REAPER via a
ReaScript panel (`reaper/`). See [`m4l/`](m4l/) and the [integration
architecture](ARCHITECTURE.md).

GitHub, but for DAW projects — Ableton Live (`.als`), Cubase (`.cpr`),
REAPER (`.rpp`) and FL Studio (`.flp`). Version your tracks, see *what
actually changed* between versions (not just "file modified"), and
collaborate without zip-files floating around a Discord server.

## Why this is different from git/GitHub

DAW project files are opaque blobs to normal version control. GitHub
shows you "this 40 MB binary changed" and nothing else.

SoundHub parses the project files and understands them:

| | GitHub on `.als` | SoundHub on `.als` |
|---|---|---|
| Diff | "binary file changed" | **BPM 128 → 132** |
| | | **+ track `Pad` (midi)** |
| | | **+ plugin `Vital`** |
| | | **+ sample `VocalChop_01.wav`** |
| Metadata | nothing | tracks, devices, plugins, samples, signature |

It also stores files **content-addressed** (deduplicated by SHA-256), so a
full-snapshot commit model costs almost nothing when little changed.

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy · SQLite · PyJWT
- **Frontend:** React 18 · TypeScript · Vite
- **Storage:** content-addressed blobs on disk (`backend/data/blobs/`),
  no external services required

## Quick start

```bash
# 1. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m scripts.seed_demo     # demo user: demo / demo123
.venv/bin/uvicorn app.main:app --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173

# 3. Open http://localhost:5173 and sign in with demo / demo123
```

## Tests

```bash
# Backend
cd backend
.venv/bin/python -m pytest tests/ -q

# Contracts (compile + 12 tests: token, royalties, splits, escrow, faucet, DAO)
cd contracts
npm test

# Frontend (tsc + vite build)
cd frontend
npm run build
```

All three run automatically in [CI](.github/workflows/ci.yml) on every push
and pull request.

## Releases

Tag a version and CI publishes a [GitHub Release](.github/workflows/release.yml)
with the built Max for Live device:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Per-version notes — what changed, how to test, known limits — live in
[CHANGELOG.md](CHANGELOG.md).

## API overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | create account |
| POST | `/api/auth/login` | get JWT |
| GET | `/api/projects` | list repos |
| POST | `/api/projects` | create repo |
| GET | `/api/projects/{id}/tree` | file tree of HEAD (with DAW analysis) |
| POST | `/api/projects/{id}/commits` | upload files → new commit |
| GET | `/api/projects/{id}/commits` | history |
| GET | `/api/projects/{id}/files/{path}` | download a file |
| GET | `/api/projects/{id}/diff?path=…&from=…&to=…` | smart diff |

## `snd push` — push a complete DAW project (branch: `snd-project-push`)

`backend/snd` is a small CLI that pushes a DAW project to SoundHub as a
versioned commit — fast mode (project + DAW metadata) or full review mode
(master audio + stems → public review session with gapless A/B). DAW files
are parsed **locally** (tracks, instruments, plugins AND their settings
where the format stores them — REAPER `PARAM` lines, Ableton preset refs)
and the parsed structure is stored as `SOUNDHUB-MANIFEST.json` inside the
commit tree (also re-analyzed server-side by the tree/diff endpoints).

```bash
cd backend
./snd login --user demo --password demo123
# fast: project + extracted DAW metadata as one commit
./snd push ./Track_v12.als --project "artist-track" --branch review/v12 --message "v12"
# full: master + stems open a public review session (gapless A/B) and return the review URL
./snd push ./Track_v12.als --audio ./master.wav --stems ./stems \
    --project "artist-track" --branch review/v12 --round 3 \
    --message "Round 3 candidate" --open --json
# directory mode (legacy): scan a folder, media skipped unless --include-media
./snd push ~/Projects/Neon --project "Neon Warehouse" --message "v12 bounce" --include-media
```

- `--project` accepts an existing project name/id or a new name to auto-create.
- **Preflight before upload**: file existence, size, extension and `.als`
  readability (a corrupt file is rejected) — for single files and folders alike.
- **Atomic**: blobs are stored first (content-addressed → re-pushes dedup),
  then the commit + review session/version/stems are created in ONE
  transaction — a failed push never leaves a half-pushed version.
- `--audio` attaches the master as a review version (available for gapless
  A/B once a second version exists), `--stems` attaches stem renders as
  structured `StemAsset`s matched by logical name (Kick→drums, Bass→bass…),
  `--round` sets the version's `round_number`.
- `--json` prints a stable machine-readable contract for automation (M4L):

```json
{"ok": true, "project_id": 1, "branch": "review/v12", "commit_id": 5,
 "version_id": 3, "session_id": 2, "share_token": "…",
 "review_url": "http://localhost:5173/r/…",
 "uploaded": {"als": true, "master": true, "stems": 12},
 "deduplicated": 4}
```

## Native sidecar — push from inside Live (Max 8.5+)

The Max for Live push button runs a **native sidecar** (`m4l/sidecar.js`)
through Max's built-in `node.script` (Max 8.5+ ships a Node.js runtime). It
reads the current `.als` from disk and posts a real multipart body straight
to the backend — **no external process** (`shell` is blocked inside Live and
`httprequest` mangles binary multipart, so a sidecar is the in-Live
transport). The same code is a plain CLI:

```bash
cd backend
node ../m4l/sidecar.js push --target ./Track_v12.als --audio ./master.wav \
  --project "artist-track" --branch review/v12 --round 3 \
  --api http://127.0.0.1:8000 --token <token> --json
# → {"ok": true, "commit_id": 42, "review_url": "http://localhost:5173/r/…"}
```

The sidecar does not build the local `SOUNDHUB-MANIFEST.json` (that needs
the Python parsers); the backend re-parses every pushed DAW file itself, so
smart diff and tree analysis still work. Covered by
`backend/tests/test_snd_sidecar.py` (live uvicorn + real `node`).

## Bridge contract — `snd serve` (localhost:8765, fallback)

On Max versions without `node.script` (before 8.5), the device falls back to
a tiny localhost JSON bridge, a thin client over the same `snd push --json`
pipeline: the device POSTs JSON and the bridge does the real work.

```bash
cd backend
./snd login --user demo --password demo123   # once
./snd serve                                  # bridge on http://127.0.0.1:8765
```

### `POST /push` — request

```json
{"target": "/path/to/Track_v12.als",
 "audio": "/path/to/master.wav",
 "stems": "/path/to/stems",
 "project": "artist-track",
 "branch": "review/v12",
 "round": 3,
 "message": "Round 3 candidate"}
```

Only `target` is required. `audio`/`stems` switch on review mode; `project`
auto-creates when missing; `branch` defaults to `main`.

### `POST /push` — response (stable contract for automation)

```json
{"ok": true, "project_id": 5, "branch": "review/v12", "commit_id": 42,
 "version_id": 7, "session_id": 3, "share_token": "tok123",
 "review_url": "http://localhost:5173/r/tok123",
 "uploaded": {"als": true, "master": true, "stems": 2},
 "deduplicated": 1}
```

### Error codes

| HTTP | JSON | Meaning |
|---|---|---|
| `400` | `{"ok": false, "error": "bad JSON body…"}` | malformed request — never reaches the backend |
| `400` | `{"ok": false, "error": "Not found: …"}` | preflight: missing `.als` |
| `400` | `{"ok": false, "error": "Master file not found: …"}` | review mode without the audio file |
| `400` | `{"ok": false, "error": "Review mode requires --audio…"}` | stems given without a master |
| `400` | `{"ok": false, "error": "Unsupported project file type…"}` | not a `.als`/`.cpr`/`.rpp`/`.flp` (or directory) |
| `400` | `{"ok": false, "error": "HTTP 401: …"}` | pipeline failed server-side (auth, missing project, …) — any server status ≥ 400 is surfaced as `HTTP <code>: <body>` |

All preflight failures return `400` and never create a version — the bridge
runs the same preflight as the CLI. `GET /health` → `{"ok": true, "service": "snd-bridge"}`.

### Idempotency

The push pipeline is **idempotent by construction**: blobs are stored
content-addressed (SHA-256), so re-pushing an identical `.als` + manifest
creates no new blobs (`deduplicated` counts them) and yields a predictable
`commit_id`/`version_id`. Only a changed file produces new blobs and a new
commit — same input, same result.

### curl smoke — golden path

```bash
# 1. health
curl -s http://127.0.0.1:8765/health
# {"ok": true, "service": "snd-bridge"}

# 2. fast push (project + DAW metadata)
curl -s -X POST http://127.0.0.1:8765/push \
  -H "Content-Type: application/json" \
  -d '{"target": "/abs/path/Track_v12.als", "project": "artist-track", "message": "v12"}'
# {"ok": true, "project_id": 5, "commit_id": 42, "branch": "main", …}

# 3. re-push the same export — idempotent, no new blobs
curl -s -X POST http://127.0.0.1:8765/push \
  -H "Content-Type: application/json" \
  -d '{"target": "/abs/path/Track_v12.als", "project": "artist-track", "message": "v12"}'
# {"ok": true, "commit_id": 42, "deduplicated": N > 0}
```

### Negative smoke (must all return `400` + `{"ok": false, …}`)

```bash
# missing target
curl -s -X POST http://127.0.0.1:8765/push -H "Content-Type: application/json" -d '{}'
# {"ok": false, "error": "…target…"}

# nonexistent .als
curl -s -X POST http://127.0.0.1:8765/push -H "Content-Type: application/json" \
  -d '{"target": "/abs/path/nope.als"}'
# {"ok": false, "error": "Not found: /abs/path/nope.als"}

# malformed JSON
curl -s -X POST http://127.0.0.1:8765/push -H "Content-Type: application/json" -d '{not json'
# {"ok": false, "error": "bad JSON body…"}
```

These are exactly the cases the CI bridge smoke covers
(`pytest -k bridge`); the CI script and this README stay in sync.

### Troubleshooting — symptom → cause → fix

| Symptom | Cause | Fix |
|---|---|---|
| `Push failed (bridge unreachable?)` | Max < 8.5 (no `node.script`) and `snd serve` isn't running | upgrade to Max 8.5+ (native sidecar), or run `./snd serve` and keep it open |
| `Push failed: HTTP 401/403` | no valid session | run `./snd login --user … --password …` once |
| `Push failed: bad JSON body` | device ↔ bridge mismatch | reload the device, check `bridge` points at `http://127.0.0.1:8765` |
| `Push failed: Target file not found` | `.als` path wrong / unsaved set | save the Live set (Cmd/Ctrl+S), use the absolute path |
| `Push failed: Master file not found` | `audio` configured but missing | point `audio` at the real render, or drop it for a fast push |
| `Push failed: File too large` | `.als` above the upload limit | raise `MAX_UPLOAD_SIZE` in `backend/app/config.py` or trim media |
| `fast push (no review)` | no master render attached | add `audio <path>` so the push opens a review session for A/B |

## DAW parsing engine (`backend/app/services/daw/`)

| Format | File | Approach |
|---|---|---|
| Ableton Live | `als_parser.py` | gunzip → XML → tempo, signature, tracks, devices, plugins, samples |
| Cubase | `cpr_parser.py` | XML scan → tempo, tracks, VST plugins |
| REAPER | `rpp_parser.py` | text parse → tempo, signature, tracks, FX |
| FL Studio | `flp_parser.py` | binary chunk walk (FLhd/FLPI/FLdt) → version, name, author, tempo |
| Diff engine | `diff_engine.py` | structured summary diff + unified raw diff (pretty XML / text / hex) |

## Roadmap — marketplace first (don't generate, buy)

- [x] Foundation: repos, snapshot commits, content-addressed storage
- [x] DAW parsing for all four formats + smart metadata diff
- [x] Tokenized layer: SND, Release NFTs, DAO, wallet sign-in (Base Sepolia)
- [x] `SoundHubMarket` escrow contract (tested, deployed on Base Sepolia)
- [x] Marketplace UI: list/buy/confirm/refund + SND faucet (100 SND/day)
- [x] In-DAW prototype: SoundHub inside Ableton Live (M4L, `m4l/`) — catalog, BPM suggestions, buy & load
- [x] Recommendation service (`/api/assets/recommend`, DAW-metadata scoring) + asset delivery (signed-token download)
- [x] Auto-import into Live: `/download64` → User Library write → browser refresh
- [x] Repo-first UI (own design): repo tabs, branch selector, commits view, README; Ableton light/dark themes; SoundHub-repo page via GitHub API
- [x] Branches: named pointers, per-branch history/tree/diff (merges: DAG — next)
- [ ] Token gating on purchase, one-click device insert, key/tracks/devices context from Live API
- [x] Verification badges (wallet-linked), seller reputation (real platform data), license enforcement
- [ ] Merges (DAG), audio preview, real-time collab
- [x] FL Studio & Cubase integration prototypes (`feat/flstudio-integration`, `feat/cubase-integration`)
- [ ] WalletConnect signing in M4L / relayer; REAPER push via bridge (ReaScript panel ships in `reaper/` — push via `snd` CLI, comments via public export)
- [ ] S3/Azure blob backend for production scale

## Tokenized platform (web3) 🪙

SoundHub is a tokenized platform on **Base** (EVM). Four smart contracts
live in `contracts/` (Hardhat + OpenZeppelin):

| Contract | What it does |
|---|---|
| `SND.sol` | **SND** ERC-20 platform token — permit, votes for the DAO, fixed supply, marketplace payment rail |
| `SoundHubRelease.sol` | **Release NFTs** (ERC-721 + ERC-2981) — music releases with royalty %, on-chain collaborator revenue split, fundable treasury (ETH/SND) with order-independent claiming |
| `SoundHubMarket.sol` | **Escrow marketplace** — list finished sounds for SND, buy into escrow, dispute window, refunds |
| `SoundHubFaucet.sol` | **Testnet faucet** — 100 SND per wallet per day so testers can buy |
| `SoundHubGovernor.sol` | **DAO** — SND holders propose/vote, execution via 1-day timelock |
| `TimelockController` | safety delay before any executed proposal |

### Features wired into the app
- **Sign in with wallet** (EIP-191 personal_sign verified server-side, JWT issued)
- **Marketplace** — list finished sounds for SND, buy through escrow, confirm receipt, request refunds
- **SND faucet** — claim 100 testnet SND per day to try buying
- **Mint a Release NFT** per project — set royalty and collaborator split
- **Tip artists** — fund a release treasury with SND or ETH, collaborators claim on-chain
- **DAO page** — connect wallet, see voting power, vote on proposals

### Deploy

```bash
cd contracts
npm install
cp .env.example .env            # set DEPLOYER_PRIVATE_KEY
npm run deploy:base-sepolia     # or: deploy:base for mainnet
```

The deploy script writes addresses to `deployments/{network}.json` and copies
them to `frontend/public/contracts.json` so the UI connects automatically.
Contracts are verified against real transactions in the test suite
(`npx hardhat test`, 12 tests covering token, royalties, splits, escrow
marketplace, faucet and the full propose → vote → queue → execute DAO flow).

## Security note

- MVP uses a dev JWT secret — set `SOUNDHUB_SECRET_KEY` and tighten CORS
  (`allow_origins`) before any real deployment.
- Smart contracts are unaudited — test on testnet first.
- SND supply is fixed (1,000,000) — no mint function.
