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

TC считается пройденным, если есть хотя бы один тест с его ID в имени и все такие тесты зелёные. Пропущенный тест (`skip`, `fixme`) или его отсутствие в обязательном блоке означает FAIL гейта, а не PASS.

## Блок 1

### Дефекты

Нет.

## Блок 2

### Дефекты

Нет.

## Блок 3

### Дефекты

Нет.

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

Нет.

## Блок 9

### Дефекты

Нет.
