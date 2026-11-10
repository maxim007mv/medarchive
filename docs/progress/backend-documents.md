# Бэкенд: загрузка, документы, экспорт, очистка (BE-06..BE-11, BE-13, BE-17)

Статус: код модулей, воркера и сида написан; API-тесты ждут двух правок БД (запросы ниже) и подключения роутеров в `app/main.py`. Агент BACKEND-DOCUMENTS, 10.11.2026.

## Опубликованные интерфейсы

| Модуль | Что даёт |
|---|---|
| `app/storage/s3.py` | `ObjectStorage(endpoint, public_endpoint, access_key, secret_key, quarantine_bucket, docs_bucket)`, `ObjectStorage.from_settings(settings)`; бакеты `storage.quarantine`, `storage.docs`: `size(key) -> int | None` (HEAD), `download(key, file)`, `upload(key, file)`, `open(key) -> BinaryIO`, `delete(key)` (отсутствующий ключ не ошибка), `list(prefix)`; `presign_quarantine_upload(key, max_bytes=, expires_in_seconds=)`. Любой сбой хранилища = `StorageUnavailableError` (подкласс `ProblemError`: 503 `storage_unavailable`, `Retry-After: 60`). Методы синхронные, из async вызывать через `asyncio.to_thread` |
| `app/modules/uploads/router.py` | `router`: `POST /api/v1/uploads` |
| `app/modules/documents/router.py` | `router`: `GET/POST /api/v1/documents`, `GET/PATCH/DELETE /api/v1/documents/{document_id}`, `GET /api/v1/documents/{document_id}/content` |
| `app/modules/exports/router.py` | `router`: `POST /api/v1/exports`, `GET /api/v1/exports/{export_id}/content` |
| `app/modules/documents/service.py` | `create_document`, `get_document`, `update_document`, `delete_document`, `list_documents`, `find_matching`, `get_selected`, `get_export_items`, `open_content`; `etag(version)` |
| `app/modules/uploads/pdf.py` | `inspect_pdf(stream) -> int | None`, `PdfRejectedError.code` in `not_pdf`, `pdf_unreadable`, `pdf_encrypted` |
| `app/modules/documents/filenames.py` | `pdf_file_name(title, date)`, `unique_names(names)`, `content_disposition(disposition, title, date)` |
| `app/modules/documents/listing.py` | `build_filter(...)`, `ListFilter`, `Position` (курсор), `fingerprint(filter, tz, order_by)` |
| `app/modules/exports/manifest.py` | `build_csv(entries)`, `build_json(entries)` |
| `app/workers/purge.py` | `Purger(sessions, storage).run_once() -> PurgeReport`; `python -m app.workers.purge [--once]` |
| `app/cli.py` | `python -m app.cli seed --new` или `seed --workspace <id>` [`--root DIR`] |
| `tests/integration/conftest.py` | `database` (PostgreSQL 17 + роли + миграции; `superuser`, `owner`, `app`, `worker` URL), `storage` (MinIO), `redis_url`, `api` (приложение с lifespan и свежим KEK), `app_sessions`, `worker_sessions`, `superuser_engine` |

## Запросы к агенту ядра

1. Подключить роутеры в `create_app` (`app/main.py`), файлы готовы:
   ```python
   from app.modules.documents.router import router as documents_router
   from app.modules.exports.router import router as exports_router
   from app.modules.uploads.router import router as uploads_router
   ...
   app.include_router(uploads_router)
   app.include_router(documents_router)
   app.include_router(exports_router)
   ```
2. ~~`app.state.storage`~~ сделано.
3. ~~RUF001~~ сделано (`allowed-confusables`).
4. Зона пользователя: в `SessionContext` нет `timezone` (у ядра тот же запрос к БД про колонку `workspaces.timezone`). Мне она нужна для `date_in_future`, `tz` по умолчанию в списке и даты в имени ZIP. Пока поля нет, использую `DEFAULT_TIMEZONE = "Europe/Moscow"` в `app/modules/documents/dependencies.py`; когда появится `session.timezone`, заменю.

## Запросы к агенту БД

1. **Колонка `app.uploads.original_name_ct bytea`** (миграция 0003; у `ma_app` уже есть INSERT и SELECT на `uploads`) и поле `Upload.original_name_ct: Mapped[bytes | None]` в `app/db/models.py`. Контракт принимает `original_name` в `POST /api/v1/uploads`, а `POST /api/v1/documents` его не передаёт; хранить имя между вызовами больше негде. Шифрую AEAD пространства с AAD = `upload_id`, при создании документа перешифровываю с AAD = `document_id` в `document_files.original_name_ct`. CHECK по желанию: `original_name_ct IS NULL OR octet_length(original_name_ct) BETWEEN 29 AND 2048`. Код уже пишет в эту колонку (`app/modules/uploads/repository.py`), без неё mypy и `POST /uploads` падают.
2. **Мягкое удаление под `ma_app` невозможно**: `UPDATE app.documents SET deleted_at = now() WHERE id = $1` упирается в RESTRICTIVE-политику `hide_deleted` (FOR SELECT): при UPDATE с WHERE PostgreSQL проверяет политики SELECT и для новой строки. Проверено на 0001+0002 в testcontainers: `new row violates row-level security policy "hide_deleted" for table "documents"`. Прошу `app.soft_delete_document(p_document_id uuid) RETURNS boolean` (`SECURITY DEFINER`, `UPDATE app.documents SET deleted_at = now() WHERE id = p_document_id AND workspace_id = app.require_workspace() AND deleted_at IS NULL`, true если строка обновлена; аудит `document.delete` пишет существующий триггер) с `GRANT EXECUTE` только для `ma_app`. Версию (`If-Match`) проверяю сам через `SELECT ... FOR UPDATE` в той же транзакции. Код вызывает её в `app/modules/documents/repository.py:soft_delete`.
3. `app.workspaces_due_for_purge` считает просроченными загрузки с `expires_at <= now()` любого статуса, поэтому воркер удаляет такие строки сразу. Следствие: через несколько минут после истечения часа `POST /documents` отвечает 404 `upload_not_found`, а не 410 `upload_expired`. Если 410 должен держаться дольше, нужен порог `u.expires_at <= now() - interval '24 hours'` в функции; воркер тогда возьмёт тот же порог.

## Запросы к DevOps (MinIO)

1. Воркеру нужен `s3:ListBucket` на `ma-docs` и `ma-quarantine` (поиск объектов без строки старше часа, удаление всех объектов удалённого архива по префиксу) и `s3:DeleteObject`. В `infra/minio/api-policy.json` есть только Get/Put/Delete объектов. Предлагаю отдельного пользователя MinIO `ma-worker` (List + Delete, без Get/Put) и его ключи в сервисе `worker`. Пока сервис `worker` в `docker-compose.yml` ходит ключами API: шаги со списком объектов пишут `purge_storage_unavailable` в лог и повторяются на следующем проходе, остальные шаги работают.

## Решения

1. PDF: подпись `%PDF-` ровно с нулевого байта; любой зашифрованный файл (в том числе с пустым паролем пользователя) = `pdf_encrypted`; ноль страниц = `pdf_unreadable`; больше 2000 страниц сохраняется с `page_count = null` (CHECK колонки).
2. `POST /documents`: проверка и шифрование вне транзакции, затем одна транзакция (повторная проверка загрузки под `FOR UPDATE`, `documents`, `document_files`, `uploads.status = consumed`, `enqueue_purge` объекта карантина). Объект карантина удаляется сразу после коммита; если хранилище не ответило, его удалит очередь воркера, а запрос не падает (иначе клиент повторил бы уже потреблённую загрузку). Отклонённый PDF помечает загрузку `rejected` с кодом, повтор с ней отвечает тем же кодом.
3. `date_in_future`: верхний `code` = `date_in_future` и `errors[0].pointer = /document_date` (TC-014 читает любой из них).
4. Список с `q`: кандидаты по слепому индексу без фильтра по дате, с признаком попадания в период; после расшифровки подстрока проверяется в приложении, `matched`, `undated_excluded`, сортировка и курсор считаются в памяти по тем же ключам, что и SQL-keyset. Без `q` счётчики одним запросом (Q3), страница keyset по `(list_key, uploaded_at, id)`.
5. `order_by=uploaded_at desc`: документы без даты тоже в конце (контракт: «без даты всегда последние»), затем `uploaded_at` и `id` по убыванию.
6. `Range`: только один диапазон; некорректный, многодиапазонный и невыполнимый `Range` отдаётся целиком с 200 (RFC 9110 разрешает игнорировать, 416 в контракте нет).
7. Маршруты без 422 в контракте (`documents.get`, `documents.delete`, `documents.content`, `exports.content`) читают id, `If-Match`, `If-None-Match`, `Range`, `disposition` из запроса: объявленный параметр добавил бы 422 в схему. Id не в формате UUID = 404 `not_found`, неизвестный `disposition` = `inline`.
8. `filename*` строится из даты и названия документа (`2026-04-08_Общий анализ крови.pdf`, пример 9.16), `filename` из транслита.
9. ZIP без сжатия (PDF уже сжаты) с известным размером: `Content-Length` в ответе. В CSV колонка `type` содержит русское название типа («Анализ»), в JSON код (`analysis`); ячейки CSV, начинающиеся с `=`, `+`, `-`, `@`, получают префикс `'` (CSV injection).
10. Экспорт пишет аудит `export.create` и `export.download`; `scope=filtered` без `filter` = весь архив; документы, удалённые между созданием экспорта и скачиванием, в ZIP не попадают.
11. Воркер: строки удаляются даже если хранилище отказало, объект тогда уходит в `purge_queue` и повторяется с задержкой 1, 2, 4 ... минут (не больше 6 часов); при мягком удалении документа API ничего в очередь не ставит, объект и строку удаляет воркер через 24 часа. Отказ хранилища на одном архиве не останавливает остальные.

## Проверка

| Команда (из `apps/api`) | Результат |
|---|---|
| `uv run pytest tests/unit/test_pdf.py tests/unit/test_export_names.py tests/unit/test_export_manifest.py tests/unit/test_list_rules.py tests/unit/test_content_range.py tests/unit/test_document_schemas.py tests/unit/test_purge_rules.py` | 101 passed |
| `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/integration/test_storage.py tests/integration/test_document_files.py tests/integration/test_purge.py` | 15 passed (MinIO `pgsty/minio`, PostgreSQL 17 с 0001+0002) |
| `uv run ruff check` и `ruff format --check` по моим файлам | чисто |
| `uv run mypy` по моим файлам | 1 ошибка: нет `Upload.original_name_ct` (запрос БД 1) |
