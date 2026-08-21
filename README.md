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

**То же самое, что GitHub, но не для разработчиков, а для музыкальных продюсеров, саунд-дизайнеров, звукоинженеров и всех, кто создаёт музыку.**

GitHub изменил, как пишут код. SoundHub меняет, как создают музыку.

---

## Аналогия

| GitHub (для кода) | SoundHub (для музыки) |
|-------------------|----------------------|
| Хранение кода | Хранение DAW-проектов (.als, .flp, .logic, .song) |
| Коммиты (снимки кода) | Коммиты (снимки музыкальных проектов) |
| Ветки (параллельная разработка) | Ветки (параллельные версии трека) |
| Pull Requests (ревью кода) | Pull Requests (ревью микса) |
| Branch Protection (защита main) | Branch Protection (защита финального микса) |
| CI/CD (тесты кода) | Audio CI (проверка LUFS, True Peak, sample rate) |
| Issues (задачи) | Tasks (задачи по проекту) |
| Wiki (документация) | Wiki (notes, brief, references) |
| Projects (Kanban) | Kanban (управление релизами) |
| Code Review | Waveform Review (комментарии на таймлайне) |
| Diff (сравнение кода) | DAW Diff (сравнение треков, плагинов, BPM) |
| Merge (слияние веток) | Merge (слияние версий микса) |

---

## Что такое SoundHub

SoundHub — это облачная платформа для совместной работы над музыкальными проектами. Она применяет best practices из мира разработки ПО к музыкальному продакшну.

### Для кого

- **Музыкальные продюсеры** — управление версиями треков, совместная работа
- **Саунд-дизайнеры** — хранение и версионирование сэмплов и пресетов
- **Звукоинженеры** — review workflow для миксов и мастеринга
- **Микс-инженеры** — обратная связь от клиентов с таймкодами
- **Лейблы** — контроль релизов, approval chains, audit trail
- **Студии** — командная работа, roles, branch protection
- **Обучение** — classroom mode, learning paths

---

## Ключевые особенности

### 🎛 Git-like Version Control для DAW

```
main ← release/v2.0 ← feat/new-drums ← hotfix/volume-fix
```

Ветки. Мержи. Diff. Каждое сохранение — это коммит с parent chain. Можно откатиться к любой версии.

**Поддерживаемые DAW:**
- Ableton Live (`.als`)
- FL Studio (`.flp`)
- Logic Pro (`.logic`)
- Studio One (`.song`)
- REAPER (`.rpp`)
- Cubase (`.cpr`)

### 🎵 Pull Requests для Музыки

Коллега загрузил новые стемы? Создаёт PR. Вы прослушиваете, оставляете комментарии на waveform, одобряете или запрашиваете изменения. Как code review, но для музыки.

### ✅ Audio CI/CD

При каждом push автоматически проверяется:

| Проверка | Норма | Статус |
|----------|-------|--------|
| Integrated LUFS | -16 до -12 | ✅ / ⚠️ / ❌ |
| True Peak | < -1.0 dBTP | ✅ / ⚠️ / ❌ |
| Sample Rate | ≥ 44100 Hz | ✅ / ❌ |
| Channels | 1-2 (mono/stereo) | ✅ / ⚠️ |

Красный свет = микс не готов. Зелёный = можно релизить.

### 🛡 Branch Protection

Защитите main-ветку: требуйте PR, назначайте ревьюеров, блокируйте force push. Как в GitHub, но для .als файлов.

### 📋 Project Management

- **Kanban Boards** — визуализация задач
- **Tasks** — GitHub Issues для музыки
- **Wiki** — документация проекта
- **Epics** — крупные задачи
- **Roadmaps** — планы развития
- **Milestones** — дедлайны
- **Calendar** — события и повторения
- **Time Tracking** — учёт времени

### 🔒 Enterprise Security

- SAST/DAST scanning
- Encrypted secrets
- Audit log
- IP allowlist
- Custom roles

---

## Как это работает

### 1. Создайте проект

```bash
# Через CLI
cd backend
./snd login --user demo --password demo123
./snd push ./Track_v12.als --project "my-track" --branch main --message "initial"
```

### 2. Загрузите новую версию

```bash
./snd push ./Track_v13.als --project "my-track" --branch feat/new-drums --message "v13: new drums"
```

### 3. Создайте Pull Request

Через веб-интерфейс или API:
```
POST /api/projects/{id}/pull-requests
```

### 4. Получите feedback

Клиент оставляет комментарии на waveform:
> "На 1:32 слишком громкий вокал"

### 5. Исправьте и загрузите v2

```bash
./snd push ./Track_v14.als --project "my-track" --branch fix/volume --message "v14: vocals fixed"
```

### 6. CI проверяет качество

```
✅ LUFS -14.5 (в пределах нормы)
✅ True Peak -1.2 dBTP (безопасно)
✅ Sample Rate 48000 Hz
✅ Channels 2 (stereo)
```

### 7. Мерж в main

PR одобрен → мерж → релиз готов.

---

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy · SQLite · PyJWT
- **Frontend:** React 18 · TypeScript · Vite
- **Storage:** Content-addressed blobs (SHA-256), no external services
- **AI:** Loudness analysis (EBU R128), stem splitting
- **API:** REST + GraphQL + Webhooks

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

## Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -q     # 35 tests, all green
```

---

## Roadmap

### ✅ Shipped
- Git-like version control (branches, commits, file snapshots)
- DAW-aware parsing (6 formats + smart metadata diff)
- Audio CI checks (LUFS, True Peak, sample rate, channels)
- Review sessions with approval flow
- Pull Requests + Branch Protection
- Project Management (Kanban, Tasks, Wiki, Epics, Roadmaps)
- GraphQL API + Full-text Search (FTS5)
- Webhooks + Audit Log
- Enterprise Security (SAST/DAST, secrets, custom roles)
- Demo review endpoint (`/api/demo/review`)

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

Backend: **FastAPI** · **70+ API endpoints** · **32 database tables** · **20+ routers**

| Component | Count | Description |
|-----------|-------|-------------|
| API Routers | 20+ | Auth, Sessions, Projects, Files, Diffs, Assets, Change Orders, Release Packages, Comparisons, Portfolio, References, Reminders, Roles, Search, Activity, Analytics, Templates, Tags, Groups, Pins, Webhooks |
| Database Tables | 32 | Users, Projects, Branches, Commits, Review Sessions, Versions, Comments, Rounds, Approvals, Ledgers, Packages, Deliverables |
| Services | 15+ | Storage, Waveform, Analysis, Watermark, Ledger, Versioning, Roles, Reminders, Activity, Analytics, Webhooks, Loudness, DAW Parsers |

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
