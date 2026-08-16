
![SoundHub](frontend/public/logo.png)

<div align="center" style="margin: 20px 0px;">
<a href="https://github.com/CRYPTOSCOPE101/SoundHub/actions/workflows/ci.yml">
  <img src="https://github.com/CRYPTOSCOPE101/SoundHub/actions/workflows/ci.yml/badge.svg" />
</a>
<a href="https://github.com/CRYPTOSCOPE101/SoundHub/actions/workflows/release.yml">
  <img src="https://github.com/CRYPTOSCOPE101/SoundHub/actions/workflows/release.yml/badge.svg" />
</a>
<a href="https://github.com/CRYPTOSCOPE101/SoundHub/releases">
  <img src="https://img.shields.io/github/v/release/CRYPTOSCOPE101/SoundHub?label=Release" />
</a>
<a href="https://github.com/CRYPTOSCOPE101/SoundHub/issues">
  <img src="https://img.shields.io/github/issues/CRYPTOSCOPE101/SoundHub" />
</a>
<a href="https://github.com/CRYPTOSCOPE101/SoundHub/stargazers">
  <img src="https://img.shields.io/github/stars/CRYPTOSCOPE101/SoundHub?style=social" />
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

🎛 **SoundHub inside Ableton Live** — Max for Live prototype that embeds the
marketplace in the DAW: catalog, BPM-aware suggestions, buy & load. See
[`m4l/`](m4l/) and the [integration architecture](ARCHITECTURE.md).

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
- [ ] Verification badges (DAW-parsed), seller reputation, license enforcement
- [ ] Merges (DAG), audio preview, real-time collab
- [x] FL Studio & Cubase integration prototypes (`feat/flstudio-integration`, `feat/cubase-integration`)
- [ ] WalletConnect signing in M4L / relayer; REAPER equivalent (ReaScript)
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
