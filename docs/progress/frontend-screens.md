# Блоки 3..6: экраны фронтенда (FE-10..FE-22)

Статус: готово. Все экраны и сценарии FE-10..FE-22 сделаны; unit и компонентные тесты зелёные; все E2E этого агента (TC из задания) зелёные на Chromium 1440 и WebKit iPhone 13 против живого API. Агент FRONTEND-SCREENS, 10–11.11.2026.

Оговорка про стенд: на `HEAD` маршруты `uploads`, `documents`, `exports` ещё не подключены в `apps/api/app/main.py` (D-008, агент ядра). Для E2E блоков 4..6 API запускался с локальной точкой входа вне репозитория (`/tmp/fe_main.py`: `create_app()` плюс три закоммиченных роутера), код `apps/api` не менялся.

## Запросы к другим агентам

| Кому | Что | Зачем | Статус |
|---|---|---|---|
| SPEC / FRONTEND-FOUNDATION | Ключи `empty.period.range` «за {from} – {to}», `empty.period.from` «с {from}», `empty.period.to` «по {to}» в `docs/texts.md` §10 и `lib/texts.ts` | Подстановка `{period}` в `empty.text.queryPeriod` и `empty.text.period` (D08). Фразы есть только в абзаце под таблицей §10, генератор их не берёт. Пока они стоят константой `PERIOD` в `components/documents/list-texts.ts` дословно из §10; после появления ключей заменить на `t("empty.period.*")` | открыт |
| FRONTEND-FOUNDATION | `components/ui/dialog.tsx`: Radix возвращает фокус только своему `Dialog.Trigger`, а `Dialog` используется управляемым без триггера, поэтому после закрытия любого диалога фокус уходит на `<body>` | В `DeleteDialog` обойдено пропом `returnFocusTo` (TC-056). Для остальных диалогов (добавление, экспорт, ключ) нужен общий фикс: запоминать `document.activeElement` при открытии и фокусировать его в `onCloseAutoFocus` | закрыт: `Dialog` запоминает открывшего и возвращает ему фокус, `finalFocus` и `handOff` (FE-06, 11.11.2026) |
| FRONTEND-FOUNDATION | `eslint.config.mjs`: `new FlatCompat({ baseDirectory, resolvePluginsRelativeTo: <каталог eslint-config-next> })` | `eslint-plugin-react-hooks` ищется от `apps/web` вверх и на этой машине находится в `~/node_modules` (4.6.2, несовместим с ESLint 9): `exhaustive-deps` падает `context.getSource is not a function`, как только ему есть что сообщить. Локально обойдено симлинком `apps/web/node_modules/eslint-plugin-react-hooks` на 5.2.0 из `node_modules/.pnpm` (не в git) | открыт |
| BACKEND-CORE | Подключить роутеры `uploads`, `documents`, `exports` в `app/main.py` (D-008) | Без этого E2E блоков 4..6 на `HEAD` получают 404 | открыт |
| FRONTEND-FOUNDATION | `lib/policy.ts` из `docs/policy.md` | Сделал сам: `scripts/gen-policy.mjs`, сверка `lib/policy.test.ts`; SPEC уже перегенерировал им файл в `fa17a4c` | закрыт |
| FRONTEND-FOUNDATION | Toast: провайдер и `useToast()` | | закрыт: `ToastProvider` в `app/providers.tsx` |
| FRONTEND-FOUNDATION | `vitest.setup.ts` падал в тестах с `@vitest-environment node` | | закрыт: весь набор зелёный |
| DEVOPS | `CSRF_SECRET` и `PAGE_TOKEN_KEY` не доходили до api | | закрыт: `f9840ce` |
| DEVOPS / QA | WebKit не сохраняет `Secure` cookie на `http://localhost` | | закрыт: профиль `tls` (Caddy), `50ecb1b` |

## Что сделано

| Задача | Файлы | Тесты |
|---|---|---|
| FE-10 клиент и сессия | `lib/api/client.ts` (openapi-fetch из `schema.d.ts`, `X-CSRF-Token` из `GET /api/v1/session` и из ответов, создающих сессию), `lib/api/errors.ts` (problem+json → `ApiError` с `Retry-After`; голый 5xx прокси и сбой fetch → `NetworkError`), `lib/api/connectivity.ts`, `lib/api/queries.ts` (ключи `['session']`, `['workspace']`, `['documents', filters]`, `['document', id]`), `HomeScreen.tsx`, `app/page.tsx` | `lib/api/client.test.ts`, `lib/api/queries.test.ts`, `HomeScreen.test.tsx` |
| FE-11 онбординг и согласие | `EmptyArchive.tsx` (D01; на телефоне M01 с закреплённой кнопкой), `AccessKeyDialog.tsx` (ключ один раз, «Скопировать», «Скачать как файл»), `app/policy/page.tsx`, `PolicyDocument.tsx`, `lib/policy.ts` + `scripts/gen-policy.mjs`; архив создаётся только после согласия и проверки первого файла, ключ показывается после закрытия первой формы | `HomeScreen.test.tsx`, `lib/policy.test.ts`, E2E `onboarding.spec.ts` |
| FE-12 загрузка | `lib/api/upload.ts` (тип, `%PDF-`, 20971520 байт до любого запроса; XHR presigned POST: поля, затем файл), `upload-machine.ts` (idle → selected → uploading(p) → verifying → ready → saving → saved / failed(code)), `use-upload-file.ts` (свой `Idempotency-Key` на загрузку и на сохранение каждой загрузки), `UploadDialog.tsx` (зона перетаскивания в пустом диалоге, очередь «Файл 1 из 3», «Закрыть без сохранения?»), `EditForm.tsx` (общая форма с правкой) | `lib/api/upload.test.ts`, `upload-machine.test.ts`, `UploadDialog.test.tsx`, E2E `upload.spec.ts` |
| FE-13 список | `ArchiveScreen.tsx`, `DocumentTable.tsx` (от 1024 px, строка кликабельна, ссылка в названии, `aria-sort`), `DocumentCard.tsx` (ниже 1024 px), `RowMenu.tsx` («Ещё» → «Удалить»), `ListSkeleton.tsx` (D13 через `useDelayedFlag`), подсветка новой строки 1200 мс без перемещения, диалоги грузятся лениво | E2E TC-010, TC-011, `keyboard.spec.ts` |
| FE-14 поиск и фильтры | `lib/filters.ts` (nuqs: `q`, `date_field`, `from`, `to`, `type`, `order_by`, `undated`; ISO в URL, `дд.мм.гггг` в полях), `SearchField.tsx` (250 мс, от 3 символов, `/`), `PeriodFields.tsx`, `Toolbar.tsx` (мобильный лист «Показать N» через `page_size=1`), `AppliedFilters.tsx` (чипы, «N из M», «Сбросить всё») | `lib/filters.test.ts`, E2E `list.spec.ts` |
| FE-15 ничего не найдено | `EmptySearch.tsx`, `list-texts.ts` (только запрос → «Сбросить поиск»; даты → «Убрать фильтр по дате» и «Сбросить всё»; показ только при `isSuccess` и не на плейсхолдере) | `EmptySearch.test.tsx`, E2E TC-033 |
| FE-16 просмотр | `DocumentScreen.tsx`, `PdfViewer.tsx` (iframe `…/content?disposition=inline#view=FitH`, карточка при `navigator.pdfViewerEnabled === false`), «Скачать», «В новой вкладке», «Все документы» возвращает к фильтрам | E2E TC-050, TC-057 |
| FE-17 правка | `EditPanel.tsx` (`PATCH` с `If-Match`, 412 → баннер и «Обновить», ввод сохраняется) | E2E TC-054 |
| FE-18 заметка | `use-note-autosave.ts` (800 мс, `onMutate`/`onError` с откатом, запросы по одному с новым ETag, копия в `sessionStorage`, `keepalive` при `visibilitychange=hidden` и `beforeunload`), `NotePanel.tsx` («Очистить» = `note: null` + тост «Заметка очищена · Вернуть» 6 с, счётчик `N / 2000`) | `use-note-autosave.test.tsx`, `NotePanel.test.tsx`, E2E TC-051..TC-053 |
| FE-19 удаление | `DeleteDialog.tsx` (название и дата, фокус на «Отмена», Enter не удаляет, `If-Match`, фокус возвращается на открывшую кнопку) | E2E TC-055, TC-056, TC-060 |
| FE-20 экспорт | `ExportDialog.tsx` («Только найденные» по умолчанию при фильтре, «Выбранные» недоступно без отметок, размер из `total_bytes`, ссылка на `content_url`) | `ExportDialog.test.tsx`, E2E `export.spec.ts` |
| FE-21 ошибки и офлайн | `use-problem.ts` (`title` как есть, `N` → секунды `Retry-After`, `request_id` для 5xx), `use-countdown.ts`, `OfflineBanner.tsx` (D14, кнопки изменения заблокированы с причиной), `BootUnavailable.tsx` (автоповтор 5, 10, 30 с) | `HomeScreen.test.tsx`, E2E TC-085, TC-082 |
| FE-22 настройки | `SettingsScreen.tsx` (хранение, новый ключ с подтверждением, «Открыть архив по ключу», выход, удаление архива словом «удалить» без учёта регистра), `RestoreForm.tsx` (дефисы и регистр нормализуются), `app/settings`, `app/restore` | E2E `sessions.spec.ts` |

## Результаты TC (E2E `e2e/tests/screens`)

Прогон 11.11.2026 против стека этого агента: Chromium 1440 x 900 и WebKit iPhone 13 через `https://localhost:3343` (профиль `tls`), `page.clock` 10.11.2026 12:00 МСК, каждый тест со своим архивом.

| TC | Chromium 1440 | WebKit iPhone 13 |
|---|---|---|
| TC-001 (×2), TC-002, TC-004 | pass | pass |
| TC-010, TC-011 (×2), TC-012, TC-013, TC-014, TC-015, TC-016, TC-019, TC-020, TC-021 | pass | pass |
| TC-030..TC-041 | pass | pass |
| TC-050 (×2), TC-051, TC-052, TC-053, TC-054, TC-055, TC-056, TC-057, TC-060 | pass | pass |
| TC-070, TC-071, TC-072 | pass | pass |
| TC-080, TC-081, TC-083, TC-084, TC-085 | pass | pass |
| TC-082 (лимиты включены, отдельный прогон) | pass | pass |
| TC-111, TC-112 | pass | pass |

Итого 94 из 94 при выключенных лимитах (`RATE_LIMITS_ENABLED=false`, как в функциональных прогонах гейта) и 2 из 2 для TC-082 с лимитами.

## Проверка

| Команда | Результат |
|---|---|
| `pnpm --filter web lint` | eslint `--max-warnings 0` и prettier чисто |
| `pnpm --filter web typecheck` | чисто |
| `pnpm --filter web test` | 27 файлов, 249 тестов, все зелёные; покрытие `lib/` 99,6% строк, 93,4% ветвей (порог 90%) |
| `pnpm --filter web build` | собирается; First Load JS: `/` 205 КБ, `/documents/[id]` 209 КБ, `/settings` 180 КБ, `/restore` 161 КБ, `/policy` 138 КБ |
| `tsc --noEmit` (e2e) | чисто |
| E2E `tests/screens` | см. таблицу выше |

Стек: `WEB_PORT=3300 API_PORT=8800 MINIO_PORT=9300 MINIO_CONSOLE_PORT=9301 NET_PREFIX=10.158.0 TLS_WEB_PORT=3343 TLS_STORAGE_PORT=9343 S3_PUBLIC_ENDPOINT=https://localhost:9343 docker compose -f docker-compose.yml -f /tmp/fe-compose.override.yml --profile tls up -d --build --wait`, где override монтирует `/tmp/fe_main.py` (роутеры) и ставит `RATE_LIMITS_ENABLED=false`. Прогон: `E2E_BASE_URL=https://localhost:3343 pnpm --filter e2e exec playwright test tests/screens --grep-invert "screens,|TC-082"`; TC-082 отдельно с лимитами.

Снимки для ручной сверки с `MedArchive/02_design/screens`: `e2e/artifacts/screens/{chromium-desktop,webkit-iphone13}/*-{light,dark}.png` (D01..D14, настройки, политика, вход по ключу; 34 на профиль), генерирует `e2e/tests/screens/screens.spec.ts`. Встроенного просмотрщика PDF в headless-браузерах нет, поэтому на D09 видна карточка «Откройте PDF в новой вкладке».

## Отклонения

1. «Добавить PDF» открывает «Новый документ» в состоянии `idle` с зоной перетаскивания (D04, верх), а не сразу системный выбор файла: так же ждут a11y-тесты QA, и это состояние `idle` машины загрузки. На онбординге «Выбрать первый PDF» открывает выбор файла сразу.
2. `upload.file.meta` «{size} · {n} {страница}»: число страниц до сохранения неизвестно (его считает сервер в `POST /documents`), в строке файла формы только размер. На странице документа «PDF · {size} · {n} стр.» из `file.page_count`.
3. Пустая дата без «Дата не указана в документе» считается ошибкой `date_invalid`: путь пользователя требует явного «неизвестно», отдельного текста для пустого поля в словаре нет.
4. Список грузится клиентом (TanStack Query), а не RSC с первыми 200 документами (TZ §6): сессия и CSRF живут в браузере. First Load JS `/` 205 КБ при бюджете 180 КБ: диалоги, форма и zod уже вынесены в ленивые чанки; остаток: Radix (popover, tooltip, dialog, radio, checkbox, toast), TanStack Query, nuqs, date-fns календаря.
5. Ключ идемпотентности экспорта создаётся на каждый выбранный состав (радио-строку), а не на открытие диалога: тело запроса у каждого состава своё, один ключ дал бы `idempotency_key_reused`.
6. «Сохранить в архив» после обрыва загрузки повторяет загрузку и сохраняет без второго нажатия (D05 показывает «Сохраняем…» в этом состоянии).
7. Ссылки «Скачать» и «Скачать ZIP» без атрибута `download`: WebKit iOS такие ссылки игнорирует, а API и так отдаёт `Content-Disposition: attachment`.
8. Фразы `{period}` пустого поиска стоят константой из `docs/texts.md` §10 до появления ключей (запрос выше).
9. TC-082 проверяет «сначала только 401, затем только 429, не позже шестой попытки»: лимит входа 5 за 15 минут на IP общий для всего прогона, и ключевые тесты в одном файле идут последовательно.

## Решения владельца 11.11.2026

| Что | Как сделано | Тесты |
|---|---|---|
| Путь назад со всех экранов, кроме списка | Один компонент `BackLink` («← К документам») над заголовком: настройки и экран после удаления архива, вход по ключу, политика, документ (заменил «Все документы» D09) и его ошибки, новые `app/not-found.tsx` и `app/error.tsx`. Ведёт к списку с фильтрами, с которыми его покинули (`list-url.ts`, `sessionStorage`); пока в браузере нет архива, называется «На главную» и ведёт на стартовый экран; до ответа `GET /session` скрыт (`invisible`). Диалоги и листы (экспорт, фильтр, добавление, удаление, ключ) уже закрываются крестиком «Закрыть», «Отмена» и Esc с возвратом фокуса: вторую кнопку «назад» в них не добавлял | `BackLink.test.tsx`, E2E `navigation.spec.ts` (TC-116), `document.spec.ts` (TC-050) |
| Значок «i» у «Дата документа» | `components/ui/info-tip.tsx` на Radix Popover: наведение мышью, фокус, нажатие; Esc и нажатие мимо закрывают, фокус остаётся на значке, пояснение связано с ним `aria-describedby`. Место под значок: `labelAddon` у `Input` | `UploadDialog.test.tsx`, E2E `document-date.spec.ts` (TC-117) |
| Автозаполнение даты | `lib/document-date.ts`: имя файла, затем `/CreationDate` в первом и последнем МиБ файла; только реальные дни с 1900 года по сегодня; 1 января 00:00:00 пропускается (у всех шести фикстур `D:20000101000000`). Подстановка не считается вводом: Esc закрывает форму без вопроса. Подпись под полем связана с ним `aria-describedby` и исчезает после правки. Без новых зависимостей | `document-date.test.ts` (40 случаев), `UploadDialog.test.tsx`, E2E `document-date.spec.ts` (TC-118) |
| «Такой даты нет» раньше времени | Было: после неудачного сохранения ошибка не уходила, пока дату стирали и набирали заново. Стало: неполная дата снимает ошибку и не проверяется, полная проверяется сразу | `UploadDialog.test.tsx` (TC-119) |
| Пустое место на онбординге | Карточка загрузки от 1024 px растягивается на высоту левой колонки, содержимое по центру, как на D01; телефон без изменений | Снимки D01 |
| Ключ после первого документа «кривой» | Кольцо фокуса «Скопировать» срезал `overflow-y-auto` области содержимого `Dialog` (последний контрол вплотную к краю): у области запас снизу на кольцо, отрицательный отступ возвращает расстояние. Второй тёмный прямоугольник был размытой чёрной `shadow-3` на подложке: у модалки и листа новый токен `--shadow-dialog` (тёмная тема только рамка `#2E2E32`, ADR-050). Все отступы были 3,5 px за шаг (Tailwind `0.25rem` от корня 14 px): `--spacing` теперь `--space-1`, 4 px. Переход: ключ грузится не лениво, `Dialog handOff` не гасит и не зажигает подложку заново и наследует цель возврата фокуса; закрывшийся диалог не забирает фокус у открывшегося. Тост «Документ добавлен · Открыть» и подсветка строки ждут «Готово» (тост закрывал «Готово» на телефоне, «Открыть» уводил от ключа); после «Готово» фокус на заголовке «Документы» | `dialog.test.tsx`, `HomeScreen.test.tsx` (TC-004), E2E `onboarding.spec.ts` (TC-004), снимки `key-dialog-*` |

## Наблюдения для других агентов

1. Прокси Next добавляет 0,5–1,5 с к каждому запросу `/api/v1/*` на этом стенде (API сам отвечает за 10–30 мс); `POST /documents` под 2..3 воркерами занимает до 6 с. В E2E ожидание сохранения 15 с.
2. Журнал запросов API на этом стенде пишет только `/healthz` (после `BE-15` с приглушёнными логгерами).
