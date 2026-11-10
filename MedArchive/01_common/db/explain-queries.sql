SET search_path = app, public;
SET ROLE ma_app;
\pset footer off
SELECT set_config('app.workspace_id', '002606fe-2bdf-4b58-b55b-b9821e999b53', false) \g /dev/null
\echo '=== Q1 Список, первая страница (пространство на 10 000 документов)'
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, type_code, title_ct, document_date, uploaded_at, version, note_ct IS NOT NULL AS has_note
FROM documents WHERE workspace_id = '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid AND deleted_at IS NULL
ORDER BY list_key, uploaded_at, id LIMIT 51;
\echo '=== Q2 Следующая страница по курсору (keyset, без OFFSET)'
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, type_code, title_ct, document_date, uploaded_at, version
FROM documents WHERE workspace_id = '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid AND deleted_at IS NULL
  AND (list_key, uploaded_at, id) > (DATE '1900-01-01' - DATE '2025-06-01', TIMESTAMPTZ '2025-06-01 10:00+03', '00000000-0000-0000-0000-000000000000'::uuid)
ORDER BY list_key, uploaded_at, id LIMIT 51;
\echo '=== Q3 Период по дате документа + matched и undated_excluded одним запросом'
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) FILTER (WHERE list_key <> 2147483647) AS matched,
       count(*) FILTER (WHERE list_key = 2147483647) AS undated_excluded
FROM documents WHERE workspace_id = '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid AND deleted_at IS NULL
  AND (list_key BETWEEN DATE '1900-01-01' - DATE '2025-04-30' AND DATE '1900-01-01' - DATE '2025-04-01'
       OR list_key = 2147483647);
\echo '=== Q4 Поиск «анализ» через слепой индекс триграмм (GIN)'
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title_ct FROM documents
WHERE workspace_id = '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid AND deleted_at IS NULL
  AND title_bidx @> '{-8425595970062312051,-2339064653628628107,1212668895800741549,1962914994022631601,2456375386582506399,6182701532411684708,7347711748363165975}'::bigint[]   -- хэши триграмм запроса считает приложение (HMAC-SHA256, ключ пространства)
ORDER BY list_key, uploaded_at, id LIMIT 51;
\echo '=== Q5 Период по дате загрузки в часовом поясе Europe/Moscow'
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, document_date, uploaded_at FROM documents
WHERE workspace_id = '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid AND deleted_at IS NULL
  AND uploaded_at >= (DATE '2025-04-01')::timestamp AT TIME ZONE 'Europe/Moscow'
  AND uploaded_at <  (DATE '2025-04-30' + 1)::timestamp AT TIME ZONE 'Europe/Moscow'
ORDER BY uploaded_at, id LIMIT 51;
\echo '=== Q6 Только документы без даты'
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, uploaded_at FROM documents
WHERE workspace_id = '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid AND deleted_at IS NULL AND list_key = 2147483647
ORDER BY list_key, uploaded_at, id LIMIT 51;
\echo '=== Q7 Обычное пространство (100 документов), первая страница'
SELECT set_config('app.workspace_id', '00aa0cd3-8275-408c-998f-981873c54c63', false) \g /dev/null
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, type_code, title_ct, document_date, uploaded_at, version
FROM documents WHERE workspace_id = '00aa0cd3-8275-408c-998f-981873c54c63'::uuid AND deleted_at IS NULL
ORDER BY list_key, uploaded_at, id LIMIT 51;
\echo '=== Q8 Изоляция: запрос к чужому пространству при контексте NORMAL'
SELECT count(*) AS visible_foreign FROM documents WHERE workspace_id = '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid;
\echo '=== Q9 Изоляция: без app.workspace_id не видно ничего'
SELECT set_config('app.workspace_id', '', false) \g /dev/null
SELECT count(*) AS visible_without_context FROM documents;
\echo '=== Q10 Удалённые не видны даже по прямому условию'
SELECT set_config('app.workspace_id', '002606fe-2bdf-4b58-b55b-b9821e999b53', false) \g /dev/null
SELECT count(*) AS visible_deleted FROM documents WHERE workspace_id = '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid AND deleted_at IS NOT NULL;
\echo '=== Q11 Попытка вставить документ в чужое пространство'
INSERT INTO documents (id, workspace_id, type_code, title_ct, title_bidx) VALUES (gen_random_uuid(), '00aa0cd3-8275-408c-998f-981873c54c63', 'other', gen_random_bytes(40), '{1}');
