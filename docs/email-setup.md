# Деловая почта + SMTP приложения (runbook)

Цель: адрес **soundhub@soundhub.io** для общения с инвесторами (приём +
отправка, брендовый домен) и реальная отправка напоминаний приложения
(Reminders) через SMTP.

## Схема

| Нужно | Сервис | Стоимость |
|---|---|---|
| Домен `soundhub.io` | DreamHost (регистратор) | ~$30–40/год |
| Почтовый ящик `soundhub@soundhub.io` (IMAP + webmail) | Zoho Mail **Free** (1 ящик на своём домене) | бесплатно |
| Отправка напоминаний приложения | Resend SMTP-реле (`smtp.resend.com:465`) | free tier |
| Ключ Resend | уже есть (`re_cyq…`) | — |

> Альтернатива Zoho: если в план DreamHost уже входит email-хостинг — можно
> завести ящик там (всё в одном месте). Zoho Free — запасной бесплатный путь.

## Шаг 1 — купить домен (DreamHost)

1. dreamhost.com → Domains → поиск `soundhub.io` → в корзину → оплата.
2. Домен появится в панели DreamHost (Manage Domains).

## Шаг 2 — ящик на Zoho Mail Free

1. zoho.com/mail (план Free) → «Set up with custom domain» → ввести
   `soundhub.io`.
2. Zoho покажет DNS-записи. Добавить их у DreamHost:
   **Manage Domains → soundhub.io → DNS → Add custom DNS record:**

   | Тип | Имя | Значение |
   |---|---|---|
   | MX | `soundhub.io` | `mx.zoho.eu` (или `mx.zoho.com`, смотря регион аккаунта) — приоритет 10 |
   | TXT | `soundhub.io` | `v=spf1 include:zoho.eu ~all` (или `zoho.com`) |
   | TXT | `zoho._domainkey` | DKIM-ключ из панели Zoho (кнопка копирования) |

3. Создать пользователя/ящик **soundhub** → адрес `soundhub@soundhub.io`.
4. Проверить приём: отправить письмо на `soundhub@soundhub.io` и открыть
   webmail Zoho.

## Шаг 3 — Resend: верификация домена (для напоминаний приложения)

1. resend.com/domains → Add Domain → `soundhub.io` → скопировать записи
   (SPF + 3 DKIM) → добавить их у DreamHost (те же DNS).
2. Дождаться статуса **Verified** (обычно минуты).
3. После этого напоминания приложения смогут слать с `soundhub@soundhub.io`
   на любые адреса (сейчас с тестового `resend.dev` — только на свой).

## Шаг 4 — переменные окружения

Бэкенд читает `os.environ` (без .env-файла).

**Локально** — бэкенд сам читает `backend/.env` (python-dotenv, env из
окружения имеет приоритет). Файл создан (gitignored):

```bash
# backend/.env — уже лежит локально, менять только SMTP_FROM/пароль
SMTP_HOST=smtp.resend.com
SMTP_PORT=465
SMTP_USER=resend
SMTP_PASSWORD=re_…
SMTP_FROM=SoundHub <soundhub@soundhub.io>
```

Шаблон для новых окружений: `backend/.env.example.smtp`.

**Render** (soundhub-backend): Dashboard → Environment → добавить те же
5 переменных как secrets (не в `render.yaml` — ключ не должен попадать в git).

**Fly** (если на нём): `fly secrets set SMTP_HOST=… SMTP_PORT=465 SMTP_USER=resend SMTP_PASSWORD='re_…' 'SMTP_FROM=SoundHub <soundhub@soundhub.io>'`

## Шаг 5 — проверка

```bash
# из backend/
SMTP_HOST=smtp.resend.com SMTP_PORT=465 SMTP_USER=resend \
SMTP_PASSWORD='re_…' SMTP_FROM='SoundHub <soundhub@soundhub.io>' \
.venv/bin/python -m scripts.test_smtp ваш@email.com
```

Плюс проверить в UI сессии: включаются reminders с `client_email` → после
`POST /api/reminders/evaluate` письмо уходит (в логе `notification.sent`).

## Troubleshooting

| Симптом | Причина | Фикс |
|---|---|---|
| `550 domain is not verified` | домен не верифицирован в Resend | добавить DNS-записи из resend.com/domains, ждать Verified |
| `550 only testing emails to your own address` | отправка с `resend.dev` | верифицировать свой домен |
| Письма не приходят в Zoho | MX/SPF не прописались | проверить через dns.google/resolve (TXT/MX) |
| `notification.failed` в логе | SMTP-транспорт | см. `n.error` в БД; проверить ключ/порт |

## Статус

- [x] Ключ Resend, SMTP-аутентификация
- [x] Транспорт в коде (SMTPS 465 / STARTTLS 587) + тесты (151 ✅)
- [x] Локальный `backend/.env` (dotenv, gitignored) — бэкенд шлёт бесплатно
- [x] Живая отправка из приложения (resend.dev → свой адрес, `sent:1`)
- [ ] Брендовый ящик: `soundhub@proton.me` (бесплатно) или `soundhub@soundhub.io` (~$30–40/год)
- [ ] Верификация домена в Resend (после покупки домена)
- [ ] SMTP-переменные в Render (для продакшена)
