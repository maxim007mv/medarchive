# 05. Архитектура системы (RFC-001)

Статус: принято к реализации. Связанные документы: 03-stack-decision, 06-api-contract (v1), 07-database, 07-data-model.sql, 08-security-privacy, 09-decisions-ADR, 10-patterns.

## 1. Цели и не-цели

Цели:
1. Все 8 требований задания (R1 до R8, см. 01) проходят сценарием от начала до конца на онлайн-стенде и локально.
2. Данные переживают перезапуск браузера, сервера и контейнеров.
3. p95 открытия списка < 300 мс на 1000 документов, загрузка PDF 1 МБ < 2 с на канале 20 Мбит/с.
4. Контракт API описан в OpenAPI и проверяется в CI.

Не-цели: многопользовательские роли, совместный доступ, OCR, медицинские выводы, мобильные приложения.

## 2. Контекст (C4, уровень 1)

```
[Пользователь, браузер] --HTTPS--> [ALB, Yandex Cloud ru-central1]
        |                               |-- /*        --> [Web: Next.js]
        |                               |-- /api/v1/* --> [API: FastAPI] --SQL + RLS--> [Managed PostgreSQL]
        |                                                     |  |--Encrypt/Decrypt DEK--> [Yandex KMS]
        |  presigned POST (только загрузка)                   |  |--S3 API--> [Object Storage: ma-docs, шифртекст]
        +----------------------> [Object Storage: ma-quarantine] <--проверка--+
                                                              |--(опционально)--> [Redis: очередь, лимиты] --> [AI-воркер] --> [LLM в РФ]
```

Один домен для web и API: cookie `__Host-ma_sid` с `SameSite=Lax` работает без CORS, CSP проще. Все компоненты в ru-central1 (152-ФЗ ст. 18 ч. 5, S42; ADR-007).

## 3. Контейнеры (C4, уровень 2)

| Контейнер | Технология | Ответственность | Масштабирование |
|---|---|---|---|
| web | Next.js 15, Node 22 | SSR каркаса и первой страницы списка, UI | Yandex Serverless Containers, без состояния |
| api | FastAPI, uvicorn, Python 3.12 | Сессии, скоупы, CRUD, presigned загрузка, проверка PDF, шифрование, экспорт | 2 до N реплик, без состояния; открытые ключи пространства только на время запроса (ADR-041) |
| db | Managed PostgreSQL 17 (проверено на 18), PgBouncer transaction | Пространства, документы (поля шифртекстом), сессии, аудит | 2 хоста в разных зонах, ежедневная копия + PITR 7 дней |
| storage | Yandex Object Storage (MinIO локально) | `ma-quarantine` (сырые загрузки, жизненный цикл 1 день), `ma-docs` (только шифртекст Tink) | Управляемое, публичный доступ запрещён |
| kms | Yandex KMS | KEK, обёртка DEK пространств | Управляемое |
| redis (опц.) | Managed Redis 7 | Лимиты GCRA, ограниченная очередь AI | 1 инстанс, без ПДн |
| ai-worker (опц.) | Python, arq | Подсказка полей по тексту PDF | Число воркеров = лимит параллельности модели |

## 4. Компоненты API (уровень 3, модульный монолит)

```
app/
  main.py                      сборка приложения, middleware (request_id, заголовки безопасности), роутеры /api/v1
  core/config.py               настройки (pydantic-settings), секреты из Lockbox
  core/errors.py               исключения -> RFC 9457 problem+json, каталог кодов
  core/deps.py                 get_session, require_scope(...), get_uow(workspace_id) c set_config('app.workspace_id', .., true)
  core/idempotency.py          Idempotency-Key: отпечаток тела, 400/422/409, повтор ответа
  core/ratelimit.py            GCRA в Redis, заголовки RateLimit / RateLimit-Policy, 429 + Retry-After
  core/crypto.py               Tink AEAD и Streaming AEAD, обёртка DEK через KMS, слепой индекс HMAC
  modules/auth/                POST /workspaces, GET /session, POST /sessions, DELETE /sessions/current, ключ доступа
  modules/workspace/           GET/DELETE /workspace, POST /workspace/access-key
  modules/uploads/             POST /uploads (presigned POST), проверка объекта в карантине
  modules/documents/           GET/POST /documents, GET/PATCH/DELETE /documents/{id}, GET /documents/{id}/content
  modules/suggestions/         POST /suggestions, адаптер модели (JSON-схема, маскирование ФИО)
  modules/exports/             POST /exports, GET /exports/{id}/content (zipstream)
  modules/*/repository.py      SQLAlchemy 2 async, selectinload, lazy="raise"
  workers/                     ai_suggest, purge (мягко удалённые, загрузки, экспорты), audit-партиции
```

Правило слоёв: router знает HTTP, service бизнес-правила, repository SQL; модули общаются только через публичные сервисы (10-patterns).

## 5. Ключевые потоки

### 5.1. Загрузка и создание документа (R2)

```
Browser                         API                                  Object Storage            KMS        DB
  | POST /api/v1/uploads {original_name, size_bytes, content_type} + Idempotency-Key
  |------------------------------>| size <= 20 МБ? иначе 413 file_too_large
  |                               | INSERT uploads(status=pending, expires_at=+1ч)
  |<-- 201 {upload_id, url, fields: policy c content-length-range 1..20971520, key}
  | POST url (multipart: fields + file) ------------------------------->| ma-quarantine/q/{ws}/{upload}.bin
  |<------------------------------------------------------------- 204 --|
  | (параллельно человек заполняет форму; при флаге AI: POST /api/v1/suggestions {upload_id})
  | POST /api/v1/documents {upload_id, title, type, document_date|null, note} + Idempotency-Key
  |------------------------------>| 1. сессия -> workspace_id, скоуп documents:write, согласие действует
  |                               | 2. HEAD объекта: есть? иначе 409 upload_incomplete
  |                               | 3. чтение потоком: сигнатура %PDF-, pypdf открывает, нет шифрования, страницы
  |                               | 4. ключи пространства: расшифровка KEK на каждый запрос, без кэша (ADR-041) ->|
  |                               | 5. Streaming AEAD (AAD=document_id) -> ma-docs/ws/{ws}/{doc}.bin
  |                               | 6. транзакция: INSERT documents (title_ct, title_bidx, note_ct), document_files,
  |                               |    uploads.status=consumed, audit_log; uploaded_at = now() в БД -------------->|
  |                               | 7. DELETE объекта из карантина (иначе удалит жизненный цикл за 1 день)
  |<-- 201 Document + ETag "v1" + Location
```

Решения:
1. Файл не проходит через API при загрузке: лимит размера проверяет хранилище условием политики (S45, S47), API не держит 20 МБ в памяти.
2. Проверка и шифрование выполняются до записи в `ma-docs`; в постоянном бакете не бывает непроверенного или открытого файла (OWASP File Upload, S29).
3. `uploaded_at` ставит только сервер; `document_date` nullable, `null` = «не указана».
4. Строка без файла невозможна: файл в `ma-docs` пишется до транзакции; если транзакция упала, объект удаляет задача `purge` (сравнение с `document_files` старше 1 часа).
5. Повтор `POST /documents` с тем же `Idempotency-Key` возвращает первый ответ (S19).

### 5.2. Список, поиск, фильтр (R3, R4)

Запрос: `GET /api/v1/documents?q=анализ&date_field=document&from=2026-04-01&to=2026-04-30&type=analysis&order_by=document_date%20desc&page_size=50&page_token=...`

SQL (упрощённо, полный текст и планы в 07-database, разделы 4 и 5):
```sql
SELECT id, type_code, title_ct, document_date, uploaded_at, note_ct IS NOT NULL AS has_note, version
FROM documents                                   -- RLS: workspace_id = current_setting('app.workspace_id')
WHERE (:bidx IS NULL OR title_bidx @> :bidx)     -- слепой триграммный индекс, GIN (workspace_id, title_bidx)
  AND (:types IS NULL OR type_code = ANY(:types))
  AND (:from IS NULL OR <поле> >= :from)
  AND (:to   IS NULL OR <поле> <  :to + 1)        -- граница включительно
  AND (NOT :undated OR document_date IS NULL)
  AND (list_key, uploaded_at, id) > (:k, :u, :id) -- keyset из page_token
ORDER BY list_key, uploaded_at, id                -- = дата документа по убыванию, без даты последние, затем порядок добавления
LIMIT :page_size + 1;
```
`list_key` = `DATE '1900-01-01' - document_date`, для `NULL` = 2147483647 (сгенерированная колонка). `<поле>` это `document_date` или `uploaded_at` в зоне пользователя (`tz`). Названия расшифровываются в API для одной страницы (до 200 AES-GCM операций, меньше 1 мс). Ответ: `items`, `total`, `matched`, `undated_excluded`, `next_page_token`.

### 5.3. Просмотр и скачивание файла (R3)

`GET /api/v1/documents/{id}/content?disposition=inline|attachment` проверяет скоуп и RLS, расшифровывает Streaming AEAD потоком и отдаёт `application/pdf` c `Accept-Ranges: bytes` (встроенный просмотрщик браузера запрашивает части), `Content-Security-Policy: sandbox`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, имя файла через `filename*=UTF-8''...`. Presigned GET не используется: в хранилище лежит только шифртекст, а ссылка без проверки сессии была бы утечкой (ADR-011).

### 5.4. Заметка и правки (R5)

`PATCH /api/v1/documents/{id}` с `{note}` и `If-Match: "v3"`. Нет заголовка: 428; устарел: 412 `version_conflict` с текущим ETag; клиент сохраняет введённый текст и показывает «Документ изменился в другой вкладке. Обновите, чтобы увидеть новую версию». Пустая строка нормализуется в `null`. Клиент сохраняет заметку через 800 мс после ввода с оптимистичным обновлением и откатом (S56).

### 5.5. Удаление (R6)

1. `DELETE /api/v1/documents/{id}` с `If-Match`: транзакция ставит `deleted_at = now()` и пишет аудит; политика `hide_deleted` сразу скрывает строку из всех запросов, ответ 204.
2. Задача `purge` в течение 24 часов удаляет объект из `ma-docs` и строку физически (07-database, раздел 8). Документ не возвращается ни в список, ни по прямой ссылке (404).
3. Удаление архива: `DELETE /api/v1/workspace` отзывает сессии и удаляет DEK пространства (криптоудаление), очистка за 24 часа.

### 5.6. Экспорт (R8)

`POST /api/v1/exports {scope: all|filtered|selected, filter | document_ids}` с `Idempotency-Key` фиксирует состав и возвращает `document_count`, `total_bytes` (подпись кнопки «Скачать ZIP · 157 КБ») и `content_url` на 1 час. `GET /api/v1/exports/{id}/content` отдаёт `application/zip` потоком (zipstream): PDF с именами `{YYYY-MM-DD|bez-daty}_{транслит-названия}.pdf` (правила транслитерации, замены символов на `-`, длины до 80 и суффикса `-2` для совпадений в `docs/texts.md`, раздел 13), `documents.csv` (UTF-8 с BOM) и `documents.json`.

## 6. Сессии и доступ без регистрации

| Элемент | Решение | Почему |
|---|---|---|
| Пространство | `workspaces` создаётся вызовом `POST /api/v1/workspaces` после согласия и выбора первого файла | Без согласия нельзя обрабатывать сведения о здоровье (152-ФЗ ст. 10, S41) |
| Сессия | Cookie `__Host-ma_sid`: 256 бит, в БД SHA-256; `HttpOnly; Secure; SameSite=Lax; Path=/`; простой 30 дней, абсолютный срок 180 дней | Кража базы не даёт войти; ограничен ущерб от украденной cookie (S28) |
| Ключ доступа | 24 символа Crockford Base32 группами по 4: `lookup_id` 6 символов + секрет 18 символов (90 бит), секрет Argon2id m=19 MiB, t=2, p=1 | Открыть архив на другом устройстве без email (S51) |
| Восстановление | `POST /api/v1/sessions {access_key}`; 5 попыток за 15 минут на IP; одинаковое время ответа | Защита от перебора |
| CSRF | `X-CSRF-Token` из `GET /api/v1/session` на всех изменяющих запросах | SameSite=Lax закрывает не всё |
| Скоупы | `documents:read`, `documents:write`, `exports:create`, `workspace:manage` | Готовность к ссылке «показать врачу» только на чтение (API5) |


Ограничение, которое честно пишем пользователю: без ключа доступа очистка cookie означает потерю доступа к архиву.


## 7. AI-подсказка и обратное давление (опционально)

Генерация моделью медленная (1 до 6 с) и дорогая, её скорость задаёт всю систему. Стандарт команды: **ограниченная очередь, явный отказ с временем повтора, ничего не теряется молча.**

```
POST /api/v1/suggestions {upload_id} + Idempotency-Key
   -> лимит на сессию: 10 в минуту (GCRA в Redis), иначе 429 rate_limited + Retry-After
   -> очередь arq, глубина не больше 20 задач на инстанс API
        очередь полна  -> 429 ai_busy, Retry-After: <оценка по текущей скорости>
        принято        -> ответ ждёт результата до 8 с (синхронно для клиента)
        нет ответа     -> 503 ai_unavailable, форма остаётся ручной
воркеры: N = лимит параллельности модели; 1 повтор с jitter при 5xx/429 от модели
```

| Правило | Реализация |
|---|---|
| Очередь ограничена | Атомарная проверка длины (Lua-скрипт `LLEN` + `RPUSH`) |
| Не терять молча | Любой отказ это явный 429 / 503 c `Retry-After` и текстом из каталога ошибок |
| Скорость задаёт медленная сторона | При 429 от провайдера воркер уважает его `Retry-After` и снижает параллельность (AIMD: вдвое вниз, плюс 1 каждые 30 с успеха) |
| Клиент уважает Retry-After | «Повторить» заблокирована с обратным отсчётом; автоповтор максимум 1 раз |
| Основной сценарий не зависит от AI | Ручная форма доступна сразу, подсказка только дополняет поля и помечена |
| Таймауты | Сервер 8 с, клиент 10 с, затем «Не успели подсказать, заполните вручную» (S6) |
| Минимизация | В модель уходят первые 4000 символов текста без ФИО и даты рождения; модель с хостингом в РФ |

Метрики: `ai_queue_depth`, `ai_rejected_total{reason}`, `ai_latency_seconds` (p50/p95), `llm_429_total`.

## 8. Нефункциональные требования

| NFR | Значение | Как проверяем |
|---|---|---|
| Доступность стенда | 99,5% в период проверки | Uptime-монитор раз в минуту |
| p95 GET /api/v1/documents | < 150 мс на 50 строк (онлайн), план Q1 0,12 мс на 210 тыс. строк | k6, 05_qa; 07-database |
| p95 POST /api/v1/documents (1 МБ) | < 1,5 с серверного времени | k6 |
| Размер JS первой загрузки | < 180 КБ gzip | `next build` + бюджет в CI |
| LCP главной | < 2,0 с на 4G | Lighthouse CI |
| Доступность | WCAG 2.2 AA | axe в e2e + ручной чек-лист |
| Резервное копирование | БД ежедневно + PITR 7 дней (S46); бакет `ma-docs` без версионирования, чтобы удаление было окончательным | Ежеквартальный тест PITR (TZ-devops-security, OPS-09) |

## 9. Наблюдаемость
1. Логи JSON (structlog): `request_id`, `workspace_id` (хэш), путь, статус, длительность. Никогда не логируем названия документов, заметки, имена файлов.
2. Метрики Prometheus: RED на эндпоинт, размер загрузок, ошибки S3.
3. Трейсы OpenTelemetry: web -> api -> S3/DB.
4. Sentry (self-hosted в ru-central1) для фронта и бэка со скрабом ПДн.

## 10. Деплой и окружения

| Окружение | Ветка | URL | Данные |
|---|---|---|---|
| local | любая | http://localhost:3000 | docker volumes |
| preview | PR | preview-контейнер в Yandex Cloud + общий staging API | синтетические |
| prod (стенд для проверки) | main | https://medarchive.<домен> | только тестовые PDF из задания |

Конфигурация через env, секреты из Lockbox: `DATABASE_URL`, `S3_ENDPOINT`, `S3_BUCKET_QUARANTINE`, `S3_BUCKET_DOCS`, `KMS_KEK_ID`, `PAGE_TOKEN_KEY`, `MAX_UPLOAD_MB=20`, `AI_SUGGEST_ENABLED=false`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `AI_WORKERS=4`. Локально KMS заменяется ключом Tink из файла (только для разработки).

## 11. Риски

| Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|
| Проверяющий открывает в другом браузере и видит пустой архив | Средняя | Высокое | В README и онбординге: «Архив привязан к браузеру; ключ доступа открывает его везде»; на стенде можно сразу предложить ключ |
| Встроенный просмотр PDF не работает в браузере проверяющего | Низкая | Среднее | Кнопки «В новой вкладке» и «Скачать» всегда рядом |
| S3 или KMS недоступны | Низкая | Среднее | 503 `storage_unavailable` с `Retry-After`; удаление файла повторяет задача `purge` (5.5) |
| Часовые пояса в фильтре по дате загрузки | Средняя | Среднее | Параметр `tz`, тесты на границы суток |
| LLM перегружен | Средняя | Низкое | Backpressure (раздел 7), AI не блокирует сценарий |
