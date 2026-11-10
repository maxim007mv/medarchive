# Блоки 3..6: экраны фронтенда (FE-10..FE-22)

Статус: в работе. Агент FRONTEND-SCREENS, 10.11.2026.

## Запросы к агенту компонентов

| Что | Зачем | Статус |
|---|---|---|
| Ключи `empty.period.range` «за {from} – {to}», `empty.period.from` «с {from}», `empty.period.to` «по {to}» в `docs/texts.md` §10 и `lib/texts.ts` | Подстановка `{period}` в `empty.text.queryPeriod` и `empty.text.period` (D08); сейчас эти фразы есть только в абзаце под таблицей §10, генератор их не берёт | открыт |
| `lib/policy.ts` из `docs/policy.md` тем же генератором, что `lib/texts.ts`: `export const policyVersion = "2026-11-10"` и `export const policyMarkdown = "…"` (байты файла) | Страница `/policy` и `consent.policy_version` в `POST /api/v1/workspaces`; `docs/` исключён из контекста Docker-сборки web (`.dockerignore`), читать файл при сборке нельзя | открыт |
| Toast: провайдер и viewport внутри `Providers`, хук или функция показа с действием и длительностью (6 с для «Заметка очищена · Вернуть») | Тосты списка, заметки, удаления, ключа | открыт |

## Что сделано

| Задача | Файлы | Тест |
|---|---|---|
| FE-10 клиент API | `lib/api/client.ts` (openapi-fetch, `X-CSRF-Token` из `GET /api/v1/session`), `lib/api/errors.ts` (problem+json → `ApiError`, голый 5xx прокси и сбой fetch → `NetworkError`), `lib/api/connectivity.ts`, `lib/api/queries.ts` (ключи `['documents', filters]`, `['document', id]`) | `lib/api/client.test.ts` |
| FE-12 загрузка | `lib/api/upload.ts` (проверка типа, `%PDF-`, 20971520 байт; XHR presigned POST: поля, затем файл), `components/documents/upload-machine.ts`, `use-upload-file.ts` | `lib/api/upload.test.ts`, `upload-machine.test.ts` |
| FE-14 фильтры в URL | `lib/filters.ts` (nuqs: `q`, `date_field`, `from`, `to`, `type`, `order_by`, `undated`; ISO в URL) | `lib/filters.test.ts` |
| FE-18 заметка | `components/documents/use-note-autosave.ts` | `use-note-autosave.test.tsx` |

## Проверка

## Отклонения

## Открытые вопросы
