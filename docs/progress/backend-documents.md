# Бэкенд: загрузка, документы, экспорт, очистка (BE-06..BE-11, BE-13, BE-17)

Статус: готово, всё закоммичено. Агент BACKEND-DOCUMENTS, 10.11.2026.

## Что сделано

| Задача | Где | Коммиты |
|---|---|---|
| Зависимость | `pypdf[crypto]`: без `cryptography` pypdf бросает `DependencyError` на AES-файле, и TC-017 давал бы 500 | `4665d5b` |
| BE-06 | `app/storage/s3.py`; `app/modules/uploads/**` (`pdf.py`, схемы, репозиторий, сервис, роутер); `app/modules/documents/files.py` (проверка, SHA-256, Streaming AEAD в `ma-docs`, расшифровка потоком) | `592deca`, `12c94e7`, `e3a8362`, `c0e5b87`, `1ae2423` |
| BE-07 | `listing.py` (правила фильтра, ключи сортировки, курсор), `queries.py` (список, поиск по слепому индексу, счётчики), `repository.py`; зона архива из `workspaces.timezone` | `57533fc`, `5a9de70`, `e3a8362`, `fda1908`, `43f4bfc` |
| BE-08 | `content.py` (`Range` без `seek`), `filenames.py` (`Content-Disposition`), карточка с `ETag` и 304 | `093c8f9`, `e3a8362`, `7067d3c` |
| BE-09, BE-10 | `schemas.py` (коды каталога в `errors[].code`), PATCH с `If-Match`, мягкое удаление через `app.soft_delete_document` | `b3f2f77`, `e3a8362`, `7067d3c` |
| BE-11 | `app/modules/exports/**`: состав экспорта, ZIP потоком, `documents.csv`, `documents.json` | `f52fd50`, `709aa44`, `610daa6` |
| BE-13 | `app/workers/purge.py`, `python -m app.workers.purge [--once]`; сервис `worker` в `docker-compose.yml` (попал в `d398560` вместе с OPS-06) | `9414eae`, `1a7d88d` |
| BE-17 | `app/cli.py`, цель `make seed` (`WORKSPACE=<id>` или новый архив с выводом ключа доступа) | `96fb970`, `520318e`, `8d953e2` |

## Опубликованные интерфейсы

| Модуль | Что даёт |
|---|---|
| `app/storage/s3.py` | `ObjectStorage(...)`, `ObjectStorage.from_settings(settings)`; бакеты `storage.quarantine`, `storage.docs`: `size(key) -> int | None` (HEAD), `download`, `upload`, `open(key) -> BinaryIO`, `delete` (отсутствующий ключ не ошибка), `list(prefix)`; `presign_quarantine_upload(key, max_bytes=, expires_in_seconds=)`. Сбой хранилища = `StorageUnavailableError` (подкласс `ProblemError`: 503 `storage_unavailable`, `Retry-After: 60`). Методы синхронные |
| `app/modules/{uploads,documents,exports}/router.py` | `router` каждого модуля: 9 операций контракта, подключены в `create_app` |
| `app/modules/documents/service.py` | `create_document`, `get_document`, `update_document`, `delete_document`, `open_content`, `etag(version)` |
| `app/modules/documents/queries.py` | `list_documents`, `find_matching`, `get_selected`, `get_export_items` |
| `app/modules/documents/dependencies.py` | `Storage`, `Keys`, `PageTokens`, `UserTimezone` (зона архива, для старых архивов `Europe/Moscow`), `today_in(tz)` |
| `app/workers/purge.py` | `Purger(sessions, storage).run_once() -> PurgeReport` |
| `app/cli.py` | `python -m app.cli seed --new` или `seed --workspace <id>` [`--root DIR`] |
| `tests/integration/conftest.py` | `database` (PostgreSQL 17 + роли + миграции; URL `superuser`, `owner`, `app`, `worker`), `storage` (MinIO, с повтором старта), `redis_url`, `api`, `app_sessions`, `worker_sessions`, `superuser_engine` |

## Запросы к другим агентам

Ядро: все запросы закрыты (роутеры подключены, `api_stack.py` закоммичен, зона архива сохраняется). Замечание: при перегруженном Docker один раз `POST /workspaces` упал 500 в `issue_access_key` (запрос шёл 17 с при `statement_timeout` 5 с); повтор зелёный.

БД: `uploads.original_name_ct` и `app.soft_delete_document(uuid)` сделаны в 0002. Открыт один вопрос: `app.workspaces_due_for_purge` считает просроченными загрузки с `expires_at <= now()` любого статуса, воркер удаляет такие строки сразу, и через несколько минут после истечения часа `POST /documents` отвечает 404 `upload_not_found`, а не 410 `upload_expired`. Если 410 должен держаться дольше, нужен порог `u.expires_at <= now() - interval '24 hours'`; воркер возьмёт тот же порог.

DevOps: в рабочем дереве `infra/minio/api-policy.json` получает `s3:ListBucket` на `ma-docs`. Воркеру нужен он же на `ma-quarantine` (удаление `q/{id}/` удалённого архива). Без него архив всё равно удаляется: остатки в карантине снимет правило жизненного цикла за сутки, в логе `purge_storage_unavailable`.

QA (schemathesis в гейте): исключить `missing_required_header` для PATCH и DELETE документа (контракт требует 428 без `If-Match`) и выдавать в хуке свой `Idempotency-Key` на каждый случай, иначе ST202 на `idempotency_key_reused`.

## Вопросы владельцу

1. PDF с паролем только владельца (открывается без пароля, ограничены печать и копирование) по правилу BE-06 тоже `pdf_encrypted`. Такие бывают у выписок из лабораторий. Оставить отказ или принимать файлы, которые открываются без пароля?
2. Колонка `type` в `documents.csv`: сейчас русское название («Анализ»), в `documents.json` код (`analysis`). Подтвердить.

## Решения

1. PDF: подпись `%PDF-` с нулевого байта; любой зашифрованный файл (в том числе с пустым паролем пользователя) = `pdf_encrypted`; ноль страниц = `pdf_unreadable`; больше 2000 страниц сохраняется с `page_count = null` (CHECK колонки).
2. `POST /documents`: проверка и шифрование вне транзакции, затем одна транзакция (повторная проверка загрузки под `FOR UPDATE`, `documents`, `document_files`, `uploads.status = consumed`, `enqueue_purge` объекта карантина). Объект карантина удаляется сразу после коммита; если хранилище не ответило, его удалит очередь воркера, а запрос не падает (иначе клиент повторил бы уже потреблённую загрузку). Отклонённый PDF помечает загрузку `rejected` с кодом; повтор с ней отвечает тем же кодом. Шифртекст, записанный до упавшей транзакции, воркер удаляет как сироту через час.
3. `date_in_future`: «сегодня» по зоне архива; верхний `code` = `date_in_future` и `errors[0].pointer = /document_date`. Даты в теле и в запросе принимаются только как `YYYY-MM-DD` (pydantic сам по себе принимал `0` как Unix-время, нашёл schemathesis).
4. Список с `q`: кандидаты по слепому индексу без фильтра по дате, с признаком попадания в период; после расшифровки подстрока проверяется в приложении, `matched`, `undated_excluded`, сортировка и курсор считаются в памяти по тем же ключам, что SQL-keyset. Без `q` счётчики одним запросом (Q3), страница keyset по `(list_key, uploaded_at, id)`.
5. `order_by=uploaded_at desc`: документы без даты тоже в конце (контракт: «без даты всегда последние»), затем `uploaded_at` и `id` по убыванию.
6. `Range`: один диапазон; некорректный, многодиапазонный и невыполнимый `Range` отдаётся целиком с 200 (RFC 9110 разрешает игнорировать, 416 в контракте нет). Объект открывается до ответа, так что сбой хранилища = 503, а не оборванный поток.
7. Маршруты без 422 в контракте (`documents.get`, `documents.delete`, `documents.content`, `exports.content`) и PATCH читают id, `If-Match`, `If-None-Match`, `Range`, `disposition` из запроса: объявленный параметр добавил бы 422 в схему. Id не в формате UUID = 404 `not_found`, неизвестный `disposition` = `inline`.
8. `filename*` строится из даты и названия (`2026-04-08_Общий анализ крови.pdf`, пример 9.16), `filename` из транслита; название обрезается до 100 символов, запрещённые в именах файлов символы заменяются на `_`.
9. ZIP без сжатия (PDF уже сжаты) с известным размером: `Content-Length` в ответе. Ячейки CSV, начинающиеся с `=`, `+`, `-`, `@`, получают префикс `'` (CSV injection). `slug` до 80 символов по `docs/texts.md` (раздел 13), а не 120 из задания: 120 остаётся верхней границей полного имени.
10. Экспорт пишет аудит `export.create` и `export.download`; `scope=filtered` без `filter` = весь архив; документы, удалённые между созданием экспорта и скачиванием, в ZIP не попадают.
11. Воркер: строки удаляются даже если хранилище отказало, объект уходит в `purge_queue` и повторяется с задержкой 1, 2, 4 ... минут (не больше 6 часов). При мягком удалении документа API в очередь ничего не ставит: объект и строку удаляет воркер через 24 часа. Отказ хранилища на одном архиве не останавливает остальные; удалённый архив удаляется и без `ListBucket`.

## Проверка

Docker Desktop: `TESTCONTAINERS_RYUK_DISABLED=true TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`.

| Команда (из `apps/api`) | Результат |
|---|---|
| `uv run pytest tests/unit` | 235 passed (мои: `test_pdf`, `test_export_names`, `test_export_manifest`, `test_list_rules`, `test_content_range`, `test_document_schemas`, `test_document_dates` с freezegun 12:00, 23:59 и 00:30 МСК, `test_purge_rules`) |
| Чистый `git worktree` на HEAD + мои тесты: `ruff check`, `ruff format --check`, `mypy app tests` (strict), `pytest tests/unit tests/integration tests/test_health.py tests/contract` | чисто; 153 passed + 1 падение `POST /workspaces` из-за нагрузки на Docker (см. замечание ядру), повтор зелёный |
| `pytest tests/integration/test_documents_api.py test_list_api.py test_exports_api.py test_uploads_api.py test_list_boundaries_api.py tests/contract` после перехода на зону архива | 103 passed |
| Мои интеграционные тесты | 100: `test_storage` 7, `test_document_files` 5, `test_purge` 4, `test_uploads_api` 12, `test_documents_api` 22, `test_list_api` 37, `test_list_boundaries_api` 3, `test_exports_api` 8, `test_seed` 2 |
| `tests/contract/test_openapi_diff.py`; отдельная сверка 9 моих операций | 0 расхождений по методу, пути и кодам |
| schemathesis `--checks all --max-examples 25 --seed 20261110` по 9 операциям против API на testcontainers | 627 случаев, ни одного 5xx и ни одного незаявленного кода; 7 оставшихся находок все по контракту (см. запрос QA выше и 422 `date_invalid` на дату до 1900) |
| Живой стек `medarchive` (3300/8800): лог `worker` | проходы каждые 5 минут, очередь из 174 объектов карантина разобрана, `storage_failures: 0` |
| Живой стек: `docker compose run ... api python -m app.cli seed --root /seed --new` (с исправленным `cli.py`), затем вход ключом и `GET /api/v1/documents` | 6 документов в порядке 05, 03, 04, 01, 02, 06 с размерами из манифеста; апрель: `matched 3, undated_excluded 1`; «анализ» + апрель: 2 и 0; `undated=true`: только ЭКГ |

Покрытие TC: TC-010, TC-011, TC-014, TC-015, TC-016 (413 до записи в хранилище), TC-017, TC-018, TC-019, TC-022, TC-023, TC-024 (`filename*`), TC-030..TC-039, TC-042, TC-043, TC-044 (23:59 и 00:30 МСК, та же пара в UTC), TC-050, TC-057 (SHA-256 после расшифровки), TC-058, TC-059, TC-070 (имена, CSV с BOM, JSON), TC-071, TC-073, TC-090, TC-094, TC-096 (в БД шифртекст, в логах нет названия, запроса и имени файла), TC-097; идемпотентность очистки (второй проход ничего не удаляет).

## Отклонения от задания

1. Длина `slug` в именах ZIP 80 символов по `docs/texts.md`, а не 120: 120 остаётся пределом полного имени.
2. Сервис `worker` в `docker-compose.yml` закоммичен агентом DevOps в `d398560` вместе с OPS-06 (файл был общий в рабочем дереве), затем DevOps заменил отключённый healthcheck проверкой БД и MinIO.
3. `make seed` в живом стеке проверен через `docker compose run` с примонтированным исправленным `cli.py`: образ стека был собран до исправления `8d953e2`; после `make up` (пересборка) цель работает без монтирования.
