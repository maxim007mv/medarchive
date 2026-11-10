# Экраны: каталог

Снимки сгенерированы из HTML-макетов (`02_design/source/gen.py`, стили `app.css`, шрифт Medeo); экраны в Figma собраны из компонентов по тем же макетам. Обоснование каждого экрана: `01_common/11-design-rationale.md`. Шаги пути пользователя: `01_common/04-customer-journey.md`.

## Figma

Файл: https://www.figma.com/design/wcz0Kh4DkoVRqGBEvp4uT2. Подробности и id узлов: `docs/progress/design.md`.

| Страница | Содержимое |
|---|---|
| Основа | Переменные, 12 стилей текста, иконки, компоненты с вариантами, слоты модалок и листов |
| Десктоп | Секции «Десктоп · светлая · D01–D14», «Десктоп · тёмная · D01–D14», «Вне объёма: AI · D15–D16» |
| Мобайл | Секции «Мобайл · светлая · M01–M08», «Мобайл · тёмная · M01–M08» |

1. Страниц три: больше не даёт тариф Starter.
2. Starter разрешает один режим на коллекцию, поэтому цвета лежат в двух коллекциях `color · light` и `color · dark` с одинаковыми именами переменных; тёмный экран привязан к `color · dark`. На платном тарифе коллекции сливаются в одну `color` с режимами light и dark.
3. Стили текста временно на Geist (база Medeo Sans с теми же метриками латиницы): облачный рантайм Figma не загружает локально установленный Medeo. Замена семейства в 12 стилях текста в Figma desktop переводит все макеты на Medeo.
4. 44 экрана (D01–D14 и M01–M08 в светлой и тёмной теме) собраны из экземпляров компонентов, отсоединённых нет. AI-экраны D15 и D16 вне объёма прототипа (ADR-042) и лежат снимками в секции «Вне объёма: AI».
5. На каждом экране скрытый слой `Spec`: цели нажатия, порядок фокуса, отступы, aria-label иконок-кнопок.

## Десктоп 1440 x 900, светлая

| Файл | Экран |
|---|---|
| `screens/desktop-light-01.png` | D01 Онбординг и пустой архив |
| `screens/desktop-light-02.png` | D02 Добавление: форма заполнена |
| `screens/desktop-light-03.png` | D03 Добавление: дата не указана |
| `screens/desktop-light-04.png` | D04 Добавление: ошибки валидации |
| `screens/desktop-light-05.png` | D05 Добавление: обрыв сети |
| `screens/desktop-light-06.png` | D06 Архив: список |
| `screens/desktop-light-07.png` | D07 Фильтр по периоду |
| `screens/desktop-light-08.png` | D08 Ничего не найдено |
| `screens/desktop-light-09.png` | D09 Просмотр документа и заметка |
| `screens/desktop-light-10.png` | D10 Редактирование описания |
| `screens/desktop-light-11.png` | D11 Удаление с подтверждением |
| `screens/desktop-light-12.png` | D12 Экспорт |
| `screens/desktop-light-13.png` | D13 Загрузка списка: скелетон |
| `screens/desktop-light-14.png` | D14 Нет связи с сервером |
| `screens/desktop-light-15.png` | D15 AI-подсказка полей: генерация |
| `screens/desktop-light-16.png` | D16 AI-подсказка полей: результат |

## Десктоп, тёмная

| Файл | Экран |
|---|---|
| `screens/desktop-dark-01.png` | D01 Онбординг и пустой архив |
| `screens/desktop-dark-02.png` | D02 Добавление: форма заполнена |
| `screens/desktop-dark-03.png` | D06 Архив: список |
| `screens/desktop-dark-04.png` | D07 Фильтр по периоду |
| `screens/desktop-dark-05.png` | D08 Ничего не найдено |
| `screens/desktop-dark-06.png` | D09 Просмотр документа и заметка |
| `screens/desktop-dark-07.png` | D11 Удаление с подтверждением |
| `screens/desktop-dark-08.png` | D12 Экспорт |
| `screens/desktop-dark-09.png` | D15 AI-подсказка полей: генерация |

## Мобильный 390 x 844, светлая

| Файл | Экран |
|---|---|
| `screens/mobile-light-01.png` | M01 Онбординг |
| `screens/mobile-light-02.png` | M02 Список |
| `screens/mobile-light-03.png` | M03 Добавление (bottom sheet) |
| `screens/mobile-light-04.png` | M04 Фильтр (bottom sheet) |
| `screens/mobile-light-05.png` | M05 Ничего не найдено |
| `screens/mobile-light-06.png` | M06 Документ и заметка |
| `screens/mobile-light-07.png` | M07 Удаление |
| `screens/mobile-light-08.png` | M08 Экспорт |

## Мобильный, тёмная

| Файл | Экран |
|---|---|
| `screens/mobile-dark-01.png` | M02 Список |
| `screens/mobile-dark-02.png` | M04 Фильтр (bottom sheet) |
| `screens/mobile-dark-03.png` | M06 Документ и заметка |
| `screens/mobile-dark-04.png` | M07 Удаление |

Пересборка снимков и PDF брендбука (33 страницы): команды в `02_design/source/README.md`. Снимки D09, D10 и M06 (`desktop-light-09.png`, `desktop-light-10.png`, `desktop-dark-06.png`, `mobile-light-06.png`, `mobile-dark-03.png`) не перегенерированы: в пакете нет `doc01-1.png` (первая страница фикстуры 01), без него просмотрщик PDF на снимке пустой.