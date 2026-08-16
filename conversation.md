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

## Фаза 16 — `snd push` (ветка `snd-project-push`) + находки GitHub Ableton

**`snd push` — пуш полного DAW-проекта одним versioned-коммитом (ветка `snd-project-push`):**
- CLI `backend/snd` + `backend/snd_cli.py` (чистый stdlib): `snd login` / `snd push <dir> --project "Name" --message "v12"` / `--include-media`.
- **Локальный парсинг DAW** перед загрузкой: треки, инструменты, плагины И их настройки (REAPER `<PARAM name=… val=…/>` — реальное состояние инстанса; Ableton `PresetRef` → файлы пресетов типа `Neon Lead.xvl`).
- Push в `POST /api/projects/{id}/push` одним коммитом + `SOUNDHUB-MANIFEST.json` (структура: files, daws → tracks/plugins/params/presets) в дереве коммита; сервер ре-анализирует файлы для tree/diff.
- UX-фикс: `--project "Имя"` на первой заливке авто-создаёт проект (было «not found»). Парсер REAPER: `<TEMPO 128 4 4` без `>` — regex исправлен.
- Проверено на живом сервере: `✓ pushed “Neon Warehouse” — commit #1 · 3 files · main; RPP: Neon.rpp — 2 tracks, 3 plugins, 3 plugins with settings`. 96 backend-тестов зелёные.

**Контракт Фазы 16 — `snd push` как безопасная, предсказуемая команда (проект → версия → review):**

- **CLI принимает `.als` файл напрямую** (`snd push ./Track_v12.als`) или каталог (старый режим сохранён);
  новые флаги: `--audio <master.wav>` (открывает review-версию для gapless A/B), `--stems <dir>`
  (каталог стемов прикрепляется как набор StemAsset по logical name из имени файла), `--round N`,
  `--open` (открыть review URL в браузере), `--json` (машинный контракт).
- **Preflight до upload**: существование файла/каталога, размер (MAX_UPLOAD_SIZE), расширение
  (только .als/.rpp/.flp/.cpr для проекта; аудио/стемы — по белому списку), читаемость `.als`
  (детект + реальный парсинг — битый файл отклоняется с понятной ошибкой), в review-режиме
  обязателен master (`--audio`) — стемы без мастера отклоняются.
- **Атомарность**: блобы пишутся первыми (content-addressed → повторный пуш идентичных файлов
  дедуплицируется), затем commit + review session/version/stems создаются в **одной транзакции**
  (`create_commit(commit_transaction=False)`) — ошибка на середине загрузки не оставляет
  пользователю «полу-запушенной» версии (тест: валидный .als+master + битый stem → 400, сессий/коммитов ноль).
- **Связка с review**: первый пуш с `--audio` создаёт (или переиспользует) review-сессию проекта
  (`share_permission=download` — гости слушают A/B без пароля), версия получает waveform,
  `round_number` из `--round`, стемы — `_guess_stem_name` (Kick→drums, Bass→bass, Vocals→vocal…);
  второй пуш в ту же сессию даёт v1/v2 → level-matched A/B работает. Ledger: `version.created` +
  `stem.uploaded`.
- **Стабильный JSON-контракт** (для M4L/автоматизации): `{"ok", "project_id", "branch",
  "commit_id", "version_id", "session_id", "share_token", "review_url", "uploaded":
  {"als", "master", "stems"}, "deduplicated"}`; при ошибке с `--json` — `{"ok": false, "error": …}`.
- **Фикс по пути**: `versioning.ensure_branch` не создавал новую не-default ветку (`--branch review/v12`
  падал `AttributeError`) — теперь ветка синтезируется при первом пуше.
- **Тесты: 111 backend** (12 новых: fast-mode контракт, audio→review-версия для A/B, две версии
  → сравнение 201, стемы как набор с logical names, дедуп повторного пуша без новых блобов,
  атомарность при mid-upload ошибке, 401/404/400/413, CLI single-.als + `--json` контракт,
  preflight-отказы, `--json` ошибка, `--open`) + frontend build + живой smoke
  (`.als`+master+3 стема → `deduplicated: 6` при ре-пуше, review URL 200, стемы прикреплены).
- **Проверка риска (legacy dir-режим vs новый контракт)**: JSON-схема единая (оба режима →
  один эндпоинт), дублей метаданных нет (один манифест), но **dir-режим обходил preflight
  читаемости** — `_preflight_daw_readable` вызывался только для одиночного файла. Фикс: каталог
  теперь прогоняет ту же проверку по каждому DAW-файлу (.als/.rpp/.flp/.cpr). Тест
  `test_snd_push_dir_mode_preflights_daw_readability`: каталог с битым .als → rc 1 «Cannot
  parse» и ноль HTTP-запросов; после удаления битого файла тот же каталог пушится. Итого 112 тестов.
- **README обновлён**: секция `snd push` приведена к контракту Фазы 16 (два режима,
  preflight, атомарность, дедуп, `--json` контракт с примером; исправлено имя ветки
  `snd-push` → `snd-project-push`).
- **M4L «Push current export» (тонкий клиент над `snd push --json`):** в `m4l/`
  добавлена 4-я кнопка `push` — читает `live_set.current_song_path` (текущий `.als`)
  и шлёт JSON `{target, project, branch, message}` на локальный мост `snd serve`
  (localhost:8765), который гоняет ту же проверенную пайплайн-функцию `run_push`
  (preflight → атомарная загрузка → review-версия) и возвращает контракт; панель
  показывает «✓ pushed commit #N» + review URL. Почему мост: `shell` заблокирован
  в Live, а `httprequest` портит бинарный multipart — JSON-мост на stdlib `http.server`
  решает оба ограничения. `snd push`/`snd serve` теперь делят одно ядро `run_push(opts)`;
  конфиг M4L: `bridge`/`pushProject`/`pushBranch`/`pushMessage`. Тест
  `test_snd_serve_bridge_health_and_push` (health + push контракт + 400 {"ok": false}).
  Итого 113 backend-тестов; живой smoke: push из моста → commit + review URL 200.
  m4l/README.md обновлён (кнопка, мост, «что застаблено»).
- **Production-grade-закрепление пункта (по ревью):** негативные тесты bridge
  (`test_snd_serve_bridge_negative_cases`): битый JSON → 400 «bad JSON», audio-путь
  без файла → 400 «Master file not found», стемы без мастера → 400 «requires --audio»,
  повторный push того же экспорта — оба проходят и несут тот же .als+манифест;
  preflight-отказы не доходят до бэкенда.  Старт моста в тестах переведён на
  `start_bridge(port=0)` + `server_address` (убрана гонка за портом — два bridge-теста
  подряд больше не падают). m4l/README.md: блок Troubleshooting (7 симптомов панели:
  мост не запущен, сейв сета, master не найден, 401, oversize, fast-push без review)
  + end-to-end checklist через curl без открытия Live. Итого 114 backend-тестов.

**Лендинг в CodeRabbit-стиле (фон сохранён):** по реквесту «такой же красивый лендинг
со скриншотами» — hero перестроен под CodeRabbit-паттерн: бейдж-пилюля + крупный
заголовок + CTA + **продуктовый скриншот в браузерной рамке** (точки macOS + URL-бар,
`/screenshots/repo-page.png`), под ним лента «Works with the DAWs you already use»
(Ableton Live · FL Studio · Cubase · REAPER). Добавлены две фиче-секции со скриншотами
(текст + браузерный кадр, вторая зеркальная): «One workspace for every version»
(`projects.png`) и «Push from the DAW, review in the browser» (`repo-page-branches.png`),
живая демо-сессия, diff-кард, pillars/roadmap/FAQ/CTA/футер сохранены. Скриншоты
скопированы в `frontend/public/screenshots/`. Цвет фона не тронут — тот же `#F2F0EB`
(проверено по пикселям). Frontend build ✅, страницы отдают скриншоты (200).
- **Секция «Best-in-class context»** (CodeRabbit-паттерн, после smart diff): подзаголовок
  «Across each step, we pull in dozens more points of context than other tools.» +
  сравнение «Что видно в общем файле» (filename · file size · “binary changed”, пунктирная
  карточка с ✕) против «Что SoundHub извлекает» (6 строк: BPM/сигнатура, 12 треков,
  8 плагинов с настройками, 42 сэмпла/пресета, LUFS/true peak, стемы по ролям) + ряд
  статистики (4 DAW-формата · 30+ точек контекста на версию · 0 ZIP-ов). Ссылка в футере.
  Проверено playwright: 3+6+3 строк на месте, build ✅.

**Изучен GitHub-организации Ableton (29 репозиториев):** почти всё — внутренняя инфра (Ansible/Jenkins), нерелевантно. Применимы четыре:
1. **`Ableton/web-audio-sequencing` (MIT)** — lookahead-планирование на часах AudioContext. **Применено сразу:** оба Web Audio плеера (`ABCompare.tsx`, `ReferenceCompare.tsx`) переведены с «RAF-тик ловит границу loop и перезапускает source с зазором» на планировщик сегментов (`start(when)`/`stop(when)` на точных временах аудио-часов, горизонт 0.15 с) — loop-регион теперь gapless, без frame-квантования и дрейфа. Frontend build зелёный.
2. **`Ableton/m4l-connection-kit` (MIT)** — примеры M4L-устройств, связывающих Live с внешним миром через **OSC** и **JSON API**; зафиксирован как референс транспорта для будущего «review comments in the DAW» панели (не интегрируется сейчас).
3. **`Ableton/maxdevtools` (MIT, Python)** — CI-инструменты сборки Max-пакетов; кандидат на замену самопального `build_amxd.py` при релизе реальной панели.
4. **`Ableton/Link`** — **не берём**: требует лицензионного соглашения и не про review/delivery.

Все три находки задокументированы в `m4l/README.md`.

**Ещё две правки перед интервью:** footer-ссылки DAW приведены к integrations (Ableton Live · available, FL Studio/Cubase/REAPER · planned — убрано «REAPER · Q4 2026»); ссылка «Demo session» в footer унифицирована на публичный `/r/demo-review-token` (как все CTA) вместо `/session`. Позже убрана ссылка «Community → /dao» из footer (реального community hub нет, DAO governance — в Later; роут остаётся только в топбаре для залогиненных).

**Правки перед стартом тестов:** CLI **не обязателен** в первом тесте инженера — основной сценарий идёт через web-flow (UI upload, сравнение, package+QC), CLI только для инженеров, живущих в терминале, с вопросом «в какой момент реальной DAW-работы ты бы запустил эту команду?» (это определит, нужен ли CLI как продукт или только как фундамент Max for Live). В лендинг-тест добавлен вопрос **«Что это за продукт и кому он нужен?»** после 10–15 сек; при 2/3 ответах «магазин пресетов» — marketplace уменьшается вдвое, escrow/on-chain копии уходят в docs, CTA в топ-навигации меняется на «How it works»/«Open review». **Integrations приведены к реальности:** Ableton/CLI — available now; FL Studio, Cubase, REAPER — planned без конкретных обещаний (убраны MIDI scripting device / web panel / Q4 2026). Сводная таблица болей + правило фиксов: только 2+ повтора или полный блок сценария.

---

## Фаза 17 — Редизайн в стиле bandcamp.com (лендинг + весь сайт)

По фидбеку «лендинг и сам сайт категорически не нравятся» — полный переход с Ableton-стиля
(тёмные градиенты, жёлтый акцент, стеклянный nav) на дизайн-язык bandcamp.com:

- **Токены**: тёплый off-white `#f2f0eb`, почти чёрный текст `#1f1f1f`, оранжевый акцент
  `#ff5e1a`, «bandcamp-синий» для ссылок `#3a4c6b`, тонкие тёплые рамки `#d8d3c8`;
  тёмная тема — тёплый тёмный вариант той же системы (переключатель сохранён).
- **Весь CSS переведён с захардкоженных тёмных цветов на токены** (~90 замен: `#101216`/`#17191d`
  → `var(--bg2)`, `#ffd900` → `var(--accent)`, синие `#3a6ea5`/`#6ba3d8` → `var(--blue)`,
  полупрозрачные подложки → `--*-soft`). Результат: review-плеер, public review, delivery,
  portfolio, A/B-панели — всё перекрасилось в bandcamp-палитру автоматически.
- **Кнопки**: чёрные (bandcamp-style), `approve` = оранжевая «buy»-кнопка; инпуты/карточки —
  белые с тонкой рамкой, острые углы (3px).
- **Лендинг переписан** (`bc-*` классы): единая светлая шапка (глобальный topbar скрыт на `/`),
  hero без градиентов, «featured release» — квадратная обложка + живая демо-сессия с пульсирующей
  меткой «● Live sample», нумерованный трек-лист шагов, трек-лист smart-diff, интеграции списком
  со статусами, roadmap/FAQ в минимализме, CTA + bandcamp-футер. Watch-workflow модалка перекрашена.
- **KettlePage** переведён на те же классы (topbar скрыт на `/kettle`), чайник стал оранжевым.
- **Canvas-волны** (`ReviewShared`): проигранная часть оранжевая, остальное — серое, маркеры
  комментариев — красные; луп-регион — оранжевая подсветка.

**Тесты:** frontend build зелёный + `make smoke` OK (backend-тесты не затронуты — правки только фронтовые).
Старые тёмные landing/demo-стили остались в styles.css как мёртвый код (классы больше не используются)
— можно вычистить отдельным коммитом.

**Правки по фидбеку (шапка):**
- **Шапка на всю ширину** — full-bleed через `margin: 0 calc(50% - 50vw)` + выравнивающие паддинги
  (контент остаётся в колонке 1100px).
- **Лого из README** — `screenshots/LOGO_modSHA.jpg` (обрезаны поля, `frontend/public/logo-readme.jpg`)
  в шапке лендинга, Kettle, топбаре и публичных страницах. Позже заменено на новый логотип
  `screenshots/LOGO_N.jpg` (горизонтальный логотип-лок-ап, в котором уже есть слово SOUNDHUB —
  дублирующий текст рядом с лого убран из шапки, топбара, футеров и публичных страниц;
  размеры подстроены под горизонтальную композицию).

**Ещё правки по фидбеку:**
- **Лого с прозрачным фоном** — `LOGO_N.jpg` → PNG с прозрачностью (ImageMagick `-trim` +
  `-transparent white`), сохранён как `frontend/public/logo.png` (старый jpg удалён, ссылки обновлены).
- **Крупнее шрифты** — body 14→15px, h1 22→26px, h2 14→16px, инпуты/кнопки 13→14px; лендинг:
  заголовок до 54px, bc-h2 24→30px, подзаголовок 16→18px, шаги/интеграции/FAQ/футер подняты;
  review-плеер (rs-*) и публичные страницы тоже увеличены.
- **Блоки с белым фоном → общий фон** — `--bg2`/`--bg-soft`/`--card` стали равны цвету страницы
  (плоский bandcamp-вид: никаких белых коробок, только тонкие рамки); убраны захардкоженные
  `#ffffff`-фоны в light-оверрайдах (portfolio/kettle/public-brief/refs).
- **Шапка как на bandcamp.com (2 ряда, глобально на всех страницах):** верхняя панель — только
  лого + поиск + «Sign up» / «Log in» (для залогиненных — username, переключатель темы, log out);
  вторая панель — вся остальная навигация с пиктограммами (inline-SVG): Workflow, Smart diff,
  Marketplace, FAQ, Kettle + для залогиненных Sessions, Portfolio, Market, DAO, Repo, а для гостей
  «Sample review». Новый компонент `SiteHeader` вместо topbar и лендинговой шапки (`BandcampHeader`
  удалён). «Sign up» ведёт на `/login?mode=register` (LoginPage читает параметр).
- **Сайт шире** — `.content` 1100 → 1400px, внутренние страницы (public review/delivery/portfolio/
  sessions) расширены. **Шрифты ещё крупнее** — body 16px, заголовки до 60px, шаги/FAQ/футер/плеер
  подняты ещё на ступень.
- **Две новые секции на лендинге**: «Sound-tech engine backbone» (6 столпов: DAW parsing engine,
  smart diff, decision ledger, content-addressed storage, loudness analysis, watermarking) и
  «DAW-native track assets» (треки/плагины с настройками, стемы по logical name, сэмплы и пресеты,
  `snd push` с манифестом). Uppercase-заголовки, сетка 3/2 колонки с тонкими рамками.
- **Поиск** (bandcamp-style): `GET /api/search?q=` — находит только публично достижимое: инженеров
  с ≥1 публичной сессией (→ `/p/:username`) и публичные сессии по имени (→ `/r/:token`).
  Выпадающий список с дебаунсом 200мс, Enter → первый результат, Esc/клик-вне — закрыть.
  Общий компонент `BandcampHeader` (навигация + CTA + поиск) вместо дублированных шапок.
  Демо-сессия сделана `portfolio_public` (сид + живая БД) — поиск «neon»/«demo» сразу что-то находит.
  Тесты: 99 backend (3 новых `test_search.py` — публичный поиск, приватность, лимиты) + build + smoke.

**Скриншоты README пересняты** (playwright + chromium в backend-venv, без браузера в окружении):
`backend/scripts/screenshots.py` — лендинг (main-light.png), список проектов (projects.png),
repo-страница (repo-page.png), ветки (repo-page-branches.png) — все в новом bandcamp-дизайне;
добавлен `projects.png` в README. Шапка README обновлена на новое прозрачное лого
(`frontend/public/logo.png` вместо старого `LOGO_modSHA.jpg`). `demo.gif` остался старым —
в окружении нет ffmpeg, чтобы переснять.

**Лендинг в стиле coderabbit.ai** (по запросу «такой же красивый, фон оставить»):
- **Hero** — бейдж-пилюля, крупный заголовок + CTA, продуктовый скриншот в браузерной рамке
  (macOS-точки + URL-бар `soundhub.local/projects/aurora-night`, живой `repo-page.png`);
  лента доверия «Works with the DAWs you already use» (Ableton Live · FL Studio · Cubase · REAPER).
- **Фиче-секции со скриншотами** (`cr-feature`): «One workspace for every version» (projects.png)
  и «Push from the DAW, review in the browser» (repo-page-branches.png, зеркальная).
- **Best-in-class context** — сравнение «What a shared file shows» (✕ ZIP/Discord) vs
  «What SoundHub extracts» (BPM · time signature · tracks · plugins with settings · samples ·
  LUFS/true peak · stems by role) + статистика 4 DAW formats / 30+ context points / 0 ZIPs.
- **Ещё пять CodeRabbit-элементов** (выбраны пользователем из списка):
  - **Табы с фичами** (`cr-tabs`): Review · A/B · Approval — переключение без перезагрузки;
  - **Отзывы** (`cr-testimonials`) — честные, из исследованного Ableton-комьюнити (не выдуманные);
  - **Сравнительная таблица** (`cr-compare`) — SoundHub vs ZIP/Discord vs GitHub;
  - **Pricing** (#pricing) — честные бета-тарифы: FREE $0 + PRO (beta), без выдуманных цен;
  - **Анимированный hero** — rotating word в заголовке (review → versions → A/B → …).
- Фон не тронут — тот же тёплый off-white `#F2F0EB` (проверено по пикселям на живом скриншоте).
- Проверено: frontend build ✅ + playwright (табы переключаются, rotating word крутится, все 5
  секций видимы, фон `#F2F0EB` на 4 высотах).

---

## Фаза 18 — П.2 roadmap: smart diff прямо в review-контексте

**Боль (Reddit-сигнал):** «видеть, что именно изменилось между версиями» — не «binary changed»,
а BPM / track / plugin-level diff. Раньше diff жил только на repo-странице, review — на `/r/:token`;
теперь клиент видит изменения прямо в плеере.

**Backend:**
- `ReviewVersion.commit_id` (nullable FK на `commits`) — версия, запушенная через `snd push`,
  теперь связана с DAW-коммитом (миграция `ALTER TABLE review_versions ADD COLUMN commit_id`).
  У ручных audio-аплоадов — NULL, diff для них недоступен с понятной ошибкой.
- `_version_diff()`: сравнивает версию с **предыдущей версией сессии**, запушенной из коммита
  (vN vs vN-1), фолбэк на parent-коммит; первый пуш → «File created». Переиспользует движок
  `summary_diff` + `normalize_content`/`unified_diff` — BPM, time signature, DAW version, треки,
  плагины, сэмплы + raw diff (кап 400 строк).
- Два эндпоинта: `GET /api/sessions/{id}/versions/{vid}/diff` (owner) и
  `GET /api/sessions/public/{token}/versions/{vid}/diff` (гость, view-permission, лог `diffed`).
- `ReviewVersionOut.commit_id` — фронт по нему решает, показывать ли кнопку.

**Frontend:**
- Общий компонент `VersionDiffPanel` (ReviewShared): заголовок «✦ What changed · v2 vs v1»,
  строки с бейджами +/−/·, old→new (BPM 128→132), raw diff в `<details>`.
- **PublicReviewPage** (клиент): блок «✦ What changed in this bounce» с кнопкой
  «What changed in vN» — прямо под плеером, до секции A/B.
- **ReviewSessionPage** (инженер): кнопка «✦ What changed» в панели версий + иконка ✦ у каждой
  версии с `commit_id` в сайд-листе.

**Проверено:** 116 backend-тестов ✅ (+2: smart summary owner+guest с bpm/track/plugin и
from_label, plain-audio upload → 400 «no linked daw project», 404 для чужого токена); frontend
build ✅; живой smoke: пуш v1(128) и v2(132, +Pad, +Vital) → diff `128→132`, `+Pad`, `+Vital`
через оба эндпоинта; playwright: кнопка «What changed in v2» на `/r/:token` → панель с
изменениями → закрытие. Backend перезапущен, миграция применена к живой БД.

---

## Фаза 19 — П.3 roadmap: аудит пути гостя на `/r/:token`

**Боль (Reddit-сигнал):** «1–2 действия, а не 8 экранов». Правило: если от ссылки до первого
комментария >3 кликов — сократить.

**Аудит (playwright, живая сессия):** форма «Leave feedback» лежала в самом низу страницы —
после player → diff → compare → refs (~6 секций прокрутки). Минимальный путь был:
прокрутка до низа + клик по шаблону + «Add note» — плюс опционально переключение режима
и клик по волне для привязки момента. Форма не помещалась в первый экран.

**Фикс — перенос блока `public-review-lower` (комментарии + форма + approval) сразу под плеер:**
- Новый порядок: header → intro → brief → **player → feedback-форма** → diff → compare → refs → change.
- Форма **видна в первом экране** без прокрутки (y=721 при viewport 900).
- **2 клика** до первого комментария: шаблон («I like this — keep it») → «Add note» →
  «✓ Note added to your draft notes». Voice-рекордер уже в форме (всегда виден, без раскрытия).
- Привязка момента — опциональна: по умолчанию note садится на позицию playhead.

**Проверено:** frontend build ✅; playwright: порядок секций (player → lower → compare),
форма в первом экране, комментарий появляется в списке выше формы, diff-блок ниже работает,
фон `#F2F0EB` сохранён. Backend не тронут.

---

## Фаза 20 — П.4 roadmap: pre-flight прогон USER_TESTS.md (автоматизированный)

Реальных людей позвать нельзя — сделана честная замена: **автоматизированный pre-flight**
всех трёх сценариев ролей из USER_TESTS.md через живой стек (playwright + API), чтобы
перед живыми тестами ничего не блокировалось. Найдены и починены 2 блокера:

**Блокер 1 — инженер: сессия открывается пустой.** `SessionDetail` никогда не вызывал
`refresh()` при монтировании, а список сессий (`ReviewSessionOut`) не содержит версии →
плеер, версии и share-ссылка отсутствуют, пока пользователь не сделает действие (например,
аплоад — который и триггерил refresh). Фикс: `useEffect(() => { void refresh(); }, [session.id])`.
Багу было минимум 5 фаз (проверено по git-истории Phase 11).

**Блокер 2 — клиент: A/B-сравнение роняло всю review-страницу.** Два под-бага:
1. `compareBaseId` стартует как `null` и выставляется только при ручном изменении дропдауна —
   первый клик «Compare» молча ничего не делал (функция выходила раньше). Фикс: фолбэк на
   самую старую версию внутри `runPublicCompare`.
2. `ABCompare` на публичной странице грузил stems через **owner-эндпоинт**
   `/api/versions/{id}/stems` → 401 → перехватчик `api.ts` делает
   `window.location.href = "/login"` — вся страница ревью исчезала. Фикс: в guest-режиме
   (передан `audioUrls`) stems не грузятся — публичное сравнение и так только full_mix
   (backend отклоняет stem-режим для гостей).

**Проверено по ролям (всё зелёное):**
- **Инженер:** логин → sessions → открытие сессии (фикс) → аплоад v3 через UI → A/B →
  share/copy ссылка → «What changed» у запушенных версий (commit_id), нет у UI-аплоада →
  консолидация draft-заметок → Round 2 (2 draft → 2 open requests) → панель Release package.
- **Клиент (телефон 390px):** плеер → форма в первом экране → structured note за 2 клика →
  voice-рекордер → compare v1↔v3 (фикс) → approval-панель.
- **A&R:** `label_workflow` + приглашённый член `a_r` → случайный email → 403 с понятным
  сообщением («master approval requires Artist, A&R — approve with the invited team
  member's email») → член A&R → 201 с ролью → версия approved.

Frontend build ✅ (backend не тронут). Это pre-flight, а не замена живых тестов: реальные
люди всё ещё нужны для дословных формулировок и метрик времени — но теперь сценарии не
ломаются на базовом пути.

---

## Фаза 21 — Анимированные скриншоты на сером фоне (README)

Старый `demo.gif` был снят до редизайна (тёмные страницы, кадры разной высоты). Пересобрано:

- **`screenshots/demo.gif`** — слайдшоу с кроссфейдом 4 новых скриншотов (main-light, projects,
  repo-page, repo-page-branches) на едином **сером канвасе** `#DCDCDC` (1280×800, карточка
  с рамкой `#C6C6C6` + мягкой тенью, 58 кадров, 4.2MB). Скрипт `scripts/make_demo_gif.sh`
  обновлён (канвас + новые шоты, вместо старого набора с тёмным main-dark).
- **`screenshots/landing-demo.gif`** — новый: **настоящая запись** скролла лендинга
  (playwright record_video → webm → ffmpeg GIF через `imageio-ffmpeg` в venv, без sudo),
  тот же серый канвас (880×560, 67 кадров, 4.2MB, 10fps, без дизеринга — иначе 13MB).
- **README**: оба GIF в галерее, подписи уточнены.

Урок по размеру: мягкая тень и дизеринг раздувают GIF (13MB) — для веба убраны
(рамка + серый фон достаточно), иначе README не загрузится.

## Фаза 22 — Анимированные скриншоты в лендинге + табы в стиле CodeRabbit

Два запроса: (1) анимированные скриншоты на сером фоне прямо в лендинге,
(2) анимированный элемент как на coderabbit.ai ниже «Best-in-class context».

**Записи (playwright record_video → ffmpeg GIF через imageio-ffmpeg в venv):**

- `screenshots/repo-page-demo.gif` — hero: repo-страница + открытие smart diff (клики),
  300KB / 45 кадров.
- `screenshots/projects-demo.gif` — список проектов → repo (клик по проекту), 672KB / 42 кадра.
- `screenshots/branches-demo.gif` — ветки (branches tab), 556KB / 45 кадров.
- Все три — **серый канвас `#DCDCDC`** 880×560 (как README-гифы), 8fps, без дизеринга
  (с ним было бы 13MB+). Логин-пролог срезан (`-ss 2`), длительность ограничена
  `-frames:v 45` (баг: `-t 5` попадал на палитру, а не на вывод).
- Скопированы в `frontend/public/screenshots/` и подключены в `BrowserShot`
  (`LandingPage.tsx`): hero — `repo-page-demo.gif`, фиче-фреймы — `projects-demo.gif`
  и `branches-demo.gif`. `loading="lazy"` оставлен — ниже фолда грузятся при скролле
  (проверено playwright: все 3 complete 880×560).

**Табы в стиле CodeRabbit (`cr-engine`, ниже «Best-in-class context»):**

- 5 табов: ⚙️ DAW parsing engine · 🔄 Smart diff · 📜 Decision ledger · 🧱 Content-addressed
  storage · ✅ Review & approval — как у них (Review generation / Ensemble / Codegraph / …).
- У каждого таба — **анимированный визуал**: `EngineVisual`-компоненты — каскад чипов
  `eng-chip` (128 BPM, 4/4, 12 tracks, 8 plugins, 42 samples, −14 LUFS) с staggered
  `animation-delay`, diff-строки с подсветкой +/−, ledger-записи, blob-дедуп, approval-чейн.
- Проверено playwright: 5 табов переключаются, активный подсвечен, 6 чипов на месте,
  ноль JS-ошибок.

**Апгрейд: GIF → видео в полном разрешении.** Пользователь: «скриншоты не устраивают,
нужны чёткие с максимальным разрешением, чтобы было видно все детали». GIF ограничен
256 цветами и 880×560 — детали мылись. Решение:

- Клипы перезаписаны playwright (viewport 1440×900, device_scale_factor=2) — исходный
  webm уже 1440×900 (VP8, 25fps). Логин-пролог (~3.2s) срезан, конвертация в **H.264 MP4**
  (libx264, crf 20, yuv420p, +faststart) — полный цвет, все детали, ~200KB на клип.
  `screenshots/{repo-page,projects,branches}-demo.mp4` + копии в `frontend/public/screenshots/`.
- `BrowserShot` переведён на `<video autoPlay muted loop playsInline preload="metadata"
  poster=…>` со статическим PNG-постером (`repo-page.png` / `projects.png` /
  `repo-page-branches.png`) и `<img>`-фолбэком для браузеров без видео. CSS: `.cr-shot
  video` = те же правила, что у img.
- Старые GIF-версии клипов удалены из обоих каталогов.
- Проверено playwright: все 3 видео 1440×900, readyState 4, играют, постеры на месте,
  ноль ошибок/сорвавшихся запросов; яркость кадра ~90% (не чёрный блок). Build ✅.

## Фаза 23 — Страницы интеграций Cubase и FL Studio (синий / оранжевый)

Запрос: «добавь ещё страницы про интеграции Cubase и FL Studio также со скриншотами,
только другим цветом». Выбор: отдельные страницы + карточки на лендинге, реальные
скриншоты SoundHub, фирменные цвета DAW.

**Реальные данные:** в живой БД созданы два проекта через `snd push`:

- `Cubase Sessions` (id 6) — .cpr: 126 BPM, Cubase 13.0.40, 5 треков (midi/audio/group),
  8 плагинов (Serum, Vital, FabFilter Pro-Q 3 / Pro-L 2, SSL Bus Comp, CLA-76, deesser,
  ValhallaVintageVerb), 4 сэмпла.
- `FL Sessions` (id 7) — .flp: 140 BPM, FL Studio 21 (marker 0x65), 3 канала (Kick,
  Lead, Sub Bass) из FLCh-чанков.

**Скриншоты:** страницы проекта с раскрытым DawInfoBox (клик по .cpr/.flp, скролл
к последнему .daw-box — первый это NFT-блок), deviceScaleFactor=2 → 2880×1800,
сохранены как `cubase-integration.png` / `fl-integration.png`.

**Страницы:** новый `DawIntegrationPage.tsx` — переиспользуемый макет с темой через
`--daw-accent` (CSS-переменная): hero с пульсирующим бейджем, скриншот в браузерной
рамке с цветной тенью, сетка «что парсим» (6 ячеек), workflow `snd push`, чипы
форматов, честный next-step. Маршруты `/integrations/cubase` (синий #2e6bd6) и
`/integrations/fl-studio` (оранжевый #ff7a1a).

**Лендинг:** секция «Where you make music» — FL Studio и Cubase стали `available`
с деталями и ссылкой «Page →»; футер — ссылки на обе страницы (REAPER остался planned).

**Проверено (playwright):** обе страницы — акцент применён, скриншот 2880×1800
complete, 6 ячеек, 0 ошибок; клик «Page →» с лендинга открывает /integrations/cubase;
build ✅.

Пользователь не увидел страницы — ссылки были только в секции «Where you make music»
внизу лендинга. Добавил **кнопки с пиктограммами в нижнюю панель навигации**
(SiteHeader): «Cubase» (иконка-куб) и «FL Studio» (иконка-плейлист) — сразу после
«Smart diff». Проверено playwright: пункты в панели, клики открывают обе страницы,
0 ошибок.

**Выделение блоков со скриншотами.** Пользователь: «выделить блоки со скриншотами,
чтобы не сливались с главным фоном». Скриншоты и фон оба ~#f2f0eb — сливались.
Фикс: новые CSS-переменные темы `--shot-bg` / `--shot-border` / `--shot-shadow`
(light: белый #fff + тень 0 26px 70px; dark: #23221f + глубже). `.cr-shot` (лендинг)
получил белую подложку padding 14px + рамку + двойную тень; `.daw-int-shot-frame`
(страницы интеграций) — белый фон + `--shot-shadow` поверх цветной акцент-тени.
Проверено: computed style white #fff / dark #23221f, build ✅. Потом по просьбе
«ещё темнее» — подложка `#d6d2c7`, тень 0.2/0.32.

**Гигантский логотип в футере (CodeRabbit-стиль).** Пользователь: «смотри
coderabbit.ai — внизу огромный на всю ширину логотип, снизу затенённый». Изучил
их футер: под колонками — `div.mt-14.w-full.overflow-hidden` с картинкой
`object-cover w-full opacity-80` (footer-logo.png 1200×171). У SoundHub лого
929×293 с прозрачным фоном. Добавил в `.bc-footer`: `.bc-footer-giant` —
контейнер на всю ширину (height clamp 120–240px), логотип `width: min(92%, 1400px)`,
`opacity: 0.5`, `filter: grayscale(0.35)` и **mask-image: linear-gradient
(to bottom, 0.9 → transparent)** — нижняя часть растворяется в фон, как на
CodeRabbit. Hover — opacity 0.75. Проверено: контейнер 1352×240, маска применена,
лого видно; светлая и тёмная темы ок, build ✅.

## Фаза 24 — Whitepaper.pdf (подробный, с формулами, графиками и скриншотами)

Создан **`Whitepaper.pdf`** (18 стр., A4, 1.3MB) + исходник `docs/whitepaper.html`
и 6 графиков в `docs/`. Фактура — из LITEPAPER.md / DESCRIPTION.md / README
(честно, без выдумок).

**Формулы (MathJax 3 → SVG, 22 рендера, 8 нумерованных):** (1) SHA-256 blob key,
(2) commit = path→hash, (3) smart diff Δ(A,B), (4) EIP-191 ecrecover,
(5) order-independent collaborator claim, (6) кусочная vesting-функция (cliff 6,
24 мес), (7) quorum-условие Governor, (8) fee/seller payout.

**Графики (matplotlib в venv):** time.png (часы на звук vs покупка), daw.png
(покрытие парсеров), escrow.png (жизненный цикл эскроу), tokenomics.png (donut
35/25/20/10/10), vesting.png (кривая разблокировки 800k + team 24m/6m cliff),
dao.png (Governor-таймлайн).

**Скриншоты (из живого продукта):** Cubase-проект с распарсенными данными,
repo-страница, лендинг, FL Studio-проект.

**Сборка:** HTML → playwright page.pdf() (A4, print_background, поля 14/16мм),
MathJax через jsDelivr CDN с ожиданием mjx-container. Проверено: 22 формулы,
0 пустых SVG, сырого LaTeX в PDF нет, 18 страниц, изображения и шрифты на месте.

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
