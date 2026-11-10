# QA и DevSecOps: инфраструктура тестов и гейты

Статус: в работе. Агент QA & SECURITY-OPS, 10.11.2026. Журнал гейтов: `docs/progress/blocks.md`.

## Как запускать

| Что | Команда | Нужен стек |
|---|---|---|
| Гейт блока N на закоммиченном HEAD, запись в `blocks.md` | `tools/verify_block.sh N` или `make verify-block N=N`; `--no-record` без записи, `--keep-stack` оставить стек | поднимает свой `medarchive_qa` |
| E2E по своему стеку | `E2E_BASE_URL=http://localhost:3300 make e2e`, выборка блоков: `pnpm --filter e2e exec playwright test --grep "@b[1-3]\b"` | да |
| Доступность (QA-05) | `make a11y` | да |
| Визуальная регрессия (QA-06) | `make visual`; эталоны создаёт только `make visual-baseline`, затем просмотр глазами и коммит | да |
| Контракт (QA-02) | `make contract BLOCK=N API_URL=http://localhost:8800` | да |
| Безопасность (OPS-04, OPS-05) | `make security IMAGE_TAG=local` (pip-audit, `pnpm audit --prod`, gitleaks, Trivy); по отдельности `audit-python`, `audit-node`, `gitleaks`, `trivy IMAGE=…` | нет, нужны образы |
| ZAP baseline | `make zap ZAP_COOKIE='__Host-ma_sid=…' COMPOSE_PROJECT=medarchive` | да |
| Нагрузка k6 | `make load COMPOSE_PROJECT=medarchive LOAD_DOCUMENTS=1000` | да |
| Алерты (OPS-08) | `make alerts` (`promtool check rules` и `promtool test rules`) | нет |

Отчёты пишутся в `REPORT_DIR` (по умолчанию `reports/`), гейт пишет их в `/tmp/medarchive-gate-logs/<время>-<sha>-b<N>/`.

## Соглашения для всех агентов

1. ID тест-кейса в имени теста: Playwright `test("TC-012 …")` или тег `@TC-012`; pytest `test_tc091_…` или `TC-091` в id параметра; vitest `it("TC-013 …")`. Гейт находит TC по шаблону `TC-\d{3}b?` в имени и в пути отчёта JUnit или JSON.
2. Каждый E2E-тест несёт тег блока, в котором появляется его функциональность: `{ tag: ["@b4", "@P0", "@TC-015"] }`. Гейт блока N запускает `@b1..@bN`; тесты поздних блоков считаются pending и в PASS не попадают.
3. Тесты в `*.api.spec.ts` идут в проекте `api` один раз, без браузера; остальные в `chromium-desktop` (1440 x 900) и `webkit-iphone13`.
4. Фикстуры E2E (`e2e/support/fixtures.ts`): `freshArchive` создаёт новый архив через `POST /api/v1/workspaces` и кладёт сессию в контекст браузера; `api.addSource(source)` и `api.addAllSources()` загружают PDF из `qa/fixtures/manifest.json` тем же путём, что браузер; часы зафиксированы на 10.11.2026 12:00 МСК (`page.clock.setFixedTime`), для границ суток `test.use({ clockTime: null })`.
5. Пути к фикстурам только из манифеста: `sources`, `titlesInDefaultOrder`, `generatedFixture(name)` из `e2e/support/manifest.ts`.
6. Ошибка в тесте показывает маршрут, статус, `code` и `X-Request-Id` (`expectStatus`), но не тело ответа: в нём могут быть названия.
7. Доступность: `expectNoSeriousA11yViolations(page, testInfo)` (WCAG 2.2 AA, 0 serious и critical). Визуал: `expectScreen(page, name)` с масками PDF-просмотрщика и прогресса.

## Что сделано

| Задача | Файлы | Проверка |
|---|---|---|
| QA-04 инфраструктура E2E | `e2e/playwright.config.ts` (проекты, отчёты JUnit, JSON, HTML, `toHaveScreenshot` с порогом 0,1%), `e2e/support/{archive,fixtures,manifest,axe,visual}.ts` | `pnpm --filter e2e typecheck`, `playwright test --list` |
| QA-02 API по контракту | `e2e/tests/api/*.api.spec.ts` (TC-003, TC-019 API, TC-022, TC-023, TC-024, TC-042, TC-043, TC-058, TC-059, TC-090, TC-094, TC-097), `apps/api/tests/contract/test_openapi_diff.py` (`app.openapi()` против `openapi.yaml`, блоки операций в `operation-blocks.json`), `apps/api/tests/contract/hooks.py` (schemathesis: сессия и CSRF нового архива) | `CONTRACT_BLOCK=1 pytest tests/contract`: 4 passed; `CONTRACT_BLOCK=3`: 6 failed, операции блока 3 ещё не реализованы |
| OPS-10 тесты угроз, веб | `e2e/tests/security/`: TC-093 (CSRF), TC-094 (no-store страницы), TC-095 (XSS в названии), TC-098 (лимит загрузок), SEC-01 (только свой origin), SEC-02 (нет `Server` и `X-Powered-By`), SEC-03 (атрибуты cookie), OPS-06 (заголовки web и API) | гейты блоков |
| QA-05 доступность | `e2e/tests/a11y/`: онбординг и `/policy` (`@b3`), список, «ничего не найдено», документ (`@b5`), диалоги удаления, экспорта, добавления (`@b6`), обе темы | гейты блоков |
| Гейты | `tools/verify_block.{sh,py}`, `tools/check_hardening.sh` (OPS-05, OPS-07), `tools/check_migrations.sh` (PostgreSQL 17 и 18), цели Makefile `contract a11y visual visual-baseline security audit-python audit-node gitleaks trivy zap load alerts verify-block` | `ruff`, `mypy --strict`, shellcheck чисто |
| OPS-04 | `.github/workflows/ci.yml` (jobs `checks`, `security`, `stack`, ночью ZAP и k6), `.github/dependabot.yml` (uv, npm с паузой 2 дня под `minimumReleaseAge`, docker, actions) | |
| OPS-08 | `infra/prometheus/alerts.yml`: 5xx > 1% за 5 мин, p95 `GET /api/v1/documents` > 300 мс, ошибки KEK; `alerts.test.yml` | `make alerts`: 3 правила, все unit-тесты SUCCESS |
| Нагрузка | `load/k6/documents-list.js`: сид 1000 документов через uploads → presigned POST → documents, 50 VU 60 с, пороги p95 < 300 мс, 0% 5xx, 100% ответов 200 | гейт блока 7 |

## Правки чужих файлов (OPS-05, OPS-07)

| Файл | Правка | Зачем |
|---|---|---|
| `docker-compose.yml` | `image: medarchive/{api,web}:${IMAGE_TAG:-local}`; порты MinIO `${MINIO_PORT:-9000}` и `${MINIO_CONSOLE_PORT:-9001}`; `S3_PUBLIC_ENDPOINT: http://localhost:${MINIO_PORT:-9000}` | Второй стек (гейт) не перетирает образы первого и не спорит за порты 9000 и 9001; значения по умолчанию прежние |
| `docker-compose.yml`, сервис `web` | `S3_PUBLIC_ENDPOINT: http://localhost:${MINIO_PORT:-9000}` (`d398560`) | `apps/web/middleware.ts` строит `connect-src` CSP из этой переменной; без неё браузер стенда с MinIO не на 9000 не может загрузить файл. Проверено: заголовок стенда :3400 содержит `connect-src 'self' http://localhost:9400` |
| `docker-compose.yml`, сервис `api` | `TRUSTED_PROXIES: ${TRUSTED_PROXIES:-[]}`, `RATE_LIMITS_ENABLED: ${RATE_LIMITS_ENABLED:-true}` (`470c9be`) | Параметры BE-12 из `fa14f11` (D-005, D-006); гейт переключает лимиты между фазами E2E |
| Ошибка атрибуции | Коммит `d398560` по ошибке включил незакоммиченный тогда сервис `worker` (BE-13, агент BACKEND-DOCUMENTS): `git commit -- docker-compose.yml` берёт файл целиком. Содержимое совпадает с их работой (`9414eae`), поведение не изменилось | Дальше общие файлы коммичу из отдельного индекса только своими фрагментами (`git apply --cached`) |
| Чужой коммит моих правок | `8ba9610` (23:38) закоммитил мои тогда незакоммиченные правки тестов a11y, TC-024, XSS и D-011 с сообщением `test(QA-05)`; содержимое моё и совпадает с рабочим деревом | Без последствий; отмечено для трассировки |
| `Makefile`, `TESTCONTAINERS_RYUK_DISABLED ?= true` | Ryuk на Docker Desktop под нагрузкой падает (порт 8080 не публикуется вовремя); фикстуры сами останавливают контейнеры | D-011 |
| `Makefile` | `lint` и `typecheck` проверяют и `tools/`; `images` принимает `IMAGE_TAG`; `setup` ставит WebKit; новые цели (таблица выше) | Скрипты гейта проходят те же проверки, что код |
| `e2e/tests/smoke.spec.ts` | Проверка `<h1>Медархив</h1>` заменена на `lang="ru"`, добавлен тег `@b1` | Заголовок каркаса уходит с онбордингом FE-11; смоук не должен падать от этого |

## Отброшенные прогоны

| Когда | HEAD | Почему не записан в `blocks.md` |
|---|---|---|
| 10.11.2026 23:40..23:45 | `e3cdd4a`, `520318e` | Прерваны мной (`pkill`) после того, как стало ясно, что Ryuk под нагрузкой Docker Desktop даёт 255 ошибок setup (D-011) |
| 11.11.2026 00:00 | `9e705cd` | Гейт унаследовал `RATE_LIMITS_ENABLED=false` из моей оболочки после отладочного стека: 9 тестов лимитов в pytest упали не из-за кода. С этого прогона гейт не передаёт детям `RATE_LIMITS_ENABLED`, `TRUSTED_PROXIES`, `NET_PREFIX` |

## Решения

- Гейт идёт по закоммиченному HEAD в отдельном worktree: рабочее дерево общее для семи агентов, и в нём всегда есть чужие незаконченные правки.
- Пропущенный или отсутствующий тест обязательного TC это FAIL, а не PASS.
- Trivy блокирует только HIGH и CRITICAL, у которых есть исправленная версия (`--ignore-unfixed`): на нефиксируемые находки в базовом образе повлиять нечем, они видны в отчёте.
- ZAP идёт по сети compose (`http://web:3000`) с cookie нового архива через replacer, k6 тоже внутри сети и подменяет хост presigned URL на `minio:9000` (подпись POST-политики не включает хост).
