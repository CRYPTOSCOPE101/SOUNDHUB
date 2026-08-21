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

# 🎛 SoundHub — GitHub for Music

**The same thing as GitHub, but not for developers — for music producers, sound designers, audio engineers, and everyone who makes music.**

GitHub changed how code is written. SoundHub is changing how music is made.

---

## The Analogy

| GitHub (for code) | SoundHub (for music) |
|-------------------|----------------------|
| Code storage | DAW project storage (.als, .flp, .logic, .song, .rpp, .cpr) |
| Commits | Commits (snapshots of music projects) |
| Branches | Branches (parallel versions of a track) |
| Pull Requests | Pull Requests (mix review) |
| Branch Protection | Branch Protection (protect final mix) |
| CI/CD | Audio CI (LUFS, True Peak, sample rate) |
| Issues | Tasks (project tasks) |
| Wiki | Wiki (notes, brief, references) |
| Projects (Kanban) | Kanban (release management) |
| Code Review | Waveform Review (timeline comments) |
| Diff | DAW Diff (compare tracks, plugins, BPM) |
| Merge | Merge (merge mix versions) |
| Releases | Release Packages (release distribution) |
| Actions (CI/CD) | Workflows (YAML-based pipelines) |
| Dependabot | Security Alerts |

---

## Platform Scale

| Component | Count | Description |
|-----------|:-----:|-------------|
| **Database Models** | 122 | SQLAlchemy tables |
| **API Endpoints** | 364 | REST + GraphQL |
| **Routers** | 48 | API modules |
| **Services** | 20+ | Business logic |

---

## Key Features

### 🎛 Git-like Version Control for DAW

```
main ← release/v2.0 ← feat/new-drums ← hotfix/volume-fix
```

Branches. Merges. Diff. Every save is a commit with a parent chain. You can revert to any version.

**Supported DAWs:**
- Ableton Live (`.als`)
- FL Studio (`.flp`)
- Logic Pro (`.logic`)
- Studio One (`.song`)
- REAPER (`.rpp`)
- Cubase (`.cpr`)

### 🎵 Pull Requests for Music

Colleague uploaded new stems? Creates a PR. You listen, leave comments on the waveform, approve or request changes. Like code review, but for music.

### ✅ Audio CI/CD

On every push, automatically checks:

| Check | Target | Status |
|-------|--------|--------|
| Integrated LUFS | -16 to -12 | ✅ / ⚠️ / ❌ |
| True Peak | < -1.0 dBTP | ✅ / ⚠️ / ❌ |
| Sample Rate | ≥ 44100 Hz | ✅ / ❌ |
| Channels | 1-2 (mono/stereo) | ✅ / ⚠️ |

Red = mix not ready. Green = ready to release.

### 🛡 Branch Protection

Protect your main branch: require PRs, assign reviewers, block force push.

### 📋 Project Management

- **Kanban Boards** — visualize tasks
- **Tasks (Issues)** — GitHub Issues for music
- **Wiki** — project documentation with revisions
- **Epics** — large tasks
- **Roadmaps** — visual timeline of plans
- **Milestones** — deadlines
- **Calendar** — events and recurrence
- **Time Tracking** — time logging
- **Discussions** — forum for conversations
- **Requirements** — project requirements
- **OKRs** — objectives and key results

### 🎤 Review Workflow

- **Review Sessions** — feedback rounds with approval chain
- **Review Rounds** — numbered rounds
- **Approvals** — approve/reject with comments
- **Change Orders** — change orders with pricing
- **Share Links** — public links with password and expiry
- **Waveform Comments** — timestamped comments
- **Voice Comments** — voice feedback
- **Watermarking** — automatic preview watermarking

### 📦 Release Management

- **Release Packages** — assemble releases with deliverables
- **Immutable Releases** — immutable releases
- **Delivery Tokens** — secure file delivery
- **Invoice / Billing** — Stripe integration
- **Preflight QC** — quality checks before release

### 🔍 DAW-Aware Intelligence

- **DAW Parsing** — parse .als, .flp, .logic, .song, .rpp, .cpr
- **Smart Diff** — compare tracks, plugins, BPM, structure
- **Stem Management** — logical stem names (Kick→drums, Bass→bass)
- **Reference Track Comparison** — A/B comparison with level matching

### 🔒 Enterprise Security

- **SAST/DAST Scanning** — static and dynamic analysis
- **Secrets Management** — encrypted secrets
- **Audit Log** — audit trail
- **IP Allow List** — IP whitelist
- **Custom Roles** — custom roles
- **Environments** — staging/production
- **Push Rules** — commit validation rules

### 🔄 CI/CD & DevOps

- **Workflows** — YAML-based pipelines
- **Pipeline Artifacts** — build artifacts
- **Container Registry** — Docker images
- **Feature Flags** — feature management
- **Error Tracking** — error tracking
- **Incident Management** — incident management
- **On-call Schedules** — on-call rotations
- **Status Page** — status page

### 🧪 Testing

- **Test Plans** — test plans
- **Test Suites** — test suites
- **Test Cases** — test cases
- **Test Results** — results
- **Load Testing** — load testing

### 🌐 Code Intelligence

- **Code Search** — full-text search (FTS5)
- **Code Insights** — code reports
- **Code Owners** — automatic reviewers

### 📊 Analytics & Monitoring

- **Activity Feed** — activity timeline
- **Analytics** — project analytics
- **Notifications** — notifications
- **Reminders** — automated reminders

### 🏢 Collaboration

- **Teams** — teams with roles
- **Session Groups** — session groups
- **Session Tags** — tags for organization
- **Session Templates** — session templates
- **Portfolio** — public sessions
- **References** — reference tracks

### 📱 Integrations

- **Webhooks** — HTTP notifications
- **GraphQL API** — extended API
- **Full-text Search** — search across everything
- **Metadata** — project metadata
- **Extensions** — platform extensions

### 💰 Packages & Distribution

- **Packages** — sample packs, presets, plugins
- **Gists** — snippets
- **Sponsors** — sponsorship
- **Artifact Feeds** — artifact feeds

### 🏃 Agile Delivery

- **Sprints** — sprints
- **Retrospectives** — retrospectives
- **Story Points** — story points

---

## How It Works

### 1. Create a project

```bash
cd backend
./snd login --user demo --password demo123
./snd push ./Track_v12.als --project "my-track" --branch main --message "initial"
```

### 2. Upload a new version

```bash
./snd push ./Track_v13.als --project "my-track" --branch feat/new-drums --message "v13: new drums"
```

### 3. CI checks quality

```
✅ LUFS -14.5 (within range)
✅ True Peak -1.2 dBTP (safe)
✅ Sample Rate 48000 Hz
✅ Channels 2 (stereo)
```

### 4. Pull Request → Review → Merge

Colleague listens, comments on waveform, approves → merge to main.

---

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy · SQLite/PostgreSQL · PyJWT
- **Frontend:** React 18 · TypeScript · Vite
- **Storage:** Content-addressed blobs (SHA-256), no external services
- **AI:** Loudness analysis (EBU R128), stem splitting (Demucs/Spleeter)
- **API:** REST (364 endpoints) + GraphQL + Webhooks
- **CLI:** `snd` — push DAW projects from terminal

---

## Quick Start

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m scripts.seed_demo     # demo: demo / demo123
.venv/bin/uvicorn app.main:app --port 8000

# Frontend
cd frontend
npm install
npm run dev          # http://localhost:5173
```

---

## CLI — `snd push`

```bash
cd backend
./snd login --user demo --password demo123

# Fast: project + DAW metadata
./snd push ./Track_v12.als --project "my-track" --branch main --message "v12"

# Full: master + stems → review session
./snd push ./Track_v12.als --audio ./master.wav --stems ./stems \
    --project "my-track" --branch review/v12 --round 3 \
    --message "Round 3 candidate" --open --json
```

---

## Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -q     # 35 tests, all green
```

---

## Feature Matrix

### Version Control

| Feature | Status |
|---------|:------:|
| Git branches & merges | ✅ |
| Commits with parent chain | ✅ |
| File snapshots (content-addressed) | ✅ |
| Branch diff (DAW-aware) | ✅ |
| Pull Requests | ✅ |
| Branch Protection | ✅ |
| CODEOWNERS | ✅ |
| Merge Trains | ✅ |
| Git Tags + Releases | ✅ |
| Push Rules | ✅ |

### Audio

| Feature | Status |
|---------|:------:|
| DAW parsing (6 formats) | ✅ |
| Audio CI checks (LUFS/True Peak) | ✅ |
| Waveform comments | ✅ |
| Voice comments | ✅ |
| Stem management | ✅ |
| Reference track comparison | ✅ |
| Watermarking | ✅ |
| Loudness analysis | ✅ |

### Review & Approval

| Feature | Status |
|---------|:------:|
| Review Sessions | ✅ |
| Review Rounds | ✅ |
| Approval flow | ✅ |
| Change Orders | ✅ |
| Share links (password + expiry) | ✅ |
| Late-change protection | ✅ |
| Reminder automation | ✅ |
| Ledger (immutable history) | ✅ |

### Project Management

| Feature | Status |
|---------|:------:|
| Kanban Boards | ✅ |
| Tasks (Issues) | ✅ |
| Wiki (with revisions) | ✅ |
| Epics | ✅ |
| Roadmaps | ✅ |
| Milestones | ✅ |
| Calendar | ✅ |
| Time Tracking | ✅ |
| Discussions | ✅ |
| Requirements | ✅ |
| OKRs | ✅ |

### Security & DevOps

| Feature | Status |
|---------|:------:|
| Workflows (CI/CD) | ✅ |
| SAST/DAST | ✅ |
| Security Alerts | ✅ |
| Secrets Management | ✅ |
| Environments | ✅ |
| IP Allow List | ✅ |
| Custom Roles | ✅ |
| Audit Log | ✅ |
| Container Registry | ✅ |
| Feature Flags | ✅ |
| Error Tracking | ✅ |
| Incident Management | ✅ |
| On-call | ✅ |
| Status Page | ✅ |

### Testing

| Feature | Status |
|---------|:------:|
| Test Plans | ✅ |
| Test Suites | ✅ |
| Test Cases | ✅ |
| Test Results | ✅ |
| Load Testing | ✅ |

### Collaboration

| Feature | Status |
|---------|:------:|
| Teams (with roles) | ✅ |
| Session Groups | ✅ |
| Session Tags | ✅ |
| Session Templates | ✅ |
| Portfolio | ✅ |
| References | ✅ |
| Activity Feed | ✅ |
| Notifications | ✅ |

### API & Integrations

| Feature | Status |
|---------|:------:|
| REST API (364 endpoints) | ✅ |
| GraphQL API | ✅ |
| Full-text Search (FTS5) | ✅ |
| Webhooks | ✅ |
| Metadata | ✅ |

### Packages & Distribution

| Feature | Status |
|---------|:------:|
| Packages (sample packs) | ✅ |
| Gists | ✅ |
| Sponsors | ✅ |
| Artifact Feeds | ✅ |

### Agile Delivery

| Feature | Status |
|---------|:------:|
| Sprints | ✅ |
| Retrospectives | ✅ |
| Story Points | ✅ |

---

## Roadmap

### ✅ Shipped (all of the above)

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

*GitHub changed how code is written. SoundHub is changing how music is made.*
