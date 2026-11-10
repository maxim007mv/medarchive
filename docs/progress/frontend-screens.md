# Блоки 3..6: экраны фронтенда (FE-10..FE-22)

Статус: экраны и логика готовы, unit и компонентные тесты зелёные; E2E блока 3 прогнан на живом API, E2E блоков 4..6 написаны и ждут маршрутов `uploads`, `documents`, `exports` (на `HEAD` их ещё нет). Агент FRONTEND-SCREENS, 10.11.2026.

## Запросы к другим агентам

| Кому | Что | Зачем | Статус |
|---|---|---|---|
| SPEC / FRONTEND-FOUNDATION | Ключи `empty.period.range` «за {from} – {to}», `empty.period.from` «с {from}», `empty.period.to` «по {to}» в `docs/texts.md` §10 и `lib/texts.ts` | Подстановка `{period}` в `empty.text.queryPeriod` и `empty.text.period` (D08). Фразы есть только в абзаце под таблицей §10, генератор их не берёт. Пока они стоят константой `PERIOD` в `components/documents/list-texts.ts` дословно из §10; после появления ключей заменить на `t("empty.period.*")` | открыт |
| FRONTEND-FOUNDATION | `lib/policy.ts` из `docs/policy.md` | Страница `/policy` и `consent.policy_version`; `docs/` исключён из контекста Docker-сборки web. Сделал сам: `scripts/gen-policy.mjs` пишет `lib/policy.ts`, `lib/policy.test.ts` сверяет его с `docs/policy.md` побайтно. Можно забрать в общий генератор (`pnpm gen:texts`) | закрыт мной |
| FRONTEND-FOUNDATION | Toast: провайдер и `useToast()` | Тосты списка, заметки, удаления, ключа | закрыт: `ToastProvider` в `app/providers.tsx` |
| FRONTEND-FOUNDATION | `eslint.config.mjs`: `new FlatCompat({ baseDirectory, resolvePluginsRelativeTo: <каталог eslint-config-next> })` | `eslint-plugin-react-hooks` ищется от `apps/web` вверх и на этой машине находится в `~/node_modules` (4.6.2, несовместим с ESLint 9): `exhaustive-deps` падает `context.getSource is not a function`, как только ему есть что сообщить. Локально обойдено симлинком `apps/web/node_modules/eslint-plugin-react-hooks` на 5.2.0 из `node_modules/.pnpm` (не в git) | открыт |
| FRONTEND-FOUNDATION | `vitest.setup.ts`: `Element.prototype…` падает в тестах с `// @vitest-environment node` (`ReferenceError: Element is not defined`, в том числе `lib/texts.test.ts`) | Обернуть в `if (typeof Element !== "undefined")` | открыт |
| DEVOPS / BACKEND-CORE | `docker-compose.yml`: сервис `api` не получает `CSRF_SECRET` и `PAGE_TOKEN_KEY` (обязательны в `app/core/config.py`), `.env.example` и `make secrets` их не создают; api падает при старте | Локально передал через временный `-f /tmp/fe-compose.override.yml` вне репозитория | открыт |
| DEVOPS / QA | WebKit (профиль iPhone 13) не сохраняет `Secure` cookie `__Host-ma_sid` на `http://localhost:3300`: в TC-002 `context.cookies()` пуст, следующие запросы браузера идут без сессии | Риск ADR-048: запасной вариант HTTPS через Caddy для E2E. Из UI это не чинится | открыт |

## Что сделано

| Задача | Файлы | Тесты |
|---|---|---|
| FE-10 клиент и сессия | `lib/api/client.ts` (openapi-fetch из `schema.d.ts`, `X-CSRF-Token` из `GET /api/v1/session` и из ответов, создающих сессию), `lib/api/errors.ts` (problem+json → `ApiError` с `Retry-After`; голый 5xx прокси и сбой fetch → `NetworkError`), `lib/api/connectivity.ts`, `lib/api/queries.ts` (ключи `['session']`, `['workspace']`, `['documents', filters]`, `['document', id]`), `components/documents/HomeScreen.tsx`, `app/page.tsx` | `lib/api/client.test.ts`, `HomeScreen.test.tsx` |
| FE-11 онбординг и согласие | `EmptyArchive.tsx` (D01/M01: чекбокс согласия, кнопка и зона перетаскивания заблокированы с причиной, ссылки на `/policy` и `/restore`), `AccessKeyDialog.tsx` (ключ один раз, «Скопировать», «Скачать как файл»), `app/policy/page.tsx`, `PolicyDocument.tsx`, `lib/policy.ts` | `HomeScreen.test.tsx`, `lib/policy.test.ts`, E2E `onboarding.spec.ts` |
| FE-12 загрузка | `lib/api/upload.ts` (тип, `%PDF-`, 20971520 байт до любого запроса; XHR presigned POST: поля, затем файл), `upload-machine.ts` (idle → selected → uploading(p) → verifying → ready → saving → saved / failed(code)), `use-upload-file.ts`, `UploadDialog.tsx` (зона перетаскивания в пустом диалоге, очередь «Файл 1 из 3», «Закрыть без сохранения?»), `EditForm.tsx` (общая форма с правкой) | `lib/api/upload.test.ts`, `upload-machine.test.ts`, `UploadDialog.test.tsx`, E2E `upload.spec.ts` |
| FE-13 список | `ArchiveScreen.tsx`, `DocumentTable.tsx` (от 1024 px, строка кликабельна, ссылка в названии, `aria-sort`), `DocumentCard.tsx` (ниже 1024 px), `RowMenu.tsx` («Ещё» → «Удалить»), `ListSkeleton.tsx` (D13 через `useDelayedFlag`), подсветка новой строки 1200 мс без перемещения | E2E `upload.spec.ts` (TC-010, TC-011) |
| FE-14 поиск и фильтры | `lib/filters.ts` (nuqs: `q`, `date_field`, `from`, `to`, `type`, `order_by`, `undated`; ISO в URL), `SearchField.tsx` (250 мс, от 3 символов, `/`), `PeriodFields.tsx`, `Toolbar.tsx` (мобильный лист со счётчиком через `page_size=1`), `AppliedFilters.tsx` | `lib/filters.test.ts`, E2E `list.spec.ts` |
| FE-15 ничего не найдено | `EmptySearch.tsx`, `list-texts.ts` (только запрос → «Сбросить поиск»; даты → «Убрать фильтр по дате» и «Сбросить всё»; показ только при `isSuccess` и не на плейсхолдере) | `EmptySearch.test.tsx`, E2E TC-033 |
| FE-16 просмотр | `DocumentScreen.tsx`, `PdfViewer.tsx` (iframe `…/content?disposition=inline#view=FitH`, карточка при `navigator.pdfViewerEnabled === false`), «Скачать», «В новой вкладке», «Все документы» возвращает к фильтрам (`sessionStorage`) | E2E `document.spec.ts` |
| FE-17 правка | `EditPanel.tsx` (`PATCH` с `If-Match`, 412 → баннер и «Обновить», ввод сохраняется) | E2E TC-054 |
| FE-18 заметка | `use-note-autosave.ts` (800 мс, `onMutate`/`onError` с откатом, запросы по одному с новым ETag, копия в `sessionStorage`, `keepalive` при `visibilitychange=hidden` и `beforeunload`), `NotePanel.tsx` («Очистить» = `note: null` + тост «Заметка очищена · Вернуть» 6 с, счётчик `N / 2000`) | `use-note-autosave.test.tsx`, `NotePanel.test.tsx`, E2E TC-051..TC-053 |
| FE-19 удаление | `DeleteDialog.tsx` (название и дата, фокус на «Отмена», Enter не удаляет, `If-Match`) | E2E TC-055, TC-056, TC-060 |
| FE-20 экспорт | `ExportDialog.tsx` («Только найденные» по умолчанию при фильтре, «Выбранные» недоступно без отметок, размер из `total_bytes`, ссылка на `content_url`) | `ExportDialog.test.tsx`, E2E `export.spec.ts` |
| FE-21 ошибки и офлайн | `use-problem.ts` (`title` как есть, `N` → секунды `Retry-After`, `request_id` для 5xx), `use-countdown.ts`, `OfflineBanner.tsx` (D14, кнопки изменения заблокированы с причиной), `BootUnavailable.tsx` (автоповтор 5, 10, 30 с) | `HomeScreen.test.tsx`, E2E TC-085 |
| FE-22 настройки | `SettingsScreen.tsx` (хранение, новый ключ с подтверждением, «Открыть архив по ключу», выход, удаление архива словом «удалить» без учёта регистра), `RestoreForm.tsx`, `app/settings`, `app/restore` | E2E `sessions.spec.ts` |

## Проверка

| Команда | Результат |
|---|---|
| `tsc --noEmit` (apps/web) | чисто |
| `eslint --max-warnings 0 components/documents app lib` | чисто (с локальным симлинком react-hooks, см. запросы) |
| `vitest run components/documents lib/api lib/filters.test.ts lib/policy.test.ts` | 11 файлов, 104 теста, все зелёные; на чистом `git archive HEAD` то же |
| `next build` | собирается; First Load JS: `/` 205 КБ, `/documents/[id]` 208 КБ, `/settings` 180 КБ, `/restore` 161 КБ, `/policy` 137 КБ |
| E2E `onboarding.spec.ts`, Chromium 1440 | 4 из 4 (TC-001 ×2, TC-002, TC-004) |
| E2E `onboarding.spec.ts`, WebKit iPhone 13 | 3 из 4; TC-002 падает на `Secure`-cookie (запрос DEVOPS / QA) |
| E2E блоков 4..6 | не запускались: маршрутов `uploads`, `documents`, `exports` на `HEAD` нет (404) |

Стек для E2E: `WEB_PORT=3300 API_PORT=8800 MINIO_PORT=9300 MINIO_CONSOLE_PORT=9301 docker compose -f docker-compose.yml -f /tmp/fe-compose.override.yml up -d --wait`; прогон `E2E_BASE_URL=http://localhost:3300 pnpm --filter e2e exec playwright test tests/screens`.

Снимки для ручной сверки с `MedArchive/02_design/screens`: `e2e/artifacts/screens/{chromium-desktop,webkit-iphone13}/*-{light,dark}.png`, генерирует `e2e/tests/screens/screens.spec.ts`.

## Отклонения

1. «Добавить PDF» открывает «Новый документ» в состоянии `idle` с зоной перетаскивания (D04, верх), а не сразу системный выбор файла: так же ждут a11y-тесты QA, и это состояние `idle` машины загрузки. На онбординге «Выбрать первый PDF» открывает выбор файла сразу.
2. `upload.file.meta` «{size} · {n} {страница}»: число страниц до сохранения неизвестно (его считает сервер в `POST /documents`), в строке файла формы только размер. На странице документа «PDF · {size} · {n} стр.» из `file.page_count`.
3. Пустая дата без «Дата не указана в документе» считается ошибкой `date_invalid`: путь пользователя требует явного «неизвестно», отдельного текста для пустого поля в словаре нет.
4. Список грузится клиентом (TanStack Query), а не RSC с первыми 200 документами (TZ §6): сессия и CSRF живут в браузере. First Load JS `/` 205 КБ при бюджете 180 КБ: диалоги, форма и zod уже вынесены в ленивые чанки; остаток — Radix (popover, tooltip, dialog, radio, checkbox, toast), TanStack Query, nuqs, date-fns календаря.
5. Ключ идемпотентности экспорта создаётся на каждый выбранный состав (радио-строку), а не на открытие диалога: тело запроса у каждого состава своё, один ключ дал бы `idempotency_key_reused`.
6. TC-082 и ключевые тесты (TC-081, TC-083, TC-084) идут в одном файле последовательно: лимит входа 5 за 15 минут на IP общий для всего прогона, поэтому TC-082 проверяет «сначала только 401, затем только 429, не позже шестой попытки».

## Открытые вопросы

1. `GET /api/v1/documents/{id}/content` отдаёт `Content-Security-Policy: sandbox`: Chromium может не показывать встроенный PDF во фрейме с такой политикой. Проверю на живом API; если так, нужна правка политики на стороне API (например, `sandbox allow-scripts` только для `disposition=inline`), а не обход в UI.
