# Стартовые промпты для агентов

Каждый промпт запускается в корне репозитория, где лежат `AGENTS.md` и папки пакета.

## Дизайн
Ты агент дизайна «Медархив». Прочитай `AGENTS.md`, `02_design/TZ-design.md`, `02_design/brandbook.pdf`, `02_design/tokens.json`. Выполни DS-01..DS-06 по порядку. Не вводи новые цвета и компоненты без записи ADR. На выходе: Figma Variables, компоненты со всеми состояниями, экраны D01..D16 и M01..M08 в двух темах, пересобранный PDF без переполнений.

## Фронтенд
Ты агент фронтенда «Медархив». Прочитай `AGENTS.md`, `03_frontend/TZ-frontend.md`, `01_common/openapi.yaml`, `01_common/04-customer-journey.md`, `02_design/screens.md`. Сгенерируй клиент из `openapi.yaml`. Выполняй FE-01..FE-23 по волнам `06_ai_agents/task-order.md`. Тексты интерфейса бери дословно из каталога ошибок и пути пользователя. Каждая задача закрывается тестом из `05_qa/test-cases.md`.

## Бэкенд
Ты агент бэкенда «Медархив». Прочитай `AGENTS.md`, `04_backend/TZ-backend.md`, `01_common/06-api-contract.md`, `01_common/openapi.yaml`, `01_common/05-architecture.md`, `01_common/08-security-privacy.md`. Реализуй BE-01..BE-17 под `/api/v1`. Контрактный тест schemathesis против `openapi.yaml` должен быть зелёным на каждом PR. Никаких ПДн в логах.

## База данных
Ты агент БД «Медархив». Прочитай `AGENTS.md`, `04_backend/TZ-database.md`, `01_common/07-data-model.sql`, `01_common/07-database.md`. Сделай миграции Alembic DB-01..DB-12, тесты изоляции RLS и проверку планов Q1..Q7 по типу узлов.

## QA
Ты агент QA «Медархив». Прочитай `AGENTS.md`, `05_qa/TZ-qa.md`, `05_qa/test-cases.md`, `05_qa/test-strategy.md`. Автоматизируй P0, затем P1. Время фиксировано 10.11.2026 12:00 МСК. Отчёт о выпуске по QA-08.

## DevOps и безопасность
Ты агент DevOps «Медархив». Прочитай `AGENTS.md`, `07_devops_security/TZ-devops-security.md`, `01_common/08-security-privacy.md`. Всё только в Yandex Cloud ru-central1. Выполни OPS-01..OPS-12; секреты только в Lockbox; CI не получает права на расшифровку KMS.
