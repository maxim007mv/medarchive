# База данных: роли, функции, транзакции

Схема: миграции `apps/api/migrations` (`0001_init` из `07-data-model.sql`, `0002_privileges_functions` по ADR-044, ADR-045, ADR-047, `0003_workspace_timezone`: часовой пояс архива). Модели ORM: `app/db/models.py`, DDL они не создают.

## Роли

| Роль | Что может |
|---|---|
| `ma_owner` | Владелец базы и схемы `app`, только миграции (`docker compose run --rm migrate`). Член `ma_auth` с `SET`, без `INHERIT` |
| `ma_app` | API. Таблицы данных под RLS; в `sessions`, `access_keys`, `purge_queue`, `workspace_create_keys`, `audit_log` (кроме `INSERT`) прав нет, только через функции ниже |
| `ma_worker` | Очистка. Чтение и удаление под RLS, `purge_queue` целиком, две функции выборки |
| `ma_auth` | `NOLOGIN BYPASSRLS`, владелец функций входа и записи. Право `CREATE` на схему получает только внутри миграции |

## Транзакции

Любой запрос к данным архива идёт внутри `workspace_tx`: первым оператором транзакции ставятся `app.workspace_id`, `app.session_id`, `app.request_id` (`set_config(..., true)`, живут до конца транзакции).

```python
from app.db.engine import create_engine, create_sessionmaker
from app.db.transaction import workspace_tx

engine = create_engine(settings.database_url)  # пул 10, statement_timeout 5s
sessions = create_sessionmaker(engine)          # autobegin выключен

async with sessions() as session, workspace_tx(session, workspace_id, session_id=sid, request_id=rid):
    ...  # commit на выходе, rollback при исключении
```

Без архива в контексте (вход по ключу, `resolve_session`, `claim_workspace_create_key`) транзакция открывается явно: `async with session.begin():`. Запрос вне транзакции падает (`autobegin=False`). Связи моделей `lazy="raise"`: грузить через `selectinload` или `joinedload`.

## Функции

Все `SECURITY DEFINER`, `SET search_path = pg_catalog, pg_temp`, `EXECUTE` только одной роли. Архив берётся из `app.workspace_id`; без него функции записи падают с `42501` («app.workspace_id is not set»).

| Функция | Возвращает | Кто | Что делает |
|---|---|---|---|
| `app.resolve_session(p_token_sha256 bytea)` | `TABLE(session_id uuid, workspace_id uuid)` | ma_app | Живая сессия неудалённого архива, без контекста |
| `app.find_access_key(p_lookup_id text)` | `TABLE(access_key_id uuid, workspace_id uuid, secret_hash text)` | ma_app | Активный ключ неудалённого архива, без контекста |
| `app.create_workspace(p_dek_ciphertext bytea, p_kek_key_id text, p_policy_version text, p_evidence_sha256 bytea, p_timezone text DEFAULT NULL)` | `timestamptz` (`created_at`) | ma_app | Строки `workspaces` (id = контекст, `timezone` = IANA-имя или `NULL`) и `consents`; вызов с четырьмя аргументами работает |
| `app.create_session(p_token_sha256 bytea, p_idle_ttl interval, p_absolute_ttl interval)` | `TABLE(session_id uuid, idle_expires_at timestamptz, absolute_expires_at timestamptz)` | ma_app | Новая сессия; 0 строк, если архив удалён |
| `app.touch_session(p_session_id uuid, p_idle_ttl interval)` | `timestamptz` или `NULL` | ma_app | Продлевает простой, не дальше абсолютного срока; `NULL` для чужой, отозванной, истёкшей |
| `app.revoke_sessions(p_session_id uuid DEFAULT NULL)` | `integer` | ma_app | Отзывает одну сессию или, без аргумента, все сессии архива |
| `app.issue_access_key(p_lookup_id text, p_secret_hash text)` | `TABLE(access_key_id uuid, revoked_previous boolean)` | ma_app | Отзыв активного ключа и выпуск нового под блокировкой архива; 0 строк, если архив удалён; совпадение `lookup_id` даёт `23505`, повторить запрос с новым ключом |
| `app.revoke_access_key()` | `boolean` | ma_app | Отзывает активный ключ |
| `app.delete_workspace()` | `timestamptz` (`purge_after`) или `NULL`, если уже удалён | ma_app | `deleted_at`, `purge_after = now() + 24 ч`, `dek_ciphertext = NULL`, отзыв сессий, ключа и согласия |
| `app.soft_delete_document(p_document_id uuid)` | `boolean` | ma_app | `deleted_at = now()` живого документа архива. Проверку `If-Match` делает вызывающий под `SELECT ... FOR UPDATE` в той же транзакции |
| `app.enqueue_purge(p_object_key text, p_reason text)` | `void` | ma_app | Только `ws/{архив}/{uuid}.bin` и `q/{архив}/{uuid}.bin`, повтор не ошибка |
| `app.claim_workspace_create_key(p_key_sha256 bytea, p_fingerprint bytea)` | `TABLE(is_new boolean, state text, fingerprint bytea, response_status smallint, workspace_id uuid, response_body_ct bytea)` | ma_app | Ключ идемпотентности `POST /workspaces`, без контекста; истёкший ключ заменяется |
| `app.complete_workspace_create_key(p_key_sha256 bytea, p_response_status integer, p_response_body_ct bytea)` | `boolean` | ma_app | Под контекстом созданного архива: сохраняет статус и тело |
| `app.release_workspace_create_key(p_key_sha256 bytea)` | `boolean` | ma_app | Удаляет строку `in_progress` после ответа 4xx или 5xx |
| `app.workspaces_due_for_purge(p_limit integer)` | `TABLE(workspace_id uuid)` | ma_worker | Архивы, где есть что чистить: удалённые документы старше 24 ч, архив после `purge_after`, просроченные загрузки, экспорты, ключи идемпотентности. Не больше 500 |
| `app.purge_expired_workspace_create_keys(p_limit integer)` | `integer` | ma_worker | Удаляет просроченные ключи `POST /workspaces`, не больше 500 |
| `app.ensure_audit_partitions()` | `integer` (создано секций) | ma_worker | Секции `audit_log_YYYY_MM` (UTC) на текущий и два следующих месяца. Владелец `ma_owner`, без `BYPASSRLS` |

Воркер удаляет сам под RLS: для каждого архива из `workspaces_due_for_purge` открывает `workspace_tx` и выполняет `DELETE` своими правами; каскады от `workspaces` удаляют сессии, ключи, согласия.

## Идемпотентность

- `idempotency_keys` (операции `documents.create`, `exports.create`, `suggestions.create`, `uploads.create`, `workspace.rotateKey`): `ma_app` пишет сам под RLS. Захват ключа двумя операторами, в режиме `READ COMMITTED` второй видит строку, которую параллельная транзакция зафиксировала, пока первый ждал:
  `INSERT ... ON CONFLICT (workspace_id, key) DO NOTHING RETURNING state`, затем, если строк нет, `SELECT ... WHERE workspace_id = app.current_workspace() AND key = $1`. Тело ответа хранится в `response_body_ct` (только при `state = 'completed'`). Заголовки `Location` и `ETag` повтора выводятся из тела, отдельной колонки для них нет. `in_progress` после ответа 4xx или 5xx удаляется `DELETE` (право выдано в 0002).
- `POST /workspaces`: таблица `workspace_create_keys` без политик и без прав для приложения, только функции выше. Ключ хранится как SHA-256.

## Решения, которые не видны из DDL

- Часовой пояс архива `workspaces.timezone` (0003): IANA-имя, CHECK только на длину 1..64, проверку по базе зон делает API. Для `GET /session` `ma_app` читает его обычным `SELECT timezone FROM app.workspaces` внутри `workspace_tx`; `NULL` у архивов без пояса, подставлять пояс по умолчанию приложению.
- Абсолютный срок сессии 180 дней, простой 30 дней (ADR-047): значения передаёт приложение в `create_session` и `touch_session`; БД гарантирует только `idle_expires_at <= absolute_expires_at`.
- `dek_ciphertext` остаётся `BETWEEN 32 AND 1024`: связка трёх keyset под KEK занимает 390 байт (ADR-047). `NULL` разрешён только у удалённого архива.
- Поиск Q4: `title_bidx @>` под `ma_app` стоит в `Filter`, а не в `Index Cond` (ADR-046). Проверено ещё раз на 18: под суперпользователем условие в `Index Cond`, под `ma_app` в `Filter` и с явными `uuid_ops`/`array_ops`, и с отдельным `gin (title_bidx)`.
- Фильтр по дате загрузки (Q5) строить как в 07-database, раздел 4: `uploaded_at >= CAST(:from AS date)::timestamp AT TIME ZONE 'Europe/Moscow'`. Выбор между `Index Scan` и `Bitmap Heap Scan + Sort` зависит от физического порядка строк (корреляция `workspace_id`), оба варианта укладываются в бюджет.
- Мягкое удаление документа только через `soft_delete_document`: политика `hide_deleted` требует, чтобы новая строка `UPDATE` оставалась видимой, и обычный `UPDATE ... SET deleted_at` от `ma_app` отклоняется.

## Тесты

`apps/api/tests/db`: PostgreSQL 17 и 18 в Testcontainers, роли создаёт настоящий `infra/postgres/init/01-roles.sh`. Запуск: `cd apps/api && uv run pytest tests/db`. На Docker Desktop для macOS добавить `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` (или `TESTCONTAINERS_RYUK_DISABLED=true`, если Ryuk не стартует). Планы Q1..Q7 сидят 210 000 документов, около 50 с на версию.
