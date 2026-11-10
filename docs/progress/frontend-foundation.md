# Блок 2: фундамент фронтенда (FE-01..FE-09, OPS-06 для web)

Статус: готово. Агент FRONTEND-FOUNDATION, 10.11.2026.

## Что сделано

| Задача | Файлы | Итог |
|---|---|---|
| FE-01 Токены и тема | `styles/theme.css`, `app/globals.css`, `app/layout.tsx`, `app/providers.tsx`, `components/ui/theme.ts`, `components/ui/theme-toggle.tsx` | Tailwind 4 читает переменные `tokens.css` напрямую (`@theme inline reference`), палитры и шкалы Tailwind по умолчанию сброшены. Тема ставится inline-скриптом с nonce до первой отрисовки: выбор из `localStorage`, иначе `prefers-color-scheme`. Провайдеры: TanStack Query, nuqs, тосты |
| FE-01 Линтер токенов | `eslint-rules/design-tokens.mjs`, `eslint.config.mjs` | `eslint-plugin-tailwindcss` не понимает Tailwind 4, поэтому написаны свои правила: `no-hex-color` (любой литерал `#rgb…` в `.ts/.tsx`) и `tailwind-tokens` (произвольные значения `gap-[13px]`, `bg-(--x)` и отступы вне шкалы 0.5/1/1.5/2/2.5/3/4/5/6/8/12/16 в `className`, `cn()` и `*Classes`) |
| OPS-06 Заголовки | `middleware.ts` | CSP с nonce на каждый запрос, `Referrer-Policy: no-referrer`, `Permissions-Policy: camera=(), geolocation=(), microphone=()`, `nosniff`. `connect-src` добавляет origin хранилища (`S3_PUBLIC_ENDPOINT`, по умолчанию `http://localhost:9000`) для presigned POST |
| FE-03 Button | `components/ui/button.tsx` | 5 вариантов × 3 размера; loading не меняет ширину; disabled через `aria-disabled` с причиной в `aria-describedby` |
| FE-04 Поля | `field.tsx`, `input.tsx`, `date-input.tsx`, `textarea.tsx` | Подпись сверху, подсказка или ошибка снизу, `aria-invalid`; DateInput с маской и календарём; Textarea со счётчиком |
| FE-04 Тексты и форматы | `scripts/gen-texts.mjs`, `lib/texts.ts`, `lib/format.ts` | См. разделы ниже |
| FE-05 Выбор | `segmented-control.tsx`, `radio-row.tsx`, `checkbox.tsx` | Radix RadioGroup и Checkbox, строка и чекбокс кликабельны целиком |
| FE-06 Dialog/Sheet | `dialog.tsx` | От 768 px модалка 560/440, ниже нижний лист с `pb-safe`; фокус-ловушка, Esc, возврат фокуса, `initialFocus` |
| FE-07 | `toast.tsx`, `banner.tsx`, `skeleton.tsx` | Тосты внизу по центру, 4 с, `aria-live="polite"`; Banner D14; Skeleton и `useDelayedFlag(1000)` |
| FE-08 IconButton | `icon-button.tsx` | 40/32, `aria-label` обязателен по типу, подсказка при наведении |
| FE-09 | `tag.tsx`, `chip.tsx`, `alert.tsx` | TypeTag, UndatedTag, Chip, Alert info/warn/danger/success |
| Галерея | `app/(dev)/ui/page.tsx`, `gallery.tsx` | `/ui`: все состояния в светлой и тёмной панели рядом, плюс диалоги, календарь и тост; в production отдаёт 404 |

Зависимости (отдельный коммит `build(web)`): `@radix-ui/react-tooltip` 1.4.1; dev: `@testing-library/user-event` 14.6.9, `axe-core` 4.14.0, `@vitest/coverage-v8` 5.1.0. Скрипты `package.json`: `gen:texts`, `test:coverage`.

## API компонентов (`components/ui/*`)

Все компоненты клиентские, `className` у них только для раскладки (ширина, отступ снаружи).

| Компонент | Пропсы |
|---|---|
| `Button` | `variant: primary\|secondary\|tertiary\|danger\|dangerText`, `size: sm\|md\|lg`, `icon?: LucideIcon`, `loading?`, `loadingText?`, `disabled?`, `disabledReason?` + атрибуты `<button>` (`type` по умолчанию `button`). `buttonClasses({variant,size,disabled})` для ссылок-кнопок |
| `IconButton` | `aria-label: string` (обязателен), `icon: LucideIcon`, `size: md\|sm`, `variant: ghost\|outline`, `disabled?`, `disabledReason?` |
| `Input` | `label`, `labelHidden?`, `hint?`, `error?`, `counter?: string`, `leading?`, `trailing?` + атрибуты `<input>` |
| `DateInput` | `label`, `value: string` (текст `дд.мм.гггг`), `onChange(text)`, `max?: 'YYYY-MM-DD'`, `hint?`, `error?`, `disabled?`. Проверка: `parseDate(text)` из `lib/format` |
| `Textarea` | `label`, `hint?`, `error?`, `counter?: (length) => string` + атрибуты `<textarea>` |
| `SegmentedControl<T>` | `options: {value,label}[]`, `value: T \| undefined`, `onValueChange`, `fullWidth?`, `disabled?`, `error?`; имя: `label` или `aria-label` или `aria-labelledby` (проверяется типом) |
| `RadioRowGroup<T>` / `RadioRow` | группа: `value`, `onValueChange`, имя как у сегмента; строка: `value`, `title`, `description?`, `disabled?` |
| `Checkbox` | `label` или `aria-label`, `checked: boolean \| 'indeterminate'`, `onCheckedChange` и прочие пропсы Radix Checkbox |
| `Dialog` | `open`, `onOpenChange`, `title`, `description?`, `width: form\|confirm`, `initialFocus?: RefObject`, `footer?`, `children?`. `DialogClose` для кнопки «Отмена» |
| `ToastProvider` / `useToast()` | `show({ title, action?: {label,onClick}, durationMs? })` |
| `Banner` | `icon?`, `title?`, `children`, `action?` |
| `Alert` | `variant: info\|warn\|danger\|success`, `title?`, `children?`, `action?` |
| `Skeleton` / `useDelayedFlag(active, delayMs = 1000)` | `className` задаёт размер; хук возвращает `true` только после задержки |
| `TypeTag` / `UndatedTag` | `type: analysis\|conclusion\|other` (тип из `openapi.yaml`); «Не указана» |
| `Chip` | `text` (строка словаря «Поле: значение»), `onRemove` |
| `ThemeToggle` | без пропсов |

## Тексты (`lib/texts.ts`)

Генерируется из `docs/texts.md` командой `pnpm --filter web gen:texts`: 226 ключей интерфейса, 32 кода ошибок (`errorTitles`), формы склонения (`plurals.документ`, `страница`, `найден`, `участвует`). `t(key, params)` подставляет `{имя}`, набор параметров проверяется типом по ключу. Тест `lib/texts.test.ts` падает, если файл разошёлся со словарём. Файл исключён из prettier, чтобы сверка была побайтной.

## Форматы (`lib/format.ts`)

`plural`, `formatDate` (`2026-04-08` → `08.04.2026`), `formatDateTime` (`дд.мм.гггг, чч:мм`, Europe/Moscow или зона пользователя), `formatSize` (`79 КБ`, `2,4 МБ`, неразрывный пробел), `titleFromFileName`, `maskDate`, `parseDate` (только реальные даты).

## Проверка (команды и результат)

| Команда | Результат |
|---|---|
| `pnpm --filter web lint` | eslint `--max-warnings 0` и prettier: чисто |
| `pnpm --filter web typecheck` | `tsc --noEmit`: чисто |
| `pnpm --filter web test:coverage` | 27 файлов, 247 тестов зелёные (весь web, с тестами других агентов); `lib/`: строки 100%, ветви 96,8%, `format.ts` 100/96 |
| `pnpm --filter web build` | Compiled successfully; `/ui` 171 kB First Load, Middleware 34,3 kB |
| `BASE_URL=… node docs/progress/frontend-foundation/csp-check.mjs` на `next start` | `/policy` и неизвестный URL: нарушений CSP от наших компонентов нет, `data-theme` выставлен скриптом |
| `GALLERY_URL=… node docs/progress/frontend-foundation/shots.mjs` | 13 снимков, ошибок в консоли нет, ширина кнопки «Сохранить в архив» и «Сохраняем…» 157,25 px в обоих состояниях, кнопка листа 48 px, Esc: календарь, затем диалог |

Тесты по пунктам задания:

| Проверка | Где |
|---|---|
| DateInput: 31.02.2026 невалидна, 29.02.2028 валидна | `date-input.test.tsx`, `lib/format.test.ts` |
| format: 79114 → «79 КБ», 2,4 МБ, даты, «01-general-blood-test.pdf» → «General blood test», plural 1/2/5/11/21/22 | `lib/format.test.ts` |
| Button: loading держит ширину, `aria-disabled` с причиной, disabled не отправляет форму | `button.test.tsx` |
| SegmentedControl стрелками | `choice.test.tsx` |
| RadioRow: клик по тексту выбирает | `choice.test.tsx` |
| Dialog: Esc и возврат фокуса, ловушка фокуса, фокус на «Отмена», Enter не удаляет | `dialog.test.tsx` |
| Календарь внутри диалога: Esc закрывает сначала календарь, потом диалог | `date-input.test.tsx` (в StrictMode) и в браузере |
| Toast `aria-live="polite"`, действие, 4 с | `feedback.test.tsx` |
| `useDelayedFlag` | `feedback.test.tsx` |
| IconButton без `aria-label` не компилируется | `icon-button.test.tsx` (`@ts-expect-error`) |
| axe без serious/critical на всей галерее и с открытым диалогом | `app/(dev)/ui/gallery.test.tsx`, плюс по каждому компоненту |
| Тема без вспышки: скрипт, сохранённый выбор, системная тема | `theme.test.ts`, `theme-toggle.test.tsx` |
| CSP, заголовки, matcher | `middleware.test.ts` |
| Линтер токенов | `eslint-rules/design-tokens.test.ts` (RuleTester) |

## Снимки

Сделаны Playwright из пакета `e2e` (1440 × 900 и 390 × 844, `reducedMotion: reduce`), лежат в `docs/progress/frontend-foundation/`:

- `gallery-light.png`, `gallery-dark.png`: все компоненты, светлая и тёмная панели рядом, корень в светлой и тёмной теме;
- `dialog-form-light.png`, `dialog-form-dark.png`: форма как D02;
- `date-popover-light.png`, `date-popover-dark.png`: календарь под полем даты внутри модалки;
- `dialog-delete-light.png`, `dialog-delete-dark.png`: подтверждение как D11 и тёмный D11;
- `toast-light.png`, `toast-dark.png`;
- `sheet-form-mobile-light.png`, `sheet-delete-mobile-light.png`: нижние листы как M03 и M07.

Сверка с брендбуком на глаз: слои фона, главная кнопка почти чёрная и почти белая в тёмной теме, красное только в подтверждении, полоска `accent` у выбранного сегмента, порядок «Отмена» и действие на десктопе и столбиком на мобильном совпадают с D02, D11, M03, M07.

## Решения

- `@theme inline reference`: значения не дублируются в `:root`, утилиты ссылаются на переменные `tokens.css`, поэтому две темы работают из одной разметки. Брейкпоинты повторены литералами: медиазапросы не читают переменные.
- Анимации появления только с `motion-safe:`. При `prefers-reduced-motion` все длительности 0 мс, браузер не шлёт `animationstart`, и Radix Presence ждёт конец анимации вечно: подсказки и поповеры не исчезали.
- Подсказка IconButton только при наведении (брендбук §13). Подсказка по фокусу ложилась поверх поповера и диалога и забирала их Esc.
- Крестик диалога последний в DOM и спозиционирован в правый верхний угол: начальный фокус попадает в содержимое (первое поле или «Отмена»), а не на крестик.
- Кнопка календаря не `Popover.Trigger`: с собственным якорем Radix перемонтирует триггер и теряет фокус. Календарь привязан ко всему полю, фокус ставится в `onOpenAutoFocus` (после паузы ловушки диалога), при закрытии возвращается в поле ввода.
- Регион тостов рендерится после гидратации: Radix отдаёт его с атрибутом `style`, который CSP `style-src` блокирует.
- В dev сервер галереи работал на копии `apps/web` в `/tmp/fe-web` (порт 3311): общий `.next` пересобирали другие агенты, а на 3300 кто-то запрашивал `/` с ещё незаконченным кодом. Чужие контейнеры и процессы не трогал.

## Отклонения и вопросы

1. Значений нет в `tokens.json`, взяты из брендбука и добавлены в `styles/theme.css` с комментарием: текст кнопки lg 15 px (§5), ширины модалок 560 и 440 (§9), кольцо фокуса поля 22% `accent` и рамка ошибки 2 px (§6), тень выбранного сегмента и строки (FE-05, D12). Вопрос SPEC: внести их в `tokens.json`.
2. В словаре нет текста для региона тостов: Radix требует непустую подпись, а по умолчанию она английская. Сейчас `app.name` («Медархив»). Нужен ключ вида `toast.region`.
3. В словаре нет подписей кнопок «предыдущий/следующий месяц» календаря: сейчас кнопку называет целевой месяц из `Intl` («октябрь 2026 г.»). Нужны ключи вида `calendar.prevMonth`, `calendar.nextMonth`.
4. Граница чекбокса и радио 2 px (в `app.css` 1,5 px: в Tailwind 4 ширины рамок только целые, токена нет). Иконка в UndatedTag и галочка чекбокса 14 px (брендбук: 16/20/24). Иконка IconButton 20 px в 40 и 16 px в 32, как в брендбуке и `app.css` (в ТЗ FE-08 «16 или 24»).
5. Встроенная страница 404 Next.js использует inline-стили, CSP их блокирует (страница работает, но без оформления). Нужен `app/not-found.tsx` на токенах: это маршрут агента экранов.
6. `/ui` собирается в production, но отдаёт 404 (`notFound()` по `NODE_ENV`); полностью исключить маршрут из сборки без правки `next.config` нельзя.
7. `titleFromFileName` для имени только из цифр («20260408.pdf») даёт пустую строку, форма попросит название.
8. На мобильном тост может перекрыть закреплённую кнопку «Добавить PDF» на время показа (4 с): отступ региона `pb-safe`. Если мешает, нужен токен высоты закреплённой панели.
9. First Load JS главной страницы 205 kB (бюджет ТЗ §6 180 kB gzip); общий слой 102 kB, остальное страница. Проверить на этапе QA с gzip.
10. `prettier-plugin-tailwindcss` не знает классов темы и ставит их в начало списка; на работу не влияет.
