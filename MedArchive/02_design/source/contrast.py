"""WCAG 2.2 contrast of every colour pair used in the UI.

Reads ../tokens.json, writes palette.json (input for bb.py) and prints the
markdown table for brandbook.md §1.3.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKENS = HERE.parent / 'tokens.json'
PALETTE = HERE / 'palette.json'

EXEMPT = 0  # SC 1.4.3 does not apply to inactive controls
PAIRS = [
    ('Основной текст на фоне', 'text', 'bg', 4.5),
    ('Основной текст на карточке', 'text', 'surface', 4.5),
    ('Основной текст в модалке и листе', 'text', 'raised', 4.5),
    ('Вторичный текст на карточке', 'text2', 'surface', 4.5),
    ('Вторичный текст на фоне', 'text2', 'bg', 4.5),
    ('Вторичный текст на подложке (сегмент, инфо-блок)', 'text2', 'sunken', 4.5),
    ('Подписи, плейсхолдер на карточке', 'text3', 'surface', 4.5),
    ('Подписи на фоне', 'text3', 'bg', 4.5),
    ('Подписи в модалке и листе', 'text3', 'raised', 4.5),
    ('Текст главной кнопки, тост', 'onPrimary', 'primary', 4.5),
    ('Текст главной кнопки, hover', 'onPrimary', 'primaryHover', 4.5),
    ('Текст главной кнопки, нажатие', 'onPrimary', 'primaryActive', 4.5),
    ('Текст разрушительной кнопки', 'onPrimary', 'danger', 4.5),
    ('Ссылка, акцент на карточке', 'accent', 'surface', 4.5),
    ('Акцент на фоне', 'accent', 'bg', 4.5),
    ('Акцент на мягком акценте (шаги, AI-блок)', 'accent', 'accentSoft', 4.5),
    ('Текст выбранной строки', 'text', 'accentSoft', 4.5),
    ('Граница поля на карточке (1.4.11)', 'control', 'surface', 3),
    ('Граница поля на фоне (1.4.11)', 'control', 'bg', 3),
    ('Граница поля в модалке и листе (1.4.11)', 'control', 'raised', 3),
    ('Кольцо фокуса на карточке (1.4.11)', 'focus', 'surface', 3),
    ('Кольцо фокуса на фоне (1.4.11)', 'focus', 'bg', 3),
    ('Отмеченный чекбокс (1.4.11)', 'primary', 'surface', 3),
    ('Метка «Анализ»', 'analysis', 'analysisBg', 4.5),
    ('Метка «Заключение»', 'conclusion', 'conclusionBg', 4.5),
    ('Метка «Другое»', 'other', 'otherBg', 4.5),
    ('«Дата не указана», баннер, предупреждение', 'warn', 'warnBg', 4.5),
    ('Ошибка в блоке', 'danger', 'dangerBg', 4.5),
    ('Ошибка у поля, разрушительная текстовая', 'danger', 'surface', 4.5),
    ('Ошибка в модалке и листе', 'danger', 'raised', 4.5),
    ('Успех в блоке', 'success', 'successBg', 4.5),
    ('«Сохранено» на карточке', 'success', 'surface', 4.5),
    ('Текст заблокированной кнопки', 'disabledText', 'disabledBg', EXEMPT),
    ('Текст заблокированного поля', 'text3', 'sunken', EXEMPT),
]
THEMES = (('light', 'светлая'), ('dark', 'тёмная'))


def luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(fg, bg):
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def verdict(value, threshold):
    if threshold == EXEMPT:
        return 'не требуется (неактивный элемент, SC 1.4.3)'
    return 'проходит' if value >= threshold else 'НЕ проходит'


def main():
    colors = json.loads(TOKENS.read_text(encoding='utf-8'))['color']
    rows = []
    for label, fg, bg, threshold in PAIRS:
        for theme, theme_ru in THEMES:
            pal = colors[theme]
            rows.append([theme_ru, label, pal[fg], pal[bg], ratio(pal[fg], pal[bg]), threshold])
    opaque = {theme: {k: v for k, v in colors[theme].items() if v.startswith('#')} for theme, _ in THEMES}
    PALETTE.write_text(json.dumps({**opaque, 'rows': rows}, ensure_ascii=False), encoding='utf-8')

    print('| Тема | Пара | Цвет | Фон | Контраст | Порог WCAG | Итог |')
    print('|---|---|---|---|---|---|---|')
    for theme_ru, label, fg, bg, value, threshold in rows:
        limit = 'не требуется' if threshold == EXEMPT else f'{threshold}:1'
        print(f'| {theme_ru} | {label} | `{fg}` | `{bg}` | {value:.2f}:1 | {limit} | {verdict(value, threshold)} |')


if __name__ == '__main__':
    main()
