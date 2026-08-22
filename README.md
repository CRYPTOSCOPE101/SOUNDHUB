
![SoundHub](frontend/public/logo.png)

![AVL](screenshots/AVL.png)

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
<a href="https://deepwiki.com/soundXlab/SoundHub">
  <img src="https://deepwiki.com/badge.svg?repo=soundXlab/SoundHub" alt="DeepWiki" />
</a>
</div>





---

## What is SoundHub?

**SoundHub** is a collaborative cloud platform and educational hub for music production that brings GitHub-style workflows to DAW projects. 
It replaces scattered files and “mix_v3_FINAL_FINAL” folders with version control, project branches, Pull Requests, professional review sessions, and automated Audio CI checks for LUFS, True Peak, and file format. Producers, sound designers, mix engineers, studios, and labels can manage projects, compare versions, map stems, validate DAW files, and turn reusable samples, presets, and project assets into searchable artifacts. 
As an educational hub, SoundHub provides structured learning paths, interactive tutorials, classroom tools, and a community knowledge base that help creators master version control, audio production workflows, collaboration, and release management — from their first project to professional, repeatable production processes.

---

## Core Components

### 1. Version Control Engine (Git for Music)
- Distributed version control system tailored for DAW project files
- Every producer stores a **full copy** of the project history locally
- Operations (commit, branch, merge) work **instantly** without network
- Content-addressed storage (SHA-256) deduplicates identical audio blobs — pushing the same mix twice costs almost nothing

### 2. Project Hosting
- Cloud storage for DAW projects (Ableton `.alp`, FL Studio `.flp`, Logic `.logic`, Studio One `.song`, REAPER `.rpp`, Cubase `.cpr`)
- Pull Requests — the review process: propose a change → discuss → review → merge into main branch
- Tasks — issue tracking and task management for music projects
- Workflows — automated CI/CD pipelines (quality checks, builds, deployments triggered on every push)
- Kanban Boards — visual task management for releases
- Wiki — documentation inside the project
- Discussions — forum for conversations about the project

### 3. Community
- Fork — copy someone else's project to suggest changes
- Star — "liked" / bookmark
- Sponsor — fund producers and engineers
- Portfolio — public showcase of review sessions and releases

---

## What Makes SoundHub Unique

| Capability | Description |
|------------|-------------|
| **Pull Requests** | Review process: proposal → discussion → review → merge |
| **Branch Protection** | Rules: can't merge without review, without passing quality checks |
| **Audio CI/CD** | Automatic quality checks (LUFS, True Peak, sample rate) on every push |
| **DAW-Aware Parsing** | Understands .als, .flp, .logic, .song, .rpp, .cpr — shows tracks, plugins, BPM, structure |
| **Smart Diff** | Compares what actually changed: "BPM 128 → 132", "+ track Pad", "+ plugin Vital" |
| **Waveform Review** | Timestamped comments directly on the audio timeline |
| **Change Orders** | Formal change requests with pricing and approval workflow |
| **Release Packages** | Assemble deliverables, run QC preflight, lock and deliver securely |
| **Enterprise Security** | SAST/DAST scanning, encrypted secrets, audit log, IP allowlist, custom roles |
| **Full Project Management** | Kanban, Tasks, Wiki, Epics, Roadmaps, Milestones, Calendar, Time Tracking |

---

## Architecture

```
SoundHub (Cloud)
├── Projects (DAW project storage)
├── Pull Requests (mix review + approval)
├── Tasks (project management)
├── Workflows (CI/CD pipelines)
├── Kanban (release management)
├── Packages (distribution registry)
├── Portfolio (public showcase)
└── API (REST + GraphQL + Webhooks)

Local (CLI / Desktop)
├── Commits (project snapshots)
├── Branches (parallel versions)
├── Merges (combine versions)
├── Diffs (compare what changed)
└── snd CLI (push from terminal or DAW)
```

---

## Key Concepts

| Concept | What it means in music |
|---------|----------------------|
| **Commit** | A snapshot of all project files at a specific moment (DAW project + stems + metadata) |
| **Branch** | A parallel line of development (e.g., `feature/new-drums`, `fix/volume-123`) |
| **Merge** | Combining branches (squash, fast-forward, recursive) — merging mix versions |
| **Revert** | Rolling back to a previous mix version |
| **Cherry-pick** | Taking a specific commit from one branch into another |
| **Blame** | Who changed each track and when |
| **Monorepo** | One repository for multiple releases or EPs |
| **Pull Request** | A proposed change that gets reviewed before merging — like code review, but for mixes |
| **Branch Protection** | Rules on the main branch: require PR, require CI checks pass, block force push |
| **CI/CD** | Automated quality checks: LUFS, True Peak, sample rate, channels — run on every push |

---

## How It Works in Practice

### A producer working alone

1. Create a project on SoundHub
2. Push your Ableton set: `snd push ./Track_v1.als --project "my-track"`
3. SoundHub parses the DAW file, extracts track names, plugins, BPM
4. Continue working, push v2, v3, v4...
5. Every push creates a commit with full history
6. Compare any two versions with smart diff

### A sound designer discovering unique sounds

*   1.  
    Search for unique sounds, samples, presets, and project assets
*   2.  
    Filter results by instrument, genre, BPM, key, format, and license
*   3.  
    Preview and compare assets before adding them to a project
*   4.  
    Buy or license the perfect sound and download it with its metadata
*   5.  
    Import it into the DAW and continue building the track
*   6.  
    Publish original sounds as searchable artifacts and grow a creative portfolio

### A mix engineer working with a client

1. Engineer creates a Review Session, uploads mix v1
2. Client receives a share link (no account needed)
3. Client leaves timestamped comments: "at 1:32 vocals too loud"
4. Engineer sees comments, fixes, uploads v2
5. Client approves → release package → delivery

### A student learning music production

1. Follow structured tutorials and guided learning paths
2. Practice inside real DAW projects instead of isolated exercises
3. Study project versions, mix decisions, stems, plugins, and production workflows
4. Submit assignments or project updates for instructor and peer review
5. Receive timestamped feedback and track progress through project history
6. Build a portfolio of completed projects and demonstrate professional skills

### A label managing multiple artists

1. All projects in one place
2. Branch protection: main is protected, PR required
3. Custom roles: A&R sees everything, artist sees only their project
4. Audit log: who changed what and when
5. Kanban: track status of every release
6. Milestones: deadlines and plans

---

## Platform Scale

| Metric | Count |
|--------|------:|
| Database Models | 122 |
| API Endpoints | 364 |
| API Routers | 48 |
| Services | 20+ |
| Supported DAWs | 6 |
| Test Cases | 35 |

---

## Full Feature List

### Version Control (10 features)
- Git branches & merges (merge, squash, fast-forward)
- Commits with parent chain (full history)
- Content-addressed file snapshots (SHA-256 deduplication)
- DAW-aware branch diff (compare tracks, plugins, BPM)
- Pull Requests with reviews (approve/request_changes)
- Branch Protection Rules (require PR, require CI, block force push)
- CODEOWNERS (automatic reviewer assignment)
- Merge Trains (merge queue to prevent conflicts)
- Git Tags + Release Notes
- Push Rules (commit validation)

### Audio (8 features)
- DAW parsing for 6 formats (.als, .flp, .logic, .song, .rpp, .cpr)
- Audio CI checks (LUFS, True Peak, sample rate, channels)
- Waveform timestamped comments
- Voice comments
- Stem management with logical names
- Reference track A/B comparison with level matching
- Automatic watermarking of preview versions
- Loudness analysis (EBU R128)

### Review & Approval (8 features)
- Review Sessions with approval chain
- Numbered Review Rounds
- Approval flow (approve/reject with comments)
- Change Orders with pricing
- Share Links with password + expiry + allowlist
- Late-change protection (retention period + recall fee)
- Automated reminders
- Immutable Ledger (audit trail of all actions)

### Project Management (11 features)
- Kanban Boards
- Tasks (Issues)
- Wiki with revisions
- Epics
- Roadmaps (visual timeline)
- Milestones
- Calendar with recurrence
- Time Tracking
- Discussions (forum)
- Requirements
- OKRs (Objectives and Key Results)

### Security & DevOps (14 features)
- Workflows (YAML-based CI/CD)
- SAST/DAST scanning
- Security Alerts
- Secrets Management (encrypted)
- Environments (staging/production)
- IP Allow List
- Custom Roles
- Audit Log
- Container Registry (Docker)
- Feature Flags
- Error Tracking
- Incident Management
- On-call Schedules
- Status Page

### Testing (5 features)
- Test Plans
- Test Suites
- Test Cases
- Test Results
- Load Testing

### Collaboration (8 features)
- Teams with roles
- Session Groups
- Session Tags
- Session Templates
- Portfolio (public sessions)
- References (reference tracks)
- Activity Feed
- Notifications

### API & Integrations (5 features)
- REST API (364 endpoints)
- GraphQL API
- Full-text Search (SQLite FTS5)
- Webhooks
- Metadata

### Packages & Distribution (4 features)
- Packages (sample packs, presets, plugins)
- Gists (snippets)
- Sponsors
- Artifact Feeds

### Agile Delivery (3 features)
- Sprints
- Retrospectives
- Story Points

---

## Business Model

| Plan | Price | What you get |
|------|-------|-------------|
| **Free** | $0 | Open-source, self-hosted, everything included |
| **Cloud (planned)** | TBD | Hosted version, no server setup needed |
| **Enterprise (planned)** | Custom | SLA, SSO, dedicated instance, priority support |

---

## Scale of the Ecosystem

- **Open source** — MIT license, anyone can self-host
- **122 database models** — covering every aspect of music production workflow
- **364 API endpoints** — full REST + GraphQL access
- **6 DAW formats** supported natively
- **20+ backend services** — storage, analysis, watermarking, versioning, webhooks, and more
- **35 automated tests** — ensuring reliability

---

## Where SoundHub is NOT

SoundHub is **not**:
- A DAW (no audio editing, no real-time collaboration)
- A sample marketplace (no buying/selling of sounds)
- A streaming platform (no Spotify-like playback)
- A social network (no follower feeds, no likes)
- A mobile app (desktop + web only, for now)

SoundHub **is** a **version control and collaboration platform** for music production — the place where producers, engineers, and labels manage their projects, review mixes, and deliver releases.

---

## In One Sentence

**SoundHub is to music production what GitHub is to software development: a platform where you store your projects, track every change, review with your team, automate quality checks, and deliver releases — all in one place.**

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

## Backend Architecture

The backend is a **FastAPI** application with **70 API endpoints**, **32 database tables**, and **20 routers**.

![Project Structure](screenshots-backend/01-project-structure.png)
![Architecture](screenshots-backend/04-architecture-diagram.png)
![Auth Flow](screenshots-backend/06-auth-flow.png)
![Deployment](screenshots-backend/10-deployment.png)

### Key Components

| Component | Count | Description |
|-----------|-------|-------------|
| API Routers | 20 | Auth, Sessions, Projects, Files, Diffs, Assets, Change Orders, Release Packages, Comparisons, Portfolio, References, Reminders, Roles, Search, Activity, Analytics, Templates, Tags, Groups, Pins, Webhooks |
| Database Tables | 32 | Users, Projects, Branches, Commits, Review Sessions, Versions, Comments, Rounds, Approvals, Ledgers, Packages, Deliverables, Notifications, Templates, Tags, Groups, Pins, Webhooks |
| Services | 15+ | Storage, Waveform, Analysis, Watermark, Ledger, Versioning, Roles, Reminders, Activity, Analytics, Webhooks, Templates, Tags, Groups, Stripe Pay, USDC Pay, Reputation, Licenses, Catalog, DAW Parsers |
| Endpoints | 70 | RESTful API with JWT + Web3 wallet auth |

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

- `SOUNDHUB_SECRET_KEY` is required when `SOUNDHUB_ENV=production` (the app
  refuses to boot without it); locally an ephemeral key is generated per run.
- CORS origins are an allowlist — set `SOUNDHUB_CORS_ORIGINS` (comma-separated)
  to the frontend origins you deploy; it defaults to the vite dev server.
- Review-link passwords are stored in plaintext and passed as a `?password=`
  query parameter — do not treat a share link as a strong access control.
- The Render blueprint seeds a demo account (`demo` / `demo123`); drop
  `python -m scripts.seed_demo` from `startCommand` for anything non-demo.
- Smart contracts are unaudited — test on testnet first.
- SND supply is fixed (1,000,000) — no mint function.
