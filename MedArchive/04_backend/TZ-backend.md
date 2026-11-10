# ТЗ бэкенд: Медархив API (FastAPI)

Роль: бэкенд-разработчик или AI-агент. Входы: `01_common/05-architecture.md` (RFC-001), `01_common/06-api-contract.md`, `01_common/openapi.yaml` (источник истины), `01_common/07-data-model.sql`, `01_common/08-security-privacy.md`. Выход: сервис `apps/api`, проходящий контрактные и интеграционные тесты из `05_qa`.

## 0. Правила работы
1. `openapi.yaml` первичен. Любое расхождение кода и схемы = красный CI (schemathesis + проверка `app.openapi()` против файла).
2. Тексты ошибок для пользователя (`title`, `errors[].message`) берутся из таблицы раздела 4 дословно, на русском. Они совпадают с `04-customer-journey.md`; при расхождении прав путь пользователя.
3. Слои: `api` → `services` → `repositories`. `services` не импортируют FastAPI.
4. Никаких названий, заметок и имён файлов в логах, метриках и Sentry.
5. Коммиты `BE-07: ...`, задача закрыта только с тестом.

## 1. Окружение

| Компонент | Версия | Зачем |
|---|---|---|
| Python | 3.12 | |
| FastAPI + Uvicorn | 0.115+ | HTTP, OpenAPI |
| SQLAlchemy 2 (async) + asyncpg | 2.0+ | ORM, пулы |
| Alembic | 1.13+ | миграции из `07-data-model.sql` |
| PostgreSQL | 16 | pg_trgm, генерируемые колонки |
| MinIO локально, S3-совместимое хранилище в облаке | | файлы |
| pypdf | 5+ | проверка PDF, число страниц |
| zipstream-ng | 1.7+ | потоковый ZIP |
| argon2-cffi | 23+ | хэш ключа доступа |
| Redis + arq | 7 / 0.26 | только при `AI_SUGGEST_ENABLED=true` |
| structlog, prometheus-client, opentelemetry, sentry-sdk | | наблюдаемость |
| pytest, pytest-asyncio, httpx, testcontainers, schemathesis | | тесты |

`docker compose up` поднимает `web`, `api`, `db`, `minio`, `redis` (профиль `ai`). `make seed` загружает 6 PDF из `05_qa/fixtures` с датами из задания.

## 2. Задачи по порядку

| ID | Задача | Детали | Приёмка |
|---|---|---|---|
| BE-01 | Каркас | Модульный монолит по `05-architecture.md`, раздел 4; роутеры под `/api/v1`; конфиг pydantic-settings, секреты из Lockbox; `/healthz` и `/readyz` (БД, хранилище, KMS); JSON-логи с `request_id` без ПДн | `GET /readyz` = 503, если MinIO или KMS недоступны |
| BE-02 | Схема БД | Alembic по `07-data-model.sql` и `TZ-database.md` (DB-01..DB-12): роли, FORCE RLS, `list_key`, слепой индекс, аудит | `alembic upgrade head` и `downgrade base` зелёные |
| BE-03 | Ошибки | Единый обработчик → `application/problem+json` (RFC 9457) с `code` из каталога `06-api-contract.md`, раздел 8, `request_id`, `errors[].pointer`; 500 без трассы и без значений полей | Контрактный тест: каждый код каталога достижим и совпадает с `openapi.yaml` |
| BE-04 | Сессии и согласие | `POST /api/v1/workspaces` (только с `consent.accepted=true`, иначе 403 `consent_required`) создаёт `workspace`, DEK в KMS, `consents`, `session`; cookie `__Host-ma_sid` (256 бит, в БД SHA-256, `HttpOnly; Secure; SameSite=Lax; Path=/`, простой 30 дней, абсолютный 180); `GET /api/v1/session` отдаёт `csrf_token` и скоупы; `DELETE /api/v1/sessions/current`; зависимость `require_scope` | Без cookie 401 `unauthenticated`; без `X-CSRF-Token` 403 `csrf_failed` |
| BE-05 | Ключ доступа | Выдаётся в ответе `POST /api/v1/workspaces` и `POST /api/v1/workspace/access-key` (старый отзывается): 24 символа Crockford Base32 = `lookup_id` 6 + секрет 18 (90 бит), Argon2id m=19 MiB, t=2, p=1; вход `POST /api/v1/sessions` через `find_access_key` (`ma_auth`), 5 попыток за 15 мин на IP, одинаковое время ответа | Ключ показывается один раз; перебор получает 429 |
| BE-06 | Загрузка | `POST /api/v1/uploads` (Idempotency-Key): `size_bytes` > 20 МБ → 413 сразу; иначе строка `uploads` и presigned POST в `ma-quarantine` с `content-length-range 1..20971520`, точным `key`, сроком 15 мин. `POST /api/v1/documents {upload_id,...}`: HEAD объекта (нет → 409 `upload_incomplete`), чтение потоком: `%PDF-` иначе 415 `not_pdf`, pypdf иначе 422 `pdf_unreadable` / `pdf_encrypted`, страницы; Streaming AEAD (AAD = `document_id`) в `ma-docs`; одна транзакция: `documents`, `document_files`, `uploads.status=consumed`, аудит; удаление из карантина | 6 фикстур сохраняются; `fake.pdf` 415; `big-21mb.pdf` 413 до передачи файла |
| BE-07 | Список | Фильтры `q` (от 3 символов, нормализация регистра и `ё→е`, триграммы → HMAC слепого индекса, поиск `title_bidx @> :bidx` литеральным массивом), `type`, `date_field`, `from`, `to` (включительно, для `uploaded` через `AT TIME ZONE :tz`), `undated`; сортировки из схемы, без даты всегда в конце; keyset по `(list_key, uploaded_at, id)`, `page_token` AES-GCM с хэшем фильтров (AIP-158), `page_size` до 200; `total`, `matched`, `undated_excluded`, `next_page_token` | TC-030..TC-044 |
| BE-08 | Карточка и файл | `GET /api/v1/documents/{id}` с `ETag` и `If-None-Match` → 304; чужой id = 404 (RLS); `GET /api/v1/documents/{id}/content` расшифровывает потоком, поддерживает `Range` (206), заголовки `Content-Security-Policy: sandbox`, `nosniff`, `no-store`, `filename*=UTF-8''...`; presigned GET не используется | Скачанный файл совпадает с исходным по SHA-256 |
| BE-09 | Изменение | `PATCH /api/v1/documents/{id}` частичный (`minProperties: 1`, лишние поля 422); `If-Match` обязателен: нет → 428 `precondition_required`, не совпал → 412 `version_conflict` с текущим `etag`; `note` пустая строка → `null`; `ETag` в ответе; поля перешифровываются, `title_bidx` пересчитывается | TC-058, TC-059 |
| BE-10 | Удаление | `DELETE /api/v1/documents/{id}` с `If-Match`: `deleted_at = now()` + аудит в транзакции, 204; физическое удаление объекта и строки задачей `purge` за 24 ч; `DELETE /api/v1/workspace`: отзыв сессий, удаление DEK (криптоудаление), 202 с `purge_before` | Повторный DELETE = 404; после удаления архива объект не расшифровывается |
| BE-11 | Экспорт | `POST /api/v1/exports {scope, filter / document_ids}` (Idempotency-Key) фиксирует состав, возвращает `document_count`, `total_bytes`, `content_url`, срок 1 ч; `GET /api/v1/exports/{id}/content` поток zipstream: PDF с именами `{YYYY-MM-DD|bez-daty}_{транслит}.pdf`, `documents.csv` (UTF-8 с BOM, разделитель `;`), `documents.json` | TC-070, TC-071 |
| BE-12 | Лимиты | GCRA в Redis по таблице `06-api-contract.md`, раздел 3; заголовки `RateLimit-Policy` и `RateLimit` на каждом ответе лимитируемых маршрутов; превышение 429 `rate_limited` + `Retry-After` | TC-098 |
| BE-13 | Фоновые задачи | Воркер `ma_worker`: `purge` (мягко удалённые документы и архивы, брошенные загрузки, объекты `ma-docs` без строки старше 1 ч, экспорты старше 1 ч), чистка `idempotency_keys` старше 24 ч, создание партиции `audit_log` следующего месяца | Задачи идемпотентны, пакеты по 500 |
| BE-14 | Безопасность | Меры `08-security-privacy.md` (T1..T16): заголовки (`default-src 'none'` для API, `nosniff`, HSTS), CORS только свой origin, `additionalProperties: false` во входных схемах, шифрование полей Tink AEAD c AAD | Отчёт `zap-baseline` без high; TC-090..TC-098 |
| BE-15 | Наблюдаемость | RED-метрики на эндпоинт, `upload_bytes`, `s3_errors_total`; трейсы OTel; Sentry с `before_send`, вырезающим тело запроса | Проверка лога: нет названий документов |
| BE-16 | AI-подсказка (флаг) | `POST /api/v1/suggestions {upload_id}` (Idempotency-Key): лимит 10 в мин, очередь arq не больше 20 на инстанс, иначе 429 `ai_busy` + `Retry-After`; ожидание результата до 8 с, затем 503 `ai_unavailable`; в модель первые 4000 символов без ФИО и даты рождения; ответ по JSON-схеме, невалидный отбрасывается | TC-100..TC-104 |
| BE-17 | Сид для стенда проверки | `make seed` и `python -m app.cli seed --workspace <id>` загружают 6 фикстур из задания через тот же путь uploads → documents | 6 документов с датами из `test-strategy.md` |

## 3. Правила бизнес-логики (проверяются unit-тестами)
1. Дата загрузки не меняется никогда, в том числе при PATCH.
2. Дата документа может быть `null`; фильтр по дате документа такие документы не возвращает и считает их в `undated_excluded` только если они прошли остальные фильтры (`q`, `type`).
3. `from > to` → 422 с полем `from` и текстом «Начало периода позже конца».
4. Только `from` или только `to` допустимы.
5. Поиск по подстроке без учёта регистра и `ё/е`; пустой `q` после trim = без поиска.
6. Сортировка по умолчанию: дата документа ↓, при равенстве в порядке добавления (дата загрузки ↑, раньше добавленный выше), затем `id`; документы без даты в конце по тому же правилу. Так документы одного визита в клинику стоят в том порядке, в каком их добавили.
7. Пространства изолированы: каждый запрос репозитория принимает `workspace_id` обязательным аргументом (нет функций без него).

## 4. Тексты ошибок

| code | HTTP | title | Поле / пример `errors[].message` |
|---|---|---|---|
| validation_error | 422 | Проверьте выделенные поля | title: «Введите название, чтобы найти документ в списке»; document_date: «Такой даты нет. Проверьте день и месяц»; document_date: «Дата документа не может быть в будущем» |
| not_pdf | 415 | Файл не добавлен: это не PDF. Сервис принимает только PDF. Сохраните документ в PDF и попробуйте снова. | |
| file_too_large | 413 | Файл больше 20 МБ. Сожмите PDF или разделите его на части. | |
| pdf_unreadable | 422 | Не удаётся открыть этот PDF. Возможно, он повреждён или защищён паролем. | |
| not_found | 404 | Документ не найден. Возможно, его уже удалили | |
| version_conflict | 412 | Документ изменился в другой вкладке. Обновите страницу | |
| rate_limited | 429 | Слишком много запросов. Повторите через {n} с | |
| ai_busy | 429 | Подсказка сейчас занята. Заполните поля вручную или повторите через {n} с | |
| unauthorized | 401 | Ключ не подошёл. Проверьте символы и попробуйте снова | |
| csrf_failed | 403 | Сессия устарела. Обновите страницу | |
| internal | 500 | Что-то пошло не так на нашей стороне. Попробуйте ещё раз | |

## 5. Определение готовности (DoD)
1. BE-01..BE-15 и BE-17 закрыты; BE-16 работает при включённом флаге и не влияет на сценарий при выключенном.
2. Unit + интеграционные тесты (testcontainers: Postgres, MinIO) зелёные, покрытие `services/` ≥ 90%.
3. schemathesis `--checks all` без ошибок по `openapi.yaml`.
4. k6: p95 `GET /documents` < 300 мс при 1000 документов и 50 VU; 0% 5xx.
5. После `docker compose restart` все документы, заметки и даты на месте (TC-080).
