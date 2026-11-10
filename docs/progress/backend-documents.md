# Бэкенд: загрузка, документы, экспорт, очистка (BE-06..BE-11, BE-13, BE-17)

Статус: код BE-06..BE-11, BE-13, BE-17 закоммичен; API-тесты (82 шт.) зелёные локально и ждут коммита `tests/integration/api_stack.py` (агент ядра), маршруты ждут подключения в `app/main.py` (агент ядра, D-008). Агент BACKEND-DOCUMENTS, 10.11.2026.

## Что сделано

| Задача | Где | Коммит |
|---|---|---|
| Зависимость | `pypdf[crypto]`: без `cryptography` pypdf бросает `DependencyError` на AES-файле, и TC-017 давал бы 500 | `4665d5b` |
| BE-06 | `app/storage/s3.py`; `app/modules/uploads/**` (`pdf.py`, схемы, репозиторий, сервис, роутер); `app/modules/documents/files.py` (проверка, SHA-256, Streaming AEAD в `ma-docs`, расшифровка потоком) | `592deca`, `12c94e7`, `e3a8362` |
| BE-07 | `listing.py` (правила фильтра, ключи сортировки, курсор), `queries.py` (список, поиск по слепому индексу, счётчики), `repository.py` | `57533fc`, `e3a8362` |
| BE-08 | `content.py` (`Range` без `seek`), `filenames.py` (`Content-Disposition`), карточка с `ETag` и 304 | `093c8f9`, `e3a8362` |
| BE-09, BE-10 | `schemas.py` (коды каталога в `errors[].code`), PATCH с `If-Match`, мягкое удаление через `app.soft_delete_document` | `b3f2f77`, `e3a8362` |
| BE-11 | `app/modules/exports/**`: состав экспорта, ZIP потоком, `documents.csv`, `documents.json` | `f52fd50`, `709aa44` |
| BE-13 | `app/workers/purge.py`, `python -m app.workers.purge [--once]`; сервис `worker` в `docker-compose.yml` (попал в `d398560` вместе с OPS-06) | `9414eae`, `1a7d88d` |
| BE-17 | `app/cli.py`, цель `make seed` (`WORKSPACE=<id>` или новый архив с выводом ключа доступа) | `96fb970` |

## Опубликованные интерфейсы

| Модуль | Что даёт |
|---|---|
| `app/storage/s3.py` | `ObjectStorage(...)`, `ObjectStorage.from_settings(settings)`; бакеты `storage.quarantine`, `storage.docs`: `size(key) -> int | None` (HEAD), `download`, `upload`, `open(key) -> BinaryIO`, `delete` (отсутствующий ключ не ошибка), `list(prefix)`; `presign_quarantine_upload(key, max_bytes=, expires_in_seconds=)`. Сбой хранилища = `StorageUnavailableError` (подкласс `ProblemError`: 503 `storage_unavailable`, `Retry-After: 60`). Методы синхронные |
| `app/modules/{uploads,documents,exports}/router.py` | `router` каждого модуля: 9 операций контракта |
| `app/modules/documents/service.py` | `create_document`, `get_document`, `update_document`, `delete_document`, `open_content`, `etag(version)` |
| `app/modules/documents/queries.py` | `list_documents`, `find_matching`, `get_selected`, `get_export_items` |
| `app/workers/purge.py` | `Purger(sessions, storage).run_once() -> PurgeReport` |
| `app/cli.py` | `python -m app.cli seed --new` или `seed --workspace <id>` [`--root DIR`] |
| `tests/integration/conftest.py` | `database` (PostgreSQL 17 + роли + миграции; URL `superuser`, `owner`, `app`, `worker`), `storage` (MinIO, с повтором старта), `app_sessions`, `worker_sessions`, `superuser_engine`; после коммита `api_stack.py` ещё `redis_url` и `api` |

## Запросы к агенту ядра

1. **Подключить роутеры в `create_app`** (D-008), модули закоммичены:
   ```python
   from app.modules.documents.router import router as documents_router
   from app.modules.exports.router import router as exports_router
   from app.modules.uploads.router import router as uploads_router
   app.include_router(uploads_router)
   app.include_router(documents_router)
   app.include_router(exports_router)
   ```
2. Закоммитить `tests/integration/api_stack.py`: на нём стоят мои `test_uploads_api.py`, `test_documents_api.py`, `test_list_api.py`, `test_list_boundaries_api.py`, `test_exports_api.py`, `test_seed.py` и фикстуры `redis_url`, `api` в `conftest.py` (сейчас в рабочем дереве, не в HEAD).
3. Зона пользователя: в `SessionContext` нет `timezone` (у ядра тот же запрос к БД про `workspaces.timezone`). Нужна для `date_in_future`, `tz` по умолчанию в списке и даты в имени ZIP. Пока использую `DEFAULT_TIMEZONE = "Europe/Moscow"` (`app/modules/documents/dependencies.py`); когда появится `session.timezone`, заменю.
4. ~~`app.state.storage`~~, ~~RUF001~~ сделано.

## Запросы к агенту БД

1. ~~`uploads.original_name_ct`~~ сделано в 0002.
2. ~~`app.soft_delete_document(uuid)`~~ сделано в 0002 (под `ma_app` прямой UPDATE с `deleted_at` падает на `hide_deleted`, проверено).
3. `app.workspaces_due_for_purge` считает просроченными загрузки с `expires_at <= now()` любого статуса, поэтому воркер удаляет такие строки сразу. Через несколько минут после истечения часа `POST /documents` отвечает 404 `upload_not_found`, а не 410 `upload_expired`. Если 410 должен держаться дольше, нужен порог `u.expires_at <= now() - interval '24 hours'`; воркер возьмёт тот же порог. Вопрос владельцу, сейчас оставлено как есть.

## Запросы к DevOps (MinIO)

1. В рабочем дереве `infra/minio/api-policy.json` получает `s3:ListBucket` на `ma-docs`, спасибо. Воркеру нужен он же на `ma-quarantine` (удаление `q/{id}/` удалённого архива). Без него архив всё равно удаляется: остатки в карантине снимет правило жизненного цикла за сутки, в логе `purge_storage_unavailable`.

## Вопросы владельцу

1. PDF с паролем только владельца (открывается без пароля, ограничены права печати и копирования) по правилу BE-06 тоже `pdf_encrypted`. Такие бывают у выписок из лабораторий. Оставить отказ или принимать файлы, которые открываются без пароля?
2. Колонка `type` в `documents.csv`: сейчас русское название («Анализ»), в `documents.json` код (`analysis`). Подтвердить.

## Решения

1. PDF: подпись `%PDF-` с нулевого байта; любой зашифрованный файл (в том числе с пустым паролем пользователя) = `pdf_encrypted`; ноль страниц = `pdf_unreadable`; больше 2000 страниц сохраняется с `page_count = null` (CHECK колонки).
2. `POST /documents`: проверка и шифрование вне транзакции, затем одна транзакция (повторная проверка загрузки под `FOR UPDATE`, `documents`, `document_files`, `uploads.status = consumed`, `enqueue_purge` объекта карантина). Объект карантина удаляется сразу после коммита; если хранилище не ответило, его удалит очередь воркера, а запрос не падает (иначе клиент повторил бы уже потреблённую загрузку). Отклонённый PDF помечает загрузку `rejected` с кодом; повтор с ней отвечает тем же кодом. Шифртекст, записанный до упавшей транзакции, воркер удаляет как сироту через час.
3. `date_in_future`: верхний `code` = `date_in_future` и `errors[0].pointer = /document_date`. Даты в теле и в запросе принимаются только как `YYYY-MM-DD` (pydantic сам по себе принимал `0` как Unix-время, нашёл schemathesis).
4. Список с `q`: кандидаты по слепому индексу без фильтра по дате, с признаком попадания в период; после расшифровки подстрока проверяется в приложении, `matched`, `undated_excluded`, сортировка и курсор считаются в памяти по тем же ключам, что SQL-keyset. Без `q` счётчики одним запросом (Q3), страница keyset по `(list_key, uploaded_at, id)`.
5. `order_by=uploaded_at desc`: документы без даты тоже в конце (контракт: «без даты всегда последние»), затем `uploaded_at` и `id` по убыванию.
6. `Range`: один диапазон; некорректный, многодиапазонный и невыполнимый `Range` отдаётся целиком с 200 (RFC 9110 разрешает игнорировать, 416 в контракте нет). Объект открывается до ответа, так что сбой хранилища = 503, а не оборванный поток.
7. Маршруты без 422 в контракте (`documents.get`, `documents.delete`, `documents.content`, `exports.content`) и PATCH читают id, `If-Match`, `If-None-Match`, `Range`, `disposition` из запроса: объявленный параметр добавил бы 422 в схему. Id не в формате UUID = 404 `not_found`, неизвестный `disposition` = `inline`.
8. `filename*` строится из даты и названия (`2026-04-08_Общий анализ крови.pdf`, пример 9.16), `filename` из транслита; название обрезается до 100 символов, запрещённые в именах файлов символы заменяются на `_`.
9. ZIP без сжатия (PDF уже сжаты) с известным размером: `Content-Length` в ответе. Ячейки CSV, начинающиеся с `=`, `+`, `-`, `@`, получают префикс `'` (CSV injection). `slug` до 80 символов по `docs/texts.md` (раздел 13), а не 120 из задания: 120 остаётся верхней границей полного имени.
10. Экспорт пишет аудит `export.create` и `export.download`; `scope=filtered` без `filter` = весь архив; документы, удалённые между созданием экспорта и скачиванием, в ZIP не попадают.
11. Воркер: строки удаляются даже если хранилище отказало, объект уходит в `purge_queue` и повторяется с задержкой 1, 2, 4 ... минут (не больше 6 часов). При мягком удалении документа API в очередь ничего не ставит: объект и строку удаляет воркер через 24 часа. Отказ хранилища на одном архиве не останавливает остальные.

## Проверка

Docker Desktop: `TESTCONTAINERS_RYUK_DISABLED=true TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` (Ryuk не монтирует сокет и конфликтует между параллельными прогонами агентов).

| Команда (из `apps/api`) | Результат |
|---|---|
| `uv run pytest tests/unit` | 228 passed (мои: `test_pdf`, `test_export_names`, `test_export_manifest`, `test_list_rules`, `test_content_range`, `test_document_schemas`, `test_purge_rules`) |
| `uv run pytest tests/integration` (рабочее дерево; мои роутеры подключались локальным pytest-плагином вне репозитория до D-008) | 152 passed, из них моих 98: `test_storage` 7, `test_document_files` 5, `test_purge` 4, `test_uploads_api` 12, `test_documents_api` 20, `test_list_api` 37, `test_list_boundaries_api` 3, `test_exports_api` 8, `test_seed` 2 |
| Чистый `git worktree` на HEAD + мои файлы: `ruff check`, `ruff format --check`, `mypy app tests`, `pytest` | чисто; 238 passed (unit + integration) |
| Сверка `app.openapi()` с `openapi.yaml` для 9 моих операций (метод, путь, коды) | 0 расхождений |
| schemathesis `--checks all --max-examples 25 --seed 20261110` по 9 операциям против API на testcontainers | 627 случаев; ни одного 5xx и ни одного незаявленного кода. Осталось 7 находок, все по контракту: 428 без `If-Match` (ST203, контракт требует 428), 400 `invalid_page_token` на случайный токен, 422 `idempotency_key_reused` (хук повторяет один ключ с разными телами), 422 `date_invalid` на дату до 1900 (CHECK схемы). Для гейта: исключить `missing_required_header` у PATCH/DELETE и генерировать свой `Idempotency-Key` в хуке |

Покрытие TC: TC-010, TC-011 (порядок через API), TC-014, TC-015, TC-016 (413 до записи в хранилище), TC-017, TC-018, TC-019, TC-022, TC-023, TC-024 (`filename*`), TC-030..TC-039, TC-042, TC-043, TC-044 (23:59 и 00:30 МСК, та же пара в UTC), TC-050, TC-057 (SHA-256 после расшифровки), TC-058, TC-059, TC-070 (имена, CSV с BOM, JSON), TC-071, TC-073, TC-090, TC-094, TC-096 (в БД шифртекст, в логах нет названия, запроса и имени файла), TC-097; идемпотентность очистки (второй проход ничего не удаляет).

## Не сделано

1. `make seed` и сервис `worker` в живом стеке не проверены: стек `docker compose` на HEAD не поднимался из-за D-008 и переменных `CSRF_SECRET`/`PAGE_TOKEN_KEY` (DevOps добавляет). Сид проверен тестом через тот же путь сервисов (`test_seed.py`), воркер интеграционными тестами.
2. Зона пользователя фиксирована `Europe/Moscow` до появления `session.timezone`.
