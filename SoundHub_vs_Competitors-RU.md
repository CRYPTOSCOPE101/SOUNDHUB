# SoundHub vs Splice Studio и конкуренты — Итоговая сравнительная таблица

---

## Краткое описание платформ

| Платформа | Описание | Статус | Год запуска |
|-----------|----------|--------|-------------|
| **SoundHub** | GitHub для музыки — Git-like version control + DAW-aware + professional review workflow + project management | ✅ Активна | 2024+ |
| **Splice Studio** | Облачный бэкап + контроль версий для DAW + DNA Player | ❌ Закрыта (2023) | 2013 |
| **SyncMuse** | Async-коллаборация через stems + waveform feedback | ✅ Активна (ранняя стадия) | 2023 |
| **Boombox** | All-in-one: хранилище + коллаб + splits + дистрибуция + AI | ✅ Активна (100K+) | 2020 |
| **BandLab** | Бесплатный браузерный DAW + AI + соцсеть | ✅ Активна (100M+) | 2011 |
| **Soundtrap** | Real-time браузерный DAW (ex-Spotify) | ✅ Активна | 2012 |
| **Pibox** | Enterprise аудио/видео ревью | ✅ Активна | 2018 |
| **Sessionwire** | Real-time DAW-плагин (студийное качество) | ✅ Активна | 2020 |
| **Sesh** | Браузерный DAW для битмейкеров | ✅ Активна (50K+) | 2021 |
| **Feedtracks** | Google Drive для аудио + waveform feedback | ✅ Активна | 2020 |
| **musiciansXchange** | Git-подобный workflow + discovery + auto-credit | ✅ Активна (ранняя стадия) | 2023 |
| **Satellite Sessions** | DAW-плагин для cross-DAW real-time | ✅ Активна | 2021 |
| **Kompoz** | Краудсорсинг музыки (200K+ треков) | ✅ Активна | 2007 |

---

## Сравнение по ключевым возможностям

### 🔧 Контроль версий и Git-workflow

| Возможность | SoundHub | Splice Studio | SyncMuse | Boombox | musiciansXchange |
|-------------|:--------:|:-------------:|:--------:|:-------:|:----------------:|
| Branching (ветки) | ✅ Полноценные Git-ветки | ❌ Линейные версии | ❌ Линейные версии | ❌ Версионирование миксов | ✅ Git-style ветки |
| Merge / Fast-forward | ✅ merge, squash, fast-forward | ❌ | ❌ | ❌ | ❌ |
| Diff (сравнение версий) | ✅ DAW-aware diff + text diff | ❌ | ✅ A/B сравнение | ❌ | ❌ |
| Pull Requests | ✅ Полные PR с ревью | ❌ | ❌ | ❌ | ❌ |
| Branch Protection | ✅ + require reviewers + status checks | ❌ | ❌ | ❌ | ❌ |
| CODEOWNERS | ✅ Автоматические ревьюеры | ❌ | ❌ | ❌ | ❌ |
| Merge Trains | ✅ Очередь мержей | ❌ | ❌ | ❌ | ❌ |
| Git Tags / Releases | ✅ Теги + release notes | ❌ | ❌ | ❌ | ❌ |
| Push Rules | ✅ Валидация коммитов | ❌ | ❌ | ❌ | ❌ |
| Auto-commit history | ✅ (commits с parent chain) | ✅ (таймлайн сохранений) | ✅ (timeline) | ❌ | ❌ |
| Возврат к прошлой версии | ✅ Через checkout ветки | ✅ Через таймлайн | ❌ | ❌ | ❌ |

### 🎵 Аудио-специфичные возможности

| Возможность | SoundHub | Splice Studio | SyncMuse | Boombox | BandLab |
|-------------|:--------:|:-------------:|:--------:|:-------:|:-------:|
| DAW-aware (парсинг .als/.flp/.logic) | ✅ 4 формата + info | ✅ 4 формата | ❌ | ❌ | Встроенный DAW |
| Waveform timestamped comments | ✅ | ✅ | ✅ | ✅ | ❌ |
| Voice comments (голосовые) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Stem management | ✅ С логическими именами | ✅ Audio-Only Projects | ✅ | ❌ | ✅ (AI split) |
| Audio CI checks (LUFS, True Peak) | ✅ Автоматические при push | ❌ | ❌ | ❌ | ❌ |
| Loudness analysis | ✅ integrated LUFS + true peak | ❌ | ❌ | ❌ | ❌ |
| Sample rate / channel checks | ✅ | ❌ | ❌ | ❌ | ❌ |
| Reference track comparison | ✅ A/B с level matching | ❌ | ❌ | ❌ | ❌ |
| Version A/B audio comparison | ✅ Short-term LUFS analysis | ❌ | ✅ (visual) | ❌ | ❌ |
| Watermarking | ✅ Автоматический watermark | ❌ | ❌ | ❌ | ❌ |
| DNA Player (мьютинг треков) | ❌ | ✅ | ❌ | ❌ | ❌ |
| AI stem splitting | ❌ (пока) | ❌ | ❌ | ✅ Boombot AI | ✅ Splitter |
| AI mastering | ❌ | ❌ | ❌ | ✅ | ❌ |

### 💼 Professional Review Workflow

| Возможность | SoundHub | Splice Studio | SyncMuse | Pibox | Feedtracks |
|-------------|:--------:|:-------------:|:--------:|:-----:|:----------:|
| Review Sessions | ✅ С approval chain | ❌ | ❌ | ❌ | ❌ |
| Review Rounds (раунды фидбека) | ✅ Нумерованные раунды | ❌ | ❌ | ❌ | ❌ |
| Approval flow | ✅ solo_client, approve/reject | ❌ | ❌ | ❌ | ❌ |
| Change Orders | ✅ Заказы на изменения с ценой | ❌ | ❌ | ❌ | ❌ |
| Share links (пароль + срок) | ✅ password + expiry + allowlist | ❌ | ✅ secure sharing | ❌ | ❌ |
| Team roles (admin/maintainer) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Session members | ✅ email-based invitations | ✅ email invitations | ❌ | ✅ | ❌ |
| Deposit / billing | ✅ stripe integration | ❌ | ❌ | ❌ | ❌ |
| Required deliverables | ✅ Бриф + список | ❌ | ❌ | ❌ | ❌ |
| Late-change protection | ✅ retention_until + recall_fee | ❌ | ❌ | ❌ | ❌ |
| Reminder automation | ✅ | ❌ | ❌ | ❌ | ❌ |
| Access event logging | ✅ Полный audit trail | ❌ | ❌ | ✅ | ❌ |
| Portfolio (публичные сессии) | ✅ | ✅ (Community Tab) | ❌ | ❌ | ❌ |

### 📦 Релизы и дистрибуция

| Возможность | SoundHub | Splice Studio | Boombox | BandLab | Soundtrap |
|-------------|:--------:|:-------------:|:-------:|:-------:|:---------:|
| Release Packages | ✅ С deliverables | ❌ | ❌ | ❌ | ❌ |
| Immutable releases | ✅ immutable_at | ❌ | ❌ | ❌ | ❌ |
| Delivery tokens | ✅ Безопасная выдача | ❌ | ❌ | ❌ | ❌ |
| Invoice / billing | ✅ Stripe session | ❌ | ❌ | ❌ | ❌ |
| Sample pack registry | ✅ Packages (sample_pack, preset, plugin) | ❌ | ❌ | ❌ | ❌ |
| Song splits / contracts | ❌ | ❌ | ✅ | ❌ | ❌ |
| Distribution (Spotify etc.) | ❌ | ❌ | ✅ (150+ платформ) | ✅ (Pro) | ❌ |
| Blockchain certification | ❌ | ❌ | ❌ | ❌ | ❌ |

### 🏗️ Project Management

| Возможность | SoundHub | Splice Studio | Boombox | BandLab | ANY другой |
|-------------|:--------:|:-------------:|:-------:|:-------:|:----------:|
| Pull Requests | ✅ | ❌ | ❌ | ❌ | ❌ |
| Tasks (GitHub Issues) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Kanban Boards | ✅ | ❌ | ❌ | ❌ | ❌ |
| Milestones | ✅ | ❌ | ❌ | ❌ | ❌ |
| Wiki | ✅ С ревизиями | ❌ | ❌ | ❌ | ❌ |
| Discussions (форум) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Time Tracking | ✅ | ❌ | ❌ | ❌ | ❌ |
| Epics | ✅ | ❌ | ❌ | ❌ | ❌ |
| Roadmaps | ✅ Визуальная шкала | ❌ | ❌ | ❌ | ❌ |
| Calendar | ✅ С повторением | ❌ | ❌ | ❌ | ❌ |
| Requirements | ✅ | ❌ | ❌ | ❌ | ❌ |
| OKRs | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gists (сниппеты) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Sponsors (спонсорство) | ✅ | ❌ | ❌ | ❌ | ❌ |

### 🔒 Безопасность и DevOps

| Возможность | SoundHub | Splice Studio | Boombox | BandLab | Другие |
|-------------|:--------:|:-------------:|:-------:|:-------:|:------:|
| Workflows (CI/CD) | ✅ YAML-based | ❌ | ❌ | ❌ | ❌ |
| Audio CI checks | ✅ Автоматические | ❌ | ❌ | ❌ | ❌ |
| SAST/DAST scanning | ✅ | ❌ | ❌ | ❌ | ❌ |
| Security alerts (Dependabot) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Secrets management | ✅ Зашифрованные | ❌ | ❌ | ❌ | ❌ |
| Environments (staging/prod) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Variable groups | ✅ | ❌ | ❌ | ❌ | ❌ |
| Secure files | ✅ | ❌ | ❌ | ❌ | ❌ |
| IP Allow List | ✅ | ❌ | ❌ | ❌ | ❌ |
| Push rules | ✅ | ❌ | ❌ | ❌ | ❌ |
| Custom roles | ✅ | ❌ | ❌ | ❌ | ❌ |
| Audit log | ✅ | ❌ | ❌ | ❌ | ❌ |
| Container Registry | ✅ Docker images | ❌ | ❌ | ❌ | ❌ |
| Feature Flags | ✅ | ❌ | ❌ | ❌ | ❌ |
| Error Tracking | ✅ | ❌ | ❌ | ❌ | ❌ |
| Incident Management | ✅ | ❌ | ❌ | ❌ | ❌ |
| On-call Schedules | ✅ | ❌ | ❌ | ❌ | ❌ |
| Status Page | ✅ | ❌ | ❌ | ❌ | ❌ |
| Webhooks | ✅ С доставкой | ❌ | ❌ | ❌ | ❌ |
| Git LFS | ✅ | ❌ | ❌ | ❌ | ❌ |
| GraphQL API | ✅ | ❌ | ❌ | ❌ | ❌ |
| Full-text search (FTS5) | ✅ | ❌ | ❌ | ❌ | ❌ |

### 🌐 Коллаборация и социальные

| Возможность | SoundHub | Splice Studio | SyncMuse | Boombox | BandLab |
|-------------|:--------:|:-------------:|:--------:|:-------:|:-------:|
| Real-time DAW collaboration | ❌ | ❌ | ❌ | ❌ | ✅ (до 50) |
| Async stem sharing | ✅ | ✅ | ✅ | ✅ | ✅ |
| Teams | ✅ С ролями | ❌ | ❌ | ❌ | ❌ |
| Project Star / Watch / Fork | ✅ | ❌ | ❌ | ❌ | ✅ (follow) |
| User profiles (bio, specialty) | ✅ | ❌ | ❌ | ✅ | ✅ |
| Activity feed | ✅ | ❌ | ❌ | ❌ | ✅ |
| In-app notifications | ✅ | ❌ | ❌ | ❌ | ✅ |
| Service Desk (email support) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Design management | ✅ | ❌ | ❌ | ❌ | ❌ |
| Desktop app | ❌ (CLI/API) | ✅ (macOS/Win) | ❌ | ✅ (macOS) | ✅ (mobile) |
| Mobile app | ❌ | ❌ | ❌ | ✅ | ✅ |
| Browser DAW | ❌ | ❌ | ❌ | ❌ | ✅ |

### 💰 Ценообразование

| Платформа | Бесплатный план | Минимальная цена | Что даёт |
|-----------|:---------------:|:----------------:|----------|
| **SoundHub** | ✅ Open-source | $0 | Всё включено (self-hosted) |
| **Splice Studio** | ✅ (был бесплатен) | $0 (закрыт) | Безлимитное хранилище |
| **SyncMuse** | ✅ | $0 (Pro TBD) | Базовые функции |
| **Boombox** | ✅ (1 GB) | $4.20/мес | 500 GB, видео, AI |
| **BandLab** | ✅ (полный DAW) | $0 | 16 треков, AI, дистрибуция |
| **Soundtrap** | ✅ (5 проектов) | $9.99/мес | Полная библиотека |
| **Pibox** | ✅ (2 user, 1 GB) | $10/user/мес | 100 GB, безлимитные проекты |
| **Sessionwire** | ✅ (базовый) | $9/мес | Приватная Studio |
| **Sesh** | ✅ (ограничен) | $5/мес | Безлимитные проекты |
| **Feedtracks** | ✅ (1 GB) | €6.99/мес | 200 GB |
| **musiciansXchange** | ✅ (2 GB) | $3.99/мес | 25 GB, безлимит коллабораций |
| **Satellite** | ✅ (30 мин) | $9.99/мес | Безлимитные сессии |
| **Kompoz** | ✅ (3 public) | $5/мес | Больше коллабораций |

---

## Уникальные преимущества SoundHub

### Что есть ТОЛЬКО в SoundHub и НИГДЕ больше:

1. **Audio CI Checks** — автоматическая проверка LUFS, True Peak, sample rate, channels при каждом push (аналог GitHub Actions для аудио)
2. **Pull Requests для музыки** — полноценные PR с approve/request_changes, diff между ветками, required reviewers
3. **Branch Protection Rules** — защита main-ветки, требование PR,限制 force push
4. **CODEOWNERS** — автоматическое назначение ревьюеров по паттернам файлов
5. **Merge Trains** — очередь мержей для предотвращения конфликтов
6. **Kanban Boards + Epics + Roadmaps + Milestones** — полный project management
7. **Change Orders** — система заказов на изменения с ценами и согласованием
8. **Late-change Protection** — защита от поздних изменений (retention period + recall fee)
9. **Watermarking** — автоматическая маркировка.preview-версий
10. **Reference Track A/B Comparison** — сравнение микса с референсом с level matching
11. **Git LFS** — хранение больших аудиофайлов (LAAD-оптимизированное)
12. **SAST/DAST + Security Alerts** — безопасность на уровне enterprise
13. **Service Desk** — система тикетов для клиентов
14. **Design Management** — хранение и ревью обложек/арта
15. **Wallet Authentication** — Web3 аутентификация через кошелёк
16. **GraphQL API + Full-text Search** — расширенный API для интеграций

### Сильные стороны по сравнению с каждым конкурентом:

| vs Кого | Преимущества SoundHub |
|---------|----------------------|
| **vs Splice Studio** | Git-ветки, PR, branch protection, CI checks, project management, merge trains,安全 (Splice был только линейный) |
| **vs SyncMuse** | DAW-aware, auto-sync через CLI, DAW diff, project management (SyncMuse — только stems) |
| **vs Boombox** | Git-workflow, CI/CD, branch protection, не нужен Desktop app (Boombox — всё через GUI) |
| **vs BandLab** | Профессиональный workflow, версионирование, review process (BandLab — social DAW) |
| **vs Pibox** | Version control, DAW-aware, CI checks, project management (Pibox — только review) |
| **vs musiciansXchange** | DAW-aware, project management, CI/CD, branch protection (musiciansXchange — discovery + stems) |
| **vs Sessionwire** | Version control, cloud storage, review workflow (Sessionwire — только real-time streaming) |

---

## Сравнительная матрица: что важно для какого сценария

| Сценарий | Лучший выбор | Почему |
|----------|-------------|--------|
| "Хочу GitHub-подобный workflow для музыки" | **SoundHub** | Единственная платформа с PR, branches, merge, CI/CD |
| "Нужен бесплатный DAW с real-time" | **BandLab** | 100M+ комьюнити, полный бесплатный DAW |
| "Нужен async-фидбек на миксах" | **SoundHub** или **Pibox** | Waveform comments + version control + approval |
| "Нужна дистрибуция + splits" | **Boombox** | All-in-one: хранение + коллаб + контракты + дистрибуция |
| "Нужен real-time DAW-плагин" | **Sessionwire** или **Satellite** | Студийное качество, интеграция с DAW |
| "Нужен budget-friendly backup + фидбек" | **SyncMuse** или **Feedtracks** | Дешёвые, простые, waveform comments |
| "Нужен professional mixing workflow" | **SoundHub** | Review rounds, approval chain, change orders, billing |
| "Нужно enterprise-ревью для лейбла" | **Pibox** | Enterprise security, multi-team, API |
| "Нужен Git для музыки + discovery" | **musiciansXchange** | Git-ветки + поиск коллег + auto-credit |
| "Нужен браузерный DAW для битов" | **Sesh** | Serum-level синтез, real-time, $5/мес |

---

## Итоговая оценка

| Критерий | SoundHub | Splice | SyncMuse | Boombox | BandLab | Pibox | Sessionwire |
|----------|:--------:|:------:|:--------:|:-------:|:-------:|:-----:|:-----------:|
| Git-workflow | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| DAW-aware | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Audio CI/CD | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| Review workflow | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ |
| Project management | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ |
| Collaboration | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| AI features | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |
| Mobile | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Community | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ |
| Price | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Средняя** | **⭐ 4.1** | **⭐ 2.7** | **⭐ 2.3** | **⭐ 3.1** | **⭐ 3.5** | **⭐ 2.4** | **⭐ 2.6** |

---

## Выводы

### SoundHub vs рынок — позиционирование

**SoundHub — единственная платформа, которая объединяет:**
1. ✅ **Git-like version control** (ветки, мержи, PR, branch protection)
2. ✅ **DAW-aware** (парсинг Ableton/FL/Logic/Studio One)
3. ✅ **Audio CI/CD** (автоматические проверки качества при push)
4. ✅ **Professional review workflow** (раунды, approval, change orders, billing)
5. ✅ **Full project management** (Kanban, Epics, Roadmaps, Wiki, Tasks)
6. ✅ **Enterprise security** (SAST/DAST, secrets, audit log, IP allowlist)

**Ни одна другая платформа не предлагает всё это вместе.**

| Категория | Лидер |
|-----------|-------|
| Git-workflow для музыки | **SoundHub** (единственная) |
| Real-time DAW | **BandLab** / **Sessionwire** |
| All-in-one (хранение + дистрибуция) | **Boombox** |
| Бесплатный DAW | **BandLab** |
| Enterprise ревью | **Pibox** |
| Async-фидбек (простой) | **SyncMuse** |
| Discovery музыкантов | **Kompoz** / **musiciansXchange** |
| DAW-плагин real-time | **Sessionwire** / **Satellite** |

### Рекомендация для SoundHub

**Целевая аудитория:** Professional music producers, mix engineers, recording studios, labels, и music production teams, которые работают в команде и нуждаются в структурированном workflow.

**Ключевое competitive advantage:** SoundHub — это единственная платформа, которая применяет software engineering best practices (Git, CI/CD, PR, code review) к музыкальному продакшну. Все остальные платформы либо offering real-time DAW (BandLab, Soundtrap), либо простой async-фидбек (SyncMuse, Pibox), либо all-in-one (Boombox), но ни одна не даёт professional-grade version control + CI/CD + project management для DAW-проектов.
