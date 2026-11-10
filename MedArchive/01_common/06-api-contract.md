# 06. Контракт API v1 (RFC-001)

Статус: принято. Дата: 10.11.2026. Машиночитаемая версия: `openapi.yaml` (OpenAPI 3.1, проходит `openapi-spec-validator`). При расхождении текста и YAML прав YAML, а расхождение считается дефектом документации.

Номера `S..` ведут в `02-research-sources.md`. Каждое правило ниже записано как стандарт команды: что выбрано, где применяется, какие варианты отброшены и почему.

## 1. Принципы

| # | Правило | Где | Отброшено | Почему так | Источник |
|---|---|---|---|---|---|
| A1 | Ресурсно-ориентированный REST: существительные во множественном числе (`/documents`), действия выражены методами HTTP | Все пути | RPC-пути вида `/getDocuments`, GraphQL | 18 операций под `/api/v1`, все ложатся на CRUD; REST проще кэшировать, логировать и тестировать контрактно; GraphQL добавляет слой авторизации на поле без выгоды | S25, S26 |
| A2 | Мажорная версия в пути: `/api/v1/...` | Все пути, кроме `/healthz` | Версия в заголовке `Accept`, версия датой | Видна в логах и прокси, CDN не путает версии; ломающее изменение = `/v2` рядом, а не флаг | S23, S26 |
| A3 | Совместимые изменения без новой версии: новые поля, новые необязательные параметры, новые коды ошибок в каталоге | Эволюция v1 | Версия на каждое изменение | Клиент обязан игнорировать неизвестные поля (правило толерантного читателя) | S25 |
| A4 | JSON, `snake_case`, даты `YYYY-MM-DD`, моменты времени RFC 3339 в UTC с `Z` | Тела запросов и ответов | `camelCase`, Unix-время | Даты документа это календарная дата без зоны, момент загрузки это точка во времени: разные типы, разный формат | S25 |
| A5 | Идентификаторы UUIDv7 как непрозрачные строки | `id` всех ресурсов | Последовательные `bigint` | Не раскрывает объём архива и не перебирается (API1 BOLA), при этом монотонен по времени и хорошо ложится в btree | S27, S38 |
| A6 | Ошибки только `application/problem+json` с расширениями `code` и `errors[]` | Все ответы 4xx и 5xx | Своя обёртка `{error:{...}}` | Стандарт IETF, клиенты и прокси его понимают; `code` стабилен для кода, `title` готов для UI на русском | S16 |
| A7 | Персональные данные никогда не кэшируются промежуточными узлами: `Cache-Control: no-store` | Все ответы с документами, файлами, экспортом | `private, max-age` | Медицинские данные: копия в кэше браузера или прокси на общем компьютере это утечка | S17, S28 |
| A8 | Вебхуков в v1 нет | | Вебхук «документ добавлен» | Нет внешних потребителей событий; каждый исходящий вызов это новый канал утечки специальной категории ПДн (152-ФЗ ст. 10) и новая поверхность SSRF (API7). Появятся вместе с первым интегратором, с подписью HMAC и повторными попытками | S27, S41 |

## 2. Аутентификация, сессии, скоупы

| Решение | Что выбрано | Где | Отброшено | Почему | Источник |
|---|---|---|---|---|---|
| Модель для браузера | BFF: сессия в cookie `__Host-ma_sid`, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/` | Веб-клиент | JWT в `localStorage`, JWT в памяти + refresh в cookie | Токен в JS доступен любой XSS; BFF держит токены на сервере. Черновик IETF для браузерных приложений называет BFF самым защищённым вариантом | S31, S28 |
| Значение сессии | 256 бит из CSPRNG, в БД хранится только SHA-256 | `sessions.token_hash` | Подписанный JWT как сессия | Отзыв мгновенный (строка в БД), нет проблем с алгоритмом подписи и `alg=none` | S28, S30 |
| Время жизни | Простой 30 дней, абсолютный 180 дней, ротация идентификатора при входе по ключу | `sessions` | Бессрочная сессия | Без регистрации сессия и есть доступ к архиву; абсолютный срок ограничивает ущерб от украденной cookie | S28 |
| Ключ доступа | 24 символа Crockford Base32: 6 символов `lookup_id` + 18 символов секрета (90 бит), секрет хранится как Argon2id m=19 MiB, t=2, p=1 | Восстановление архива на другом устройстве | Пароль + email, magic link | Регистрация не требуется заданием; email это лишние ПДн и внешний провайдер рассылки. 90 бит при лимите 5 попыток в 15 минут на IP не перебираются | S51, S28 |
| CSRF | `SameSite=Lax` + обязательный заголовок `X-CSRF-Token` на `POST/PATCH/DELETE`; токен = HMAC-SHA256 серверным ключом от id сессии, без хранения, сравнение в постоянное время (ADR-047); значение из `GET /api/v1/session` и из ответов, создающих сессию | Все изменяющие запросы | Только SameSite; токен в таблице | Lax не закрывает GET-побочные эффекты и старые браузеры; второй слой дешёвый, HMAC меняется вместе с сессией | S28 |
| Скоупы | `documents:read`, `documents:write`, `exports:create`, `workspace:manage` | Проверка в зависимости FastAPI на каждый маршрут | Без скоупов | Сейчас сессия владельца получает все четыре. Скоупы нужны уже в v1, чтобы будущая ссылка «показать врачу» получила только `documents:read` без переписывания маршрутов (API5 BFLA) | S27, S50 |
| Нативные клиенты (после v1) | OAuth 2.0 Authorization Code + PKCE, access JWT 10 минут (`alg` из белого списка, `aud`, `iss`, `exp`), refresh с ротацией и детекцией повторного использования | Мобильное приложение | Долгий JWT | Контракт скоупов уже общий, меняется только транспорт | S30 |

## 3. Каталог ресурсов и операций

| Метод и путь | Назначение | Скоуп | Идемпотентность | Условные заголовки | Лимит |
|---|---|---|---|---|---|
| `POST /api/v1/workspaces` | Создать архив и сессию, принять согласие | нет | `Idempotency-Key` обязателен | | 10 в час на IP |
| `GET /api/v1/session` | Текущая сессия, CSRF-токен, скоупы | любая сессия | безопасный | | общий |
| `POST /api/v1/sessions` | Открыть архив по ключу доступа | нет | по природе | | 5 за 15 мин на IP |
| `DELETE /api/v1/sessions/current` | Выйти на этом устройстве | любая | по природе | | общий |
| `GET /api/v1/workspace` | Счётчики, объём, дата создания, версия согласия | `documents:read` | безопасный | `ETag` | общий |
| `POST /api/v1/workspace/access-key` | Выпустить новый ключ, старый отозвать | `workspace:manage` | `Idempotency-Key` | | 5 в час |
| `DELETE /api/v1/workspace` | Удалить архив целиком (отзыв согласия) | `workspace:manage` | по природе | `If-Match` | 1 в час |
| `GET /api/v1/document-types` | Справочник типов | любая | безопасный | `ETag`, `Cache-Control: public, max-age=3600` | общий |
| `POST /api/v1/uploads` | Получить presigned POST для PDF | `documents:write` | `Idempotency-Key` | | 30 в мин |
| `POST /api/v1/suggestions` | AI-подсказка полей по загруженному файлу; в прототипе выключена и отвечает 503 `ai_unavailable` (ADR-042) | `documents:write` | `Idempotency-Key` | | 10 в мин + очередь |
| `POST /api/v1/documents` | Создать документ из загрузки | `documents:write` | `Idempotency-Key` обязателен | | 30 в мин |
| `GET /api/v1/documents` | Список: поиск, фильтры, сортировка, курсор | `documents:read` | безопасный | | 120 в мин |
| `GET /api/v1/documents/{id}` | Карточка документа | `documents:read` | безопасный | `ETag`, `If-None-Match` | 120 в мин |
| `PATCH /api/v1/documents/{id}` | Изменить название, тип, дату, заметку | `documents:write` | по `If-Match` | `If-Match` обязателен | 60 в мин |
| `DELETE /api/v1/documents/{id}` | Удалить документ | `documents:write` | по природе | `If-Match` обязателен | 60 в мин |
| `GET /api/v1/documents/{id}/content` | PDF для просмотра или скачивания | `documents:read` | безопасный | `Range` | 120 в мин |
| `POST /api/v1/exports` | Собрать экспорт (весь архив, найденные, выбранные) | `exports:create` | `Idempotency-Key` обязателен | | 6 в мин |
| `GET /api/v1/exports/{id}/content` | Скачать ZIP потоком | `exports:create` | безопасный | | 6 в мин |
| `GET /healthz`, `GET /readyz` | Живость и готовность | нет | безопасный | | вне лимита |

Лимит «общий» = 300 запросов в минуту на сессию (`RateLimit-Policy: "general";q=300;w=60`).

Почему загрузка через presigned POST, а не multipart через API: файл до 20 МБ идёт напрямую в Object Storage, API не держит соединение и память под тело, а лимит размера проверяет само хранилище условием `content-length-range` (S45, S47). Почему документ создаётся отдельным вызовом после загрузки: проверка PDF, шифрование и запись метаданных выполняются атомарно в одной транзакции. У загрузки три срока: подпись presigned POST действует 15 минут (`expires_at` в ответе); строка `uploads` живёт 1 час, после этого `POST /api/v1/documents` с этим `upload_id` даёт 410 `upload_expired`; объект в бакете карантина удаляет правило жизненного цикла через 1 день.

Почему экспорт это ресурс, а не `GET /documents.zip?filter=...`: фиксируется состав (список `document_ids` на момент нажатия), повтор по `Idempotency-Key` не собирает архив дважды, ссылка живёт 1 час, а действие попадает в аудит (S25 о длительных операциях как ресурсах).

## 4. Список: пагинация, фильтры, сортировка

| Параметр | Тип и пример | Правило | Источник |
|---|---|---|---|
| `page_size` | 1 до 200, по умолчанию 50 | Больше 200 даёт 422 `validation_error`. Отступление от S21 (там максимум урезается): клиент не должен думать, что получил всё, когда получил 200 | S21 |
| `page_token` | непрозрачная строка | AES-GCM от `{list_key, uploaded_at, id, hash(q, type, date_field, from, to, undated, tz, order_by)}`; токен с другим значением любого из этих параметров, включая `order_by`, даёт 400 `invalid_page_token` | S21, S39 |
| `next_page_token` | строка или пустая строка | Пустая строка = страниц больше нет | S21 |
| `q` | `анализ` | Подстрока в названии без учёта регистра и «ё/е», по слепому триграммному индексу (07-database, раздел 5; ADR-046). Пустая строка или одни пробелы = без поиска; 1 или 2 непробельных символа = 422 `validation_error`; от 3 непробельных символов = поиск | S33 |
| `type` | `analysis,conclusion` | Список кодов через запятую, пусто = все | S22 |
| `date_field` | `document` или `uploaded` | По какой дате фильтровать | |
| `from`, `to` | `2026-04-01` | Включительно; `from > to` = 422 `date_range_invalid` | |
| `undated` | `true` | Только документы без даты документа (кнопка «Показать его»); `date_field`, `from` и `to` при этом игнорируются, `undated_excluded = 0` | |
| `tz` | `Europe/Moscow` | Граница суток для `date_field=uploaded`; по умолчанию зона из сессии | |
| `order_by` | `document_date desc` (по умолчанию) или `uploaded_at desc` | Синтаксис AIP-132; документы без даты всегда последние; тай-брейк по `uploaded_at` по возрастанию, затем `id` | S22 |

Ответ всегда содержит `total` (весь архив), `matched` (после фильтров) и `undated_excluded` (сколько документов без даты не вошло из-за фильтра по дате документа, при прочих совпадающих условиях). Это питает подпись «3 из 6» и подсказку про документ без даты в интерфейсе. Почему курсор, а не `offset`: offset на глубоких страницах читает и выбрасывает строки и даёт дубли при вставке; keyset по `(list_key, uploaded_at, id)` стоит O(page_size) независимо от глубины (S39, план Q1 в 07-database).

## 5. Идемпотентность

| Ситуация | Ответ | Источник |
|---|---|---|
| `Idempotency-Key` нет на операции, где он обязателен | 400 `idempotency_key_missing` | S19 |
| Ключ новый | Выполнить; при ответе 2xx сохранить статус, `resource_id`, SHA-256 отпечаток тела запроса и тело ответа, зашифрованное ключом пространства, на 24 часа (ADR-045). При 4xx и 5xx ключ не фиксируется, повтор выполняется заново | S19 |
| Ключ повторён, тело то же, первая попытка завершена | Тот же статус и тело, заголовок `Idempotent-Replayed: true` | S19 |
| Ключ повторён, тело другое | 422 `idempotency_key_reused` | S19 |
| Ключ повторён, первая попытка ещё выполняется | 409 `idempotency_in_progress` + `Retry-After: 1` | S19 |

Операции с ключом: `workspaces.create`, `workspace.rotateKey`, `uploads.create`, `suggestions.create`, `documents.create`, `exports.create`. Формат ключа: 16 до 64 символов, клиент генерирует UUIDv4 на одно намерение пользователя (одно нажатие «Сохранить в архив»), а не на HTTP-попытку. Область ключа: пространство + операция. Хранение: таблица `idempotency_keys`, первичный ключ `(workspace_id, key)`. Для `POST /api/v1/workspaces`, где пространства ещё нет, отдельная таблица `workspace_create_keys` с первичным ключом SHA-256 от ключа идемпотентности; повтор возвращает тот же архив и тот же `access_key`, но новую сессию (новые `Set-Cookie` и `csrf_token`), потому что токен первой сессии сервер не хранит.

## 6. Оптимистичная конкурентность

`GET /documents/{id}` возвращает `ETag: "v7"` (версия строки). `PATCH` и `DELETE` требуют `If-Match`.

| Ситуация | Ответ | Источник |
|---|---|---|
| Нет `If-Match` | 428 `precondition_required` | S18 |
| `If-Match` не совпал (документ изменили в другой вкладке) | 412 `version_conflict`, в теле текущий `etag` | S17, S24 |
| `If-None-Match` совпал на `GET` | 304 без тела | S17 |

Почему ETag, а не «последняя запись побеждает»: заметку можно править в двух вкладках; молчаливая перезапись теряет текст пользователя. Почему слабое сравнение не используется: версия строки однозначна, сильный ETag дешевле в проверке (S17, раздел 8.8.3).

## 7. Лимиты и обратное давление

Заголовки на каждом ответе лимитируемых маршрутов, то есть всех, кроме `/healthz` и `/readyz`, включая ответы с ошибкой (черновик IETF, S20):

```http
RateLimit-Policy: "burst";q=30;w=60, "daily";q=2000;w=86400
RateLimit: "burst";r=27;t=41
```

Лимит «общий» из таблицы раздела 3 = 300 запросов в минуту на сессию: `RateLimit-Policy: "general";q=300;w=60`. Вход по ключу: 5 попыток за 15 минут на IP; пятая неверная попытка ещё получает 401 `access_key_invalid`, шестая и следующие до конца окна получают 429 `rate_limited`.

При превышении 429 `rate_limited` и `Retry-After` в секундах (S18). Для AI-подсказки отдельная ограниченная очередь: глубина 20 задач на инстанс; при заполнении 429 `ai_busy` с `Retry-After`, а интерфейс сразу предлагает «Заполнить вручную» (05-architecture, раздел 7). Почему отказ, а не ожидание: очередь без верхней границы превращает всплеск в таймауты у всех пользователей; явный отказ с временем повтора честнее и не блокирует основной сценарий. Ключ лимита: сессия, для анонимных маршрутов IP (/64 для IPv6). Хранилище счётчиков: Redis, алгоритм GCRA.

## 8. Каталог ошибок

Тип ошибки: `urn:problem-type:medarchive:<code>`. `title` показывается в интерфейсе как есть, `detail` уточняет, `errors[]` указывает поля. Тот же каталог (code, HTTP, title) повторён в словаре текстов `docs/texts.md`; при правке меняются оба места.

| code | HTTP | title (для UI) | Когда | Действие клиента |
|---|---|---|---|---|
| `validation_error` | 422 | Проверьте выделенные поля | Поле не прошло схему | Подсветить поля из `errors[].pointer` |
| `title_required` | 422 | Введите название документа | Пустое название после trim | Фокус на поле |
| `title_too_long` | 422 | Название длиннее 200 символов | | Счётчик символов |
| `date_invalid` | 422 | Такой даты нет. Проверьте день и месяц | `2026-02-31` | Фокус на дату |
| `date_in_future` | 422 | Дата документа не может быть позже сегодняшней | Дата больше сегодня по зоне пользователя | |
| `date_range_invalid` | 422 | Начало периода позже конца | `from > to` | |
| `note_too_long` | 422 | Заметка длиннее 2000 символов | | |
| `type_unknown` | 422 | Выберите тип документа | Код вне справочника | |
| `not_pdf` | 415 | Файл не добавлен: это не PDF. Сохраните документ в PDF и попробуйте снова | Нет сигнатуры `%PDF-` | Вернуть к выбору файла |
| `file_too_large` | 413 | Файл больше 20 МБ. Сожмите PDF или разделите его на части | Отказ хранилища или проверка размера | |
| `pdf_unreadable` | 422 | Не удаётся открыть этот PDF. Возможно, он повреждён | pypdf не читает | |
| `pdf_encrypted` | 422 | PDF защищён паролем. Снимите пароль и загрузите снова | Зашифрованный PDF | |
| `upload_not_found` | 404 | Загрузка не найдена. Выберите файл ещё раз | Неизвестный или чужой `upload_id` | |
| `upload_expired` | 410 | Загрузка устарела. Выберите файл ещё раз | Старше 1 часа | |
| `upload_incomplete` | 409 | Файл ещё не загрузился до конца | Объекта нет в бакете | Повторить через 1 с |
| `not_found` | 404 | Документ не найден. Возможно, он удалён | Нет, удалён или чужой (не 403: не подтверждаем существование) | Вернуться к списку |
| `precondition_required` | 428 | Обновите страницу и повторите | Нет `If-Match` | Ошибка клиента, в UI не встречается |
| `version_conflict` | 412 | Документ изменился в другой вкладке. Обновите, чтобы увидеть новую версию | ETag устарел | Кнопка «Обновить» |
| `idempotency_key_missing` | 400 | Не получилось сохранить. Попробуйте ещё раз | | Ошибка клиента |
| `idempotency_key_reused` | 422 | Не получилось сохранить. Попробуйте ещё раз | Ключ с другим телом | Новый ключ |
| `idempotency_in_progress` | 409 | Сохраняем, подождите секунду | Двойной клик | Ждать `Retry-After` |
| `invalid_page_token` | 400 | Список обновился. Загружаем заново | Токен от других фильтров | Сбросить курсор |
| `unauthenticated` | 401 | Сессия закончилась. Откройте архив ключом доступа | Нет или истекла cookie | Экран ключа |
| `access_key_invalid` | 401 | Ключ не подошёл. Проверьте символы | Неверный ключ | Счётчик попыток не раскрываем |
| `csrf_failed` | 403 | Страница устарела. Обновите её | Нет или неверный `X-CSRF-Token` | Перезагрузка |
| `scope_insufficient` | 403 | Это действие недоступно по этой ссылке | Скоуп не выдан | |
| `consent_required` | 403 | Чтобы хранить медицинские документы, нужно ваше согласие | Нет действующего согласия | Экран согласия |
| `rate_limited` | 429 | Слишком много действий подряд. Повторите через N с | Лимит | Таймер из `Retry-After` |
| `ai_busy` | 429 | Подсказка сейчас занята. Заполните поля вручную или повторите через N с | Очередь полна | Ручной ввод |
| `ai_unavailable` | 503 | Подсказка недоступна. Заполните поля вручную | Флаг выключен или модель не ответила | Ручной ввод |
| `storage_unavailable` | 503 | Хранилище временно недоступно. Попробуйте через минуту | S3 или KMS недоступны | `Retry-After` |
| `internal` | 500 | Не получилось выполнить действие. Попробуйте ещё раз через минуту | Прочее | Показать `request_id` для поддержки |

Каждая ошибка содержит `request_id` (тот же в заголовке `X-Request-Id` и в логах), но никогда не содержит значений полей пользователя, имени файла и стека (API8, ASVS V16).

## 9. Примеры по каждой операции

Общие заголовки изменяющих запросов: `Cookie: __Host-ma_sid=...`, `X-CSRF-Token: ...`, `Content-Type: application/json`. Общие заголовки ответов: `X-Request-Id` на каждом ответе, `RateLimit` и `RateLimit-Policy` на каждом ответе лимитируемых маршрутов, `Idempotent-Replayed: true` только на повторе по `Idempotency-Key`. В примерах опущены.

### 9.1 Создать архив

```http
POST /api/v1/workspaces
Idempotency-Key: 0b8e1d3a-6d0e-4f53-9a43-2f1c7e5a9d10

{"consent": {"policy_version": "2026-11-10", "accepted": true}, "timezone": "Europe/Moscow"}
```
```http
201 Created
Set-Cookie: __Host-ma_sid=...; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=2592000
Cache-Control: no-store

{"workspace": {"id": "01930c6e-7b1a-7c2e-9f4e-3a5d2b1c0e9f", "created_at": "2026-11-10T16:00:02Z", "document_count": 0},
 "access_key": "7K3M-Q9TB-2XRA-HC4D-P8WN-6YFE",
 "csrf_token": "b9V4...", "scopes": ["documents:read","documents:write","exports:create","workspace:manage"]}
```
`access_key` показывается один раз; сервер хранит только Argon2id-хэш. Без `"accepted": true` ответ 422 `validation_error` (схема требует `const: true`), архив не создаётся. Код 403 `consent_required` остаётся для `POST /api/v1/documents`, если у архива нет действующего согласия. Текст политики версии `2026-11-10`: `docs/policy.md`.

### 9.2 Текущая сессия

```http
GET /api/v1/session
```
```json
{"workspace_id": "01930c6e-...", "csrf_token": "b9V4...", "scopes": ["documents:read","documents:write","exports:create","workspace:manage"],
 "idle_expires_at": "2026-12-10T16:00:02Z", "timezone": "Europe/Moscow"}
```
Без cookie: 401 `unauthenticated`.

### 9.3 Открыть архив по ключу

```http
POST /api/v1/sessions

{"access_key": "7K3M-Q9TB-2XRA-HC4D-P8WN-6YFE"}
```
```http
201 Created
Set-Cookie: __Host-ma_sid=...; Path=/; Secure; HttpOnly; SameSite=Lax

{"workspace_id": "01930c6e-...", "csrf_token": "Qm1x...", "scopes": [...]}
```
Ошибка: 401 `access_key_invalid` с одинаковым временем ответа для неизвестного `lookup_id` и неверного секрета (проверка Argon2id выполняется всегда).

### 9.4 Выйти

```http
DELETE /api/v1/sessions/current
```
`204 No Content`, `Set-Cookie: __Host-ma_sid=; Max-Age=0`.

### 9.5 Сводка архива

```http
GET /api/v1/workspace
```
```http
200 OK
ETag: "w3"

{"id": "01930c6e-...", "created_at": "2026-11-10T16:00:02Z", "document_count": 6, "total_bytes": 160768,
 "undated_count": 1, "consent": {"policy_version": "2026-11-10", "accepted_at": "2026-11-10T16:00:02Z"}}
```

### 9.6 Новый ключ доступа

```http
POST /api/v1/workspace/access-key
Idempotency-Key: 5a6f...
```
```json
201 {"access_key": "M2QF-8RZD-K4VT-1NXE-B7HC-0PAW", "revoked_previous": true}
```

### 9.7 Удалить архив

```http
DELETE /api/v1/workspace
If-Match: "w3"
```
```json
202 {"status": "scheduled", "purge_before": "2026-11-11T16:30:00Z"}
```
Сразу: сессии отозваны, данные скрыты политикой RLS, обёрнутые ключи пространства стёрты в БД (криптоудаление, ADR-041). До `purge_before`: физическое удаление строк и объектов.

### 9.8 Справочник типов

```http
GET /api/v1/document-types
```
```json
{"items": [{"code": "analysis", "title": "Анализ"}, {"code": "conclusion", "title": "Заключение"}, {"code": "other", "title": "Другое"}]}
```

### 9.9 Получить ссылку на загрузку

```http
POST /api/v1/uploads
Idempotency-Key: 3c2d...

{"original_name": "01-general-blood-test.pdf", "size_bytes": 79114, "content_type": "application/pdf"}
```
```json
201 {"upload_id": "01930c70-1f2a-7d3b-8c4d-5e6f7a8b9c0d",
     "url": "https://storage.yandexcloud.net/ma-quarantine",
     "fields": {"key": "q/01930c6e-.../01930c70-....bin", "Content-Type": "application/pdf",
                "policy": "eyJleHBpcmF0aW9uIjoi...", "x-amz-algorithm": "AWS4-HMAC-SHA256",
                "x-amz-credential": ".../ru-central1/s3/aws4_request", "x-amz-date": "20261110T160010Z", "x-amz-signature": "9f2c..."},
     "max_bytes": 20971520, "expires_at": "2026-11-10T16:15:10Z"}
```
Клиент отправляет `multipart/form-data` прямо в `url` с полями `fields` и файлом последним полем. Политика содержит `["content-length-range", 1, 20971520]` и точный `key`. `size_bytes` больше 20 МБ отклоняется сразу: 413 `file_too_large`, до передачи файла. `original_name` (1 до 255 символов) хранится зашифрованным и возвращается в `file.original_name` документа. Сроки: подпись 15 минут, строка загрузки 1 час (потом 410 `upload_expired`), объект в карантине 1 день.

### 9.10 AI-подсказка

```http
POST /api/v1/suggestions
Idempotency-Key: 77aa...

{"upload_id": "01930c70-..."}
```
```json
200 {"title": "Липидограмма", "type": "analysis", "document_date": "2026-05-21",
     "evidence": {"document_date": "Дата документа 21.05.2026"}, "source": "pdf_text_layer", "model": "yandexgpt-lite"}
```
Таймаут на стороне сервера 8 с; затем 503 `ai_unavailable`. Очередь полна: 429 `ai_busy`, `Retry-After: 12`. Поля без уверенности возвращаются как `null`. Перед отправкой в модель ФИО и дата рождения маскируются; ответ проверяется по JSON-схеме.

### 9.11 Создать документ

```http
POST /api/v1/documents
Idempotency-Key: 9b1f4c1e-5a0e-4a65-9a0b-6a2d1f0c3e11

{"upload_id": "01930c70-...", "title": "Общий анализ крови", "type": "analysis", "document_date": "2026-04-08", "note": null}
```
```http
201 Created
Location: /api/v1/documents/01930c71-2a3b-7c4d-9e5f-6a7b8c9d0e1f
ETag: "v1"

{"id": "01930c71-...", "title": "Общий анализ крови", "type": "analysis", "document_date": "2026-04-08",
 "uploaded_at": "2026-11-10T16:02:11Z", "updated_at": "2026-11-10T16:02:11Z", "note": null,
 "file": {"original_name": "01-general-blood-test.pdf", "size_bytes": 79114, "page_count": 1}, "version": 1}
```
Без даты: `"document_date": null`. Сервер проверяет сигнатуру `%PDF-`, открывает файл pypdf, считает страницы, шифрует потоково и переносит из карантина. Ошибки: 415 `not_pdf`, 422 `pdf_unreadable`, 422 `pdf_encrypted`, 404 `upload_not_found`, 410 `upload_expired`, 409 `upload_incomplete`.

### 9.12 Список

```http
GET /api/v1/documents?date_field=document&from=2026-04-01&to=2026-04-30&order_by=document_date%20desc&page_size=50
```
```json
200 {"items": [
  {"id": "...", "title": "Заключение терапевта", "type": "conclusion", "document_date": "2026-04-10", "uploaded_at": "2026-11-10T16:04:40Z", "has_note": true, "size_bytes": 78083, "version": 2},
  {"id": "...", "title": "Общий анализ крови", "type": "analysis", "document_date": "2026-04-08", "uploaded_at": "2026-11-10T16:02:11Z", "has_note": true, "size_bytes": 79114, "version": 3},
  {"id": "...", "title": "Биохимический анализ крови", "type": "analysis", "document_date": "2026-04-08", "uploaded_at": "2026-11-10T16:03:05Z", "has_note": false, "size_bytes": 78110, "version": 1}],
 "total": 6, "matched": 3, "undated_excluded": 1, "next_page_token": ""}
```
Два документа от 08.04.2026 идут в порядке добавления. Поиск: `GET /api/v1/documents?q=анализ` даёт `matched: 2` («Общий анализ крови», «Биохимический анализ крови»), `undated_excluded: 0`. Только без даты: `?undated=true` даёт «ЭКГ покоя». Заметка в списке не передаётся, только `has_note`: меньше расшифровок и меньше данных в ответе. `size_bytes` питает подпись строки «PDF · 79 КБ» (формат размера в `docs/texts.md`).

### 9.13 Карточка

```http
GET /api/v1/documents/01930c71-...
If-None-Match: "v3"
```
`304 Not Modified` или `200` с полным объектом, как в 9.11, и `ETag: "v4"`.

### 9.14 Изменить

```http
PATCH /api/v1/documents/01930c71-...
If-Match: "v3"

{"note": "Холестерин выше нормы, пересдать в октябре."}
```
```http
200 OK
ETag: "v4"

{"id": "01930c71-...", "note": "Холестерин выше нормы, пересдать в октябре.", "version": 4, "updated_at": "2026-11-10T16:20:31Z", ...}
```
Передаются только меняемые поля; `null` очищает `note` или `document_date`. Пустое тело: 422 `validation_error`. Устаревший ETag: 412 `version_conflict`.

### 9.15 Удалить документ

```http
DELETE /api/v1/documents/01930c71-...
If-Match: "v4"
```
`204 No Content`. Мягкое удаление сразу скрывает документ; физическое удаление файла и строки в течение 24 часов (07-database, раздел 8). Повтор: 404 `not_found`.

### 9.16 Файл документа

```http
GET /api/v1/documents/01930c71-.../content?disposition=inline
Range: bytes=0-65535
```
```http
206 Partial Content
Content-Type: application/pdf
Content-Range: bytes 0-65535/79114
Content-Disposition: inline; filename="2026-04-08_obshchiy-analiz-krovi.pdf"; filename*=UTF-8''2026-04-08_%D0%9E%D0%B1%D1%89%D0%B8%D0%B9...
Content-Security-Policy: sandbox
X-Content-Type-Options: nosniff
Cache-Control: no-store
Accept-Ranges: bytes
```
Файл расшифровывается потоком сегментами по 4 КБ (Tink Streaming AEAD, S52, ADR-047), поэтому presigned-ссылку на скачивание не выдаём: в хранилище лежит только шифртекст. В Python Tink 1.16.1 расшифровывающий поток не поддерживает `seek`, поэтому `Range` обслуживается последовательной расшифровкой с пропуском байтов до начала диапазона. `disposition=attachment` для кнопки «Скачать».

### 9.17 Экспорт

```http
POST /api/v1/exports
Idempotency-Key: e41b...

{"scope": "filtered", "filter": {"q": "анализ"}}
```
```json
201 {"id": "01930c80-...", "scope": "filtered", "document_count": 2, "total_bytes": 158230,
     "content_url": "/api/v1/exports/01930c80-.../content", "expires_at": "2026-11-10T17:31:00Z"}
```
`scope`: `all`, `filtered` (тот же объект фильтра, что у списка) или `selected` с `document_ids`. Пустой результат: 422 `validation_error` с `detail` «Нет документов для экспорта».

```http
GET /api/v1/exports/01930c80-.../content
```
`200`, `Content-Type: application/zip`, `Content-Disposition: attachment; filename="medarchive_2026-11-10.zip"`, тело потоком: папка `documents/` с PDF по имени `{YYYY-MM-DD|bez-daty}_{транслит названия}.pdf` (например `2026-04-08_obshchiy-analiz-krovi.pdf`), `documents.csv` (UTF-8 с BOM для Excel) и `documents.json`; файла `README.txt` нет. Правила транслитерации и имён: `docs/texts.md`, раздел «Экспорт».

### 9.18 Пример ошибки

```http
422 Unprocessable Content
Content-Type: application/problem+json

{"type": "urn:problem-type:medarchive:validation_error", "title": "Проверьте выделенные поля", "status": 422,
 "code": "validation_error", "request_id": "req_01930c9a",
 "errors": [{"pointer": "/document_date", "code": "date_invalid", "title": "Такой даты нет. Проверьте день и месяц"}]}
```

## 10. Соответствие OWASP API Security Top 10 (2023)

| Риск | Мера в контракте |
|---|---|
| API1 BOLA | Каждый запрос в контексте `workspace_id` из сессии, RLS в БД; чужой `id` даёт 404 |
| API2 Broken Authentication | Сессии в БД, Argon2id для ключа, лимит 5 попыток за 15 мин, ротация при входе |
| API3 BOPLA | Явные схемы ответа (Pydantic `response_model`), `additionalProperties: false` во входных схемах; `version`, `workspace_id` не принимаются от клиента |
| API4 Unrestricted Resource Consumption | Лимиты раздела 7, `page_size` до 200, файл до 20 МБ, заметка до 2000 символов, очередь AI с верхней границей |
| API5 BFLA | Скоупы на маршрутах, удаление архива только `workspace:manage` |
| API6 Sensitive Business Flows | Создание архивов 10 в час на IP, экспорт 6 в минуту |
| API7 SSRF | API не загружает ничего по URL от клиента; вебхуков нет |
| API8 Misconfiguration | `no-store`, `nosniff`, CSP `sandbox` на PDF, ошибки без стека; CORS на API не включён, браузер ходит через один origin (ADR-048) |
| API9 Inventory | Один публичный контракт `/api/v1`, OpenAPI в репозитории, старых версий нет |
| API10 Unsafe Consumption | Ответ LLM проверяется JSON-схемой и не исполняется; при ошибке подсказки нет |
