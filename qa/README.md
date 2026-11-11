# QA: фикстуры загрузки (QA-01)

Генерация из корня репозитория: `uv run qa/fixtures/generate.py` (или `make fixtures`). Файлы пишутся в `qa/fixtures/generated/` (в `.gitignore`), повторный запуск даёт те же байты. Зависимости скрипта закреплены в `qa/fixtures/generate.py.lock`.

Проверка: `uv run --with pytest==9.2.0 --with 'pypdf[crypto]==7.0.1' pytest qa/fixtures`. Без `crypto` pypdf не открывает файлы с AES.

`qa/fixtures/manifest.json` описывает шесть исходных PDF из `MedArchive/05_qa/fixtures/` (sha256, размер, название, тип, дата, `expected_order`) и пять сгенерированных (sha256, размер, ожидаемый код ошибки API).

| Файл | Что это | Ожидание | TC |
|---|---|---|---|
| 01..06 из `MedArchive/05_qa/fixtures/` | Исходные документы, загружаются по порядку 01→06 | Порядок в списке 05, 03, 04, 01, 02, 06 | TC-010, TC-011 |
| `fake.pdf` | PNG 1x1 с расширением .pdf | `not_pdf` (415) | TC-015 |
| `big-21mb.pdf` | Корректный PDF ровно 22020097 байт | `file_too_large` (413) до передачи файла | TC-016 |
| `encrypted.pdf` | Копия 01, AES-256 (V5 R6), пароль `secret` | `pdf_encrypted` (422) | TC-017 |
| `broken.pdf` | Первая половина байтов 01, сигнатура `%PDF-` есть | `pdf_unreadable` (422) | TC-018 |
| `cyrillic «имя» файла.pdf` | Побайтовая копия 01 | Сохраняется, `filename*` в UTF-8 | TC-024 |
