# Бэкенд: ядро, архив, сессии, ключ доступа (BE-01, BE-03, BE-04, BE-05, BE-12, BE-14, BE-15)

Статус: готово, код и тесты закоммичены; в `app/main.py` подключены все роутеры (`auth`, `workspace`, `uploads`, `documents`, `exports`). Агент BACKEND-CORE, 10.11.2026.

## Что сделано

| Задача | Где | Результат |
|---|---|---|
| BE-01 | `app/main.py`, `app/core/config.py`, `health.py`, `observability.py`, `metrics.py`, `ids.py` | Фабрика `create_app(settings=None)`, настройки читаются в lifespan; `/healthz`, `/readyz` (БД, оба бакета, файл KEK; любой сбой = 503 с `checks`), `/metrics` (вне схемы и лимитов); JSON-логи structlog с `request_id`, маршрутом-шаблоном, статусом, длительностью; access-лог uvicorn выключен (в нём сырой `q=`); Sentry только при непустом DSN, `before_send` вырезает тело, заголовки, query, значения исключений и переменные кадров; UUIDv7 |
| BE-03 | `app/core/errors.py`, `middleware.py` | 32 кода каталога (`ErrorCode`, `CATALOG`), тексты сверены тестом с `openapi.yaml` и `docs/texts.md` §16; `ProblemError`; ошибки схемы → 422 `validation_error` с `errors[].pointer` без значений; неизвестный маршрут → 404 `not_found`; необработанная ошибка → 500 `internal` без трассы, в лог только тип и кадры приложения |
| BE-04 | `app/modules/auth/**` | `POST /api/v1/workspaces` (согласие `const true`, версия политики = 2026-11-10, IANA-зона), идемпотентность через `workspace_create_keys` (повтор = тот же архив и ключ, новая сессия), `GET /api/v1/session` (продлевает простой, обновляет Max-Age cookie), `DELETE /api/v1/sessions/current`; cookie `__Host-ma_sid` HttpOnly Secure SameSite=Lax Path=/, Max-Age = остаток простоя (30 дней), абсолютный срок 180 дней в БД; аудит без значений |
| BE-05 | `app/modules/auth/access_key.py`, `app/modules/workspace/**` | Ключ 24 символа Crockford (6 lookup + 18 секрет), ввод с дефисами, пробелами, строчными, I/L→1, O→0; Argon2id m=19456 t=2 p=1 в потоке; фиктивный хэш для неизвестного ключа; 5 попыток за 15 мин на IP; `POST /api/v1/workspace/access-key` (идемпотентный, старый ключ отозван); `GET /api/v1/workspace` с ETag; `DELETE /api/v1/workspace` с `If-Match` (428/412) → 202 `purge_before`, криптоудаление, сессии отозваны, cookie стёрта; `GET /api/v1/document-types` с ETag и `public, max-age=3600` |
| BE-07 (часть ядра) | `app/core/blind_index.py`, `page_token.py` | Слепой индекс по ADR-046; курсор AES-GCM с id ключа, параметры списка в AAD |
| BE-12 | `app/core/ratelimit.py` | GCRA в Redis (WATCH/MULTI, целые миллисекунды), политики §3, `RateLimit-Policy`/`RateLimit` на каждом ответе лимитируемых маршрутов (и на 401/403), 429 `rate_limited` + `Retry-After` |
| BE-14 | `app/core/crypto.py`, `security.py`, `middleware.py`, `deps.py` | KEK из файла Tink; связка ключей пространства (AEAD RAW, Streaming AEAD 4KB, 32 байта ключа индекса) под KEK с AAD = id пространства, открывается на запрос; CSRF HMAC; заголовки API: `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, `Cache-Control: no-store` по умолчанию, HSTS только по HTTPS |
| BE-15 | `app/core/metrics.py`, `middleware.py` | `http_requests_total{method,route,status}`, `http_request_duration_seconds`, `upload_bytes`, `s3_errors_total{operation}` |

## Публичные интерфейсы для других агентов

| Что | Импорт и сигнатура |
|---|---|
| Ошибка | `from app.core.errors import ErrorCode, FieldError, ProblemError`; `raise ProblemError(ErrorCode.DATE_RANGE_INVALID, errors=[FieldError("/from")], detail=None, etag=None, headers={"Retry-After": "1"})`. Код поля из валидатора pydantic: `PydanticCustomError("title_too_long", ...)` попадает в `errors[].code` |
| Статусы маршрута для схемы | `from app.core.errors import problem_responses`; `responses=problem_responses(401, 403, 404, 429, 500)` |
| БД на запрос | `from app.core.deps import Db` (`Annotated[AsyncSession, Depends(get_db)]`, autobegin выключен) |
| Сессия | `from app.core.deps import SessionContext, Scope, require_scope`; `session: Annotated[SessionContext, Depends(require_scope(Scope.DOCUMENTS_WRITE))]`. Поля: `session_id`, `workspace_id`, `scopes`, `request_id`. Без cookie 401 `unauthenticated` |
| CSRF | Отдельной зависимости нет: `get_session` (внутри `require_scope`) проверяет `X-CSRF-Token` на любом методе, кроме GET/HEAD/OPTIONS, и отвечает 403 `csrf_failed`. Анонимные `POST /workspaces` и `POST /sessions` её не используют |
| Транзакция с RLS | `from app.core.deps import session_tx`; `async with session_tx(db, session): ...` (= `workspace_tx` с `session_id` и `request_id` для аудита) |
| Ключи пространства | `from app.core.deps import get_kek, load_workspace_keys`; `kek: Annotated[Kek, Depends(get_kek)]`; внутри `session_tx`: `keys = await load_workspace_keys(db, kek, session.workspace_id)`. Без кэша между запросами |
| Поля | `keys.encrypt_field(value: str, aad: bytes) -> bytes`, `keys.decrypt_field(ciphertext: bytes, aad: bytes) -> str` (чужой AAD = `tink.TinkError` → 500). AAD полей документа = `document_id.bytes` |
| Файлы | `keys.encrypting_stream(destination: BinaryIO, aad: bytes) -> BinaryIO` (закрытие пишет последний сегмент и закрывает `destination`), `keys.decrypting_stream(source: BinaryIO, aad: bytes) -> BinaryIO` (без `seek`) |
| Слепой индекс | `keys.title_bidx(title) -> list[int]` для `documents.title_bidx`; `keys.query_bidx(q) -> list[int]` для `title_bidx @> :hashes`; проверка кандидата `from app.core.blind_index import contains_query` (`contains_query(title, q)`), нормализация `normalize(text)` |
| Курсор | `request.app.state.page_tokens: PageTokenCodec`; `codec.encode(cursor: Mapping[str, str | int], fingerprint: bytes) -> str`, `codec.decode(token, fingerprint) -> dict` (любой чужой, испорченный или старый токен → `ProblemError(invalid_page_token)`); `from app.core.page_token import list_fingerprint` |
| Идемпотентность | `from app.core.idempotency import Operation, StoredResponse, require_idempotency_key, run_idempotent`; `key: Annotated[str, Depends(require_idempotency_key)]` (400 без заголовка); `stored = await run_idempotent(db, session, keys, operation=Operation.DOCUMENTS_CREATE, key=key, payload=body_model, execute=create)`, где `create() -> StoredResponse(status=201, body={...}, headers={"Location": ..., "ETag": ...}, resource_id=id)` открывает свои транзакции; ответ `stored.to_response()` (повтор с `Idempotent-Replayed: true`). Другое тело = 422 `idempotency_key_reused`, параллельный повтор = 409 + `Retry-After: 1`, ошибка внутри `execute` снимает захват ключа |
| Лимит | `from app.core.ratelimit import rate_limit, UPLOADS_CREATE, DOCUMENTS_CREATE, DOCUMENTS_LIST, DOCUMENTS_GET, DOCUMENTS_CONTENT, DOCUMENTS_UPDATE, DOCUMENTS_DELETE, EXPORTS_CREATE, EXPORTS_CONTENT, SUGGESTIONS_CREATE`; в декораторе маршрута `dependencies=[Depends(rate_limit(UPLOADS_CREATE))]` (тогда заголовки есть и на 401) |
| Метрики | `from app.core.metrics import UPLOAD_BYTES, S3_ERRORS`; `UPLOAD_BYTES.observe(size)`, `S3_ERRORS.labels("put").inc()`; `kek_errors_total{operation="load_kek" | "open_workspace_keys"}` считает ядро само |
| Адрес клиента | `from app.core.client import client_ip` (`client_ip(request) -> IPv4Address | IPv6Address | None`): за доверенным прокси ближайший недоверенный адрес `X-Forwarded-For` |
| Новый ключ доступа | `from app.modules.auth.service import issue_new_access_key` (внутри `workspace_tx`, повтор при занятом `lookup_id`) |
| Хранилище | `request.app.state.storage` (`ObjectStorage` из `app/storage/s3.py`, создаётся в lifespan) |
| UUIDv7 | `from app.core.ids import new_id` |
| Аудит | `from app.modules.auth.repository import add_audit` (обычный INSERT без RETURNING: у `ma_app` нет SELECT на журнал) |
| Тестовый стек API | `tests/integration/api_stack.py`: `redis_container()`, `write_kek(path)`, `settings_for(database_url, redis_url, kek_path)`, `running_api(settings, storage) -> Api`, `api.client(ip=None)` (у каждого клиента свой IP: лимиты по IP), `create_archive(client)`, `csrf(response)` |

## Решения

1. CSRF проверяется в `get_session` для всех изменяющих методов: забыть проверку на новом маршруте нельзя.
2. Лимит сессии ключуется SHA-256 cookie, а не id сессии: лимит выполняется до аутентификации, поэтому заголовки есть и на 401. Запрос без cookie лимит сессии не тратит (его отклоняет аутентификация без обращения к БД) и получает заголовки с полной квотой. Лимиты по IP (создание архива, вход по ключу) ключуются адресом клиента, IPv6 по /64.
3. GCRA через WATCH/MULTI с чистой функцией `gcra()` (её проверяют unit-тесты); при пяти подряд конфликтах WATCH запрос отклоняется (fail closed). Redis недоступен → 500.
4. Тело сохранённого ответа идемпотентности = зашифрованный конверт `{status, headers, body}`, чтобы повтор `documents.create` вернул и `Location`, и `ETag`.
5. ETag архива = SHA-256 сводки (`"w…"`): меняется при любом изменении документов, объёма или согласия.
6. `If-Match` и `X-CSRF-Token` читаются из заголовков напрямую, не объявляются параметрами: иначе FastAPI добавляет 422 в схему операции, а в контракте у `workspace.delete` и `sessions.delete` его нет.
7. Отпечаток согласия одинаков для всех, кто принял одну версию, поэтому он константа `EVIDENCE_SHA256`; unit-тест пересчитывает его из `docs/texts.md` и `docs/policy.md` и упадёт при правке текста или политики.
8. В ruff разрешены кириллические «двойники» латиницы (`allowed-confusables`): тексты интерфейса русские.
9. Адрес клиента для лимитов по IP и префикса IP в аудите: TCP-адрес, а если он входит в `TRUSTED_PROXIES`, то ближайший справа адрес `X-Forwarded-For`, который сам не доверенный (левые адреса клиент может подставить). По умолчанию доверенных прокси нет.
10. `RATE_LIMITS_ENABLED=false` (по умолчанию `true`) оставляет заголовки `RateLimit` с полной квотой, но ничего не тратит: для функциональных E2E и k6 гейта; TC-082 и TC-098 идут с включёнными лимитами.
11. `lookup_id` ключа случайный (6 символов), поэтому вставка идёт в SAVEPOINT: при `23505` выдаётся новый ключ, до трёх попыток; удалённый архив даёт 401.

## Запросы к агенту БД

1. ~~Часовой пояс архива~~: сделано в 0003 (`ae0e473`), зона сохраняется и отдаётся (`feat(BE-04): persist workspace timezone`).

## Дефекты гейта (`docs/progress/blocks.md`)

| ID | Что сделано | Коммит |
|---|---|---|
| D-005 | Лимиты по IP считают адрес пользователя за доверенным прокси (`TRUSTED_PROXIES`), подделанные левые адреса `X-Forwarded-For` не учитываются; тест с двумя адресами за одним прокси | `fa14f11` |
| D-006 | Параметр `RATE_LIMITS_ENABLED` | `fa14f11` |
| D-007 | Счётчик `kek_errors_total{operation}` | `098533d` |
| D-008 | Наблюдался на `62fe880`, до коммита фабрики: `82e87c4` подключает `auth`, `workspace`, `/readyz`, `/metrics`, `5d517a4` роутеры `uploads`, `documents`, `exports` | `82e87c4`, `5d517a4` |

## Запросы к агенту DevOps (compose и секреты)

1. Для D-005 в compose нужен `TRUSTED_PROXIES` сервиса `api` = подсеть сети compose, из которой ходит `web` (JSON-список, например `'["172.16.0.0/12"]'`); Next.js `rewrites` передаёт `X-Forwarded-For`. Для гейтов без лимитов: `RATE_LIMITS_ENABLED=false`.
2. API требует `CSRF_SECRET` и `PAGE_TOKEN_KEY` (не короче 32 символов; `PAGE_TOKEN_KEY_PREVIOUS` по желанию на время ротации), необязательные `SENTRY_DSN`, `LOG_LEVEL`. Нужно: пустые строки `CSRF_SECRET=` и `PAGE_TOKEN_KEY=` в `.env.example` (`make secrets` их заполнит), передача в `environment` сервиса `api` в `docker-compose.yml`, а для уже созданного `.env` дописывание недостающих ключей в `infra/secrets/generate.py` (существующие значения не трогать). Без них api не стартует: настройки падают при запуске.
3. Флаги `--proxy-headers` у uvicorn больше не нужны: адрес клиента берёт само приложение (п. 1).

## Вопросы владельцу

1. ~~Лимит удаления архива~~: решение владельца, считаются только принятые удаления (202), сделано ниже.

## Проверка (команды и результат)

| Команда (из `apps/api`) | Результат |
|---|---|
| `uv run ruff format` и `uv run ruff check` по файлам ядра, auth, workspace и тестам | All checks passed |
| `uv run mypy app/core app/main.py app/modules/auth app/modules/workspace tests/unit/... tests/integration/...` (strict) | no issues in 43 source files |
| `uv run pytest tests/unit tests/test_health.py` (вместе с unit-тестами агента документов) | 226 passed |
| `CONTRACT_BLOCK=3 uv run pytest tests/contract/test_openapi_diff.py` | 19 passed: операции, пути, методы и статусы ядра совпадают с `openapi.yaml`; с роутерами агента документов `CONTRACT_BLOCK=6`: 39 passed |
| `uv run pytest tests/unit tests/test_health.py tests/integration tests/contract` (все агенты API вместе, рабочее дерево) | 405 passed |
| `TESTCONTAINERS_RYUK_DISABLED=true TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/integration/test_auth.py tests/integration/test_workspace.py tests/integration/test_errors_api.py tests/integration/test_security_headers.py tests/integration/test_ratelimit_api.py` (PostgreSQL 17 с миграциями 0001+0002, MinIO, Redis 7) | 55 passed; общий прогон unit + integration ядра 281 passed |

| Schemathesis 4.33.1 против живого API (uvicorn на 127.0.0.1:8811, PostgreSQL 17 + MinIO + Redis в Docker на свободных портах), `CONTRACT_BASE_URL=... SCHEMATHESIS_HOOKS=tests.contract.hooks uv run schemathesis run ../../openapi.yaml --url http://127.0.0.1:8811 --checks all --max-examples 10 --seed 20261110 --workers 1 --include-operation-id ...` | Операции `workspaces.create`, `session.get`, `sessions.create`, `workspace.get`, `workspace.rotateKey`, `documentTypes.list`, `health.live`, `health.ready`: 221 из 221 прошли. `sessions.delete` и `workspace.delete` отдельным прогоном: 35 случаев, 2 ожидаемых замечания (ниже) |

Что нашёл Schemathesis и что исправлено: тело, которое нельзя декодировать, давало 400 (теперь 422 `validation_error`); 405 на `OPTIONS /api/v1/workspace` называл в `Allow` только `GET` (теперь `DELETE, GET`); анонимный `DELETE /api/v1/workspace` тратил общий лимит IP и получал 429 вместо 401 (теперь запрос без cookie не тратит лимит сессии). Оставшиеся замечания по `workspace.delete` не дефекты: случайный `If-Match` даёт 412 (правильный ETag генератор не знает), а лимит 1 в час на сессию исчерпывается первым же запросом хука.

Для агента QA (`tests/contract/hooks.py`): хук создаёт архив на каждое обновление авторизации, а лимит `POST /api/v1/workspaces` 10 в час на IP; при полном прогоне с одного адреса авторизация падает с 429 после десятого архива. Варианты: очищать Redis стенда перед прогоном, гонять `sessions.delete` и `workspace.delete` отдельно (они отзывают сессию) или подставлять `If-Match` из `GET /api/v1/workspace`.

Покрытие тест-кейсов: TC-002 (атрибуты cookie), TC-003, TC-082 (5×401 с одинаковым телом, затем 429 с `Retry-After`), TC-083, TC-084, TC-093, TC-094 (маршруты ядра), T6 (`test_t6_ciphertext_moved_to_another_document_fails`), поиск «анали»/«АНАЛИЗ»/ё-е, курсор с чужим фильтром и подделкой, GCRA, разбор ключа Crockford, атомарность лимита под 20 параллельными запросами, `/readyz` 503 при недоступных БД, хранилище и KEK. `scope_insufficient` проверен unit-тестом `require_scope`: у сессии владельца все скоупы, другой сессии в v1 нет.

Фикстуры `redis_url` и `api` в моих тестовых файлах объявлены локально, потому что `conftest.py` с общими фикстурами агента документов ещё не закоммичен; после его коммита локальные копии можно удалить (локальная фикстура модуля перекрывает фикстуру `conftest.py`, поэтому конфликта нет).

Testcontainers на Docker Desktop: нужен `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`; при параллельных прогонах нескольких агентов Ryuk конфликтует по имени, помогает `TESTCONTAINERS_RYUK_DISABLED=true` (фикстуры останавливают контейнеры сами).

## Доработки после блока 3 (10.11.2026)

| Что | Как | Коммит |
|---|---|---|
| D-010: ruff PT011 | `pytest.raises(OSError)` в `tests/unit/test_crypto.py` (а не в `test_security.py`) сужен до `FileNotFoundError`. Падающего теста в `tests/unit/test_security.py` на текущем `main` нет: `tests/unit` 231 passed | `0e04d04` |
| Лимит удаления архива | Только принятое удаление (202) тратит бюджет 1 в час. Маршрут читает бюджет без траты (`deferred_rate_limit`, заголовки `RateLimit` на каждом ответе), сервис тратит его атомарно (GCRA под WATCH/MULTI) внутри транзакции удаления после всех проверок: пустой бюджет даёт 429 и откатывает удаление, сбой после траты возвращает запрос (`refund`). 401, 403, 412, 428, 422 бюджет не тратят; после принятого удаления повтор той же cookie получает 401, а не 429 | `ab7b1ce` |
| Часовой пояс архива | `POST /api/v1/workspaces` сохраняет проверенную IANA-зону (`app.create_workspace(..., p_timezone)`, ревизия 0003); `GET /api/v1/session` и `POST /api/v1/sessions` отдают `timezone`, для архивов без зоны `Europe/Moscow`. Для агента документов: зону архива читает `app.modules.auth.repository.workspace_timezone(db, workspace_id)` внутри `workspace_tx` | `f83f0b8` |

Новый интерфейс лимита: `from app.core.ratelimit import RateBudget, deferred_rate_limit`; параметр маршрута `budget: Annotated[RateBudget, Depends(deferred_rate_limit(POLICY))]` перед параметром сессии, в сервисе `await budget.consume()` в точке принятия и `await budget.refund()` при сбое после неё.

| Команда (из `apps/api`) | Результат |
|---|---|
| `uv run ruff check --config pyproject.toml . ../../infra`, `ruff format --check` | All checks passed, 117 files formatted (шаг `pnpm --filter web lint` из `make lint` в этой оболочке не запускался: нет `pnpm` в PATH) |
| `uv run pytest tests/unit` | 235 passed (новые: `gcra_peek`, `gcra_refund`) |
| `uv run pytest tests/unit tests/integration/test_auth.py tests/integration/test_workspace.py tests/integration/test_errors_api.py tests/integration/test_ratelimit_api.py tests/integration/test_security_headers.py` | 293 passed (новые: 412 → 428 → 403 → 202 в течение часа с заголовками `r=1;t=0` и затем `r=0;t=3600`, исчерпанный бюджет → 429 без удаления, зона сохраняется и по умолчанию Москва) |
| `CONTRACT_BLOCK=6 uv run pytest tests/contract/test_openapi_diff.py` | 39 passed |

Замечание по стенду тестов: Docker Desktop сейчас нестабильно публикует порт MinIO (`Port mapping ... port 9000 is not available`), прогон приходилось повторять до 3 раз. В Docker висят десятки контейнеров `pgsty/minio` без проекта compose (утечки testcontainers при `TESTCONTAINERS_RYUK_DISABLED=true` у нескольких агентов); я их не удалял, часть может принадлежать идущим прогонам.
