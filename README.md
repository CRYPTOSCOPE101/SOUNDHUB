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
| Хранение кода | Хранение DAW-проектов (.als, .flp, .logic, .song, .rpp, .cpr) |
| Коммиты | Коммиты (снимки музыкальных проектов) |
| Ветки | Ветки (параллельные версии трека) |
| Pull Requests | Pull Requests (ревью микса) |
| Branch Protection | Branch Protection (защита финального микса) |
| CI/CD | Audio CI (LUFS, True Peak, sample rate) |
| Issues | Tasks (задачи по проекту) |
| Wiki | Wiki (notes, brief, references) |
| Projects (Kanban) | Kanban (управление релизами) |
| Code Review | Waveform Review (комментарии на таймлайне) |
| Diff | DAW Diff (сравнение треков, плагинов, BPM) |
| Merge | Merge (слияние версий микса) |
| Releases | Release Packages (дистрибуция релизов) |
| Actions (CI/CD) | Workflows (YAML-based pipelines) |
| Dependabot | Security Alerts |
| Codespaces | Cloud IDE (планируется) |

---

## Масштаб платформы

| Компонент | Количество | Описание |
|-----------|:----------:|----------|
| **Database Models** | 122 | Таблицы SQLAlchemy |
| **API Endpoints** | 364 | REST + GraphQL |
| **Routers** | 48 | Модули API |
| **Services** | 20+ | Бизнес-логика |

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

### 🛡 Branch Protection

Защитите main-ветку: требуйте PR, назначайте ревьюеров, блокируйте force push.

### 📋 Project Management

- **Kanban Boards** — визуализация задач
- **Tasks (Issues)** — GitHub Issues для музыки
- **Wiki** — документация проекта с ревизиями
- **Epics** — крупные задачи
- **Roadmaps** — планы развития (визуальная шкала)
- **Milestones** — дедлайны
- **Calendar** — события и повторения
- **Time Tracking** — учёт времени
- **Discussions** — форум для обсуждений
- **Requirements** — требования к проекту
- **OKRs** — цели и ключевые результаты

### 🎤 Review Workflow

- **Review Sessions** — раунды фидбека с approval chain
- **Review Rounds** — нумерованные раунды
- **Approvals** — approve/reject с комментариями
- **Change Orders** — заказы на изменения с ценами
- **Share Links** — публичные ссылки с паролем и сроком действия
- **Waveform Comments** — таймстемповые комментарии
- **Voice Comments** — голосовые комментарии
- **Watermarking** — автоматическая маркировка preview-версий

### 📦 Release Management

- **Release Packages** — сборка релиза с deliverables
- **Immutable Releases** — неизменяемые релизы
- **Delivery Tokens** — безопасная выдача файлов
- **Invoice / Billing** — Stripe интеграция
- **Preflight QC** — проверка качества перед релизом

### 🔍 DAW-Aware Intelligence

- **DAW Parsing** — парсинг .als, .flp, .logic, .song, .rpp, .cpr
- **Smart Diff** — сравнение треков, плагинов, BPM, структуры
- **Stem Management** — логические имена стемов (Kick→drums, Bass→bass)
- **Reference Track Comparison** — A/B сравнение с level matching

### 🔒 Enterprise Security

- **SAST/DAST Scanning** — статический и динамический анализ
- **Secrets Management** — зашифрованные секреты
- **Audit Log** — журнал аудита
- **IP Allow List** — белый список IP
- **Custom Roles** — кастомные роли
- **Environments** — staging/production
- **Push Rules** — правила валидации коммитов

### 🔄 CI/CD & DevOps

- **Workflows** — YAML-based пайплайны
- **Pipeline Artifacts** — артефакты сборки
- **Container Registry** — Docker imágenes
- **Feature Flags** — управление фичами
- **Error Tracking** — отслеживание ошибок
- **Incident Management** — управление инцидентами
- **On-call Schedules** — дежурства
- **Status Page** — страница статуса

### 🧪 Testing

- **Test Plans** — планы тестирования
- **Test Suites** — наборы тестов
- **Test Cases** — тест-кейсы
- **Test Results** — результаты
- **Test Runs** — запуски
- **Load Testing** — нагрузочное тестирование

### 🌐 Code Intelligence

- **Code Search** — полнотекстовый поиск (FTS5)
- **Code Insights** — отчёты по коду
- **Code Owners** — автоматические ревьюеры

### 📊 Analytics & Monitoring

- **Activity Feed** — лента активности
- **Analytics** — аналитика проектов
- **Notifications** — уведомления
- **Reminders** — автоматические напоминания

### 🏢 Collaboration

- **Teams** — команды с ролями
- **Session Groups** — группы сессий
- **Session Tags** — теги для организации
- **Session Templates** — шаблоны сессий
- **Portfolio** — публичные сессии
- **References** — референсные треки

### 📱 Integrations

- **Webhooks** — HTTP-уведомления
- **GraphQL API** — расширенный API
- **Full-text Search** — поиск по всему
- **Metadata** — метаданные проектов
- **Extensions** — расширения платформы

### 💰 Packages & Distribution

- **Packages** — sample packs, presets, plugins
- **Gists** — сниппеты
- **Sponsors** — спонсорство
- **Artifact Feeds** — фиды артефактов

### 🏃 Agile Delivery

- **Sprints** — спринты
- **Retrospectives** — ретроспективы
- **Story Points** —.story points
- **Task Groups** — группы задач

---

## Как это работает

### 1. Создайте проект

```bash
cd backend
./snd login --user demo --password demo123
./snd push ./Track_v12.als --project "my-track" --branch main --message "initial"
```

### 2. Загрузите новую версию

```bash
./snd push ./Track_v13.als --project "my-track" --branch feat/new-drums --message "v13: new drums"
```

### 3. CI проверяет качество

```
✅ LUFS -14.5 (в пределах нормы)
✅ True Peak -1.2 dBTP (безопасно)
✅ Sample Rate 48000 Hz
✅ Channels 2 (stereo)
```

### 4. Pull Request → Review → Merge

Коллега прослушивает, комментирует на waveform, одобряет → мерж в main.

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

## Полная таблица возможностей

### Version Control

| Возможность | Статус |
|-------------|:------:|
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

| Возможность | Статус |
|-------------|:------:|
| DAW parsing (6 formats) | ✅ |
| Audio CI checks (LUFS/True Peak) | ✅ |
| Waveform comments | ✅ |
| Voice comments | ✅ |
| Stem management | ✅ |
| Reference track comparison | ✅ |
| Watermarking | ✅ |
| Loudness analysis | ✅ |

### Review & Approval

| Возможность | Статус |
|-------------|:------:|
| Review Sessions | ✅ |
| Review Rounds | ✅ |
| Approval flow | ✅ |
| Change Orders | ✅ |
| Share links (password + expiry) | ✅ |
| Late-change protection | ✅ |
| Reminder automation | ✅ |
| Ledger (immutable history) | ✅ |

### Project Management

| Возможность | Статус |
|-------------|:------:|
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

| Возможность | Статус |
|-------------|:------:|
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

| Возможность | Статус |
|-------------|:------:|
| Test Plans | ✅ |
| Test Suites | ✅ |
| Test Cases | ✅ |
| Test Results | ✅ |
| Load Testing | ✅ |

### Collaboration

| Возможность | Статус |
|-------------|:------:|
| Teams (with roles) | ✅ |
| Session Groups | ✅ |
| Session Tags | ✅ |
| Session Templates | ✅ |
| Portfolio | ✅ |
| References | ✅ |
| Activity Feed | ✅ |
| Notifications | ✅ |

### API & Integrations

| Возможность | Статус |
|-------------|:------:|
| REST API (364 endpoints) | ✅ |
| GraphQL API | ✅ |
| Full-text Search (FTS5) | ✅ |
| Webhooks | ✅ |
| Metadata | ✅ |

### Packages & Distribution

| Возможность | Статус |
|-------------|:------:|
| Packages (sample packs) | ✅ |
| Gists | ✅ |
| Sponsors | ✅ |
| Artifact Feeds | ✅ |

### Agile Delivery

| Возможность | Статус |
|-------------|:------:|
| Sprints | ✅ |
| Retrospectives | ✅ |
| Story Points | ✅ |

---

## Roadmap

### ✅ Shipped (все вышеперечисленное)

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
