# Блок 0: сверка ТЗ и контракта

Статус: готово. Агент SPEC, 10.11.2026. Кода приложения нет: только документы пакета, контракт и словарь текстов.

## Что сделано

| Область | Результат |
|---|---|
| ADR | ADR-040..ADR-050 в `09-decisions-ADR.md`; у ADR-006, 007, 011, 012, 013, 016, 022, 029, 030, 031, 034 строка «Статус» и пометка в сводной таблице |
| Токены | `tokens.json`: `skel`, `skel2`, `primaryActive` (светлая `#000000`, тёмная `#FFFFFF`), `motion.highlight`; `tokens.css` пересобран из `tokens.json` целиком (ADR-050) |
| Контракт | `openapi.yaml` и копия `MedArchive/01_common/openapi.yaml` (одинаковые байты), `06-api-contract.md`, поток загрузки в `05-architecture.md` |
| Тексты | `docs/texts.md` (ключи по экранам, правила оформления, каталог ошибок), `docs/policy.md` (политика, версия 2026-11-10) |
| Документы | `04-customer-journey.md`, `test-cases.md`, `TZ-backend.md`, `TZ-frontend.md`, `TZ-database.md`, `TZ-design.md`, `TZ-qa.md`, `11-design-rationale.md`, `03-stack-decision.md`, `07-database.md`, `08-security-privacy.md`, `task-order.md`, `AGENTS.md`, `screens.md`, `10-patterns.md`, `TZ-devops-security.md` |
| Пакет | Копии `README.md` и `REVIEW.md` в `00_START_HERE` совпадают с корневыми; `INDEX.md` (95 файлов, размеры) и `MANIFEST.sha256` пересобраны |

## Замеры, на которых стоят ADR

| Что | Как проверено | Результат |
|---|---|---|
| Права БД (ADR-044) | PostgreSQL 17.8, `07-data-model.sql` + `db/seed-load.sql`, временный кластер | От `ma_app` `INSERT` в `workspaces`, `sessions`, `purge_queue` = `permission denied`; `ma_worker` без контекста видит 0 архивов и 0 из 6172 удалённых документов |
| План Q4 (ADR-046) | Тот же стенд, 10 000 документов в пространстве | Под суперпользователем `title_bidx @>` в Index Cond; под `ma_app` в Filter (2,7 мс). Явные `uuid_ops`, `array_ops` план не меняют. Причина: `arraycontains` не LEAKPROOF. Функция `SECURITY DEFINER`: `@>` в Index Cond, но 40,1 мс |
| Подстрока (ADR-046) | Python, правила триграмм ADR-046 | «анали», «нализ», «ий анал», «АНАЛИЗ» находят «Общий анализ крови»; с граничными пробелами «анали» не находит |
| Связка ключей (ADR-047) | Tink 1.16.1, Python 3.12 | Три keyset под KEK: 390 байт (CHECK 32..1024 не меняется); AEAD RAW: пустая строка 28 байт, 1 байт 29; префикс TINK: пустая строка 33 байта |
| Streaming AEAD (ADR-047) | Tink 1.16.1 | Расшифровывающий поток `seekable()` = False; накладные расходы 4 КБ: 456 байт на 100 КБ |

## Проверка

| Проверка | Команда | Результат |
|---|---|---|
| OpenAPI 3.1 | `uvx --from openapi-spec-validator openapi-spec-validator openapi.yaml MedArchive/01_common/openapi.yaml` (0.9.0) | `openapi.yaml: OK`, `MedArchive/01_common/openapi.yaml: OK` |
| Копии контракта | `cmp openapi.yaml MedArchive/01_common/openapi.yaml` | Одинаковые |
| Длинное тире | `rg -n '\x{2014}'` (U+2014) по 28 изменённым файлам и `docs/progress/spec.md` | Совпадений нет |
| Коды ошибок | Каждый из 32 кодов `Problem.code` ищется в `docs/texts.md` | Все 32 найдены; таблица раздела 16 совпадает с `06-api-contract.md`, раздел 8, построчно |
| MANIFEST | `cd MedArchive && shasum -a 256 -c 00_START_HERE/MANIFEST.sha256` | 94 из 94 OK |

## Отступления от плана

1. Q4: план предполагал, что `@>` уйдёт в Index Cond после явных классов операторов GIN. Замер это опроверг (таблица выше). ADR-046 фиксирует причину и меняет критерий DB-06: Filter под RLS ожидаем, бюджет 10 мс выдерживается.
2. ADR-045: `workspaces.create` не добавлен в CHECK `idempotency_keys`, у него отдельная таблица `workspace_create_keys` (архива ещё нет); в CHECK добавлены `uploads.create` и `workspace.rotateKey`.
3. ADR-047: колонка `bidx_key_ciphertext` удаляется миграцией 0002, оба ключа лежат одной связкой в `dek_ciphertext`; криптоудаление ADR-041 стирает эту связку.

## Что осталось другим агентам

1. `MANIFEST.sha256` хэширует рабочую копию `02_design/source/gen.py` (агент Figma её правит, изменение не закоммичено) и текущие файлы `05_qa/fixtures`. Любая следующая правка в `02_design/source/**` или `05_qa/fixtures/**` требует пересборки `MANIFEST.sha256` и `INDEX.md`.
2. Корневые `README.md` и `AGENTS.md` не входят в зону SPEC: `README.md` всё ещё называет Medeo 1.1.0 из npm и «74 тест-кейса (44 P0)» (сейчас 78 и 46, ADR-043); корневой `AGENTS.md` (копия от агента FOUNDATION) не содержит правок раздела 2 (словарь `docs/texts.md`) и раздела 3 (ADR-040).
3. Тексты с пометкой «новый текст, требует утверждения владельцем» в `docs/texts.md` и весь `docs/policy.md` надо показать владельцу до блока 3.
