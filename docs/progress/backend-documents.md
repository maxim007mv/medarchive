# Бэкенд: загрузка, документы, экспорт, очистка (BE-06..BE-11, BE-13, BE-17)

Статус: в работе. Агент BACKEND-DOCUMENTS, 10.11.2026.

## Опубликованные интерфейсы (для агентов ядра и БД)

| Модуль | Что даёт |
|---|---|
| `app/storage/s3.py` | `ObjectStorage(endpoint, public_endpoint, access_key, secret_key, quarantine_bucket, docs_bucket)` и `ObjectStorage.from_settings(settings)`; бакеты `storage.quarantine`, `storage.docs` с методами `size(key) -> int | None` (HEAD), `download(key, file)`, `upload(key, file)`, `open(key) -> IO[bytes]`, `delete(key)` (no-op для отсутствующего), `list(prefix)`; `presign_quarantine_upload(key, max_bytes=, expires_in_seconds=)`. Любой сбой хранилища поднимает `StorageUnavailableError` (подкласс `ProblemError`, 503 `storage_unavailable`, `Retry-After: 60`). Методы синхронные: вызывать через `asyncio.to_thread` |
| `app/modules/uploads/pdf.py` | `inspect_pdf(stream) -> int | None` (страницы), `PdfRejectedError.code` in `not_pdf`, `pdf_unreadable`, `pdf_encrypted` |
| `app/modules/documents/filenames.py` | `pdf_file_name(title, date)`, `unique_names(names)`, `content_disposition(disposition, title, date)` |
| `app/modules/documents/listing.py` | `build_filter(...)`, `ListFilter`, `Position` (курсор), `fingerprint(filter, tz, order_by)` для `PageTokenCodec` |
| `app/modules/exports/manifest.py` | `build_csv(entries)`, `build_json(entries)` |

## Запросы к агенту ядра

1. Подключить роутеры в `app/main.py` (`create_app`): `app.include_router(uploads_router)`, `documents_router`, `exports_router` из `app.modules.{uploads,documents,exports}.router` (каждый модуль экспортирует `router`). Файлы ядра не правлю.
2. Положить `app.state.storage = ObjectStorage.from_settings(config)` в `lifespan` (сейчас `/readyz` создаёт клиент на каждый запрос); мои маршруты берут хранилище из `request.app.state.storage`.
3. В `pyproject.toml` ruff ругается `RUF001` на любую кириллицу в строках (каталог ошибок, тексты, таблица транслитерации). Предлагаю `[tool.ruff.lint] ignore = ["RUF001"]`: интерфейс русский по заданию.
4. Testcontainers на Docker Desktop (macOS): контейнер Ryuk не монтирует `~/.docker/run/docker.sock`, нужен `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` (в Makefile или conftest).

## Запросы к агенту БД

1. **Нужна колонка `app.uploads.original_name_ct bytea NULL`** (миграция 0003, `ma_app` уже имеет INSERT/SELECT на `uploads`) и поле `Upload.original_name_ct: Mapped[bytes | None]` в `app/db/models.py`. Контракт принимает `original_name` в `POST /api/v1/uploads`, а `POST /api/v1/documents` его не передаёт; хранить имя между вызовами больше негде. Шифрую AEAD пространства с AAD = `upload_id`, при создании документа перешифровываю с AAD = `document_id` в `document_files.original_name_ct`. CHECK по желанию: `octet_length(original_name_ct) BETWEEN 29 AND 2048`.
2. Мягкое удаление документа под `ma_app`: `UPDATE app.documents SET deleted_at = now() WHERE id = $1 AND version = $2` упирается в RESTRICTIVE-политику `hide_deleted` (FOR SELECT): по документации PostgreSQL при UPDATE с WHERE политики SELECT проверяются и для новой строки, **проверено на 0001+0002 в testcontainers: `new row violates row-level security policy "hide_deleted" for table "documents"`**. Прошу функцию `app.soft_delete_document(p_document_id uuid) RETURNS boolean` (`SECURITY DEFINER`, `UPDATE ... SET deleted_at = now() WHERE id = p_document_id AND workspace_id = app.require_workspace() AND deleted_at IS NULL`, true если строка обновлена; триггер аудита запишет `document.delete`) с `GRANT EXECUTE` только для `ma_app`. Версию (`If-Match`) проверяю сам через `SELECT ... FOR UPDATE` в той же транзакции.
3. `app.workspaces_due_for_purge` считает просроченными загрузки с `expires_at <= now()` любого статуса, поэтому воркер удаляет такие строки сразу. Следствие: через несколько минут после истечения часа `POST /documents` отвечает 404 `upload_not_found`, а не 410 `upload_expired`. Если 410 должен держаться дольше, нужен порог `expires_at <= now() - interval '24 hours'` в функции; тогда воркер будет удалять строки с тем же порогом.

## Проверка

| Команда | Результат |
|---|---|
| `uv run pytest tests/unit/test_pdf.py tests/unit/test_export_names.py tests/unit/test_export_manifest.py tests/unit/test_list_rules.py` | 51 passed |
| `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/integration/test_storage.py` (MinIO `pgsty/minio`) | 7 passed |
