# База данных: DB-01..DB-09, DB-12 (блок 2, плюс планы блока 5)

Статус: готово. Агент DATABASE, 10.11.2026. Как пользоваться: `docs/db.md`.

## Что сделано

| Задача | Результат |
|---|---|
| DB-01 | `apps/api/alembic.ini`, `migrations/env.py` (asyncpg, `lock_timeout 3s`, `statement_timeout 60s`, таблица версий в `public`), ревизия `0001_init` из `07-data-model.sql`: явная схема `app`, расширения `WITH SCHEMA public`, справочник типов |
| DB-02 | Ревизия `0002_privileges_functions`: 17 функций `SECURITY DEFINER` (16 у `ma_auth`, `ensure_audit_partitions` у `ma_owner`), у каждой одна вызывающая роль; права `ma_auth` на таблицы |
| DB-03 | RLS с `FORCE` из DDL, тесты перекрёстного доступа |
| DB-04 | `app/db/transaction.py`: `workspace_tx(session, workspace_id, *, session_id, request_id)` |
| DB-05, DB-06 | Планы Q1..Q7 под `ma_app` на 210 000 документах совпадают с `db/explain-analyze.txt` по типам узлов на 17 и 18 |
| DB-07 | CHECK операций, `response_body_ct`, таблица `workspace_create_keys` (ADR-045) |
| DB-08 | Секции аудита: функция `app.ensure_audit_partitions()` (текущий месяц и два вперёд, UTC), вызывается миграцией и воркером; у секций нет прав ни у одной роли |
| DB-09 | `app.workspaces_due_for_purge(limit)` и `app.purge_expired_workspace_create_keys(limit)`, лимит 500 |
| DB-12 | `app/db/engine.py`: пул 10 без overflow, `statement_timeout 5s`, `autobegin=False`; `app/db/models.py`: типизированные модели всех 13 таблиц, связи `lazy="raise"` |

### Дополнение: 0003_workspace_timezone (по запросу BACKEND-CORE)

`workspaces.timezone text NULL` с CHECK длины 1..64; `app.create_workspace(bytea, text, text, bytea, text DEFAULT NULL)` вместо четырёхаргументной (пересоздана от `ma_auth`, вызовы с четырьмя аргументами работают, возвращает `timestamptz`). Откат возвращает прежнюю функцию и удаляет колонку. Тесты: цикл upgrade, downgrade, upgrade через 0003; пояс сохраняется и читается `ma_app` под RLS; без аргумента `NULL`; пустая строка отклоняется CHECK. `pytest tests/db` без планов: 162 passed (81 на 17 и 81 на 18).

## Отклонения от задания

1. **Q4 не переведён в `Index Cond`.** Задание просило `title_bidx @>` в `Index Cond`, ADR-046 (источник истины) фиксирует `Filter`. Проверил сам на PostgreSQL 18: под суперпользователем условие в `Index Cond`; под `ma_app` при `FORCE ROW LEVEL SECURITY` остаётся в `Filter` и с явными `public.uuid_ops`/`pg_catalog.array_ops`, и с отдельным `gin (title_bidx)`, потому что `arraycontains` не `LEAKPROOF`. Тест проверяет план ADR-046: `workspace_id` в `Index Cond`, `@>` в `Filter`. Время 7,4 мс при бюджете 10 мс.
2. **`dek_ciphertext` CHECK остался 1024**, а не 4096: ADR-047 мерил связку (390 байт) и прямо оставляет CHECK. `NULL` разрешён только у удалённого архива, `bidx_key_ciphertext` удалён.
3. **Таблица для `POST /workspaces` называется `workspace_create_keys`** (ADR-045), а не `pre_workspace_idempotency`; ключ хранится как SHA-256; доступ только через функции. Колонки `response_headers` нет: `Location` и `ETag` повтора выводятся из тела. `workspaces.create` в CHECK `idempotency_keys` не добавлен, у этой операции своя таблица.
4. **Найдены и исправлены дефекты эталонной схемы** (спецификацию `MedArchive/**` не трогал, нужна запись спецагента):
   - триггер `audit_documents` дописывал имена полей как `f || 'title'`; литерал разбирается как `text[]`, и **любое изменение документа падало** с `malformed array literal`. В `0001` заменено на `array_append`;
   - политика `hide_deleted` (RESTRICTIVE, SELECT) требует, чтобы новая строка `UPDATE` осталась видимой, поэтому мягкое удаление от `ma_app` отклоняется (`new row violates row-level security policy "hide_deleted"`). Добавлена `app.soft_delete_document(uuid) → boolean` с той сигнатурой, которую уже вызывает бэкенд;
   - контракт хранит `original_name` из `POST /uploads` до `POST /documents`, а места в `uploads` не было: добавлена `uploads.original_name_ct bytea` (бэкенд её уже использует);
   - `ON CONFLICT (object_key)` требует `SELECT` на колонку цели, поэтому в `enqueue_purge` цель не указана (первичный ключ единственный).
5. **Функции сверх списка ADR-044**: `soft_delete_document`, `claim/complete/release_workspace_create_key`, `purge_expired_workspace_create_keys`, `ensure_audit_partitions`, внутренняя `require_workspace` (без `EXECUTE` для кого-либо, кроме владельца).
6. **Права сверх DDL** (минимальные): `ma_app` `DELETE` на `idempotency_keys` (ADR-045: снять `in_progress` после 4xx/5xx); `ma_worker` `UPDATE` на `purge_queue` (счётчик попыток); `ma_auth` `SELECT/INSERT/UPDATE` на таблицы входа, `INSERT` в `purge_queue` и `audit_log`, `UPDATE` на `documents`, `SELECT` на таблицы для выборки воркера.
7. Роли миграция не создаёт (`ma_owner` без `CREATEROLE`), а проверяет; их создаёт `infra/postgres/init/01-roles.sh`, он не менялся. `audit_documents` получил `search_path = pg_catalog, pg_temp` вместо `app, pg_temp` (тело с полными именами). Границы секций 2026_11 и 2026_12 записаны с `+00`, чтобы не зависеть от часового пояса сервера.
8. Сид планов (`tests/db/seed_plans.sql`) взят из `db/seed-load.sql` с фиксированными id тяжёлого и обычного архива, фиксированным ключом индекса и `setseed`. Документы вставляются в порядке id архива, как на эталонном стенде: при корреляции `workspace_id` около 0,1 PostgreSQL 18 выбирает для Q5 `Bitmap Heap Scan + Sort` вместо `Index Scan` (проверено `CLUSTER`). Q5 в тесте строит границы суток в SQL через `AT TIME ZONE`, как в 07-database, раздел 4.
9. Абсолютный срок сессии 180 дней задаёт приложение (`p_absolute_ttl` в `create_session`), записано в `docs/db.md`.

## Проверка (команды и результат)

| Команда (из `apps/api`) | Результат |
|---|---|
| `uv run ruff check app/db migrations tests/db` | All checks passed (во всём `apps/api` одна ошибка PT011 в чужом незакоммиченном `tests/unit/test_crypto.py`) |
| `uv run ruff format --check --config pyproject.toml . ../../infra` | 115 files already formatted |
| `uv run mypy app tests migrations` | Success: no issues found in 114 source files |
| `TESTCONTAINERS_RYUK_DISABLED=true uv run pytest tests/db` | **178 passed** (89 на PostgreSQL 17.x `postgres:17-alpine`, 89 на 18.x `postgres:18-alpine`), 73 с |
| в том числе `tests/db/test_db_plans.py` | 22 passed (11 на версию), сид 210 000 документов около 50 с на версию |

Тесты по ID: DB-01 цикл upgrade, downgrade base, upgrade на пустой базе; TC-091 без контекста `ma_app` и `ma_worker` видят 0 строк во всех таблицах; TC-092 контекст пуст после COMMIT и после ROLLBACK на том же соединении; DB-03 перекрёстные SELECT, UPDATE, DELETE по id дают 0 строк, вставка в чужой архив `42501`; DB-02 `ma_app` и `ma_worker` не могут ALTER, DROP, TRUNCATE, CREATE, DROP POLICY; прямого доступа к таблицам входа, `purge_queue`, `audit_log` и секциям нет; каждая функция `SECURITY DEFINER` закреплена `search_path` и вызывается одной ролью; DB-07 повтор `INSERT ... ON CONFLICT` возвращает сохранённый ответ, CHECK отклоняет неизвестную операцию и тело до завершения; DB-08 аудит пишет имена полей без значений, `UPDATE/DELETE` журнала запрещены; DB-09 воркер находит и удаляет просроченное только под контекстом архива; DB-12 пул 10 и `statement_timeout = 5s`, модели совпадают со схемой по колонкам, типам и `NULL`.

Compose (отдельный проект, чтобы не трогать общий стек: `COMPOSE_PROJECT_NAME=medarchive-dbcheck IMAGE_TAG=dbcheck WEB_PORT=3391 API_PORT=8891 MINIO_PORT=9391 MINIO_CONSOLE_PORT=9392`):

| Команда | Результат |
|---|---|
| `docker compose up -d --wait db` и `docker compose run --rm migrate` | `0001_init`, затем `0002_privileges_functions`, код 0 |
| `docker compose run --rm migrate alembic downgrade base` | обе ревизии откатились, схемы `app` нет |
| `docker compose run --rm migrate alembic upgrade head`, затем ещё раз `run --rm migrate` | снова head, повтор ничего не делает, код 0; 17 функций `SECURITY DEFINER`, секции `2026_11`, `2026_12`, `2027_01`, `default` |
| `docker compose up -d --build --wait` | `db`, `redis`, `minio` healthy, `migrate` и `minio-init` код 0, `worker` работает с базой (`purge_finished`); **`api` падает при старте**: в окружении compose нет `CSRF_SECRET` и `PAGE_TOKEN_KEY`, которые требует `app/core/config.py` (зона бэкенда и DevOps) |
| `docker compose down -v` | проект проверки удалён вместе с томами |

Планы на PostgreSQL 18 под `ma_app`, прогретый кэш, `db/explain-queries.sql` с хэшами этого сида:

| Запрос | План | Время |
|---|---|---|
| Q1 | Limit → Result → Index Scan `documents_list` | 0,87 мс |
| Q2 | то же, `ROW(list_key, uploaded_at, id) > ROW(...)` в Index Cond | 0,28 мс |
| Q3 | Aggregate → Result → Index Only Scan `documents_list` | 1,97 мс |
| Q4 | Limit → Sort → Result → Bitmap Heap Scan (`@>` в Filter) → Bitmap Index Scan `documents_title_bidx` (`workspace_id` в Index Cond) | 7,36 мс |
| Q5 | Limit → Result → Index Scan `documents_by_upload`, границы суток в Index Cond | 0,13 мс |
| Q6 | Limit → Result → Index Only Scan `documents_list`, `list_key = 2147483647` в Index Cond | 0,14 мс |
| Q7 | Limit → Result → Index Scan `documents_list` | 0,09 мс |

## Риски и замечания

- Q4 близок к бюджету (7,4 мс из 10 на 10 000 документов). Ускорить без прав суперпользователя нельзя (ADR-046).
- План Q5 зависит от физического порядка строк. На реальных данных строки архивов перемешаны, и PostgreSQL может выбрать `Bitmap Heap Scan + Sort` (0,6 мс). Правило CI из 07-database «Sort в Q5 = провал» на таких данных будет ложно срабатывать.
- `make test` теперь включает `tests/db`: нужен Docker, около 1,5..3 минут. На Docker Desktop для macOS Ryuk не монтирует сокет: `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`, а при нехватке портов `TESTCONTAINERS_RYUK_DISABLED=true`.
- Откат `0002` на базе с данными падает намеренно: удалённую колонку ключа и стёртые ключи вернуть нельзя.
- Спецагенту: отразить в `07-data-model.sql`, `07-database.md` и ADR исправление триггера, `soft_delete_document`, `uploads.original_name_ct`, права из пункта 6.
