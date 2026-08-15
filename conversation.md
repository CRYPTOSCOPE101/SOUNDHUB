# SoundHub — Development Log

Лог разработки SoundHub: решения, итерации и что было сделано в каждой фазе.
Обновляется по ходу работы с агентом.

---

## Фаза 0 — Репозиторий и лендинг

**Контекст:** репозиторий `CRYPTOSCOPE101/SoundHub` был «скудным» — лендинг с общими
обещаниями про DAW-marketplace и crypto. Последовательность итераций:

1. **Полировка репо** — CI (backend pytest / frontend tsc+vite / contracts hardhat),
   LICENSE, собственные бейджи (не скопированные), demo GIF, шаблоны issue/PR, releases.
2. **Логотип** — вырезан рисунок из README-картинки, убран фон, добавлен в шапку и favicon.
3. **Ветки DAW-интеграций** — `feat/cubase-integration` и `feat/flstudio-integration`
   (прототипы: MIDI Remote / MIDI scripting bridge).
4. **Главная страница** в стиле frame.io → несколько итераций редизайна:
   - `f8cf673` полный frame.io-подход (nav, showcase, stats, licenses, FAQ);
   - `e47d325` product-first: интерактивное демо, меньше маркетинга, честный статус
     (testnet, audit planned);
   - `03d4afc` акцент на момент интента — покупка звука внутри DAW;
   - `0ff4c40` **pivot**: от marketplace → review & approval. Главный тезис:
     «A comment at 01:24 changed this version» — музыкальный Frame.io.

**Ключевое решение:** продукт продаёт не крипто-marketplace, а рабочий цикл
**review → revision → approval**. Крипта — инфраструктура, не причина попробовать.

---

## Фаза 1 — Review-сессии (первый рабочий цикл)

- **Бэкенд**: модель `ReviewSession` + `ReviewVersion` + `ReviewComment`,
  загрузка WAV (waveform из блобов), публичные share-ссылки `/r/:token`
  для гостей без аккаунта.
- **Фикс роутов** (`3abee79`): публичные роуты `/public/{share_token}` были
  объявлены **после** `/{session_id}` (int) — FastAPI матчил `public` как int
  и отдавал 404. Публичные роуты перенесены выше.
- **`3f23204` — настоящий review player**:
  - интерактивный canvas-waveform (клик = seek, drag = loop);
  - аудио через blob с auth-заголовком;
  - версии-табы, upload new version, carry unresolved comments;
  - approval-панель (mix / master / arrangement / release), needs changes
    с обязательным комментарием;
  - share-настройки: пароль, expiry, permission, allowlist, audit log.

---

## Фаза 2 — Revision Rounds (контролируемые правки)

Главная ставка после анализа конкурентов (Mixup, Sonido, Pibox): не «ещё один
аудио-Frame.io», а **управляемая сессия правок**.

- **Раунды**: `Round N` в шапке, версии привязаны к раунду, upload новой
  версии открывает следующий раунд.
- **Консолидированный feedback**: гости оставляют private draft-заметки,
  назначенный **feedback owner** отправляет их одним «Submit revision notes» →
  закрытый раунд (опоздавшие получают 403).
- **Жизненный цикл запроса**: `Open → Acknowledged → In progress → Fixed → Verified → Approved`
  (кнопки прямо в комментарии).
- **Авто-fix**: upload новой версии помечает open-запросы `fixed in vN`
  (связь `fixed_in`).
- **Лимиты**: `included_rounds` — задел под платные раунды.

---

## Фаза 3 — Release Package (Final Delivery)

Workflow обрывался на «approved» — добавлен завершающий handoff:

- **Lock approved master** — необратимо, считает `manifest_hash` (SHA-256 по всем
  файлам), открывает delivery-ссылку.
- Deliverable-ы: master / instrumental / acapella / clean_edit / stems / artwork
  (из версии или upload), чексуммы + WAV-метаданные.
- **`/d/:token`** — публичная delivery-страница только с approved-файлами.
- **Invoice gate**: `balance_due / deposit_due` блокируют скачивание **402**,
  review-плеер при этом не блокируется.
- Полный цикл: `Draft → Consolidate → New version → Verified → Approved → Lock → Deliver`.

---

## Фаза 4 — Decision Ledger

Доказуемая история решений, без mainnet:

- **Tamper-evident hash chain**: `event_hash = SHA256(prev_hash || canonical_payload)`
  (sorted-key JSON). Переписать старое событие = сломать все последующие хэши.
- `Verify history` — эндпоинт проверяет целостность цепочки (тест: меняем payload
  первого события → verify падает).
- **Decision log UI** в сессии: человекочитаемая лента + `View proof`
  (полный JSON, actor, prev/event hash).
- События из всего workflow: `version.created · round.submitted ·
  request.* · approval.created · package.* · delivery.* · invoice.paid`.
- On-chain anchoring — опциональный слой позже (feature flag).

---

## Фаза 5 — Loudness-matched A/B compare

«Fixed in v13» — утверждение; клиенту нужно это **услышать**:

- **Web Audio A/B**: обе версии декодируются и стартуют с одного таймкода —
  переключение не сбрасывает playhead, crossfade 40 ms.
- **Level match**: short-term LUFS вокруг региона запроса; компенсация
  применяется только в preview-графе (исходники и locked package не трогаются).
- **Compare around request** — кнопка у каждого запроса с `fixed_in`
  (луп ±8 s), чип `changed in v13`.
- `comparison.created` пишется в ledger.

---

## Фаза 6 — Stripe paid delivery

Коммерческий слой, review остаётся независимым от оплаты:

- Инженер ставит сумму (`amount_due_cents`) на locked package.
- **Checkout Session** (owner + public по delivery-токену) → карта / Apple Pay /
  Google Pay без аккаунта у клиента.
- **Webhook** с HMAC-SHA256 проверкой подписи (без SDK — httpx + нативный hmac),
  идемпотентен (replay не двойной заряд).
- Без `STRIPE_SECRET_KEY` — manual `mark paid` режим (тесты на оба пути).
- `invoice.paid` (method: stripe/manual) в ledger; 402-гейт на скачивание.

---

## Фаза 7 — Stem-level A/B comparison

Профессиональная функция для сведения:

- **`StemAsset`**: submix renders, сопоставление по **logical name** (не filename):
  `NeonBass_final_03.wav` и `bass_v13.wav` оба = `bass`. Blob content-addressed,
  locked package не подменить.
- **Пикер режимов** в A/B плеере: `Full mix · Drums · Bass · Vocal · Synths` —
  стем появляется только если есть **в обеих** версиях; иначе чёткий fallback
  `unavailable in vN`.
- Loudness считается **по стему** (с учётом `start_offset_ms`).
- Ledger: `stem.uploaded` + `comparison.created` с `mode: stem`.
- Панель **Stems · vN** в сессии: список + upload кнопки.

---

## Фаза 9 — Рынок диктует: watermark, депозиты, portfolio, Kettle

**Где брали контекст:** разбор Gearspace (форум фетчится 403, работали через
сниппеты поиска). Боль из тредов: *Mix Loop* («как остановить бесконечные
правки»), *«New mix is not a revision, it is a new job»* (тарификация recalls),
*Non Payers / Customer not paying after approving masters* (депозиты),
утечка неодобренных версий. Прямой конкурент **Wavsen** (запуск апрель 2026,
$0/$9/$19) продаёт watermark protection + version control + portfolio pages.
Вывод: закрываем те же боли, но поверх уже готового управляемого цикла.

### 1. Watermarking превью (ответ Wavsen)

- **`services/watermark.py`**: слышимый бип-маркер (1.4 kHz, 0.22 s, каждые 5 s)
  микшируется в PCM WAV на уровне сэмплов (8/16/24/32-bit, моно/стерео).
  Оригинальный блоб не трогается — водяной знак живёт в отдельном
  content-addressed блобе, `watermark_sha` кэшируется на версии.
- **Правило**: гости (public share / portfolio) слышат водяной знак на
  неодобренных версиях; approved-версии чистые; владелец всегда чистый.
  Portfolio-превью всегда с водяным знаком (чистые файлы — только через
  платную delivery). Тумблер `watermark_enabled` в share-настройках.
- Чип `🔊 watermarked preview` в плеере, заметка гостю на публичной странице.
- Не-WAV форматы отдаются как есть (нет декодера) — гейт 402 остаётся
  настоящей защитой.

### 2. Депозиты + платные раунды (Non Payers / Mix Loop)

- **Booking deposit** на сессии: `deposit_due_cents` + `deposit_status`
  (none → deposit_due → paid/waived). Гейты: lock release package **402**, а
  также скачивание с публичной delivery-страницы **402** («одобрил и не
  заплатил» — больше не проходит).
- **Платные доп. раунды**: `included_rounds` + `extra_round_price_cents` +
  `rounds_paid`. Бюджет = 1 (первичный ревью) + included + paid. Submit
  feedback за пределами бюджета → **402** (или 403, если цена не задана).
- **Checkout**: `POST /api/sessions/{id}/checkout` и
  `/api/sessions/public/{share_token}/checkout` c `kind=deposit|extra_round`;
  delivery-страница тоже умеет `kind=deposit`. Тот же webhook (metadata `kind`)
  → `deposit.paid` / `round.extra_paid` в ledger. Без Stripe-ключей — manual
  mark paid (тесты обоих путей).

### 3. Portfolio инженера (отрыв от Wavsen)

- `GET /api/portfolio/{username}` — публичная витрина: опубликованные сессии
  (`portfolio_public`), approved-версия, delivery-ссылка locked package.
- `GET /api/portfolio/{username}/preview/{version_id}` — всегда watermarked
  превью (не обходит платный гейт).
- Тумблер «Show on public portfolio» в share-настройках; ссылка `/p/:username`
  в топбаре.

### 5. Client brief + service presets (продуктовый фокус)

**Принцип (после разбора стратегии):** продукт отвечает на три вопроса быстрее,
чем Discord/Drive/email — *что исправить, сделано ли и слышно ли, кто утвердил
и что получил*. Каждая фича усиливает один из трёх ответов или убирается.

- **Brief** — ожидания фиксируются до первого bounce: `service_type`
  (mix / master / mix_master / production / stems), жанр, цель (streaming /
  label / sync / dj / social), даты (review start + deadline), референс-треки
  (по ссылке на строку), обязательные deliverables, поле **«что не менять»**
  (vocal balance, arrangement…).
- `PATCH /api/sessions/{id}/brief` + `brief.updated` в ledger.
- **Service presets** в UI: один клик заполняет тип услуги, deliverables,
  included rounds и цену доп. раунда (Mix / Master / Mix+Master / Production /
  Stem delivery).
- Клиент видит brief на публичной странице (`/r/:token`): чипы «Service ·
  Genre · Goal · Deadline · Deliverables», ссылки-референсы, жёлтый блок
  «🚫 Will not change».
- Правила ревизий уже были (included_rounds / extra round price / deposit) —
  теперь они часть одного preset-флоу.

### 6. Reference tracks + mix/reference A/B

По продуктовому фокусу: reference **не становится версией** и **никогда не
попадает в delivery**.

- **Модель**: `ReferenceTrack` (session, title, artist, source_type:
  external_url | private_upload, external_url, blob, purpose:
  balance/low_end/vocal/width/arrangement/overall, visibility:
  engineer_only | reviewers, note, created_by, analysis). `ReferenceComparison`
  — mix↔reference A/B с gain'ами.
- **Не скачиваем чужой контент**: URL-референсы только хранятся и открываются
  в новой вкладке; встроенный A/B — только для приватного аплоада (файл, на
  который у пользователя есть права). Дисклеймер во всех UI-точках.
- **Нейтральные измерения** (тот же `loudness.analyse`): integrated LUFS,
  true peak, sample rate / channels. Никаких «ваш микс хуже» — только цифры
  и выравнивание громкости.
- **A/B плеер** (`ReferenceCompare`): один playhead, loop region, level-match
  gain'ы применяются реально в Web Audio графе (GainNode, 10^(dB/20)) — файлы
  не модифицируются. Гостям доступен A/B через public share (visibility +
  permission-гейт).
- **НЕ-deliverable**: ссылки только на `review_versions`, серверный гейт в
  deliverable-эндпоинтах, публичный delivery link не содержит references
  (тест: `"references" not in payload`).
- Ledger: `reference.created / updated / removed / compared`.
- Лендинг-роадмап приведён в соответствие: stems + loop regions и
  reference A/B в NOW; Ableton — «Max for Live panel prototype».

### 4. Kettle — уголок новичков

- `🫖 Kettle` (`/kettle`) — пошаговый гайд «первая ревью-сессия за 5 шагов»,
  глоссарий (bounce, stems, LUFS, revision round, watermark, ledger, deposit…),
  FAQ. Логотип — inline-SVG чайник. Ссылка в топбаре (все пользователи),
  в нав-лендинге и футере.

### Фиксы по пути

- `update_share_settings` при частичном PATCH сбрасывал `share_permission` /
  `share_allowlist` / `feedback_owner` на дефолты (поля были не-Optional со
  значением по умолчанию). Стали `None`-able + применяются только если заданы.

## Текущее состояние

| Блок | Статус |
|---|---|
| Review-сессии, версии, комментарии, публичные ссылки | ✅ live |
| Revision rounds + консолидированный feedback | ✅ live |
| Release package + immutable master + delivery link | ✅ live |
| Decision ledger (hash chain, verify) | ✅ live |
| Loudness-matched A/B (full mix) | ✅ live |
| Stripe paid delivery (card / AP / GP) | ✅ live (manual mode без ключей) |
| Stem-level A/B | ✅ live |
| Watermarking превью (audible, снимается после аппрува/оплаты) | ✅ live |
| Booking deposit + платные доп. раунды (402-гейты) | ✅ live |
| Public portfolio инженера | ✅ live |
| Kettle — гайд и глоссарий для новичков | ✅ live |
| Client brief + service presets + revision rules | ✅ live |
| Reference tracks + mix/reference A/B (private, non-deliverable) | ✅ live |
| Voice notes + mobile-first guest review | Next |
| Reminder automation (email) | Next |
| Roles / approval chains / label mode | Next |
| USDC / Base оплата | Next |
| On-chain proof (anchor manifest hash) | Next (feature flag) |
| Ableton Max for Live integration | prototype / coming next |
| Интервью с mix/master инженерами | запланировано |

---

## Фаза 10 — Change orders + archive handoff + QC preflight (P0-пакет)

Закрывает «пришли через три месяца, поправь бесплатно», «дай stems/raw/DAW files
после сдачи» и «форматы/структура не прошли у лейбла».

**🔁 Change orders (защита от бесплатных late-правок):**
- Клиент запрашивает изменение после approval/delivery (публичная ссылка, причины: mix revision / new stem request / format change / mastering recall).
- Инженер цитирует: courtesy / paid round / new mastering pass — или отклоняет. Цена по умолчанию из preset-фи (recall / revision fee).
- Клиент принимает цену + дедлайн → инвойс → оплата (Stripe webhook `kind=change_order` или manual mark paid) → раунд переоткрывается (`change_rounds_granted`, идемпотентно).
- Ledger: `change_order.created / quoted / accepted / declined / paid / round_opened`.

**🗄 Archive & session handoff:**
- Retention policy на сессии (`retention_until`) + recall/revision fees в Money-настройках.
- 6 шаблонов пакета (streaming master, label/sync, DJ promo, stem handoff, archive handoff, post-production) — name + обязательные deliverables.
- Handoff: plugin manifest, session manifest (JSON), consolidate audio, archive expires; статусы available_now / needs_preparation / archived / permanently_deleted.

**✅ QC preflight перед lock:**
- Проверки: обязательные deliverables (по шаблону), empty/corrupt audio, дубликаты, naming, lossy master, hot master (warning, не block).
- `POST /{pkg}/preflight` → чек-лист; lock блокируется при blocking (400) или проходит с `force` («Lock anyway»).

**Сайт:** hero-строка «Set the brief. Review with context. Lock the approved master. Deliver with proof.», CTA «Open a sample review» (сид demo-сессии при старте, `/r/:token` без логина), roadmap обновлён (templates/preflight/change orders — Now), marketplace остаётся вторым слоем.

**Тесты:** 54 backend (change order full flow, courtesy/decline, preflight+force, шаблоны, archive/retention, webhook change_order, идемпотентность) + frontend build.

---

## Фаза 11 — localhost/smoke + client experience + доводка P0

**Локальный запуск и smoke (было: ERR_CONNECTION_REFUSED на :5173):**
- `make dev` — backend :8000 + frontend :5173 (vite, прокси /api) с cleanup.
- `make smoke` — health API + demo seed + frontend раздаётся + e2e journey.
- `backend/tests/test_e2e.py` — полный путь: public review → draft → submit round → upload v2 → approve → package (template) → QC preflight → lock → invoice → payment → download + целостность ledger.
- Demo-сид при старте → CTA «Open a sample review» работает без логина.

**Public review — mobile-first + structured feedback + voice notes:**
- Композитор по шаблонам: 6 чипов (too loud / masked / energy / reference / technical / keep) → Element + Direction → свободный текст → **voice note** (MediaRecorder, webm/ogg, без аккаунта).
- Счётчик «your draft notes: N», submit consolidated, approve — на виду; SHA-256, ledger, share-права, раунды — в `<details> Details`.
- Публичный A/B версий (`/api/sessions/public/{token}/compare`) — level-matched, тот же playhead/loop, guest-URLы в ABCompare.
- Voice-эндпоинты (owner + guest): multipart загрузка, blob-хранилище, стриминг, ledger с флагом `voice`; transcription — честный placeholder.

**Доводка P0:**
- **Change order:** quote живёт 7 дней (`quote_expires_at`), состояние `expired`; после `accepted` цена/scope/дедлайн заморожены (PATCH → 400); re-quote создаёт `quote_version` v2 + событие `change_order.requoted`. Клиент видит сводку до подтверждения: «New mastering pass · $99 · delivery by … · archive retained until …».
- **QC preflight:** force-lock требует reason + двухшаговое подтверждение; ledger `package.lock_forced`; manifest `qc_status: forced` + `unresolved_warnings` + `confirmed_by`.
- **Archive handoff:** `last_verified_opened_at`; честный дисклеймер на delivery-странице («archived as delivered; exact playback may require the original DAW, plugins, licenses…»).

**Тесты:** 60 backend (e2e journey, force-lock evidence, quote expiry/immutability, voice notes owner+guest, public compare) + frontend build + `make smoke`.

---

## Фаза 12 — Email reminders & deadlines + UX-фиксы (CTA/roadmap/nav)

**UX-фиксы (перед reminders, из фидбека):**
- **Фиксированный demo-токен** `demo-review-token`: сид переиспользует его, оба CTA «Open a sample review» (topnav и hero) ведут прямо на `/r/demo-review-token` — без fetch-редиректа и без `/login`. Эндпоинт `/api/demo/review` сохранён (smoke/e2e используют).
- **Roadmap:** «Voice notes & mobile-first guest review» и «Email reminders & deadlines» перенесены из Next в **Now** (страница больше не занижает готовый продукт).
- **Kettle убран из верхнего меню** (topbar App.tsx и sticky-nav лендинга), остался в footer; `/kettle` роут сохранён.

**Email reminders — модуль:**
- Модель `Notification` с уникальным `dedup_key` (`session:kind:date:scope`) — «не больше одного письма одного типа за 24ч» гарантируется БД, cron можно гонять сколько угодно.
- События: `review.opened` (v1), `approval.requested` (ревизия round≥2), `approval.reminder` (ждёт решения 7+ дней), `feedback.deadline_48h/24h/overdue` (по `feedback_due_at`/deadline), `draft_notes.idle` (3+ дня), `invoice.due_7d/1d/overdue` (по `invoice_due_at`, дефолт immutable_at+14д), `change_order.quote_expiring` (≤48ч), `archive.expiring_30d/7d`, `delivery.link_expiring` (share_expires_at ≤7д).
- Правила: engineer включает/выключает и выбирает **категории** (review/feedback/invoice/change_order/archive/delivery); клиент может **opt-out** некритичных (payment/delivery остаются); напоминания не идут по отключённым сессиям и без `client_email`.
- Транспорт: SMTP если `SMTP_HOST` задан, иначе **log-only** (честный MVP, письма не «выдумываются»); статусы `queued → sent|failed|dismissed`.
- Ledger: `notification.sent / notification.failed / notification.dismissed` (+ `reminders.settings_updated`) — человекочитаемые строки в Decision Log.
- Эндпоинты: `POST /api/reminders/evaluate` (cron/smoke, evaluate+send), `GET|PATCH /api/sessions/{id}/reminders`, `POST /api/sessions/public/{token}/reminders/opt-out`. Триггеры: upload version, invoice PATCH, quote → авт. evaluate.
- Стартовый прогон: demo-сид получает `client_email` и на первом буте уже отправляет `review.opened` (видно в логе уведомлений).

**UI:** панель «Email reminders» у инженера (тумблер, client email, чипы категорий, «Evaluate & send now», лог отправок со статусами); у клиента в Details — статус напоминаний и кнопка «Opt out of non-critical reminders».

**Тесты:** 72 backend (12 новых: события, дедуп, категории, suppression без email/выключено, quote expiring, opt-out dismisses non-critical, ledger sent/dismissed, opt-out блокирует будущие) + frontend build + `make smoke`.

---

## Фаза 13 — Roles & approval chains + hero-фикс

**Усложнение дефолта — нет:** preset по умолчанию `solo_client` (любой reviewer может approve, как раньше — ноль enterprise-шума для фрилансера). Presets: `solo_client`, `artist_team`, `label_workflow`, `post_production`.

**Модель:** таблица `SessionMember` (email + role, уникально на сессию), `ReviewSession.approval_preset`, `ReviewApproval.role` (роль, под которой подписан sign-off).

**Политики (enforced только для label_workflow/post_production):**
- `label_workflow`: mix = Artist · master = Artist + A&R · release = Label admin (prerequisite: master approved).
- `post_production`: mix = Producer · master = Producer + Director · release = Director.
- Approve с чужой ролью → **403** с понятным текстом («master approval requires Artist, A&R…»); роль определяется по email приглашённого члена (case-insensitive).
- **Lock-гейт:** enforced-пресет не залочит release package, пока на выбранной версии не выполнена политика по `approval_scope` (403 + список недостающих ролей).
- **Версии не наследуют approvals:** sign-offs привязаны к version_id — свежий v14 не получает подписи v13 и не проходит как approved для delivery (исторические approvals v13 остаются нетронутыми).

**Minimal permissions (по спеке):** engineer (upload/resolve/package/quote) — владелец; reviewer ≠ approver (гость может комментировать, но подписывать только в рамках своей роли); label admin управляет release-подписью через share-ссылку по email — без логина.

**Эндпоинты:** `GET|POST /api/sessions/{id}/members`, `DELETE …/members/{member_id}`, `PUT …/approval-preset`, `GET …/team` (policy). Ledger: `team.member_invited / member_removed / preset_updated`; `approval.created` теперь несёт `role`.

**UI:** панель «Team & approval policy» у инженера (выбор preset + политика по scope с чипами enforced/any reviewer, список членов с удалением, инвайт по email+роли); на публичной странице у enforced-пресетов хинт цепочки («Artist → mix · A&R → master · label admin → release») над кнопкой approve. Ledger-строки для team-событий.

**Hero-фикс:** «no ZIP archives» → **«no scattered ZIP archives, no Discord chaos»** (больше не противоречит package delivery). Roadmap: «Roles & approval chains» перенесены в Now.

**Тесты:** 80 backend (8 новых: дефолт solo, preset+ledger, invite/remove/dedup, гейт по ролям 403, lock-гейты master/release, prereq master для release, v2 не наследует approvals, дефолт не сломан) + frontend build + `make smoke`.

---

## Фаза 14 — DAW bridge MVP (CLI `soundhub`)

**Честная граница обещаний сохранена:** Max for Live catalog panel — prototype, review comments in the DAW — Next; CLI bridge — live.

**`backend/soundhub_cli.py` (+ исполняемый wrapper `backend/soundhub`) — чистый stdlib, без зависимостей:**
- `soundhub login --user … --password …` → токен в `~/.soundhub.json` (или `SOUNDHUB_TOKEN`/`--token`, `--api`/`SOUNDHUB_API_URL`).
- `soundhub push mix.wav --session neon --message "v14: kick revised"` → находит сессию по имени (точное → префикс → подстрока, или по id), загружает bounce multipart-ом; **открытые запросы автоматически линкуются как fixed** (тот же флоу, что веб-upload) и печатает «open requests now: N».
- `soundhub requests --session neon [--format markdown|csv] [--include-drafts]` → экспорт открытых запросов.
- `soundhub locator --session neon` → Ableton locator-хелпер: `Locator N: "bass masks the vocal" @ 1:24.500 (v12 · open · aisha@label.com)`.

**Backend `GET /api/sessions/{id}/requests/export?format=markdown|csv&include_drafts`** (owner) — открытые запросы (+ опц. черновики) с таймкодом MM:SS.mmm, автором, версией, статусом; header-safe ASCII filename (ем-даш в имени сессии ломал latin-1).

**UI:** кнопки «⬇ MD / ⬇ CSV» в шапке Comments (fetch с Bearer-токеном → Blob-скачивание, т.к. plain `<a>` не протащит auth). Лендинг: Ableton-строка теперь «panel prototype + `soundhub` CLI (push bounces, export requests, locator helper) — review comments in the DAW are next»; roadmap: «DAW bridge CLI» → Now.

**Живой смоук CLI** (uvicorn + demo): login → requests (markdown) → locator → push настоящего wav → «✓ v2 uploaded … open requests now: 0 (fixed ones were linked automatically)».

**Тесты:** 89 backend (9 новых: export markdown/csv, drafts только с флагом, owner-only, CLI login/config, find_session имя+id, requests markdown, push multipart, locator, --help) + frontend build + `make smoke`.

---

## Фаза 15 — Roadmap-сокращение + гайд user tests (фокус, не фичи)

**Roadmap на лендинге перестал быть «product spec»:**
- **Now** — только 7 реально используемых функций: Review sessions & versioning, Revision rounds, Loudness-matched A/B, Release package + QC preflight, Stripe paid delivery, Roles & approval chains, DAW bridge CLI.
- **Already works** (колонка, accent-стиль — не «планируем», а «уже доступно, но не в главном фокусе») — остальное из старого Now: stems, reference tracks, client brief, deposit, watermarked previews, share links, templates + archive handoff, change orders, voice notes, reminders, portfolio.
- **Next** — 3 пункта: USDC checkout, Max for Live review comments, REAPER integration (перенесён из Later).
- **Later** — mainnet + audit, seller packs, DAO.

**`USER_TESTS.md`** — готовый инструментарий для 5–10 живых тестов с инженерами: кого приглашать (Gearspace/Twitter/личные контакты + их клиенты), единый сценарий из 11 шагов (brief → public link → voice notes → submit round → **push через CLI** → A/B → approve → preflight → lock → Stripe → delivery → change request), чек-лист наблюдателя (вопросы, «куда нажать», роли, «что после approval»), метрики (time-to-first-feedback, % consolidated notes, число раундов, % approval без напоминаний, time-to-payment, где просили помощи), шаблон отчёта по каждому тесту и порядок обработки результатов (топ-3 боли → фиксы onboarding/public review → только потом USDC/Max for Live/REAPER).

**Принцип фазы:** не добавлять новые модули (crypto-слой, Max for Live comments) до user tests; упрощать то, что уже есть.

**`USER_TESTS.md` v2 (по фидбеку «как провести первые 3 теста»):** задачи **по ролям** вместо общего маршрута — Engineer, Client/artist с телефона, A&R/label. Единая вступительная фраза «Представь, что это твой текущий проект…», без объяснения интерфейса. Запись **дословных формулировок** — как готовые тексты для UI/onboarding/email. Отдельный чек-лист лендинга: понятен ли «Max for Live panel prototype», не воспринимается ли marketplace как главное, доходят ли до roadmap с 4 колонками.

**Ещё две правки перед интервью:** footer-ссылки DAW приведены к integrations (Ableton Live · available, FL Studio/Cubase/REAPER · planned — убрано «REAPER · Q4 2026»); ссылка «Demo session» в footer унифицирована на публичный `/r/demo-review-token` (как все CTA) вместо `/session`.

**Правки перед стартом тестов:** CLI **не обязателен** в первом тесте инженера — основной сценарий идёт через web-flow (UI upload, сравнение, package+QC), CLI только для инженеров, живущих в терминале, с вопросом «в какой момент реальной DAW-работы ты бы запустил эту команду?» (это определит, нужен ли CLI как продукт или только как фундамент Max for Live). В лендинг-тест добавлен вопрос **«Что это за продукт и кому он нужен?»** после 10–15 сек; при 2/3 ответах «магазин пресетов» — marketplace уменьшается вдвое, escrow/on-chain копии уходят в docs, CTA в топ-навигации меняется на «How it works»/«Open review». **Integrations приведены к реальности:** Ableton/CLI — available now; FL Studio, Cubase, REAPER — planned без конкретных обещаний (убраны MIDI scripting device / web panel / Q4 2026). Сводная таблица болей + правило фиксов: только 2+ повтора или полный блок сценария.

---

## Запуск

```bash
# весь стек (backend :8000 + frontend :5173)
make dev

# минимальный pre-release smoke
make smoke

# тесты
make test          # backend pytest + frontend build
make e2e           # только e2e journey
```

Переменные окружения (backend): `SOUNDHUB_DATABASE_URL`, `SOUNDHUB_SECRET_KEY`,
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_CURRENCY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SOUNDHUB_FRONTEND_URL`.

---

## Запуск

```bash
# backend
cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend
cd frontend && npm run dev   # http://localhost:5173

# тесты
cd backend && .venv/bin/python -m pytest tests/ -q
cd frontend && npm run build
```

Переменные окружения (backend): `SOUNDHUB_DATABASE_URL`, `SOUNDHUB_SECRET_KEY`,
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_CURRENCY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SOUNDHUB_FRONTEND_URL`.
