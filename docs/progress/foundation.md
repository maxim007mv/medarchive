# Блок 1: каркас репозитория (OPS-01, OPS-03, окружение)

Статус: готово. Агент FOUNDATION, 10.11.2026.

## Что сделано

| Задача | Результат |
|---|---|
| Окружение (блок 0) | Node 22.23.4 (nvm, `.nvmrc`), pnpm 12.18.0 (corepack, `packageManager`), Python 3.12.12 (uv 0.9.17), Docker 27.3.1, Compose 2.29.7 |
| Корень | `AGENTS.md` (копия `MedArchive/06_ai_agents/AGENTS.md`), `.editorconfig`, `package.json`, `pnpm-workspace.yaml` (`apps/web`, `e2e`), `.dockerignore`, `.gitignore` |
| `apps/api` | FastAPI с одним `GET /healthz` (`operationId: health.live`), Swagger UI и ReDoc выключены (грузят скрипты с CDN), ruff + mypy strict + pytest-asyncio, `uv.lock`, Dockerfile |
| `apps/web` | Next.js 15 App Router, React 19, TS strict, Tailwind 4, шрифт Medeo, rewrites `/api/v1/*` в api, eslint + prettier + vitest, `gen:api`, Dockerfile (standalone) |
| `e2e` | Playwright (Chromium), смоук: страница открывается, шрифт Medeo Sans загружен |
| OPS-01 | `docker-compose.yml`: web, api, db (postgres 17), minio + minio-init, redis 7, migrate; тома `pg_data`, `minio_data` |
| OPS-03 (частично) | `Makefile` и `.github/workflows/ci.yml`: lint, typecheck, unit, сборка образов. Интеграционные, E2E и schemathesis в CI добавят следующие блоки |
| OPS-05 (частично) | Образы slim/alpine, пользователь не root (api uid 10001, web `node`), `read_only`, `cap_drop: ALL`, `no-new-privileges`, `HEALTHCHECK` |
| OPS-07 (каркас) | Роли создаются init-скриптом; `migrate` ходит как `ma_owner`, api как `ma_app` |

### Версии ключевых зависимостей (из lock-файлов)

API: fastapi 0.162.4, uvicorn 0.54.0, pydantic 2.14.3, pydantic-settings 2.16.2, sqlalchemy 2.1.8, asyncpg 0.32.0, alembic 1.20.1, pypdf 7.0.1, zipstream-ng 1.9.3, argon2-cffi 25.1.0, tink 1.16.1, redis 8.1.0, boto3 1.43.127, structlog 26.1.0, prometheus-client 0.26.0, sentry-sdk 2.74.0, httpx 0.28.1; dev: pytest 9.2.0, pytest-asyncio 1.4.1.post1, testcontainers 4.15.0 (`minio`, `postgres`), schemathesis 4.33.1, ruff 0.17.4, mypy 2.4.1, freezegun 1.5.5, boto3-stubs 1.43.127.

Web: next 15.5.29, react/react-dom 19.3.1, typescript 5.9.3, tailwindcss и @tailwindcss/postcss 4.3.5, @radix-ui dialog 1.3.1, radio-group 1.5.1, popover 1.3.1, checkbox 1.4.1, toast 1.3.1, @tanstack/react-query 5.107.1, nuqs 2.10.2, react-hook-form 7.91.0, zod 4.6.7, @hookform/resolvers 7.0.5, date-fns 4.4.0, lucide-react 1.70.0, openapi-fetch 0.17.0, openapi-typescript 7.13.0, vitest 5.1.0, vite 8.3.7, eslint 9.39.5, eslint-config-next 15.5.29. E2E: @playwright/test 1.65.0, @axe-core/playwright 4.14.0.

Образы: postgres:17-alpine (17.11), redis:7-alpine (7.4.12), pgsty/minio:RELEASE.2026-08-04T00-00-00Z, pgsty/mc:RELEASE.2026-10-26T00-00-00Z, python:3.12-slim-bookworm, node:22-alpine, ghcr.io/astral-sh/uv:0.9.17.

### Решения

- boto3, а не aioboto3: Streaming AEAD в Tink для Python работает с синхронными файловыми объектами, поэтому потоки S3 всё равно идут в рабочем потоке; aiobotocore жёстко закрепляет узкий диапазон botocore. Presigned POST в boto3 подписывается локально.
- Toast: `@radix-ui/react-toast`, как в ADR-004.
- TypeScript 5.9, а не 7.0: `openapi-typescript` требует `typescript ^5`. ESLint 9, а не 10: `eslint-config-next@15` поддерживает до 9.
- Шрифт: четыре вызова `next/font/local` (по подмножеству), у каждого свой `unicode-range`, семейства объявлены буквально как `Medeo Sans` и `Medeo Mono`, поэтому `--font-sans` и `--font-mono` из `tokens.css` указывают на эти же файлы. Переменные `--font-medeo-sans`, `--font-medeo-mono`. Фолбэк Sans: `Geist, Inter, system-ui, sans-serif`; Mono: `Geist Mono, ui-monospace, monospace` (как в `tokens.css`). Лицо с метриками фолбэка выключено: его считают по одному подмножеству.
- Прокси: rewrites Next вычисляются при сборке, поэтому образ web собирается с `API_ORIGIN=http://api:8000`; локально `pnpm dev` идёт на `http://localhost:8000`.
- Секреты: `make secrets` создаёт `.env` из `.env.example` (пустые значения заполняются `secrets.token_urlsafe(32)`) и `secrets/kek_keyset.json` (Tink AES256_GCM, JSON). Существующие файлы не перезаписываются: новый KEK сделал бы документы нечитаемыми. Файл KEK монтируется в api как compose secret, путь в `KEK_KEYSET_PATH`.
- Роли БД (`infra/postgres/init/01-roles.sh`): `ma_owner` LOGIN и владелец базы (создаёт схему `app` и доверенные расширения в `public`), `ma_app` и `ma_worker` LOGIN NOBYPASSRLS, `ma_auth` NOLOGIN BYPASSRLS, `GRANT ma_auth TO ma_owner WITH INHERIT FALSE, SET TRUE`. У PUBLIC отозваны права на базу.
- MinIO: пользователь API `ma-api` с политикой только Get/Put/Delete объектов двух бакетов; бакеты без версионирования, анонимный доступ закрыт, `ma-quarantine` с жизненным циклом 1 день.
- `migrate` выполняет `alembic upgrade head`, только если есть `apps/api/alembic.ini`, иначе завершается с кодом 0.
- Цель `seed` не добавлена: появится в BE-17.

## Отклонения от задания

1. Официальные образы `minio/minio` и `minio/mc` больше не публикуются (Docker Hub: «repository does not exist», quay.io: unauthorized). Взят поддерживаемый форк `pgsty/minio` и `pgsty/mc` с закреплёнными тегами.
2. MinIO не поддерживает CORS на уровне бакета (`mc cors set` отвечает «A header you provided implies functionality that is not implemented»). Origin `http://localhost:${WEB_PORT}` разрешён глобально через `MINIO_API_CORS_ALLOW_ORIGIN`. Браузер обращается только к `ma-quarantine` (presigned POST); `ma-docs` без подписи отвечает 403.
3. Порт Postgres на хост не публикуется: 5432 занят другим проектом пользователя. Доступ: `docker compose exec db psql -U postgres -d medarchive`.
4. Порты хоста web и api настраиваются `WEB_PORT` и `API_PORT` (по умолчанию 3000 и 8000). На этой машине 3000 и 8000 заняты чужими контейнерами (`startup-jobs-frontend`, `mapgo-api-1`), поэтому проверка шла на 3300 и 8800.
5. `.gitignore`: правило `secrets/` заменено на `/secrets/`, иначе git и ruff не видели `infra/secrets/generate.py`.

## Проверка (команды и результат)

| Команда | Результат |
|---|---|
| `uv lock` в `apps/api` (Python 3.12) | 90 пакетов, все имена найдены на PyPI |
| `make lint` | ruff: All checks passed, 4 files formatted; eslint `--max-warnings 0` и prettier чисто |
| `make typecheck` | mypy strict: no issues in 4 files; `tsc --noEmit` web и e2e чисто |
| `make test` | pytest 1 passed (`test_healthz_returns_ok`); vitest 1 passed (`page.test.tsx`) |
| `make ci` | код 0 |
| `pnpm --filter web build` | Compiled successfully, `/` 102 kB First Load JS |
| `make images` | `medarchive/api:local` 305 MB, `medarchive/web:local` 224 MB |
| `make secrets` | создал `.env` и `secrets/kek_keyset.json` (оба 0600) |
| `WEB_PORT=3300 API_PORT=8800 docker compose up -d --build --wait` | все сервисы healthy, `migrate` и `minio-init` завершились с кодом 0 |
| `curl :8800/healthz` | `200 {"status":"ok"}` |
| `curl :3300/` | 200, `<html lang="ru">`, `viewport-fit=cover`, `<h1>Медархив</h1>` |
| `curl :3300/api/v1/session` | 404 `application/json` от FastAPI: прокси доходит до api |
| Шрифт из CSS сборки | 4 `@font-face` (`Medeo Sans`/`Medeo Mono` × latin/cyrillic), все 4 woff2 отдаются 200 `font/woff2`, размеры совпадают с исходными файлами, есть `<link rel=preload>` |
| CORS MinIO | preflight с `Origin: http://localhost:3300` получает `Access-Control-Allow-Origin`, с чужим origin нет |
| Роли БД | `pg_roles` и `pg_auth_members` как в разделе «Решения»; `ma_app` не может создать таблицу в `public` |
| Контейнеры | api `uid=10001`, web `uid=1000`, запись в `/app` отклонена (read-only), ключ KEK читается из `/run/secrets/kek_keyset` |
| MinIO | оба бакета un-versioned, правило `expire-raw-uploads` 1 день, `ma-api` пишет и читает в бакете, создать бакет не может; повторный запуск `minio-init` проходит |
| `E2E_BASE_URL=http://localhost:3300 make e2e` | 1 passed (Chromium) |
| `make fixtures` | 5 фикстур в `qa/fixtures/generated/` |
| shellcheck (образ `koalaman/shellcheck:stable`) | оба скрипта чисто |
| `docker compose down` | стек остановлен, тома сохранены |

## Риски и замечания для следующих блоков

- DDL `07-data-model.sql` падает под `ma_owner` на `ALTER FUNCTION app.resolve_session(bytea) OWNER TO ma_auth`: «permission denied for schema app». PostgreSQL требует у нового владельца право CREATE на схему, а DDL даёт `ma_auth` только USAGE. Всё до этой строки выполняется с ролями из init-скрипта (проверено прогоном с ROLLBACK). Исправление в миграции 0001 (блок 2, DB-02): например, временно выдать `CREATE ON SCHEMA app` роли `ma_auth` и отозвать после смены владельца.
- `eslint@9` помечен в npm как deprecated (актуальна 10), но `eslint-config-next@15` поддерживает только до 9.
- `pgsty/minio` это сторонний форк: цепочка поставки шире, чем у официального образа. Теги закреплены.
- Глобальный CORS MinIO (отклонение 2) шире требования «только карантин».
- Файл KEK смонтирован с правами 0600 хоста. На Docker Desktop для macOS контейнер его читает; на Linux uid 10001 может не прочитать файл другого владельца. В CI `compose up` не запускается.
- `apps/web/lib/api/schema.d.ts` сгенерирован из текущего `openapi.yaml` и закоммичен. После правок контракта нужно `make gen-api`.
- `next build` дописывает `allowJs: true` в `tsconfig.json`; оставлено как есть.

## Исправление: секреты api (10.11.2026, вечер)

Причина: `app/core/config.py` требует `CSRF_SECRET` и `PAGE_TOKEN_KEY` (`SecretStr`, не короче 32 символов; используются как UTF-8 строка для HMAC и HKDF), а compose их не передавал, и api не стартовал. Остальные обязательные настройки (`DATABASE_URL`, `REDIS_URL`, `S3_*`, `KEK_KEYSET_PATH`) уже были в окружении. `PAGE_TOKEN_KEY_PREVIOUS`, `TRUSTED_PROXIES` и прочие имеют значения по умолчанию. Воркеру (`WorkerSettings`) эти секреты не нужны.

Что изменено:

- `infra/secrets/generate.py`: в существующий `.env` дописываются ключи из `.env.example`, которых в нём нет (пустые значения заполняются `secrets.token_urlsafe(32)`, 43 символа). Имеющиеся строки и файл KEK не меняются. В вывод попадают только имена ключей.
- `.env.example`: `CSRF_SECRET`, `PAGE_TOKEN_KEY` с пояснением про ротацию через `PAGE_TOKEN_KEY_PREVIOUS`.
- `docker-compose.yml`: api получает `CSRF_SECRET` и `PAGE_TOKEN_KEY` (`:?run make secrets`).
- `docker-compose.yml`, worker: `healthcheck: { disable: true }` ломал `docker compose up --wait` («container ... has no healthcheck configured», Compose 2.29), а значит и `make up`. Теперь проверка открывает TCP-соединения к `db:5432` и `minio:9000`: это то, что нужно воркеру для очистки.
- `infra/minio/api-policy.json`: добавлен `s3:ListBucket` только на `ma-docs`. Без него шаг orphans воркера (`list_objects_v2` по `ws/`) падал с `purge_storage_unavailable`.

Проверка:

| Команда | Результат |
|---|---|
| `make secrets` на существующем `.env` | `added to .env: WEB_PORT, API_PORT, CSRF_SECRET, PAGE_TOKEN_KEY`; первые 17 строк побайтно совпадают с прежними, KEK не изменился, оба новых значения по 43 символа, права 0600 |
| повторный `make secrets` | `kept .env`, `kept secrets/kek_keyset.json` |
| генератор на чистой копии | `.env` создан, пустых значений нет |
| `COMPOSE_PROJECT_NAME=medarchive_found WEB_PORT=3500 API_PORT=8500 MINIO_PORT=9500 MINIO_CONSOLE_PORT=9501 IMAGE_TAG=found docker compose up -d --build --wait` | код 0, все сервисы healthy, `migrate` и `minio-init` код 0 |
| `curl :8500/healthz` | 200 `{"status":"ok"}` |
| `curl :8500/readyz` | 200 `{"status":"ok","checks":{"db":"ok","storage":"ok","kek":"ok"}}` |
| `curl :3500/api/v1/session` | 401 от api через прокси web |
| лог воркера после правки политики | `purge_finished`, `storage_failures: 0`; `ma-api` по-прежнему не может листать `ma-quarantine` |
| ruff, ruff format, mypy strict для `infra/` | чисто |
| `docker compose down -v` своего проекта, удаление образов `:found` | выполнено; чужие стеки `medarchive` и `medarchive_qa` не трогались |

Отклонение: порты 3300 и 8800 заняты запущенным стеком `medarchive` другого агента (а 3400/8900 стеком `medarchive_qa`), поэтому проверка шла на 3500/8500 с MinIO на 9500/9501.
