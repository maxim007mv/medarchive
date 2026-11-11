# Исходники брендбука и снимков экранов

Скрипты работают из любой папки: пути считаются от расположения файла. Нужны Python 3.11+ и [uv](https://docs.astral.sh/uv/).

| Файл | Что делает |
|---|---|
| `contrast.py` | Считает контраст WCAG 2.2 по `../tokens.json`, пишет `palette.json`, печатает таблицу для `brandbook.md` §1.3 |
| `gen.py` | HTML-макеты экранов (`desktop-light.html` и др.) из `app.css` |
| `shot.py` | PNG фреймов в `../screens/`; `board:N` снимает только фрейм N |
| `bb.py` | `brandbook.html` из `palette.json`, `gen.py` и `../screens/*.png` |
| `pdf.py` | `../brandbook.pdf` (A4 альбом), печатает `overflow [...]` |
| `fonts/` | Medeo Sans и Medeo Mono 1.0.0 (вариативные TTF) и `OFL.txt` |

## Пересборка PDF

```sh
cd MedArchive/02_design/source
uv run --with playwright playwright install chromium   # один раз
python3 contrast.py > /tmp/contrast.md
python3 bb.py
uv run --with playwright python pdf.py                  # ожидается: overflow []
pdffonts ../brandbook.pdf                               # brew install poppler; все шрифты Medeo
```

## Пересборка снимков

```sh
python3 gen.py
uv run --with playwright python shot.py desktop-light desktop-dark mobile-light mobile-dark
```

Экраны D09, D10 и M06 ссылаются на `doc01-1.png` (первая страница фикстуры `01-general-blood-test.pdf`), которого нет в пакете. Без него просмотрщик PDF на снимке пустой, поэтому обновляйте отдельные фреймы, например `shot.py desktop-light:1 mobile-light:1`.
