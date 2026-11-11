# Журнал гейтов по блокам

Официальный журнал выпуска. Каждый прогон пишет `tools/verify_block.sh N` (он же `make verify-block N=…`), агент QA & SECURITY-OPS дописывает дефекты. Гейт проверяет закоммиченный `HEAD` в отдельном git worktree (`/tmp/medarchive-gate`) и в отдельном compose-проекте `medarchive_qa` (web :3400, api :8900, minio :9400 и :9401, образы `medarchive/*:qa`), поэтому незакоммиченные правки других агентов и их стеки на :3300 и :8800 на результат не влияют. Порядок работы, теги и соглашения: `docs/progress/qa.md`.

## Что проверяет гейт

Гейт блока N включает проверки блоков 1..N. Шаг с «Блокирует: нет» записывается, но на итог не влияет: до блока 7 так идут аудит зависимостей, Trivy, gitleaks, schemathesis, проверка ПДн, ZAP и жёсткость образов.

| Блок | Что добавляется | Обязательные TC |
|---|---|---|
| 1 | `make lint`, `make typecheck`, `make test` (pytest и vitest с отчётами JUnit), `pnpm --filter web build`, `docker compose up --wait` и все сервисы healthy, E2E `@b1` (смоук, SEC-01, SEC-02) на Chromium 1440 x 900 и WebKit iPhone 13 | нет |
| 2 | Тесты БД, миграции `upgrade head`, `downgrade base`, `upgrade head` на PostgreSQL 17 и 18 (`tools/check_migrations.sh`), контракт каталога ошибок (pytest с `catalog` в имени), UI unit-тесты из `apps/web/components`, `app.openapi()` против `openapi.yaml` с `CONTRACT_BLOCK=2` | TC-091, TC-092 |
| 3 | E2E и API `@b3`, schemathesis по операциям блоков 1..3 | TC-001..TC-004, TC-093 |
| 4 | E2E и API `@b4`, проверка ПДн в логах и дампе БД | TC-010..TC-024 |
| 5 | E2E и API `@b5`, ZAP baseline | TC-030..TC-044, TC-044b, TC-050, TC-057, TC-085, TC-090 |
| 6 | E2E и API `@b6` | TC-051..TC-060, TC-070..TC-084 |
| 7 | Все шаги блокируют: schemathesis `--checks all`, pip-audit, `pnpm audit --prod` (high и critical), gitleaks, Trivy образов приложения и базовых образов (fixable HIGH и CRITICAL = 0), жёсткость образов и ролей БД (OPS-05, OPS-07), ПДн (TC-096), ZAP baseline без High, k6 p95 `GET /documents` < 300 мс при 1000 документов и 50 VU; E2E три прогона подряд (`--repeat-each=3`) | все P0 и P1 в объёме (45 P0: в каталоге 46, TC-104 вне объёма по ADR-042; TC-100..TC-103 тоже вне объёма), в том числе TC-094..TC-099, TC-110..TC-115 |
| 9 | Выпуск: весь набор ещё раз, TC-080 и TC-081, протокол QA-07 (`docs/release-report.md`) | как в блоке 7 и TC-080, TC-081 |

E2E идёт в две фазы (D-006): сначала все тесты блоков 1..N с `RATE_LIMITS_ENABLED=false` (каждый тест создаёт свой архив с одного адреса), затем TC-082 и TC-098 по одному с лимитами по умолчанию; schemathesis и k6 идут в первой фазе (иначе 429 закрывает логику операций), проверка ПДн и ZAP во второй. Перед каждой фазой Redis стенда очищается: в нём только счётчики лимитов.

Браузер E2E ходит на стенд через профиль `tls` (Caddy, `https://localhost:3444`, хранилище `https://localhost:9444`): WebKit в Playwright не сохраняет `Secure`-cookie `__Host-ma_sid` на `http://localhost` (запрос FRONTEND-SCREENS, запасной вариант ADR-048). API-тесты и schemathesis идут на api :8900 напрямую.

TC считается пройденным, если есть хотя бы один тест с его ID в имени и все такие тесты зелёные. Пропущенный тест (`skip`, `fixme`) или его отсутствие в обязательном блоке означает FAIL гейта, а не PASS.

## Блок 1

#### Прогон 10.11.2026 22:33 MSK, `5fb9fe3`: FAIL

Коммит `5fb9fe3` «ci(OPS-04): make gate scripts executable». Стек `medarchive_qa` (web :3400, api :8900, minio :9400), логи `/tmp/medarchive-gate-logs/20261110-2228-5fb9fe3-b1`. Команда `tools/verify_block.sh 1`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | fail | exit 1; лог `01-deps-pnpm-install.log` | 7 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 1 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 78 |
| make lint | да | fail | exit 2; лог `05-make-lint.log` | 1 |
| make typecheck | да | fail | exit 2; лог `06-make-typecheck.log` | 13 |
| make test: pytest | да | pass | 187 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-pytest.log` | 10 |
| make test: vitest | да | fail | 0 passed, 0 failed, 0 skipped (exit 1); лог `08-make-test-vitest.log` | 4 |
| web build | да | fail | exit 1; лог `09-web-build.log` | 4 |
| compose up, all services healthy | да | fail | exit 1, образ web не собрался (D-001); лог `10-compose-up-all-services-healthy.log` | 46 |
| stack checks: hardening, e2e, contract, PII, ZAP, k6 | да | not run | stack is not healthy | 0 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `12-pip-audit-ops-04.log` | 11 |
| pnpm audit --prod (OPS-04) | нет | fail | info 0, low 0, moderate 2, high 2, critical 0; лог `13-pnpm-audit-prod-ops-04.log` | 5 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `14-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `15-trivy-medarchive-api-qa-ops-04-ops-05.log` | 79 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | fail | no report (exit 2): образа нет, сборка web упала (D-001); лог `16-trivy-medarchive-web-qa-ops-04-ops-05.log` | 3 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `17-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 2 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `18-trivy-node-22-alpine-ops-04-ops-05.log` | 13 |

E2E-тесты блоков после 1 (pending, не запускались): не посчитаны, E2E не запускался.

Итог: каркас блока 1 на этом HEAD не собирается из чистой копии из-за коммитов блока 2 (D-001, D-002). Локальные зелёные прогоны агентов шли по рабочему дереву, где исправления есть, но не закоммичены. Повторный прогон после исправления.

#### Прогон 10.11.2026 23:26 MSK, `c251a5e`: FAIL

Коммит `c251a5e` «docs(progress): backend documents results, decisions and open requests». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261110-2315-c251a5e-b1`. Команда `tools/verify_block.sh 1`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 2 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 1 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | fail | exit 2; лог `05-make-lint.log` | 0 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 15 |
| make test: pytest | да | fail | 241 passed, 194 failed, 0 skipped (exit 1); лог `07-make-test-pytest.log` | 31 |
| make test: vitest | да | pass | 248 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-vitest.log` | 12 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 46 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 426 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `12-api-with-rate-limits-enabled-false.log` | 4 |
| e2e @b[1-1]\b, limits off | да | pass | 5 passed, 0 failed, 0 skipped (exit 0); лог `13-e2e-b-1-1-b-limits-off.log` | 7 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `14-api-with-rate-limits-enabled-true.log` | 18 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `15-pip-audit-ops-04.log` | 6 |
| pnpm audit --prod (OPS-04) | нет | fail | info 0, low 0, moderate 2, high 2, critical 0; лог `16-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `17-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `18-trivy-medarchive-api-qa-ops-04-ops-05.log` | 25 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 2 ['CVE-2026-45623', 'CVE-2026-73646']; лог `19-trivy-medarchive-web-qa-ops-04-ops-05.log` | 23 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `20-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 4 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `21-trivy-node-22-alpine-ops-04-ops-05.log` | 2 |

E2E-тесты блоков после 1 (pending, не запускались): 189.

Итог: FAIL. `make lint` красный из-за D-010. 194 падения pytest вызвал сам гейт, а не код: Ryuk из Testcontainers монтирует сокет Docker по пути `~/.docker/run/docker.sock`, который Docker Desktop для macOS смонтировать не может (`mkdir … operation not supported`); исправлено в `36acdc6` (`TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE` в Makefile, гейт вызывает `make test-api`), проверено на TC-091 для PostgreSQL 17 и 18. Trivy образа web: 2 HIGH в `postcss@8.4.31`, это D-003 в рабочем образе; находок npm больше нет (D-004 подтверждён). Стек через https, жёсткость образов и E2E блока 1 (5 из 5) зелёные.

#### Прогон 11.11.2026 00:08 MSK, `b748c48`: PASS

Коммит `b748c48` «ci(QA-04): gate children do not inherit API stack settings». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0001-b748c48-b1`. Команда `tools/verify_block.sh 1`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 1 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 4 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 10 |
| make test-api (pytest) | да | pass | 599 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 159 |
| make test-web (vitest) | да | pass | 248 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 9 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 27 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 56 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `12-api-with-rate-limits-enabled-false.log` | 16 |
| e2e @b[1-1]\b, limits off | да | pass | 5 passed, 0 failed, 0 skipped (exit 0); лог `13-e2e-b-1-1-b-limits-off.log` | 6 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `14-api-with-rate-limits-enabled-true.log` | 18 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `15-pip-audit-ops-04.log` | 4 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `16-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `17-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `18-trivy-medarchive-api-qa-ops-04-ops-05.log` | 47 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `19-trivy-medarchive-web-qa-ops-04-ops-05.log` | 2 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `20-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 1 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `21-trivy-node-22-alpine-ops-04-ops-05.log` | 1 |

E2E-тесты блоков после 1 (pending, не запускались): 220.

### Дефекты

| ID | Класс | Владелец | Что | Шаги | Ожидаемо | Фактически | Статус |
|---|---|---|---|---|---|---|---|
| D-001 | блокирует гейт | FRONTEND-FOUNDATION | Lock-файл нарушает политику `minimumReleaseAge` pnpm 12: `@testing-library/user-event@14.6.9` опубликован 10.11.2026 03:46 UTC, моложе суток | Чистый `git worktree` на `5fb9fe3`, `pnpm install --frozen-lockfile`; то же делает `RUN pnpm install --frozen-lockfile --filter web` в `apps/web/Dockerfile` | Установка и сборка образа web проходят | `ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION`; падают `make setup`, `make lint` (web), `make typecheck`, vitest, `next build`, образ web, `compose up`. Пакет добавлен коммитом `11840b0`; исключение `minimumReleaseAgeExclude` лежит в рабочем дереве `pnpm-workspace.yaml` и не закоммичено. Предложение: закрепить предыдущую версию user-event вместо исключения (политика защищает от только что опубликованных пакетов, T15), либо закоммитить исключение вместе с lock-файлом | исправлено в `b524a9b` (зависимости закреплены в пределах политики, без исключения) |
| D-002 | блокирует гейт | BACKEND-DOCUMENTS | `ruff format --check` не проходит на закоммиченном `apps/api/app/modules/documents/listing.py:121` | `make lint` на `5fb9fe3` | Чисто | `1 file would be reformatted`; в рабочем дереве файл изменён, правка не закоммичена | исправлено в `5a9de70` |
| D-003 | OPS-04, блок 7 | FRONTEND-FOUNDATION | `pnpm audit --prod`: 2 high в `postcss`, который тянет `next` (`apps__web>next>postcss`): GHSA-6g55-p6wh-862q (`<=8.5.11`) и GHSA-r28c-9q8g-f849 (`<=8.5.17`), исправлено в `>=8.5.18`; ещё 2 moderate | `make audit-node` | 0 high и critical | high 2, moderate 2. Риск на практике низкий (PostCSS работает при сборке, исходники CSS свои), но гейт блока 7 блокирует. Предложение: `pnpm.overrides` `postcss: ">=8.5.18"` в корневом `package.json` или обновление `next`. Гейт `c251a5e`: та же `postcss@8.4.31` попадает в рабочий образ web (Trivy: CVE-2026-45623, CVE-2026-73646) | открыт |
| D-010 | блокирует гейт | BACKEND-CORE | `make lint` красный на HEAD: ruff PT011 `pytest.raises(OSError)` без `match` в `apps/api/tests/unit/test_crypto.py:97` (коммит `098533d`, BE-15, исправление D-007) | `make lint` на `c251a5e` | Чисто | `Found 1 error` | открыт |
| D-010 | блокирует гейт | BACKEND-CORE | `make lint` красный на HEAD: ruff PT011 `pytest.raises(OSError)` без `match` в `apps/api/tests/unit/test_crypto.py:97` (коммит `098533d`, BE-15, исправление D-007) | `make lint` на `c251a5e` | Чисто | `Found 1 error` | открыт |
| D-011 | окружение, блокирует E2E | BACKEND-CORE, BACKEND-DOCUMENTS, DB | Контейнеры Testcontainers не удаляются: 10.11.2026 23:40 запущено 40 (33 `pgsty/minio`, 5 `postgres:17-alpine`, 2 `redis:7-alpine`, возраст до 50 минут). Причина: прогоны с `TESTCONTAINERS_RYUK_DISABLED=true` (команда в `docs/progress/backend-core.md`), без Ryuk контейнер прерванной сессии живёт вечно | `docker ps --filter label=org.testcontainers=true`; `docker run --rm alpine free -m` | После `pytest` контейнеров нет | В ВМ Docker занято 6,8 из 7,8 ГБ, swap заполнен; ядро убивает по OOM `api` и `minio` стенда гейта посреди E2E (`OOMKilled=true`, exit 137), отсюда `storage upload: 502` и `503 storage_unavailable` в тестах. Нужно: удалить свои контейнеры (`docker rm -f $(docker ps -q --filter label=org.testcontainers=true)`, когда ваши прогоны не идут) и запускать pytest через `make test-api` без отключения Ryuk: `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE` теперь задан в Makefile (`36acdc6`) | открыт |
| D-012 | флаки-тест | BACKEND-CORE | `apps/api/tests/unit/test_security.py:35`: `assert not csrf_valid(SECRET, session_id, token[:-1] + "A")` падает, когда случайный токен уже кончается на `A` (вероятность 1/64): подмены нет, сравнивается тот же токен. Код `csrf_valid` верен (`hmac.compare_digest` по строке целиком) | Гейт `e3cdd4a`, `make test-api` | Тест всегда зелёный | `AssertionError: assert not True`. Нужно менять последний символ на заведомо другой | открыт |
| D-004 | OPS-05, блок 7 | QA & SECURITY-OPS | Trivy `node:22-alpine`: 10 находок HIGH с исправлением, все в npm, который лежит в образе (`/usr/local/lib/node_modules/npm`: brace-expansion, ip-address, pacote, picomatch, sigstore). Рабочему образу web npm, npx, corepack и yarn не нужны | `make trivy IMAGE=node:22-alpine` | 0 fixable HIGH | 9 уникальных CVE HIGH | закрыт: гейт `c251a5e` не нашёл находок npm в `medarchive/web:qa`. Исправлено в рабочей стадии `apps/web/Dockerfile` (удалены npm, npx, corepack, yarn); проверено сборкой той же стадии отдельно: Trivy 0 fixable HIGH и CRITICAL, `node -v` v22.23.4, uid 1000. Полный образ web проверит следующий гейт после D-001. Сырые базовые образы гейт показывает, но не блокирует |

## Блок 2

#### Прогон 11.11.2026 00:14 MSK, `b748c48`: FAIL

Коммит `b748c48` «ci(QA-04): gate children do not inherit API stack settings». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0008-b748c48-b2`. Команда `tools/verify_block.sh 2`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 0 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 7 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 21 |
| make test-api (pytest) | да | fail | 445 passed, 155 failed, 0 skipped (exit 2); лог `07-make-test-api-pytest.log` | 140 |
| make test-web (vitest) | да | pass | 248 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 10 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 29 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 43 |
| UI unit tests (FE-03..FE-09) | да | pass | 99 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 5 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 7 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 15 |
| e2e @b[1-2]\b, limits off | да | pass | 5 passed, 0 failed, 0 skipped (exit 0); лог `17-e2e-b-1-2-b-limits-off.log` | 9 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `18-api-with-rate-limits-enabled-true.log` | 44 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `19-pip-audit-ops-04.log` | 3 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `20-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `21-gitleaks-git-history-ops-04.log` | 8 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `22-trivy-medarchive-api-qa-ops-04-ops-05.log` | 15 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `23-trivy-medarchive-web-qa-ops-04-ops-05.log` | 4 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `24-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 2 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `25-trivy-node-22-alpine-ops-04-ops-05.log` | 2 |

| TC | Итог | Тесты |
|---|---|---|
| TC-091 | нет теста | - |
| TC-092 | нет теста | - |

E2E-тесты блоков после 2 (pending, не запускались): 220.

Итог: FAIL, но вердикт TC неверный по вине гейта: шаблон TC не находил `test_tc091_…` (подчёркивание перед `tc`), а тесты TC-091 и TC-092 есть (`apps/api/tests/db`, прогон блока 1 на том же коммите: все зелёные). Исправлено в следующем коммите гейта. 155 ошибок setup интеграционных тестов: MinIO из Testcontainers не опубликовал порт 9000 вовремя (D-013). Миграции на PostgreSQL 17 и 18, контракт каталога ошибок и UI unit-тесты зелёные.

#### Прогон 11.11.2026 00:23 MSK, `f38a771`: PASS

Коммит `f38a771` «docs(QA-08): block 1 gate PASS on b748c48; block 2 run annotated, TC pattern fixed, D-013». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0015-f38a771-b2`. Команда `tools/verify_block.sh 2`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 1 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 9 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 18 |
| make test-api (pytest) | да | pass | 606 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 203 |
| make test-web (vitest) | да | pass | 249 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 8 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 23 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 97 |
| UI unit tests (FE-03..FE-09) | да | pass | 100 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 5 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 6 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 14 |
| e2e @b[1-2]\b, limits off | да | pass | 5 passed, 0 failed, 0 skipped (exit 0); лог `17-e2e-b-1-2-b-limits-off.log` | 5 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `18-api-with-rate-limits-enabled-true.log` | 14 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `19-pip-audit-ops-04.log` | 6 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `20-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `21-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `22-trivy-medarchive-api-qa-ops-04-ops-05.log` | 12 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `23-trivy-medarchive-web-qa-ops-04-ops-05.log` | 4 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `24-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 0 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `25-trivy-node-22-alpine-ops-04-ops-05.log` | 0 |

| TC | Итог | Тесты |
|---|---|---|
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |

E2E-тесты блоков после 2 (pending, не запускались): 220.

### Дефекты

| ID | Класс | Владелец | Что | Шаги | Ожидаемо | Фактически | Статус |
|---|---|---|---|---|---|---|---|
| D-011 | окружение, ломает E2E всех стеков | BACKEND-CORE, BACKEND-DOCUMENTS, DB | Утечка контейнеров Testcontainers: 10.11.2026 23:40 запущено 40 контейнеров с меткой `org.testcontainers=true` (33 `pgsty/minio`, 5 `postgres:17-alpine`, 2 `redis:7-alpine`), старшим около 50 минут. Фикстуры сессии останавливают контейнер только при нормальном завершении pytest, а прогоны идут с `TESTCONTAINERS_RYUK_DISABLED=true` (`docs/progress/backend-core.md`), поэтому прерванный прогон оставляет контейнеры навсегда | `docker ps --filter label=org.testcontainers=true`; `docker run --rm alpine free -m` | После прогонов контейнеров Testcontainers нет | В виртуальной машине Docker 6,8 из 7,8 ГБ занято, swap 1 из 1 ГБ; ядро убивает по OOM `api` и `minio` стенда E2E (`OOMKilled=true`, код 137) посреди прогона, тесты падают с 502 и 503 `storage_unavailable`. Ryuk на этой машине не помогает: с сокетом виртуальной машины его порт 8080 под нагрузкой не публикуется вовремя (`Port mapping … 8080 is not available`, затем конфликт имени `testcontainers-ryuk-…`; гейт `e3cdd4a`: 255 ошибок setup), поэтому с `TESTCONTAINERS_RYUK_DISABLED=true` в Makefile работаем без него. Нужно: не прерывать прогоны pytest (фикстуры останавливают контейнеры при нормальном завершении), гонять тесты через `make test-api`; когда ни один прогон не идёт, убрать утёкшие: `docker rm -f $(docker ps -q --filter label=org.testcontainers=true)`. Чужие контейнеры агент QA не останавливает | открыт |
| D-013 | флаки окружения | BACKEND-DOCUMENTS | `apps/api/tests/integration/conftest.py`, `_start_minio`: на Docker Desktop под нагрузкой порт 9000 контейнера MinIO публикуется с задержкой; после `STARTUP_ATTEMPTS` попыток фикстура сессии падает, и все интеграционные тесты получают ошибку setup | Гейт блока 2 на `b748c48` (`make test-api`) | Интеграционные тесты стабильны | 155 ошибок `ConnectionError: Port mapping for container … and port 9000 is not available`; на том же коммите в прогоне блока 1 тех же ошибок не было. Предложение: ждать публикации порта с таймаутом (опрос `get_exposed_port`), а не пересоздавать контейнер | открыт |

## Блок 3

#### Прогон 11.11.2026 00:27 MSK, `b7d2fa7`: FAIL

Коммит `b7d2fa7` «docs(BE-11): CSV type column is the Russian type name; owner decisions recorded». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0023-b7d2fa7-b3`. Команда `tools/verify_block.sh 3`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 0 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 4 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 11 |
| make test-api (pytest) | да | pass | 612 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 99 |
| make test-web (vitest) | да | pass | 249 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 7 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 21 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 41 |
| UI unit tests (FE-03..FE-09) | да | pass | 100 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 5 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 5 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 13 |
| e2e @b[1-3]\b, limits off | да | fail | 27 passed, 2 failed, 0 skipped (exit 1); лог `17-e2e-b-1-3-b-limits-off.log` | 12 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `18-api-with-rate-limits-enabled-true.log` | 13 |
| schemathesis --checks all | нет | pass | 7 passed, 0 failed, 0 skipped (exit 0); лог `19-schemathesis-checks-all.log` | 4 |
| schemathesis --checks all, session-ending | нет | pass | 1 passed, 0 failed, 0 skipped (exit 0); лог `20-schemathesis-checks-all-session-ending.log` | 1 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `21-pip-audit-ops-04.log` | 1 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `22-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `23-gitleaks-git-history-ops-04.log` | 0 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `24-trivy-medarchive-api-qa-ops-04-ops-05.log` | 0 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `25-trivy-medarchive-web-qa-ops-04-ops-05.log` | 0 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `26-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 0 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `27-trivy-node-22-alpine-ops-04-ops-05.log` | 0 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-002 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-003 | pass | e2e:api passed, pytest passed |
| TC-004 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |
| TC-093 | pass | e2e:api passed, pytest passed, vitest passed |

E2E-тесты блоков после 3 (pending, не запускались): 196.

Итог: FAIL только из-за D-009: тест `QA-07 policy page has no internal references` на обоих проектах находит служебную пометку в `/policy`. Все обязательные TC блоков 1..3 зелёные, в том числе TC-002 на WebKit через https; schemathesis `--checks all` по операциям блоков 1..3 без замечаний (8 операций).

### Дефекты

| ID | Класс | Владелец | Что | Шаги | Ожидаемо | Фактически | Статус |
|---|---|---|---|---|---|---|---|
| D-008 | блокирует гейты 2..7 | BACKEND-CORE | Закоммиченный `apps/api/app/main.py` остался каркасом блока 1: в нём только `GET /healthz`, роутеры модулей (`auth`, `workspace`, `uploads`, `documents`, `exports`) и `/readyz` не подключены; `create_app` из коммита `e4e30ae` в `main.py` на HEAD нет, правка лежит в рабочем дереве | Стек из чистого worktree `62fe880` (`medarchive_qa`), `curl :8900/readyz`, `POST :3400/api/v1/workspaces` с согласием | 200 и 201 | 404 `{"detail":"Not Found"}` на обоих; экран D01 не рисуется (в DOM только шапка и пустой `alert`), потому что `GET /api/v1/session` отвечает 404, а не 401 | исправлено в `82e87c4`, проверит гейт |
| D-009 | К3, текст | SPEC | Страница `/policy` показывает пользователю служебную пометку из `docs/policy.md`: «Статус: новый текст, требует утверждения владельцем. Текст написан для прототипа, который запускается через `docker compose`… (ADR-040)… (`08-security-privacy.md`, раздел 6; OPS-11)» | `https://localhost:3444/policy`, тест `QA-07 policy page has no internal references` (`e2e/tests/regression/texts.spec.ts`) | В тексте для пользователя нет ссылок на ADR, OPS, внутренние файлы и `docker compose`; термины защиты (Google Tink, AES-256-GCM, PostgreSQL Row Level Security) допустимы | Тест находит `docker`, `compose`, `ADR`, `OPS`, `security`, `privacy`, `md`. Пометку убрать из самого `docs/policy.md`, а не из вёрстки: `consents.evidence_sha256` считается от байтов файла (`docs/texts.md`, раздел 5) | открыт |

## Блок 4

#### Прогон 11.11.2026 01:18 MSK, `1ccbebb`: FAIL

Коммит `1ccbebb` «docs(QA-08): block 2 gate PASS on f38a771, block 3 FAIL on D-009 only». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0027-1ccbebb-b4`. Команда `tools/verify_block.sh 4`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 0 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 0 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 4 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 12 |
| make test-api (pytest) | да | pass | 615 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 159 |
| make test-web (vitest) | да | pass | 249 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 11 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 25 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 55 |
| UI unit tests (FE-03..FE-09) | да | pass | 100 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 18 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 10 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 2 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 23 |
| e2e @b[1-4]\b, limits off | да | fail | 43 passed, 12 failed, 0 skipped (exit 1); лог `17-e2e-b-1-4-b-limits-off.log` | 1120 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `18-api-with-rate-limits-enabled-true.log` | 14 |
| schemathesis --checks all | нет | fail | 10 passed, 1 failed, 0 skipped (exit 1); лог `19-schemathesis-checks-all.log` | 5 |
| schemathesis --checks all, session-ending | нет | pass | 1 passed, 0 failed, 0 skipped (exit 0); лог `20-schemathesis-checks-all-session-ending.log` | 1 |
| PII scan: logs and DB dump (TC-096) | нет | pass | 19 markers; in logs 0, in DB plaintext 0, dump 238750 bytes | 0 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `22-pip-audit-ops-04.log` | 4 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `23-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `24-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `25-trivy-medarchive-api-qa-ops-04-ops-05.log` | 1 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `26-trivy-medarchive-web-qa-ops-04-ops-05.log` | 0 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `27-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 0 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `28-trivy-node-22-alpine-ops-04-ops-05.log` | 0 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-002 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-003 | pass | e2e:api passed, pytest passed |
| TC-004 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-010 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, pytest passed, vitest passed |
| TC-011 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, pytest passed |
| TC-012 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, pytest passed, vitest passed |
| TC-013 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, pytest passed, vitest passed |
| TC-014 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, pytest passed, vitest passed |
| TC-015 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, pytest passed, vitest passed |
| TC-016 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, pytest passed, vitest passed |
| TC-017 | pass | pytest passed |
| TC-018 | pass | pytest passed |
| TC-019 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-020 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, vitest passed |
| TC-021 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, vitest passed |
| TC-022 | pass | e2e:api passed, pytest passed |
| TC-023 | pass | e2e:api passed, pytest passed |
| TC-024 | pass | e2e:api passed, pytest passed |
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |
| TC-093 | pass | e2e:api passed, pytest passed, vitest passed |

E2E-тесты блоков после 4 (pending, не запускались): 170.

Итог: FAIL. Все 9 падений WebKit (TC-010..TC-016, TC-020, TC-021) из-за D-014: тесты ждут клика по «Добавить PDF» 120 с. Падение schemathesis ST202 на `POST /api/v1/documents` (422 `idempotency_key_reused`) вызвал хук гейта: генератор повторил ключ с другим телом, API ответил верно; хук теперь даёт каждому случаю свой ключ, schemathesis идёт без лимитов. Политика `/policy`: D-009. Проверка ПДн (TC-096): 19 маркеров, в логах 0, открытым текстом в дампе БД 0.

### Дефекты

| ID | Класс | Владелец | Что | Шаги | Ожидаемо | Фактически | Статус |
|---|---|---|---|---|---|---|---|
| D-014 | К2, мобильный | FRONTEND-SCREENS | iPhone 13 (WebKit, 390 x 664), архив создан, документов 0: закреплённая кнопка «Добавить PDF» видна, но её перекрывает `<main>` онбординга M01 (`span.col-start-1.row-start-1` внутри `main.mx-auto.grid` перехватывает касание) | Гейт блока 4 на `1ccbebb`, `e2e/tests/screens/upload.spec.ts` на `webkit-iphone13`; трасса `e2e-b-1-4-b-limits-off/artifacts/screens-upload-…-webkit-iphone13/trace.zip` | Касание открывает «Новый документ» | Playwright 120 с повторяет клик: `<span class="col-start-1 row-start-1 …"> from <main …> subtree intercepts pointer events`; 9 тестов загрузки на WebKit падают по таймауту. На Chromium 1440 x 900 те же тесты зелёные | открыт |

## Блок 5

#### Прогон 11.11.2026 02:53 MSK, `84c2739`: FAIL

Коммит `84c2739` «test(FE-13): light and dark screenshots of every screen, desktop and phone». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0118-84c2739-b5`. Команда `tools/verify_block.sh 5`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 0 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 4 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 11 |
| make test-api (pytest) | да | pass | 618 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 115 |
| make test-web (vitest) | да | pass | 249 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 7 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 22 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 83 |
| UI unit tests (FE-03..FE-09) | да | pass | 100 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 5 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 4 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 13 |
| e2e @b[1-5]\b, limits off | да | fail | 107 passed, 3 failed, 0 skipped (exit 1); лог `17-e2e-b-1-5-b-limits-off.log` | 81 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `18-api-with-rate-limits-enabled-true.log` | 15 |
| schemathesis --checks all | нет | fail | 12 passed, 2 failed, 0 skipped (exit 1); лог `19-schemathesis-checks-all.log` | 5 |
| schemathesis --checks all, session-ending | нет | pass | 1 passed, 0 failed, 0 skipped (exit 0); лог `20-schemathesis-checks-all-session-ending.log` | 1 |
| PII scan: logs and DB dump (TC-096) | нет | pass | 19 markers; in logs 0, in DB plaintext 0, dump 2067258 bytes | 0 |
| ZAP baseline, no High | нет | pass | High []; Medium []; Low ['Cross-Origin-Resource-Policy Header Missing or Invalid', 'Permissions Policy Header Not Set', 'X-Content-Type-Options Header Missing']; лог `22-zap-baseline-no-high.log` | 49 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `23-pip-audit-ops-04.log` | 4 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `24-pnpm-audit-prod-ops-04.log` | 12 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `25-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `26-trivy-medarchive-api-qa-ops-04-ops-05.log` | 9 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `27-trivy-medarchive-web-qa-ops-04-ops-05.log` | 4 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `28-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 0 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `29-trivy-node-22-alpine-ops-04-ops-05.log` | 0 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-002 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-003 | pass | e2e:api passed, pytest passed |
| TC-004 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-010 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-011 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, e2e:webkit-iphone13 passed, pytest passed |
| TC-012 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-013 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-014 | fail | e2e:chromium-desktop failed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-015 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-016 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-017 | pass | pytest passed |
| TC-018 | pass | pytest passed |
| TC-019 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-020 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-021 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-022 | pass | e2e:api passed, pytest passed |
| TC-023 | pass | e2e:api passed, pytest passed |
| TC-024 | pass | e2e:api passed, pytest passed |
| TC-030 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-031 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-032 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-033 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-034 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-035 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-036 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-037 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-038 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-039 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-040 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-041 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-042 | pass | e2e:api passed, pytest passed |
| TC-043 | pass | e2e:api passed, pytest passed |
| TC-044 | pass | pytest passed |
| TC-044b | pass | vitest passed |
| TC-050 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-057 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-085 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-090 | pass | e2e:api passed, pytest passed |
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |
| TC-093 | pass | e2e:api passed, pytest passed, vitest passed |

E2E-тесты блоков после 5 (pending, не запускались): 115.

Итог: FAIL. E2E 107 из 110: таймауты TC-011 (WebKit, 120 с), TC-014 (Chromium, beforeEach 120 с) и a11y D08 (WebKit, beforeEach 30 с), все на этапе сида архива, под нехваткой памяти Docker VM (D-011); повтор нужен после очистки утёкших контейнеров. D-014 по этому прогону исправлен: остальные тесты загрузки на WebKit зелёные. Два ST202 schemathesis (`idempotency_key_reused` на `uploads.create` и `documents.create`) вызвал хук гейта; исправление `7d2e811` в этот коммит не вошло. ZAP baseline: High 0, Medium 0, Low 3 (`Cross-Origin-Resource-Policy`, `Permissions-Policy`, `X-Content-Type-Options` на части ответов). Проверка ПДн: 0 из 19 маркеров в логах и дампе 2 МБ.

#### Прогон 11.11.2026 06:47 MSK, `b2920da`: PASS

Коммит `b2920da` «ci(QA-04): gate keeps the Mac awake and marks steps the host slept through». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0640-b2920da-b5`. Команда `tools/verify_block.sh 5`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 0 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 0 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 4 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 12 |
| make test-api (pytest) | да | pass | 618 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 116 |
| make test-web (vitest) | да | pass | 249 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 7 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 22 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 43 |
| UI unit tests (FE-03..FE-09) | да | pass | 100 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 8 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 6 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 13 |
| e2e @b[1-5]\b, limits off | да | pass | 110 passed, 0 failed, 0 skipped (exit 0); лог `17-e2e-b-1-5-b-limits-off.log` | 79 |
| schemathesis --checks all | нет | fail | 10 passed, 5 failed, 0 skipped (exit 1); лог `18-schemathesis-checks-all.log` | 13 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `19-api-with-rate-limits-enabled-true.log` | 14 |
| PII scan: logs and DB dump (TC-096) | нет | pass | 19 markers; in logs 0, in DB plaintext 0, dump 2397829 bytes | 0 |
| ZAP baseline, no High | нет | pass | High []; Medium []; Low ['Cross-Origin-Embedder-Policy Header Missing or Invalid', 'Cross-Origin-Opener-Policy Header Missing or Invalid', 'Cross-Origin-Resource-Policy Header Missing or Invalid', 'Permissions Policy Header Not Set', 'X-Content-Type-Options Header Missing']; лог `21-zap-baseline-no-high.log` | 46 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `22-pip-audit-ops-04.log` | 6 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `23-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `24-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `25-trivy-medarchive-api-qa-ops-04-ops-05.log` | 1 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `26-trivy-medarchive-web-qa-ops-04-ops-05.log` | 1 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `27-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 1 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `28-trivy-node-22-alpine-ops-04-ops-05.log` | 1 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-002 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-003 | pass | e2e:api passed, pytest passed |
| TC-004 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-010 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-011 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-012 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-013 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-014 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-015 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-016 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-017 | pass | pytest passed |
| TC-018 | pass | pytest passed |
| TC-019 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-020 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-021 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-022 | pass | e2e:api passed, pytest passed |
| TC-023 | pass | e2e:api passed, pytest passed |
| TC-024 | pass | e2e:api passed, pytest passed |
| TC-030 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-031 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-032 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-033 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-034 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-035 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-036 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-037 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-038 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-039 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-040 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-041 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-042 | pass | e2e:api passed, pytest passed |
| TC-043 | pass | e2e:api passed, pytest passed |
| TC-044 | pass | pytest passed |
| TC-044b | pass | vitest passed |
| TC-050 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-057 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-085 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-090 | pass | e2e:api passed, pytest passed |
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |
| TC-093 | pass | e2e:api passed, pytest passed, vitest passed |

E2E-тесты блоков после 5 (pending, не запускались): 115.

### Дефекты

Нет.

## Блок 6

#### Прогон 11.11.2026 07:33 MSK, `b3fa3ab`: FAIL

Коммит `b3fa3ab` «perf(BE-07): filter document dates on list_key, an index range». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0723-b3fa3ab-b6`. Команда `tools/verify_block.sh 6`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 0 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 6 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 17 |
| make test-api (pytest) | да | pass | 661 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 212 |
| make test-web (vitest) | да | pass | 262 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 10 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 22 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 81 |
| UI unit tests (FE-03..FE-09) | да | pass | 112 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 6 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 5 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 13 |
| e2e @b[1-6]\b, limits off | да | fail | 163 passed, 2 failed, 0 skipped (exit 1); лог `17-e2e-b-1-6-b-limits-off.log` | 119 |
| schemathesis --checks all | нет | pass | 20 passed, 0 failed, 0 skipped (exit 0); лог `18-schemathesis-checks-all.log` | 12 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `19-api-with-rate-limits-enabled-true.log` | 14 |
| e2e TC-082, TC-098, limits on | да | pass | 2 passed, 0 failed, 0 skipped (exit 0); лог `20-e2e-tc-082-tc-098-limits-on.log` | 6 |
| PII scan: logs and DB dump (TC-096) | нет | pass | 19 markers; in logs 0, in DB plaintext 0, dump 3771624 bytes | 0 |
| ZAP baseline, no High | нет | pass | High []; Medium []; Low ['Cross-Origin-Resource-Policy Header Missing or Invalid', 'Permissions Policy Header Not Set', 'X-Content-Type-Options Header Missing']; лог `22-zap-baseline-no-high.log` | 38 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `23-pip-audit-ops-04.log` | 5 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `24-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `25-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `26-trivy-medarchive-api-qa-ops-04-ops-05.log` | 7 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `27-trivy-medarchive-web-qa-ops-04-ops-05.log` | 4 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `28-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 1 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `29-trivy-node-22-alpine-ops-04-ops-05.log` | 1 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-002 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-003 | pass | e2e:api passed, pytest passed |
| TC-004 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-010 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-011 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-012 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-013 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-014 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-015 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-016 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-017 | pass | pytest passed |
| TC-018 | pass | pytest passed |
| TC-019 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-020 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-021 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-022 | pass | e2e:api passed, pytest passed |
| TC-023 | pass | e2e:api passed, pytest passed |
| TC-024 | pass | e2e:api passed, pytest passed |
| TC-030 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-031 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-032 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-033 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-034 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-035 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-036 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-037 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-038 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-039 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-040 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-041 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-042 | pass | e2e:api passed, pytest passed |
| TC-043 | pass | e2e:api passed, pytest passed |
| TC-044 | pass | pytest passed |
| TC-044b | pass | vitest passed |
| TC-050 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-051 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-052 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-053 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-054 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-055 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-056 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-057 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-058 | pass | e2e:api passed, pytest passed |
| TC-059 | pass | e2e:api passed, pytest passed |
| TC-060 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-070 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-071 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-072 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-073 | pass | pytest passed |
| TC-080 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-081 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-082 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-083 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-084 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-085 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-090 | pass | e2e:api passed, pytest passed |
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |
| TC-093 | pass | e2e:api passed, pytest passed, vitest passed |

E2E-тесты блоков после 6 (pending, не запускались): 66.

#### Прогон 11.11.2026 09:33 MSK, `132535e`: FAIL

Коммит `132535e` «docs(AGENTS): point UI copy to the journey and error catalog». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0932-132535e-b6`. Команда `tools/verify_block.sh 6`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 0 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 0 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 7 |
| make typecheck | да | fail | exit 2; лог `06-make-typecheck.log` | 1 |
| make test-api (pytest) | да | fail | 0 passed, 0 failed, 0 skipped (exit 2); лог `07-make-test-api-pytest.log` | 0 |
| make test-web (vitest) | да | fail | 0 passed, 0 failed, 0 skipped (exit 2); лог `08-make-test-web-vitest.log` | 0 |
| web build | да | fail | exit 1; лог `09-web-build.log` | 10 |
| compose up, all services healthy | да | fail | exit 15; no containers; лог `10-compose-up-all-services-healthy.log` | 0 |
| UI unit tests (FE-03..FE-09) | да | fail | 0 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | fail | 0 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 14 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 8 |
| stack checks: hardening, e2e, contract, PII, ZAP, k6 | да | not run | stack is not healthy | 0 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `16-pip-audit-ops-04.log` | 5 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `17-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `18-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `19-trivy-medarchive-api-qa-ops-04-ops-05.log` | 25 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `20-trivy-medarchive-web-qa-ops-04-ops-05.log` | 9 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `21-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 1 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `22-trivy-node-22-alpine-ops-04-ops-05.log` | 0 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | нет теста | - |
| TC-002 | нет теста | - |
| TC-003 | нет теста | - |
| TC-004 | нет теста | - |
| TC-010 | нет теста | - |
| TC-011 | нет теста | - |
| TC-012 | нет теста | - |
| TC-013 | нет теста | - |
| TC-014 | нет теста | - |
| TC-015 | нет теста | - |
| TC-016 | нет теста | - |
| TC-017 | нет теста | - |
| TC-018 | нет теста | - |
| TC-019 | нет теста | - |
| TC-020 | нет теста | - |
| TC-021 | нет теста | - |
| TC-022 | нет теста | - |
| TC-023 | нет теста | - |
| TC-024 | нет теста | - |
| TC-030 | нет теста | - |
| TC-031 | нет теста | - |
| TC-032 | нет теста | - |
| TC-033 | нет теста | - |
| TC-034 | нет теста | - |
| TC-035 | нет теста | - |
| TC-036 | нет теста | - |
| TC-037 | нет теста | - |
| TC-038 | нет теста | - |
| TC-039 | нет теста | - |
| TC-040 | нет теста | - |
| TC-041 | нет теста | - |
| TC-042 | нет теста | - |
| TC-043 | нет теста | - |
| TC-044 | нет теста | - |
| TC-044b | нет теста | - |
| TC-050 | нет теста | - |
| TC-051 | нет теста | - |
| TC-052 | нет теста | - |
| TC-053 | нет теста | - |
| TC-054 | нет теста | - |
| TC-055 | нет теста | - |
| TC-056 | нет теста | - |
| TC-057 | нет теста | - |
| TC-058 | нет теста | - |
| TC-059 | нет теста | - |
| TC-060 | нет теста | - |
| TC-070 | нет теста | - |
| TC-071 | нет теста | - |
| TC-072 | нет теста | - |
| TC-073 | нет теста | - |
| TC-080 | нет теста | - |
| TC-081 | нет теста | - |
| TC-082 | нет теста | - |
| TC-083 | нет теста | - |
| TC-084 | нет теста | - |
| TC-085 | нет теста | - |
| TC-090 | нет теста | - |
| TC-091 | нет теста | - |
| TC-092 | нет теста | - |
| TC-093 | нет теста | - |

E2E-тесты блоков после 6 (pending, не запускались): не посчитаны, E2E не запускался.

#### Прогон 11.11.2026 09:45 MSK, `132535e`: FAIL

Коммит `132535e` «docs(AGENTS): point UI copy to the journey and error catalog». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0935-132535e-b6`. Команда `tools/verify_block.sh 6`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 2 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 5 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 14 |
| make test-api (pytest) | да | pass | 661 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 218 |
| make test-web (vitest) | да | pass | 313 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 11 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 23 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 42 |
| UI unit tests (FE-03..FE-09) | да | pass | 122 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 4 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 5 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 13 |
| e2e @b[1-6]\b, limits off | да | fail | 172 passed, 3 failed, 0 skipped (exit 1); лог `17-e2e-b-1-6-b-limits-off.log` | 122 |
| schemathesis --checks all | нет | pass | 20 passed, 0 failed, 0 skipped (exit 0); лог `18-schemathesis-checks-all.log` | 18 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `19-api-with-rate-limits-enabled-true.log` | 15 |
| e2e TC-082, TC-098, limits on | да | pass | 2 passed, 0 failed, 0 skipped (exit 0); лог `20-e2e-tc-082-tc-098-limits-on.log` | 8 |
| PII scan: logs and DB dump (TC-096) | нет | pass | 19 markers; in logs 0, in DB plaintext 0, dump 3837533 bytes | 1 |
| ZAP baseline, no High | нет | pass | High []; Medium []; Low ['Cross-Origin-Embedder-Policy Header Missing or Invalid', 'Cross-Origin-Opener-Policy Header Missing or Invalid', 'Cross-Origin-Resource-Policy Header Missing or Invalid', 'Permissions Policy Header Not Set', 'X-Content-Type-Options Header Missing']; лог `22-zap-baseline-no-high.log` | 72 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `23-pip-audit-ops-04.log` | 1 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `24-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `25-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `26-trivy-medarchive-api-qa-ops-04-ops-05.log` | 1 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `27-trivy-medarchive-web-qa-ops-04-ops-05.log` | 5 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `28-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 0 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `29-trivy-node-22-alpine-ops-04-ops-05.log` | 0 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-002 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-003 | pass | e2e:api passed, pytest passed |
| TC-004 | fail | e2e:chromium-desktop passed, e2e:webkit-iphone13 failed, e2e:webkit-iphone13 passed, vitest passed |
| TC-010 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-011 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-012 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-013 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-014 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-015 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-016 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-017 | pass | pytest passed |
| TC-018 | pass | pytest passed |
| TC-019 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-020 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-021 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-022 | pass | e2e:api passed, pytest passed |
| TC-023 | pass | e2e:api passed, pytest passed |
| TC-024 | pass | e2e:api passed, pytest passed |
| TC-030 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-031 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-032 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-033 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-034 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-035 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-036 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-037 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-038 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-039 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-040 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-041 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-042 | pass | e2e:api passed, pytest passed |
| TC-043 | pass | e2e:api passed, pytest passed |
| TC-044 | pass | pytest passed |
| TC-044b | pass | vitest passed |
| TC-050 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-051 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-052 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-053 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-054 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-055 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-056 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-057 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-058 | pass | e2e:api passed, pytest passed |
| TC-059 | pass | e2e:api passed, pytest passed |
| TC-060 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-070 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-071 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-072 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-073 | pass | pytest passed |
| TC-080 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-081 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-082 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-083 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-084 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-085 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-090 | pass | e2e:api passed, pytest passed |
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |
| TC-093 | pass | e2e:api passed, pytest passed, vitest passed |

E2E-тесты блоков после 6 (pending, не запускались): 70.

#### Прогон 11.11.2026 09:54 MSK, `df33296`: FAIL

Коммит `df33296` «fix(FE-06): keep dialog content padding on the spacing scale». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-0948-df33296-b6`. Команда `tools/verify_block.sh 6`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 0 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 0 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 4 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 14 |
| make test-api (pytest) | да | pass | 662 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 253 |
| make test-web (vitest) | да | pass | 313 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 14 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 22 |
| compose up, all services healthy | да | fail | exit 1; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 46 |
| UI unit tests (FE-03..FE-09) | да | pass | 122 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 5 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 7 |
| stack checks: hardening, e2e, contract, PII, ZAP, k6 | да | not run | stack is not healthy | 0 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `16-pip-audit-ops-04.log` | 4 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `17-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `18-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `19-trivy-medarchive-api-qa-ops-04-ops-05.log` | 8 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `20-trivy-medarchive-web-qa-ops-04-ops-05.log` | 5 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `21-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 0 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `22-trivy-node-22-alpine-ops-04-ops-05.log` | 0 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | pass | vitest passed |
| TC-002 | pass | pytest passed, vitest passed |
| TC-003 | pass | pytest passed |
| TC-004 | pass | vitest passed |
| TC-010 | pass | pytest passed, vitest passed |
| TC-011 | pass | pytest passed |
| TC-012 | pass | pytest passed, vitest passed |
| TC-013 | pass | pytest passed, vitest passed |
| TC-014 | pass | pytest passed, vitest passed |
| TC-015 | pass | pytest passed, vitest passed |
| TC-016 | pass | pytest passed, vitest passed |
| TC-017 | pass | pytest passed |
| TC-018 | pass | pytest passed |
| TC-019 | pass | pytest passed, vitest passed |
| TC-020 | pass | vitest passed |
| TC-021 | pass | vitest passed |
| TC-022 | pass | pytest passed |
| TC-023 | pass | pytest passed |
| TC-024 | pass | pytest passed |
| TC-030 | pass | pytest passed |
| TC-031 | pass | pytest passed |
| TC-032 | pass | pytest passed, vitest passed |
| TC-033 | pass | pytest passed, vitest passed |
| TC-034 | pass | pytest passed |
| TC-035 | pass | pytest passed, vitest passed |
| TC-036 | pass | pytest passed |
| TC-037 | pass | pytest passed |
| TC-038 | pass | pytest passed |
| TC-039 | pass | pytest passed, vitest passed |
| TC-040 | pass | vitest passed |
| TC-041 | нет теста | - |
| TC-042 | pass | pytest passed |
| TC-043 | pass | pytest passed |
| TC-044 | pass | pytest passed |
| TC-044b | pass | vitest passed |
| TC-050 | pass | pytest passed |
| TC-051 | pass | vitest passed |
| TC-052 | pass | vitest passed |
| TC-053 | pass | vitest passed |
| TC-054 | нет теста | - |
| TC-055 | нет теста | - |
| TC-056 | нет теста | - |
| TC-057 | pass | pytest passed |
| TC-058 | pass | pytest passed |
| TC-059 | pass | pytest passed |
| TC-060 | нет теста | - |
| TC-070 | pass | pytest passed, vitest passed |
| TC-071 | pass | pytest passed, vitest passed |
| TC-072 | нет теста | - |
| TC-073 | pass | pytest passed |
| TC-080 | нет теста | - |
| TC-081 | нет теста | - |
| TC-082 | pass | pytest passed |
| TC-083 | pass | pytest passed |
| TC-084 | pass | pytest passed |
| TC-085 | нет теста | - |
| TC-090 | pass | pytest passed |
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |
| TC-093 | pass | pytest passed, vitest passed |

E2E-тесты блоков после 6 (pending, не запускались): не посчитаны, E2E не запускался.

#### Прогон 11.11.2026 10:13 MSK, `ee43a77`: PASS

Коммит `ee43a77` «style(FE-06): format dialog hand-off tests with Prettier». Стек `medarchive_qa` (браузер `https://localhost:3444`, api :8900), логи `/tmp/medarchive-gate-logs/20261111-1004-ee43a77-b6`. Команда `tools/verify_block.sh 6`.

| Шаг | Блокирует | Итог | Подробности | с |
|---|---|---|---|---|
| deps: pnpm install | да | pass | exit 0; лог `01-deps-pnpm-install.log` | 2 |
| deps: uv sync | да | pass | exit 0; лог `02-deps-uv-sync.log` | 0 |
| make fixtures | да | pass | exit 0; лог `03-make-fixtures.log` | 0 |
| playwright browsers | да | pass | exit 0; лог `04-playwright-browsers.log` | 1 |
| make lint | да | pass | exit 0; лог `05-make-lint.log` | 5 |
| make typecheck | да | pass | exit 0; лог `06-make-typecheck.log` | 12 |
| make test-api (pytest) | да | pass | 662 passed, 0 failed, 0 skipped (exit 0); лог `07-make-test-api-pytest.log` | 174 |
| make test-web (vitest) | да | pass | 315 passed, 0 failed, 0 skipped (exit 0); лог `08-make-test-web-vitest.log` | 12 |
| web build | да | pass | exit 0; лог `09-web-build.log` | 22 |
| compose up, all services healthy | да | pass | exit 0; api healthy, db healthy, migrate exited(0), minio healthy, minio-init exited(0), redis healthy, tls healthy, web healthy, worker healthy; лог `10-compose-up-all-services-healthy.log` | 73 |
| UI unit tests (FE-03..FE-09) | да | pass | 124 passed, 0 failed, 0 skipped (components/) | 0 |
| error catalog contract (BE-03) | да | pass | 3 passed, 0 failed, 0 skipped (catalog) | 0 |
| migrations up/down on PostgreSQL 17 | да | pass | PostgreSQL 17: upgrade head, downgrade base, upgrade head passed; лог `13-migrations-up-down-on-postgresql-17.log` | 4 |
| migrations up/down on PostgreSQL 18 | да | pass | PostgreSQL 18: upgrade head, downgrade base, upgrade head passed; лог `14-migrations-up-down-on-postgresql-18.log` | 4 |
| hardening (OPS-05, OPS-07) | нет | pass | medarchive/api:qa user=api healthcheck=yes; medarchive/web:qa user=node healthcheck=yes; api read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; web read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; migrate read_only=true cap_drop=[ALL] security_opt=[no-new-privileges:true]; api uid=10001; web uid=1000; api role=ma_app migrate role=ma_owner; app tables not owned | 1 |
| api with RATE_LIMITS_ENABLED=false | да | pass | exit 0; лог `16-api-with-rate-limits-enabled-false.log` | 14 |
| e2e @b[1-6]\b, limits off | да | pass | 175 passed, 0 failed, 0 skipped (exit 0); лог `17-e2e-b-1-6-b-limits-off.log` | 122 |
| schemathesis --checks all | нет | pass | 20 passed, 0 failed, 0 skipped (exit 0); лог `18-schemathesis-checks-all.log` | 17 |
| api with RATE_LIMITS_ENABLED=true | да | pass | exit 0; лог `19-api-with-rate-limits-enabled-true.log` | 15 |
| e2e TC-082, TC-098, limits on | да | pass | 2 passed, 0 failed, 0 skipped (exit 0); лог `20-e2e-tc-082-tc-098-limits-on.log` | 6 |
| PII scan: logs and DB dump (TC-096) | нет | pass | 19 markers; in logs 0, in DB plaintext 0, dump 3840328 bytes | 1 |
| ZAP baseline, no High | нет | pass | High []; Medium []; Low ['Cross-Origin-Embedder-Policy Header Missing or Invalid', 'Cross-Origin-Opener-Policy Header Missing or Invalid', 'Cross-Origin-Resource-Policy Header Missing or Invalid', 'Permissions Policy Header Not Set', 'X-Content-Type-Options Header Missing']; лог `22-zap-baseline-no-high.log` | 48 |
| pip-audit (OPS-04) | нет | pass | 52 packages, vulnerabilities []; лог `23-pip-audit-ops-04.log` | 4 |
| pnpm audit --prod (OPS-04) | нет | pass | info 0, low 0, moderate 0, high 0, critical 0; лог `24-pnpm-audit-prod-ops-04.log` | 1 |
| gitleaks, git history (OPS-04) | нет | pass | findings by rule [] (values redacted); лог `25-gitleaks-git-history-ops-04.log` | 1 |
| trivy medarchive/api:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `26-trivy-medarchive-api-qa-ops-04-ops-05.log` | 1 |
| trivy medarchive/web:qa (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `27-trivy-medarchive-web-qa-ops-04-ops-05.log` | 6 |
| trivy python:3.12-slim-bookworm (OPS-04, OPS-05) | нет | pass | fixable CRITICAL 0 [], HIGH 0 []; лог `28-trivy-python-3-12-slim-bookworm-ops-04-ops-05.log` | 0 |
| trivy node:22-alpine (OPS-04, OPS-05) | нет | fail | fixable CRITICAL 0 [], HIGH 9 ['CVE-2026-102276', 'CVE-2026-102278', 'CVE-2026-13149', 'CVE-2026-14257', 'CVE-2026-33671']; лог `29-trivy-node-22-alpine-ops-04-ops-05.log` | 0 |

| TC | Итог | Тесты |
|---|---|---|
| TC-001 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-002 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-003 | pass | e2e:api passed, pytest passed |
| TC-004 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-010 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-011 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-012 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-013 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-014 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-015 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-016 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-017 | pass | pytest passed |
| TC-018 | pass | pytest passed |
| TC-019 | pass | e2e:api passed, e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-020 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-021 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-022 | pass | e2e:api passed, pytest passed |
| TC-023 | pass | e2e:api passed, pytest passed |
| TC-024 | pass | e2e:api passed, pytest passed |
| TC-030 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-031 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-032 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-033 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-034 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-035 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-036 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-037 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-038 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-039 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-040 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-041 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-042 | pass | e2e:api passed, pytest passed |
| TC-043 | pass | e2e:api passed, pytest passed |
| TC-044 | pass | pytest passed |
| TC-044b | pass | vitest passed |
| TC-050 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-051 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-052 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-053 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, vitest passed |
| TC-054 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-055 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-056 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-057 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-058 | pass | e2e:api passed, pytest passed |
| TC-059 | pass | e2e:api passed, pytest passed |
| TC-060 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-070 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-071 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed, vitest passed |
| TC-072 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-073 | pass | pytest passed |
| TC-080 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-081 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-082 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-083 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-084 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed, pytest passed |
| TC-085 | pass | e2e:chromium-desktop passed, e2e:webkit-iphone13 passed |
| TC-090 | pass | e2e:api passed, pytest passed |
| TC-091 | pass | pytest passed |
| TC-092 | pass | pytest passed |
| TC-093 | pass | e2e:api passed, pytest passed, vitest passed |

E2E-тесты блоков после 6 (pending, не запускались): 70.

### Дефекты

Нет.

## Блок 7

### Дефекты

| ID | Класс | Владелец | Что | Шаги | Ожидаемо | Фактически | Статус |
|---|---|---|---|---|---|---|---|
| D-005 | К2, безопасность (T2, T11) | BACKEND-CORE, FRONTEND-FOUNDATION | Лимиты «на IP» (`workspaces` 10 в час, `login` 5 за 15 мин) считаются по `request.client.host` (`app/core/ratelimit.py`, `client_network`). Браузер ходит в API только через прокси Next.js (ADR-048), поэтому у всех пользователей один адрес: контейнер web | Ревью кода `0acde44`; воспроизведение на стенде: 10 `POST /api/v1/workspaces` из одного браузера, затем из другого | Каждый клиент тратит свой бюджет; TC-082 «с одного IP» | 11-й архив за час не может создать никто; 5 неверных ключей от одного человека блокируют вход всем на 15 минут. Нужно: API берёт адрес из `X-Forwarded-For` только от доверенного прокси (последний адрес, который дописал web), прокси Next его передаёт; тест с двумя разными `X-Forwarded-For` через web. BACKEND-CORE предлагает `--proxy-headers --forwarded-allow-ips=<адрес web>` в `CMD` образа api (`docs/progress/backend-core.md`, запросы, п. 2); нужен владелец правки образа и compose | исправлено в коде `fa14f11` (`TRUSTED_PROXIES`); проброс в compose `470c9be`, но значение по умолчанию пустое: какую сеть считать прокси web, решает BACKEND-CORE или FOUNDATION; без этого лимиты по-прежнему общие |
| D-006 | блокирует QA-04 и k6 | BACKEND-CORE | Лимиты нельзя настроить для стенда проверки | Гейт блока 3+: каждый E2E-тест создаёт свой архив (TZ-qa, раздел 3), все с 127.0.0.1; k6: 50 VU на одной сессии при `documents_list` 120 в минуту, сид 1000 документов при `uploads` 30 в минуту (около 34 минут) | E2E и k6 проверяют функции и время ответа, TC-082 и TC-098 проверяют лимиты | С 11-го теста `POST /workspaces` отвечает 429, k6 получает 429 вместо 200. Нужен параметр настроек, например `RATE_LIMITS_ENABLED` (по умолчанию включено): гейт прогоняет функциональные E2E и k6 без лимитов, а `@ratelimit` (TC-082, TC-098) со значениями по умолчанию. Проброс в `docker-compose.yml` добавлю после появления параметра | исправлено: `RATE_LIMITS_ENABLED` в `fa14f11`, проброс в compose `470c9be`; гейт гоняет функциональные E2E и k6 с `false`, TC-082 и TC-098 с `true`. Закрою после первого прогона гейта |
| D-007 | OPS-08 | BACKEND-CORE | Нет метрики ошибок KEK для алерта `KekErrors` (`infra/prometheus/alerts.yml`) | `rg kek_errors_total apps/api` | Счётчик `kek_errors_total{operation}` растёт при ошибке чтения файла KEK и `TinkError` при открытии связки ключей | Метрики нет; правило проверено только `promtool test rules` | исправлено в `098533d`, проверю на стеке гейта (`/metrics`) |

## Блок 9

### Дефекты

Нет.
