# Дизайн: Figma, контраст, сборка брендбука (DS-01..DS-06, блок 8)

Статус: готово с двумя ограничениями плана Figma Starter (ниже). Агент DESIGN, 10.11.2026.

Файл Figma: https://www.figma.com/design/wcz0Kh4DkoVRqGBEvp4uT2

## Ограничения, которые нельзя обойти на Starter

| Требование | Что мешает | Что сделано вместо |
|---|---|---|
| Коллекция `color` с режимами light и dark | `addMode` на Starter отвечает «Limited to 1 modes only» | Две коллекции `color · light` и `color · dark` с одинаковыми именами 33 переменных. Тёмный экран = копия светлого, где каждая привязка из `color · light` заменена одноимённой из `color · dark` (экземпляры остаются привязанными, замены идут как overrides). На Professional слить в одну коллекцию с двумя режимами |
| Шрифт Medeo в стилях текста | `listAvailableFontsAsync` в облачном рантайме Figma MCP не видит установленные в `~/Library/Fonts` Medeo | 12 стилей текста на Geist (база Medeo Sans, те же метрики латиницы), в описании каждого стиля указан целевой Medeo. Замена семейства в 12 стилях в Figma desktop переводит все макеты |

## Страницы Figma

Страниц 3 (лимит Starter). Служебной страницы «Служебная · дубликат» в файле не было: файл содержал 3 страницы старых HTML-снимков (Desktop Light, Desktop Dark, Mobile Light · Mobile Dark).

| Страница | id | Содержимое |
|---|---|---|
| Основа | [`23:179`](https://www.figma.com/design/wcz0Kh4DkoVRqGBEvp4uT2?node-id=23-179) | Легенда, иконки, все компоненты, слоты модалок и листов |
| Десктоп | [`18:4`](https://www.figma.com/design/wcz0Kh4DkoVRqGBEvp4uT2?node-id=18-4) | Секции «Десктоп · светлая · D01–D14» `36:1306`, «Десктоп · тёмная · D01–D14» `41:4767`, «Вне объёма: AI · D15–D16» `41:10801` |
| Мобайл | [`18:5`](https://www.figma.com/design/wcz0Kh4DkoVRqGBEvp4uT2?node-id=18-5) | Секции «Мобайл · светлая · M01–M08» `40:1953`, «Мобайл · тёмная · M01–M08» `41:9641` |

Старые HTML-снимки D01–D14 и M01–M08 (рамки `9:2`, `15:2`, `14:2`, `17:2`, `10:2`, секции `18:6`–`18:9`) удалены: их заменили экраны из компонентов. Снимки D15, D16 (`16:2`) и D15 тёмная (`10:1917`) сохранены в секции «Вне объёма: AI».

## DS-01. Переменные и стили

| Коллекция | id | Переменных | Code syntax |
|---|---|---|---|
| color · light | `VariableCollectionId:23:91` | 33 | `var(--c-*)` |
| color · dark | `VariableCollectionId:23:122` | 33 | `var(--c-*)` |
| space | `VariableCollectionId:23:153` | 13 (`0`, `0-5` … `16`) | `var(--space-*)` |
| radius | `VariableCollectionId:27:8` | 7 (`xs` … `full`) | `var(--radius-*)` |
| size | `VariableCollectionId:27:16` | 5 (высоты контролов) | `var(--control-*)` |

Значения из `02_design/tokens.json` (включая `primaryActive`, `skel`, `skel2`). Скоупы заданы по роли, `ALL_SCOPES` нет. Старые переменные `radius/*` и `control/*` внутри `space` удалены (12 шт.) после проверки, что на них нет привязок.

Стили текста (12): display, h1, h2, h3, bodyL, body, body-medium, button-lg, label, caption, caption-medium, mono. Стили эффектов (3): `shadow/1`, `shadow/3`, `shadow/3 · dark`.

Аудит экранов: 0 сплошных заливок и обводок без привязки к переменной (28 десктопных и 16 мобильных фреймов; 1830 и 584 экземпляра).

## DS-02. Компоненты (страница «Основа»)

17 наборов вариантов, 147 вариантов; 10 одиночных компонентов; 31 иконка; 10 слотов.

| Компонент | id | Варианты |
|---|---|---|
| Button | `29:2` | 75: Variant p/s/t/dg/dgt × State default/hover/focus/loading/disabled × Size sm/md/lg; свойства Label, Icon, Glyph |
| IconButton | `31:2` | 12: Size sm/md × Style ghost/outline × State default/hover/focus |
| Input | `33:78` | 10: Kind text/search × State placeholder/filled/focus/error/disabled |
| DateInput | `33:259` | 5 состояний |
| Textarea | `33:350` | 3 состояния |
| Segment item / Segment | `31:113` / `31:118` | 2 / 6 (Count 2–4 × Width hug/fill) |
| Radio row | `31:100` | off/on |
| Checkbox | `31:75` | off/on/focus/disabled |
| Tag | `31:161` | analysis/conclusion/other/nodate |
| Chip, Kbd | `31:179`, `31:187` | одиночные |
| Toast, Banner | `33:387`, `33:429` | одиночные |
| Alert | `33:394` | info/warn/error/success |
| Modal | `35:601` | md 560 / sm 440, содержимое через INSTANCE_SWAP `Content` |
| Sheet | `35:644` | одиночный, содержимое через `Content`, safe-area 34 |
| List row, Table header | `35:266`, `35:248` | 6: State default/hover/selected × Date date/nodate |
| Mobile card | `35:568` | одиночный |
| Skeleton | `33:439` | line/block/tile |
| Также из макетов | `33:443`, `33:460`, `33:458`, `33:520`, `35:191` | Save status, File row, Progress, Step, App header (desktop-full/desktop-minimal/mobile) |

Новых цветов и компонентов вне брендбука нет (ADR-032): App header, File row, Step, Progress, Save status, Kbd повторяют элементы HTML-макетов.

## DS-03. Экраны

| Набор | Светлая | Тёмная |
|---|---|---|
| Десктоп 1440 × 900 | D01–D14 (14) | D01–D14 (14) |
| Мобайл 390 × 844 | M01–M08 (8) | M01–M08 (8) |

Все экраны собраны из экземпляров, отсоединённых экземпляров нет. D15, D16 вне объёма (AI-подсказка). Отличие от PNG-эталонов: просмотрщик PDF на D09, D10, M06 показывает заглушку страницы (в пакете нет `doc01-1.png`).

D01 и M01 содержат согласие (тексты из `docs/texts.md` §5, статус «требует утверждения владельцем»): чекбокс «Я соглашаюсь на обработку сведений о моём здоровье, которые есть в загружаемых документах, чтобы хранить их в этом архиве», ссылка «Политика обработки персональных данных», заблокированная «Выбрать первый PDF» и причина «Отметьте согласие, чтобы выбрать файл», ссылка «Уже есть архив? Открыть по ключу». Остальные тексты взяты из `04-customer-journey.md` и `06-api-contract.md` §8.

## DS-04. Слой Spec

На каждом из 44 экранов слой `Spec` (скрыт, включается видимостью): пунктирные цели нажатия, номера порядка фокуса с высотой цели («3 · 40»), легенда с отступами, правилом цели нажатия, порядком фокуса (для модалок и листов: фокус-ловушка, Esc, возврат фокуса) и списком aria-label иконок-кнопок. Имя слоя каждой иконки-кнопки равно её aria-label («Переключить тему», «Экспорт», «Фильтр», «Закрыть», «Открыть документ», «Действия с документом», «Назад к списку», «Уменьшить», «Увеличить»).

## DS-05. Контраст

`MedArchive/02_design/source/contrast.py` считает 34 пары × 2 темы = 68 строк из `tokens.json`, пишет `palette.json` и таблицу в `brandbook.md` §1.3. Все 64 обязательные пары проходят WCAG 2.2 AA. Минимальные: светлая «Граница поля на фоне» `#8B8B94` на `#F4F4F5` 3,07:1 (порог 3), светлая «Подписи на фоне» 4,80:1, светлая «Акцент на мягком акценте» 4,84:1, тёмная «Подписи в модалке» 4,87:1. Неактивные элементы без порога: тёмная `#8B8B94` на `#232326` 4,64:1, светлая `#6B6B74` на `#EBEBED` 4,43:1. В старой таблице тёмная пара disabled была посчитана на `#0A0A0A` вместо `disabledBg` `#232326`; исправлено.

## DS-06. Сборка брендбука

Скрипты в `MedArchive/02_design/source/` работают из любой папки (`pathlib` от файла скрипта), `palette.json` рядом с `bb.py`, картинки из `../screens/`, Chromium из Playwright, шрифты `fonts/MedeoSansVariable.ttf`, `fonts/MedeoMonoVariable.ttf` и `OFL.txt` из `~/Downloads/Medeo-v1.0.0`, семейства «Medeo Sans» и «Medeo Mono». Команды в `source/README.md`. Версия шрифта в `bb.py` и `brandbook.md` §2.1: 1.0.0 (ADR-043).

Результат последней сборки:

```
python3 bb.py                                  → 33 pages
uv run --with playwright python pdf.py         → overflow []
pdffonts ../brandbook.pdf                      → 130 записей, все Medeo (111 MedeoSans*, 19 MedeoMono*), не-Medeo 0
pdfinfo ../brandbook.pdf                       → Pages: 33, A4 альбом
```

Страниц 33 вместо 32: таблица контраста разделена на две страницы (светлая и тёмная). Перегенерированы снимки `desktop-light-01.png`, `desktop-dark-01.png`, `mobile-light-01.png` (согласие на D01/M01).

## Не сделано и почему

| Что | Причина |
|---|---|
| Режимы light/dark в одной коллекции | Лимит Starter: 1 режим на коллекцию |
| Medeo в стилях текста Figma | Шрифт недоступен облачному рантайму MCP; стили на Geist, переключаются в одном месте |
| Обновление `screens.md` и `TZ-design.md` (названия страниц Figma, 33 страницы PDF) | Файлы ведёт агент спецификации; мне разрешены только §1.3 `brandbook.md`, `source/`, PDF и `screens/` |
| Снимки D09, D10, M06 | Нет `doc01-1.png` в пакете; без него просмотрщик на снимке пустой, поэтому эти PNG не перегенерированы |
