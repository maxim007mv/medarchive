# ТЗ: база данных (роль: AI-агент DB / бэкенд)

Цель: развернуть схему PostgreSQL 17 или 18 из `01_common/07-data-model.sql` через Alembic и обеспечить изоляцию, шифрование и производительность из `01_common/07-database.md`. Источники S.. в `01_common/02-research-sources.md`.

## 1. Входные документы

| Документ | Что брать |
|---|---|
| `01_common/07-data-model.sql` | Эталонная DDL: таблицы, CHECK, FK, индексы, RLS, роли, функции |
| `01_common/07-database.md` | Требования D1 до D7, ERD, обоснования, планы запросов |
| `01_common/06-api-contract.md` | Какие запросы приходят от API (раздел 4 список, раздел 5 идемпотентность) |
| `01_common/db/explain-queries.sql`, `explain-analyze.txt` | Эталонные запросы Q1 до Q7 и их планы на 210 тыс. документов |

## 2. Задачи

| ID | Задача | Критерий готовности |
|---|---|---|
| DB-01 | Ревизия Alembic `0001_init` из DDL: расширения `pg_trgm`, `btree_gin`, `pgcrypto`; справочник `document_types` с тремя строками | `alembic upgrade head` на пустой БД без ошибок, `alembic downgrade base` чистит всё |
| DB-02 | Роли `ma_owner` (владелец схемы, только миграции), `ma_app` (API), `ma_worker` (очистка, экспорт), `ma_auth` (NOLOGIN BYPASSRLS, владелец `resolve_session`, `find_access_key` и функций записи миграции `0002`: `create_workspace`, `create_session`, `touch_session`, `revoke_sessions`, `issue_access_key`, `revoke_access_key`, `delete_workspace`, `enqueue_purge`, `workspaces_due_for_purge`, ADR-044) | `ma_app` не может `ALTER`, `DROP`, `TRUNCATE`; `SELECT` без `app.workspace_id` возвращает 0 строк; создание архива, вход по ключу, удаление документа и очистка воркером работают только через функции 0002 |
| DB-03 | RLS с `FORCE` на всех таблицах данных, политика по `current_setting('app.workspace_id', true)::uuid`, ограничивающая политика `hide_deleted` | Тест: две сессии, два пространства, перекрёстный `SELECT/UPDATE/DELETE` по `id` даёт 0 строк |
| DB-04 | Установка контекста только `SELECT set_config('app.workspace_id', $1, true)` в начале каждой транзакции (локально для транзакции) | Совместимо с PgBouncer в режиме transaction; тест: после `COMMIT` контекст пуст |
| DB-05 | Сгенерированный `list_key` и индекс `(workspace_id, list_key, uploaded_at, id) WHERE deleted_at IS NULL` | `EXPLAIN` Q1 показывает Index Scan без Sort, p95 меньше 5 мс на 10 тыс. документов пространства |
| DB-06 | Слепой индекс `title_bidx bigint[]` и GIN `(workspace_id, title_bidx)` через `btree_gin` | Q4 под `ma_app`: Bitmap Index Scan по `documents_title_bidx` с `workspace_id` в Index Cond, `title_bidx @>` в Filter (оператор не LEAKPROOF, при FORCE RLS в индекс не переносится, ADR-046), время меньше 10 мс на 10 тыс. документов; приложение передаёт литеральный массив, а не подзапрос; тест «анали» находит «анализ» |
| DB-07 | `idempotency_keys` с PK `(workspace_id, key)` и TTL 24 ч; в 0002 CHECK операций с `uploads.create` и `workspace.rotateKey`, колонка `response_body_ct`, таблица `workspace_create_keys` для `POST /workspaces` (ADR-045) | Вставка при конфликте ключа возвращает существующую строку; задача очистки удаляет истёкшие |
| DB-08 | `audit_log` с разбиением по месяцам, только `INSERT` для `ma_app`, `changed_fields` без значений | `UPDATE/DELETE` от `ma_app` запрещены; партиция следующего месяца создаётся заранее задачей |
| DB-09 | Очистка: мягко удалённые документы физически удаляются за 24 ч, пространства по `purge_after`, загрузки старше 1 ч, экспорты старше 1 ч | Задача `ma_worker` идемпотентна, пакетами по 500 |
| DB-10 | Миграции по схеме expand / migrate / contract: сначала добавить, потом перенести данные, потом удалить старое; `CREATE INDEX CONCURRENTLY` вне транзакции; `lock_timeout = 3s` | Каждая ревизия проходит на копии с данными; нет блокировок дольше 3 с |
| DB-11 | Резервное копирование (вне объёма прототипа, ADR-040): управляемый PostgreSQL в Yandex Cloud ru-central1, ежедневная копия и WAL для PITR 7 дней (S36, S46) | Ежеквартальное восстановление на отдельный кластер с замером RTO меньше 1 ч, RPO меньше 5 мин |
| DB-12 | Пул соединений: `asyncpg` + SQLAlchemy 2, размер 10 на инстанс, `statement_timeout = 5s` для `ma_app` | Нагрузочный тест 50 RPS без ожидания пула больше 50 мс |

## 3. Правила, обязательные к соблюдению

| Правило | Почему | Источник |
|---|---|---|
| Значения ПДн (название, заметка, имя файла) только шифртекстом AES-256-GCM, AAD = `document_id` | БД, бэкап и реплика без KMS не раскрывают данные; AAD не даёт переставить шифртекст между строками | S44, S52 |
| Не использовать `pgcrypto` для шифрования данных с ключом в SQL | Ключ попадает в журнал запросов и `pg_stat_activity` | S35 |
| Никаких `SECURITY DEFINER` функций, владелец которых имеет `BYPASSRLS`, кроме функций `ma_auth` из 0001 и 0002 (ADR-044) с `SET search_path = pg_catalog, pg_temp` и полными именами `app.*` в теле | Иначе обход RLS; `pg_temp` последним не даёт подменить объекты временной схемой | S32 |
| `ON DELETE CASCADE` только от `workspaces` вниз | Удаление архива удаляет всё; случайное удаление справочника запрещено `RESTRICT` | S32 |
| Списки без `OFFSET`, только keyset | Стоимость не растёт с глубиной | S39 |
| Загрузка связанных данных в ORM: `selectinload`, ленивые связи запрещены (`lazy="raise"`) | Нет N+1 | S40 |

## 4. Чего не делать

Не запускать тяжёлые нагрузочные прогоны на общей среде; не хранить DEK в БД открытым текстом; не логировать параметры SQL с ПДн; не добавлять триггеры с бизнес-логикой кроме аудита и `updated_at`.

## 5. Определение готовности

Миграция вверх и вниз зелёная в CI на Testcontainers PostgreSQL 17 и 18; тесты RLS (DB-03, DB-04) зелёные; планы Q1 до Q7 совпадают по типу узлов с `explain-analyze.txt`; документ `07-database.md` обновлён, если схема изменилась.
