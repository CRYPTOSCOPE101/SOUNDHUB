![SoundHub](frontend/public/logo.png)

<div align="center" style="margin: 20px 0px;">
<a href="https://github.com/soundXlab/SoundHub/actions/workflows/ci.yml">
  <img src="https://github.com/soundXlab/SoundHub/actions/workflows/ci.yml/badge.svg" />
</a>
<a href="https://github.com/soundXlab/SoundHub/releases">
  <img src="https://img.shields.io/github/v/release/soundXlab/SoundHub?label=Release" />
</a>
<a href="https://github.com/soundXlab/SoundHub/stargazers">
  <img src="https://img.shields.io/github/stars/soundXlab/SoundHub?style=social" />
</a>
<a href="LICENSE">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" />
</a>
</div>

# 🎛 SoundHub — Collaborative Workspace + Education Hub for Music Production

**GitHub + Jira + CI/CD for music. Not a marketplace. A place to work.**

SoundHub is an open-source platform that applies software engineering best practices to music production: Git-like version control, Pull Requests, Audio CI/CD, Branch Protection, and Project Management — all built for DAW projects.

![SoundHub demo](screenshots/demo.gif)

---

## What SoundHub Is

### 🎛 Collaborative Workspace
- **Git-like version control** for DAW projects (Ableton `.als`, FL Studio `.flp`, Logic `.logic`, Studio One `.song`)
- **Pull Requests** with approve/request_changes, waveform comments, diff between versions
- **Audio CI/CD** — automatic LUFS, True Peak, sample rate checks on every push
- **Branch Protection** — protect main, require PR, block force push
- **Review Sessions** — feedback rounds, approval chains, change orders
- **Project Management** — Kanban, Tasks, Wiki, Epics, Roadmaps, Milestones

### 📚 Education Hub
- **Structured learning paths** for mix engineers, producers, and students
- **Classroom mode** — teacher dashboard, student progress tracking
- **Interactive tutorials** — learn version control through real music projects
- **Community knowledge base** — wiki, discussions, best practices

---

## Why This Is Different from GitHub

DAW project files are opaque blobs to normal version control. GitHub shows you "this 40 MB binary changed" and nothing else.

SoundHub **parses** project files and understands them:

| | GitHub on `.als` | SoundHub on `.als` |
|---|---|---|
| Diff | "binary file changed" | **BPM 128 → 132** |
| | | **+ track `Pad` (midi)** |
| | | **+ plugin `Vital`** |
| | | **+ sample `VocalChop_01.wav`** |
| Metadata | nothing | tracks, devices, plugins, samples, signature |

---

## Key Features

| Feature | What it does | Unique? |
|---------|-------------|---------|
| **Git Branches & Merges** | Branches, merges, squash, fast-forward for DAW files | Only one on market |
| **Pull Requests** | PR with approve/request_changes, waveform comments | Only one on market |
| **Audio CI Checks** | Automatic LUFS, True Peak, sample rate on push | Only one on market |
| **Branch Protection** | Protect main, require PR, restrict force push | Only one on market |
| **Review Sessions** | Feedback rounds, approval chain, change orders | Best on market |
| **DAW-Aware** | Parses .als, .flp, .logic, .song — tracks, plugins, BPM | Top-3 on market |
| **Project Management** | Kanban, Epics, Roadmaps, Wiki, Tasks, Milestones | Best on market |
| **Enterprise Security** | SAST/DAST, secrets, audit log, IP allowlist | Only one on market |

---

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy · SQLite · PyJWT
- **Frontend:** React 18 · TypeScript · Vite
- **Storage:** Content-addressed blobs on disk (SHA-256), no external services required
- **AI:** Loudness analysis (EBU R128), stem splitting (Demucs/Spleeter)
- **API:** REST + GraphQL + Webhooks

---

## Quick Start

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

---

## CLI — Push DAW Projects

```bash
cd backend
./snd login --user demo --password demo123

# Fast: project + DAW metadata as one commit
./snd push ./Track_v12.als --project "artist-track" --branch review/v12 --message "v12"

# Full: master + stems → public review session with gapless A/B
./snd push ./Track_v12.als --audio ./master.wav --stems ./stems \
    --project "artist-track" --branch review/v12 --round 3 \
    --message "Round 3 candidate" --open --json
```

---

## DAW Parsing

| Format | Parser | What it extracts |
|--------|--------|-----------------|
| Ableton Live | `als_parser.py` | BPM, signature, tracks, devices, plugins, samples |
| Cubase | `cpr_parser.py` | BPM, tracks, VST plugins |
| REAPER | `rpp_parser.py` | BPM, signature, tracks, FX |
| FL Studio | `flp_parser.py` | Version, name, author, tempo |

---

## Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -q     # 35 tests
```

---

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get JWT |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |
| GET | `/api/projects/{id}/tree` | File tree with DAW analysis |
| POST | `/api/projects/{id}/commits` | Upload files → new commit |
| GET | `/api/projects/{id}/diff` | Smart diff (DAW-aware) |
| POST | `/api/sessions` | Create review session |
| GET | `/api/demo/review` | Demo review session |

---

## Roadmap

### ✅ Shipped
- Git-like version control (branches, commits, file snapshots)
- DAW-aware parsing (4 formats + smart metadata diff)
- Audio CI checks (LUFS, True Peak, sample rate, channels)
- Review sessions with approval flow
- Pull Requests + Branch Protection
- Project Management (Kanban, Tasks, Wiki, Epics)
- GraphQL API + Full-text Search (FTS5)
- Webhooks + Audit Log
- Enterprise Security (SAST/DAST, secrets, custom roles)

### 🔄 In Progress
- Desktop auto-sync CLI
- Education hub (classroom mode, learning paths)

### 📋 Planned
- Mobile app
- Real-time DAW collaboration
- AI Stem Splitter
- Browser DAW (MVP)
- Distribution integration

---

## Architecture

The backend is a **FastAPI** application with **70+ API endpoints**, **32 database tables**, and **20+ routers**.

### Key Components

| Component | Count | Description |
|-----------|-------|-------------|
| API Routers | 20+ | Auth, Sessions, Projects, Files, Diffs, Assets, Change Orders, Release Packages, Comparisons, Portfolio, References, Reminders, Roles, Search, Activity, Analytics, Templates, Tags, Groups, Pins, Webhooks |
| Database Tables | 32 | Users, Projects, Branches, Commits, Review Sessions, Versions, Comments, Rounds, Approvals, Ledgers, Packages, Deliverables, Notifications, Templates, Tags, Groups, Pins, Webhooks |
| Services | 15+ | Storage, Waveform, Analysis, Watermark, Ledger, Versioning, Roles, Reminders, Activity, Analytics, Webhooks, Templates, Tags, Groups, Loudness, DAW Parsers |

---

## Contributing

1. Fork the repo
2. Create a feature branch
3. Push and open a PR
4. Get review + CI checks pass
5. Merge

---

## License

MIT

---

*Built with ❤️ by the SoundHub community*
