# 07. База данных (RFC-002)

Статус: принято. Схема: `07-data-model.sql` (проверена на PostgreSQL 18.6, совместима с 17). Нагрузочные данные: `db/seed-load.sql`. Планы запросов: `db/explain-queries.sql` и фактический вывод `db/explain-analyze.txt`. Источники обозначены S-номерами из `02-research-sources.md`.

## 1. Требования, из которых выведена схема

| # | Требование | Откуда | Решение в схеме |
|---|---|---|---|
| D1 | Медицинские документы = специальная категория ПДн | 152-ФЗ ст. 10 ч. 1 (S41) | Шифрование полей и файлов, RLS, аудит, согласие в отдельной таблице |
| D2 | Обработка только при письменном согласии субъекта | 152-ФЗ ст. 10 ч. 2 п. 1 (S41) | Таблица `consents`, без активного согласия запись документов запрещена на уровне API |
| D3 | БД с данными граждан РФ находится в РФ | 152-ФЗ ст. 18 ч. 5 (S42) | Только Yandex Managed PostgreSQL и Object Storage в регионе ru-central1; реплик за рубежом нет |
| D4 | Уровень защищённости ИСПДн | ПП РФ № 1119 п. 10 е, п. 11 в (S43) | Спецкатегории, угрозы 3-го типа: до 100 000 субъектов УЗ-3, свыше УЗ-2. Проектируем сразу под УЗ-2 |
| D5 | Чужой документ недоступен даже при ошибке в коде | OWASP API1:2023 BOLA (S27) | RLS с `FORCE`, политика по `workspace_id`, составные FK |
| D6 | Удалённый документ не возвращается | Задание R6 | Мягкое удаление + RESTRICTIVE-политика + физическое удаление и уничтожение ключа файла за 24 часа |
| D7 | Список и фильтры быстрые на любом объёме | NFR p95 < 300 мс (RFC-001) | Частичные индексы под каждый запрос, keyset-пагинация (S21, S39), бюджет БД p95 < 10 мс |

## 2. ERD

```mermaid
erDiagram
  workspaces ||--o{ consents : "согласия"
  workspaces ||--o{ sessions : "сессии"
  workspaces ||--o| access_keys : "активный ключ"
  workspaces ||--o{ uploads : "загрузки"
  workspaces ||--o{ documents : "документы"
  workspaces ||--o{ exports : "экспорты"
  workspaces ||--o{ idempotency_keys : "ключи идемпотентности"
  workspaces ||--o{ audit_log : "аудит"
  document_types ||--o{ documents : "тип"
  documents ||--|| document_files : "файл"

  workspaces { uuid id PK
    bytea dek_ciphertext "Tink keyset под KEK"
    bytea bidx_key_ciphertext
    text kek_key_id
    timestamptz deleted_at
    timestamptz purge_after }
  consents { uuid id PK
    uuid workspace_id FK
    text policy_version
    timestamptz accepted_at
    bytea evidence_sha256
    timestamptz withdrawn_at }
  sessions { uuid id PK
    uuid workspace_id FK
    bytea token_sha256 UK
    timestamptz idle_expires_at
    timestamptz absolute_expires_at
    timestamptz revoked_at }
  access_keys { uuid id PK
    uuid workspace_id FK
    char lookup_id UK
    text secret_hash "argon2id"
    timestamptz revoked_at }
  uploads { uuid id PK
    uuid workspace_id FK
    text quarantine_key UK
    int max_bytes
    text status
    timestamptz expires_at }
  documents { uuid id PK "UUIDv7"
    uuid workspace_id FK
    text type_code FK
    bytea title_ct "AES-256-GCM"
    bigint_arr title_bidx "слепой индекс"
    bytea note_ct
    date document_date "NULL = не указана"
    timestamptz uploaded_at "только сервер"
    int version "ETag"
    int list_key "сортировка"
    timestamptz deleted_at }
  document_files { uuid document_id PK
    uuid workspace_id FK
    text object_key UK
    int size_bytes
    bytea sha256
    smallint page_count
    bytea original_name_ct }
  document_types { text code PK
    text title_ru
    smallint sort_order }
  exports { uuid id PK
    uuid workspace_id FK
    text scope
    jsonb filter
    uuid_arr document_ids
    timestamptz expires_at }
  idempotency_keys { uuid workspace_id PK
    text key PK
    text operation
    bytea fingerprint
    text state }
  audit_log { bigint id PK
    timestamptz occurred_at PK
    uuid workspace_id
    text action
    uuid entity_id
    text_arr changed_fields }
```

Нормализация: 3НФ. Справочник типов вынесен в таблицу (новый тип = `INSERT`, а не `ALTER TYPE`). Файл вынесен в `document_files` (1:1), потому что у документа и файла разные жизненные циклы: файл проверяется до создания документа, удаляется асинхронно. Денормализация одна и осознанная: `workspace_id` в `document_files` дублируется ради составного FK `(workspace_id, document_id)`, который делает невозможной ссылку файла на документ другого пространства (D5).

## 3. Ограничения целостности

| Таблица | Ограничение | Что ловит |
|---|---|---|
| documents | `documents_date_not_future`: `document_date <= uploaded_at::date + 1` | Дату из будущего (запас 1 день на часовые пояса) |
| documents | `document_date >= 1900-01-01` | Опечатку «0202» вместо «2020» |
| documents | `octet_length(title_ct) BETWEEN 29 AND 1024` | Пустое название (шифртекст GCM = 12 nonce + 16 tag + данные) |
| documents | `cardinality(title_bidx) BETWEEN 1 AND 256` | Документ, который не найдётся поиском |
| documents | триггер `bump_version`: `uploaded_at` неизменяема | Требование «дата загрузки фиксируется отдельно» нельзя нарушить даже SQL-запросом |
| document_files | `size_bytes BETWEEN 1 AND 20971520`, `content_type = 'application/pdf'`, `octet_length(sha256) = 32` | Файл вне лимита или не PDF |
| document_files | составной FK `(workspace_id, document_id)` → `documents(workspace_id, id)` | Связь между пространствами |
| uploads | `(status = 'rejected') = (reject_code IS NOT NULL)` | Отказ без причины |
| sessions | `idle_expires_at <= absolute_expires_at` | Сессию, которая живёт дольше абсолютного срока |
| access_keys | частичный UNIQUE `(workspace_id) WHERE revoked_at IS NULL` | Два активных ключа |
| consents | частичный UNIQUE `(workspace_id) WHERE withdrawn_at IS NULL` | Два активных согласия |
| idempotency_keys | PK `(workspace_id, key)` | Ключ одного клиента не находит запись другого (S19, раздел 5: составной ключ поиска) |
| workspaces | `(deleted_at IS NULL) = (purge_after IS NULL)` | Удалённое пространство без срока уничтожения |

Все проверки дублируются в API (pydantic) ради понятного текста ошибки, но источник истины база: ошибка в коде не запишет мусор.

## 4. Индексы и фактические планы

Стенд: PostgreSQL 18.6, 2001 пространство, 210 000 документов (одно «тяжёлое» пространство на 10 000, остальные по 100), 3% удалены, после `VACUUM ANALYZE`. Все запросы выполнены ролью `ma_app` под RLS. Полный вывод в `db/explain-analyze.txt`.

| Запрос | Индекс | План | Время |
|---|---|---|---|
| Q1 Первая страница, 51 строка, 10 000 документов | `documents_list (workspace_id, list_key, uploaded_at, id) INCLUDE (type_code, document_date) WHERE deleted_at IS NULL` | Index Scan, без сортировки | 0,117 мс |
| Q2 Следующая страница по курсору | тот же | Index Scan, `ROW(list_key, uploaded_at, id) > ROW(...)` в Index Cond | 0,088 мс |
| Q3 Период по дате документа + `matched` + `undated_excluded` | тот же | Index Only Scan, счётчики одним проходом через `count(*) FILTER` | 2,40 мс |
| Q4 Поиск «анализ» (15% документов совпадают) | `documents_title_bidx USING gin (workspace_id, title_bidx)` (btree_gin) | Bitmap Index Scan + top-N heapsort | 5,84 мс |
| Q5 Период по дате загрузки в Europe/Moscow | `documents_by_upload (workspace_id, uploaded_at, id)` | Index Scan, границы суток в Index Cond | 0,072 мс |
| Q6 Только без даты | `documents_list` (`list_key = 2147483647`) | Index Only Scan | 0,033 мс |
| Q7 Обычное пространство, 100 документов | `documents_list` | Index Scan | 0,059 мс |

Решения, которые дали эти цифры:
1. **`list_key` вместо `ORDER BY document_date DESC NULLS LAST, uploaded_at ASC`.** Смешанные направления сортировки не позволяют сравнивать кортеж курсора одним условием: первый вариант схемы давал `Filter` и `Rows Removed by Filter: 2496` на второй странице (2,07 мс). Генерируемая колонка `list_key = 1900-01-01 - document_date` (без даты = `INT_MAX`) переводит всю сортировку в ASC, и курсор становится `Index Cond` (0,088 мс, в 23 раза быстрее). Это и есть keyset-пагинация (S39): стоимость страницы не растёт с её номером, в отличие от `OFFSET`.
2. **Частичные индексы `WHERE deleted_at IS NULL`** (S34): удалённые строки не занимают место в индексах списка и не попадают в планы.
3. **Фильтр по дате загрузки** переводится в полуинтервал `[from 00:00 МСК, to + 1 день 00:00 МСК)` на стороне SQL через `AT TIME ZONE`. Колонка `timestamptz` не оборачивается функцией, поэтому индекс работает (Q5).
4. **`INCLUDE (type_code, document_date)`** даёт Index Only Scan для счётчиков и списка без даты.
5. **GIN по `(workspace_id, title_bidx)`** через `btree_gin`: индекс сразу ограничен пространством. С литералом массива (так передаёт приложение) условие `title_bidx @> ...` уходит в Index Cond, совпадения точные, ложных срабатываний 0 из 1457.

Бюджет: запрос к БД p95 ≤ 10 мс на пространство до 10 000 документов; CI прогоняет `db/explain-queries.sql` на сид-данных и падает, если в плане Q1, Q2, Q5, Q6 появился `Seq Scan` или `Sort` (проверка `EXPLAIN (FORMAT JSON)`, S37).

## 5. Поиск по зашифрованному названию: слепой индекс триграмм

Проблема: название документа («Заключение онколога») само по себе медицинская информация, его нужно шифровать. Но `pg_trgm` (S33) работает только с открытым текстом, а функции `pgcrypto` выполняются внутри сервера, и данные с ключами идут между приложением и БД в открытом виде (S35, раздел «Security Limitations»). Значит, шифровать в БД через `pgcrypto` нельзя: ключ окажется в логах запросов и в `pg_stat_statements`.

Решение:
1. Приложение нормализует название (`lower`, `ё → е`, схлопывание пробелов) и режет на триграммы по правилам `pg_trgm` (слово дополняется двумя пробелами слева и одним справа).
2. Каждая триграмма превращается в `HMAC-SHA256(ключ_пространства, триграмма)`, берутся первые 8 байт → `bigint`. Массив пишется в `title_bidx`.
3. Поиск «анализ» → те же триграммы и HMAC → `title_bidx @> ARRAY[...]`. Совпадения по всем триграммам дают кандидатов; приложение расшифровывает названия кандидатов и делает финальную проверку подстроки (защита от коллизий 64-битного HMAC, вероятность около 2^-64 на пару).
4. Ключ слепого индекса свой у каждого пространства, поэтому одинаковые названия в разных архивах дают разные хэши: нельзя сопоставить архивы между собой.

Что раскрывается: число триграмм и частота повторов внутри одного архива. Это осознанный компромисс; альтернатива (расшифровывать все названия архива на каждый запрос) работает до примерно 2000 документов и ломает пагинацию на стороне БД.

## 6. Шифрование

| Данные | Где | Как | Ключ |
|---|---|---|---|
| `title_ct`, `note_ct`, `original_name_ct` | PostgreSQL | AES-256-GCM (Tink AEAD), AAD = `document_id` (шифртекст нельзя переставить в другую строку) | DEK пространства |
| PDF-файлы | Object Storage | Tink Streaming AEAD AES256_GCM_HKDF_4KB, AAD = `document_id` | DEK пространства |
| DEK пространства | `workspaces.dek_ciphertext` | Конвертное шифрование: DEK зашифрован KEK в Yandex KMS (S44) | KEK в KMS, ротация раз в год |
| Диски БД, бакет, бэкапы | Yandex Cloud | Шифрование на стороне сервиса | Управляемые ключи |

Почему конверт, а не KMS на каждое поле: у прямого `encrypt` в Yandex KMS лимит 32 КБ и сетевой вызов на каждую операцию (S44). DEK расшифровывается один раз на запрос, держится в памяти процесса не дольше запроса и не пишется на диск (S44: «Открытый DEK должен расшифровываться только на время шифрования или расшифрования данных»).

**Крипто-удаление.** Удаление пространства = удаление `dek_ciphertext`. Все копии полей и файлов, включая лежащие в бэкапах до истечения их срока, становятся нечитаемыми сразу, а не через 30 дней.

## 7. Row-Level Security

1. Роли: `ma_owner` (владелец схемы, только миграции), `ma_app` (API, `NOBYPASSRLS`), `ma_worker` (фоновые задачи, `NOBYPASSRLS`), `ma_auth` (`NOLOGIN BYPASSRLS`, владеет только двумя функциями входа).
2. На всех таблицах с данными `ENABLE` и `FORCE ROW LEVEL SECURITY`. Без политики действует запрет по умолчанию (S32: «If no policy exists for the table, a default-deny policy is used»), `FORCE` распространяет политики и на владельца.
3. Контекст: в начале каждой транзакции API выполняет `SELECT set_config('app.workspace_id', $1, true)` (третий аргумент `true` = до конца транзакции). Это безопасно с PgBouncer в режиме transaction pooling: значение не переживает транзакцию и не утечёт следующему клиенту соединения.
4. Политика `ws_isolation`: `workspace_id = app.current_workspace()` для чтения и `WITH CHECK` для записи.
5. Политика `hide_deleted` (RESTRICTIVE, SELECT): удалённые документы невидимы приложению даже по прямому условию.
6. Код всё равно передаёт `workspace_id = $1` явно: это даёт планировщику точную селективность (в планах видно `Index Cond` по литералу), а RLS остаётся второй линией защиты.
7. Таблицы `sessions` и `access_keys` приложению недоступны вовсе. Вход идёт только через `app.resolve_session(token_sha256)` и `app.find_access_key(lookup_id)` (`SECURITY DEFINER`, владелец `ma_auth`, `search_path` зафиксирован).

Проверено на стенде (вывод в `db/explain-analyze.txt`, Q8 до Q11): чужое пространство при чужом контексте 0 строк; без контекста 0 строк; удалённые 0 строк; вставка в чужое пространство: `ERROR: new row violates row-level security policy`.

## 8. Мягкое удаление, сроки хранения, уничтожение

| Объект | Событие | Что происходит | Срок |
|---|---|---|---|
| Документ | `DELETE /v1/documents/{id}` | `deleted_at = now()`, строка невидима (RLS), объект файла ставится в `purge_queue` | Сразу |
| Документ | Задача `purge_documents` | Физический `DELETE` строки и файла, запись `document.purge` в аудит | ≤ 24 часа |
| Пространство | `DELETE /v1/workspace` или отзыв согласия | `deleted_at`, `purge_after = now() + 24 h`, все сессии отзываются; DEK удаляется | ≤ 24 часа |
| Загрузка | Не подтверждена документом | Объект в карантинном бакете удаляется правилом жизненного цикла | 24 часа |
| Ключ идемпотентности | | Удаление | 24 часа |
| Экспорт | | Ссылка недействительна | 1 час |
| Сессия | Нет активности | Недействительна | 30 дней простоя, 400 дней абсолютный срок (S28: idle и absolute timeout) |
| Журнал аудита | | Удаление секции целиком (`DROP TABLE audit_log_YYYY_MM`) | 12 месяцев |
| Бэкапы БД | | Автоматическая ротация | 7 дней PITR (по умолчанию в сервисе, S46) |

Основание сроков: 152-ФЗ, ст. 5 ч. 7: хранение ПДн «не дольше, чем этого требуют цели обработки» (S48). Сроки выбраны как минимально достаточные для работы сервиса. Мягкое удаление нужно не для «корзины», а для атомарности: строка исчезает из выдачи в той же транзакции, где проверены права, а медленное удаление файла не держит транзакцию.

## 9. Журнал аудита
1. Append-only: `UPDATE` и `DELETE` не выданы ни одной роли приложения.
2. Без содержимого: только действие, id сущности, **имена** изменённых полей, `request_id`, префикс IP (/24 для IPv4, /48 для IPv6).
3. Пишется триггером `audit_documents` в той же транзакции, что и изменение: не бывает изменения без записи.
4. Секционирование по месяцам (`PARTITION BY RANGE (occurred_at)`), задача `pg_partman` или cron создаёт секцию на 2 месяца вперёд; секция `DEFAULT` ловит всё остальное и мониторится (не должна расти).

## 10. Миграции

1. Alembic, по одной ревизии на изменение, только вперёд; `downgrade` пишется, но в проде не выполняется: откат = новая миграция.
2. Схема «расширить, затем сузить» (expand/contract): новая колонка добавляется nullable, код пишет в обе, бэкфилл батчами по 1000 строк, затем `NOT NULL` через `ADD CONSTRAINT ... NOT VALID` и `VALIDATE CONSTRAINT` (не блокирует запись).
3. Индексы в проде только `CREATE INDEX CONCURRENTLY` (отдельная миграция без транзакции).
4. `lock_timeout = '3s'` и `statement_timeout = '60s'` в каждой миграции: миграция падает, а не вешает прод.
5. CI: `alembic upgrade head` на пустой базе, затем на копии сид-данных, затем `EXPLAIN`-проверка из раздела 4.

## 11. Резервное копирование и восстановление
1. Yandex Managed PostgreSQL: PITR включён по умолчанию, восстановление на любой момент после самой старой полной копии, только в новый кластер; срок хранения автоматических копий 7 дней по умолчанию, настраивается 7 до 60 (S46). Механизм тот же, что в PostgreSQL: базовая копия + архив WAL (S36).
2. RPO ≤ 5 минут (архивирование WAL), RTO ≤ 1 час (восстановление в новый кластер + переключение DNS-имени).
3. Учение раз в месяц: восстановление в новый кластер на момент «вчера 12:00», прогон `SELECT count(*)` по таблицам и расшифровка 10 случайных документов. Без расшифровки учение не засчитывается: бэкап без ключей бесполезен.
4. Бакет: версионирование 7 дней (защита от ошибочного удаления до задачи purge).

## 12. Производительность приложения поверх БД
1. **N+1:** документы и файлы читаются одним `JOIN` (1:1); для коллекций `selectinload`, а в тестах `raiseload("*")`, чтобы ленивую загрузку было невозможно допустить незаметно (S40).
2. Пул соединений: `asyncpg` с пулом 10 на процесс + PgBouncer (transaction mode) перед кластером.
3. Подготовленные запросы: включены в asyncpg; с PgBouncer 1.21+ поддерживаются в transaction mode (`max_prepared_statements`).
4. Кэш: ПДн не кэшируются ни в Redis, ни в CDN. Кэшируется только справочник типов (в памяти процесса) и расшифрованный DEK в пределах запроса.
5. Счётчики `total`, `matched`, `undated_excluded` считаются одним запросом (Q3), не тремя.
