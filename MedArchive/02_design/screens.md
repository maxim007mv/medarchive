# Экраны: каталог

Снимки сгенерированы из HTML-макетов (`02_design/source/gen.py`, стили `app.css`, шрифт Medeo) и совпадают с Figma. Обоснование каждого экрана: `01_common/11-design-rationale.md`. Шаги пути пользователя: `01_common/04-customer-journey.md`.

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

Пересборка снимков: `python3 gen.py && python3 shot.py desktop-light desktop-dark mobile-light mobile-dark` в `build/screens`; пересборка PDF брендбука: `python3 bb.py && python3 pdf.py`.