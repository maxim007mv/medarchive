# QA-01: фикстуры загрузки

Статус: готово. Агент QA-FIXTURES, 10.11.2026.

## Что сделано

| Файл | Назначение |
|---|---|
| `qa/fixtures/generate.py` | uv-скрипт (PEP 723, Python 3.12, `pypdf==7.0.1`, `cryptography==50.0.2`), пишет 5 фикстур в `qa/fixtures/generated/` или в `--out DIR` |
| `qa/fixtures/generate.py.lock` | Lock-файл скрипта (`uv lock --script`), транзитивные зависимости закреплены |
| `qa/fixtures/manifest.json` | 6 исходных PDF и 5 сгенерированных: путь или имя, sha256, размер, название, тип, дата, `expected_order`, ожидаемый код API, TC |
| `qa/fixtures/test_fixtures.py` | 18 pytest-проверок: манифест против файлов, свойства фикстур, детерминизм, порядок по правилу сортировки |
| `qa/README.md` | Запуск и таблица «фикстура → ожидание → TC» |

Решения:
- `big-21mb.pdf` собирается вручную: корректный одностраничный PDF с правильной xref, добивка пробелами в потоке содержимого страницы до ровно 22020097 байт. Открывается pypdf в `strict=True`.
- `encrypted.pdf` это копия 01, зашифрованная pypdf `AES-256` (V5, R6, `/AESV3`), пароль `secret`. pypdf берёт ключ файла, соли, IV и `/ID` из `secrets.token_bytes`; на время шифрования он подменяется потоком `random.Random(1)`, поэтому `/ID` и все байты фиксированы. pikepdf проверен и отброшен: даже с `static_id=True` R6 недетерминирован (случайный ключ и соли qpdf).
- `fake.pdf` это зашитая константа PNG 1x1 (67 байт, проверена Pillow).
- `broken.pdf` это первые 39557 байт из 79114 файла 01: сигнатура `%PDF-` на месте, pypdf падает при открытии (`PdfStreamError` в нестрогом режиме, `PdfReadError: EOF marker not found` в строгом). Значит бэкенд вернёт `pdf_unreadable`, а не `not_pdf`.

## Проверка

| Команда | Результат |
|---|---|
| `shasum -a 256 MedArchive/05_qa/fixtures/*.pdf`, pypdf: версия, страницы, шифрование, Producer | 6 файлов, `%PDF-1.4`, 1 страница, не зашифрованы, ReportLab, текстовый слой есть; размеры совпадают с аудитом |
| `uv run qa/fixtures/generate.py` дважды, `shasum -a 256` до и после | Хэши идентичны; вывод одна строка `wrote 5 fixtures to ...` |
| `uv run qa/fixtures/generate.py --out /tmp/qa-gen2` | Те же 5 хэшей, что и в `qa/fixtures/generated/` |
| `uv run --with pytest==9.2.0 --with 'pypdf[crypto]==7.0.1' pytest qa/fixtures` | 18 passed |
| `uv run --with pytest --with pypdf pytest qa/fixtures` (команда из задачи) | 17 passed, 1 failed: без `cryptography` pypdf бросает `DependencyError` на открытии AES-файла |
| Мутации: без подмены `secrets.token_bytes`; `BIG_SIZE_BYTES = 20_971_520` | Падают 2 теста в каждом случае (хэш в манифесте, детерминизм; размер, порог лимита); файл восстановлен |
| `ruff check qa`, `ruff format --check qa` | Чисто |
| `git check-ignore -v qa/fixtures/generated/fake.pdf` | Игнорируется правилом `.gitignore:20` |

## Расхождения и риски

- Команда тестов из задачи не годится: нужна `pypdf[crypto]`. В README и docstring теста указана закреплённая команда с `crypto`.
- Для BE-06: pypdf без `cryptography` не может даже открыть AES-зашифрованный PDF и бросает `DependencyError`, а не возвращает `is_encrypted`. Бэкенду нужна `pypdf[crypto]` (или ловить `DependencyError` как `pdf_encrypted`), иначе TC-017 даст 500.
- Порядок 05, 03, 04, 01, 02, 06 совпадает с правилом `TZ-backend.md` §3 п. 6 (дата ↓, при равенстве раньше загруженный выше, без даты в конце) и с TC-011. Тест `test_expected_order_follows_default_sort` пересчитывает его из манифеста.
- Хэши сгенерированных файлов завязаны на `pypdf==7.0.1`: при обновлении pypdf нужно перегенерировать и обновить `manifest.json`.
- Цель `make fixtures` добавляет агент foundation; скрипт запускается ровно как `uv run qa/fixtures/generate.py` из корня.
