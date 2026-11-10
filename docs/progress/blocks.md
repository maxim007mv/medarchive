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

E2E идёт в две фазы (D-006): сначала все тесты блоков 1..N с `RATE_LIMITS_ENABLED=false` (каждый тест создаёт свой архив с одного адреса), затем TC-082 и TC-098 по одному с лимитами по умолчанию; k6 идёт в первой фазе, schemathesis, проверка ПДн и ZAP во второй. Перед каждой фазой Redis стенда очищается: в нём только счётчики лимитов.

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

### Дефекты

| ID | Класс | Владелец | Что | Шаги | Ожидаемо | Фактически | Статус |
|---|---|---|---|---|---|---|---|
| D-001 | блокирует гейт | FRONTEND-FOUNDATION | Lock-файл нарушает политику `minimumReleaseAge` pnpm 12: `@testing-library/user-event@14.6.9` опубликован 10.11.2026 03:46 UTC, моложе суток | Чистый `git worktree` на `5fb9fe3`, `pnpm install --frozen-lockfile`; то же делает `RUN pnpm install --frozen-lockfile --filter web` в `apps/web/Dockerfile` | Установка и сборка образа web проходят | `ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION`; падают `make setup`, `make lint` (web), `make typecheck`, vitest, `next build`, образ web, `compose up`. Пакет добавлен коммитом `11840b0`; исключение `minimumReleaseAgeExclude` лежит в рабочем дереве `pnpm-workspace.yaml` и не закоммичено. Предложение: закрепить предыдущую версию user-event вместо исключения (политика защищает от только что опубликованных пакетов, T15), либо закоммитить исключение вместе с lock-файлом | исправлено в `b524a9b` (зависимости закреплены в пределах политики, без исключения) |
| D-002 | блокирует гейт | BACKEND-DOCUMENTS | `ruff format --check` не проходит на закоммиченном `apps/api/app/modules/documents/listing.py:121` | `make lint` на `5fb9fe3` | Чисто | `1 file would be reformatted`; в рабочем дереве файл изменён, правка не закоммичена | исправлено в `5a9de70` |
| D-003 | OPS-04, блок 7 | FRONTEND-FOUNDATION | `pnpm audit --prod`: 2 high в `postcss`, который тянет `next` (`apps__web>next>postcss`): GHSA-6g55-p6wh-862q (`<=8.5.11`) и GHSA-r28c-9q8g-f849 (`<=8.5.17`), исправлено в `>=8.5.18`; ещё 2 moderate | `make audit-node` | 0 high и critical | high 2, moderate 2. Риск на практике низкий (PostCSS работает при сборке, исходники CSS свои), но гейт блока 7 блокирует. Предложение: `pnpm.overrides` `postcss: ">=8.5.18"` в корневом `package.json` или обновление `next`. Гейт `c251a5e`: та же `postcss@8.4.31` попадает в рабочий образ web (Trivy: CVE-2026-45623, CVE-2026-73646) | открыт |
| D-010 | блокирует гейт | BACKEND-CORE | `make lint` красный на HEAD: ruff PT011 `pytest.raises(OSError)` без `match` в `apps/api/tests/unit/test_crypto.py:97` (коммит `098533d`, BE-15, исправление D-007) | `make lint` на `c251a5e` | Чисто | `Found 1 error` | открыт |
| D-010 | блокирует гейт | BACKEND-CORE | `make lint` красный на HEAD: ruff PT011 `pytest.raises(OSError)` без `match` в `apps/api/tests/unit/test_crypto.py:97` (коммит `098533d`, BE-15, исправление D-007) | `make lint` на `c251a5e` | Чисто | `Found 1 error` | открыт |
| D-004 | OPS-05, блок 7 | QA & SECURITY-OPS | Trivy `node:22-alpine`: 10 находок HIGH с исправлением, все в npm, который лежит в образе (`/usr/local/lib/node_modules/npm`: brace-expansion, ip-address, pacote, picomatch, sigstore). Рабочему образу web npm, npx, corepack и yarn не нужны | `make trivy IMAGE=node:22-alpine` | 0 fixable HIGH | 9 уникальных CVE HIGH | закрыт: гейт `c251a5e` не нашёл находок npm в `medarchive/web:qa`. Исправлено в рабочей стадии `apps/web/Dockerfile` (удалены npm, npx, corepack, yarn); проверено сборкой той же стадии отдельно: Trivy 0 fixable HIGH и CRITICAL, `node -v` v22.23.4, uid 1000. Полный образ web проверит следующий гейт после D-001. Сырые базовые образы гейт показывает, но не блокирует |

## Блок 2

### Дефекты

Нет.

## Блок 3

### Дефекты

| ID | Класс | Владелец | Что | Шаги | Ожидаемо | Фактически | Статус |
|---|---|---|---|---|---|---|---|
| D-008 | блокирует гейты 2..7 | BACKEND-CORE | Закоммиченный `apps/api/app/main.py` остался каркасом блока 1: в нём только `GET /healthz`, роутеры модулей (`auth`, `workspace`, `uploads`, `documents`, `exports`) и `/readyz` не подключены; `create_app` из коммита `e4e30ae` в `main.py` на HEAD нет, правка лежит в рабочем дереве | Стек из чистого worktree `62fe880` (`medarchive_qa`), `curl :8900/readyz`, `POST :3400/api/v1/workspaces` с согласием | 200 и 201 | 404 `{"detail":"Not Found"}` на обоих; экран D01 не рисуется (в DOM только шапка и пустой `alert`), потому что `GET /api/v1/session` отвечает 404, а не 401 | исправлено в `82e87c4`, проверит гейт |
| D-009 | К3, текст | SPEC | Страница `/policy` показывает пользователю служебную пометку из `docs/policy.md`: «Статус: новый текст, требует утверждения владельцем. Текст написан для прототипа, который запускается через `docker compose`… (ADR-040)… (`08-security-privacy.md`, раздел 6; OPS-11)» | `https://localhost:3444/policy`, тест `QA-07 policy page has no internal references` (`e2e/tests/regression/texts.spec.ts`) | В тексте для пользователя нет ссылок на ADR, OPS, внутренние файлы и `docker compose`; термины защиты (Google Tink, AES-256-GCM, PostgreSQL Row Level Security) допустимы | Тест находит `docker`, `compose`, `ADR`, `OPS`, `security`, `privacy`, `md`. Пометку убрать из самого `docs/policy.md`, а не из вёрстки: `consents.evidence_sha256` считается от байтов файла (`docs/texts.md`, раздел 5) | открыт |

## Блок 4

### Дефекты

Нет.

## Блок 5

### Дефекты

Нет.

## Блок 6

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
