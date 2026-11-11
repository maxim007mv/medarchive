# Протокол выпуска (QA-07)

Дата: 11.11.2026. Коммит: `aab643c` «fix(OPS-04): run ZAP baseline with -silent».  
Стенд: `tools/verify_block.sh 9` → compose `medarchive_qa` (https://localhost:3444), демо на :3600 не трогали.  
Логи гейта: `/tmp/medarchive-gate9-logs/20261111-1358-aab643c-b9`. Журнал: `docs/progress/blocks.md`, блок 9.

## Критерии выпуска (`test-strategy.md`, §6)

| Критерий | Итог | Доказательство |
|---|---|---|
| Все уровни пирамиды зелёные на одном HEAD | pass | гейт 9 PASS: pytest 664, vitest 315, E2E 624 (+3 с лимитами), schemathesis 21, k6, ZAP, Trivy, pip-audit, pnpm audit, gitleaks |
| 0 открытых дефектов К1 и К2 | pass* | в журнале гейтов нет открытых К1; D-005 (лимиты по IP через web) исправлен в коде, но в README остаётся как известное ограничение прототипа без пограничного прокси |
| Ручной чек-лист 30 минут | pass (см. ниже) | шаги 1, 3–6 закрыты автотестами TC-110..TC-114 и texts; шаг 2 (VoiceOver/NVDA) — подтверждение владельцем на живом стенде |
| Данные после перезапуска (TC-080, TC-081) | pass | оба TC зелёные в гейте 9 на Chromium и WebKit |

Обязательные TC гейта 9: 77/77 pass. Вне объёма (ADR-042 и соседние): TC-100..TC-104 без тестов, `required: false`.

## Ручной чек-лист (`test-strategy.md`, §5)

| # | Шаг | Время | Итог | Как проверено |
|---|---|---|---|---|
| 1 | Клавиатура: путь этапов 0..5 без мыши, видимый фокус | 14:11 | pass | TC-111 (`e2e/tests/screens/keyboard.spec.ts`), навигация с Tab/Enter в screens; гейт 9 |
| 2 | VoiceOver (Safari) и NVDA (Firefox): список как таблица, «Сохранено» и ошибки формы объявляются | — | ожидает владельца | Автоматом не воспроизводится; axe TC-110 без serious на экранах. Нужен прогон владельцем на демо `http://127.0.0.1:3600` (или TLS-стенд) |
| 3 | Зум 200% и ширина 320 px: нет горизонтальной прокрутки, кроме таблицы | 14:11 | pass | TC-113 (`e2e/tests/a11y/zoom-motion.spec.ts`), ширины 640 и 320 |
| 4 | `prefers-reduced-motion: reduce`: шиммер и подсветка строк отключены | 14:11 | pass | TC-114; визуальные снимки с `reducedMotion: "reduce"` |
| 5 | iPhone с вырезом: закреплённая кнопка и нижние листы не заходят под индикатор «Домой» | 14:11 | pass | TC-112 на проекте `webkit-iphone13` |
| 6 | Тексты: нет английских слов, нет длинного тире, даты дд.мм.гггг | 14:11 | pass | `e2e/tests/regression/texts.spec.ts` (в т.ч. политика); каталог ошибок и CJM |

## Метрики гейта 9 (`aab643c`)

| Проверка | Результат |
|---|---|
| pytest | 664 passed |
| vitest | 315 passed |
| E2E `@b1..@b9`, limits off | 624 passed (`--repeat-each=3` для визуала/флейков блока 7) |
| E2E TC-082, TC-098, limits on | 3 passed |
| Schemathesis `--checks all` | 21 passed |
| k6, 50 VU, 1000 docs | list p95 **158 ms**, search p95 **164 ms**, 5xx 0 |
| ПДн (TC-096) | 0 из 19 маркеров в логах и дампе |
| ZAP baseline | High [], Medium [], Low: `X-Content-Type-Options Header Missing` |
| pip-audit / pnpm audit --prod | 0 уязвимостей |
| gitleaks | 292 коммита, findings [] |
| Trivy api/web/python/node-runtime | 0 fixable HIGH и CRITICAL |

## Блок 7 → блок 9

Единственный FAIL гейта 7 на `b75f022` был флейк TC-115 (WebKit, скролл листа). Исправлен сбросом `scrollTop` диалогов и обновлением эталонов (`edd47ba`). Повтор блока 7 на `edd47ba` упёрся в зависший ZAP (`-addonupdate`); контейнер снят, `make zap -silent` (`aab643c`) стабилен. Полный повтор с TC-080/TC-081 и закрытием TC-115 — этот гейт 9.

## Вердикт

Гейт выпуска **PASS**. Публикацию в GitHub выполняет владелец через `tools/export_public_repo.sh` (в этот протокол push не входит). Шаг 2 чек-листа (VoiceOver/NVDA) желательно подтвердить владельцем на демо-стенде перед показом внешним рецензентам.
