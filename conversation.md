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
| Release-package templates | Next |
| Roles / approval chains / label mode | Next |
| USDC / Base оплата | Next |
| On-chain proof (anchor manifest hash) | Next (feature flag) |
| Ableton Max for Live integration | prototype / coming next |
| Интервью с mix/master инженерами | запланировано |

**Демо:** `http://localhost:5173/sessions` (demo / demo123).
**CI:** backend pytest · frontend tsc+vite · contracts hardhat — все зелёные.

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
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_CURRENCY`.
