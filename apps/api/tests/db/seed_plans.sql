-- MedArchive/01_common/db/seed-load.sql adapted to the schema after migration 0002:
-- no bidx_key_ciphertext (ADR-047), fixed ids of the heavy and the normal workspace, fixed index
-- key of the heavy one and a fixed random seed. 2000 workspaces of 100 documents and one of 10000,
-- 3% deleted. Runs as superuser (RLS bypass), like the reference stand.
SELECT setseed(0.46);
SET search_path = app, public;
CREATE TEMP TABLE titles(t text);
INSERT INTO titles VALUES ('Общий анализ крови'),('Биохимический анализ крови'),('Липидограмма'),('Заключение терапевта'),
('УЗИ почек и мочевого пузыря'),('ЭКГ покоя'),('Анализ мочи общий'),('Гормоны щитовидной железы'),('Заключение кардиолога'),
('МРТ коленного сустава'),('Рентген грудной клетки'),('Коагулограмма'),('Ферритин'),('Витамин D'),('Заключение невролога'),
('УЗИ брюшной полости'),('Холтер ЭКГ суточный'),('Гликированный гемоглобин'),('Выписка из стационара'),('Прививочный сертификат');
CREATE FUNCTION pg_temp.bidx(title text, k bytea) RETURNS bigint[] LANGUAGE sql IMMUTABLE AS $$
  SELECT array_agg(DISTINCT ('x'||encode(substr(hmac(convert_to(g,'UTF8'), k, 'sha256'),1,8),'hex'))::bit(64)::bigint)
  FROM unnest(show_trgm(lower(replace(title,'ё','е')))) g $$;
CREATE TEMP TABLE ws AS
SELECT CASE n WHEN 1 THEN '002606fe-2bdf-4b58-b55b-b9821e999b53'::uuid
              WHEN 2 THEN '00aa0cd3-8275-408c-998f-981873c54c63'::uuid
              ELSE gen_random_uuid() END AS id,
       n,
       CASE n WHEN 1 THEN sha256(convert_to('medarchive-plans-heavy', 'UTF8')) ELSE gen_random_bytes(32) END AS k
FROM generate_series(1, 2001) n
-- Documents are inserted in workspace id order, as on the reference stand (there ws was built
-- ORDER BY id). The physical correlation of workspace_id (1 here, about 0.1 otherwise) decides
-- between Index Scan and Bitmap Heap Scan + Sort for Q5.
ORDER BY id;
INSERT INTO workspaces (id, dek_ciphertext, kek_key_id) SELECT id, gen_random_bytes(64), 'abj-kek-1' FROM ws;
INSERT INTO documents (id, workspace_id, type_code, title_ct, title_bidx, note_ct, document_date, uploaded_at)
SELECT gen_random_uuid(), ws.id, (ARRAY['analysis','conclusion','other'])[1 + (g % 3)],
       gen_random_bytes(29 + octet_length(tt.t)), pg_temp.bidx(tt.t, ws.k),
       CASE WHEN g % 4 = 0 THEN gen_random_bytes(80) END,
       CASE WHEN g % 12 = 0 THEN NULL ELSE DATE '2024-01-01' + (g % 1000) - (g % 365) END,
       TIMESTAMPTZ '2024-01-01' + (g % 1000) * interval '1 day' + random() * interval '20 hours'
FROM ws CROSS JOIN LATERAL generate_series(1, CASE WHEN ws.n = 1 THEN 10000 ELSE 100 END) g
CROSS JOIN LATERAL (SELECT t FROM titles OFFSET (g * 7 + ws.n) % 20 LIMIT 1) tt;
UPDATE documents SET deleted_at = now() WHERE random() < 0.03;
CREATE TABLE public.seed_info AS
SELECT (SELECT id FROM ws WHERE n = 1) AS heavy, (SELECT id FROM ws WHERE n = 2) AS normal,
       pg_temp.bidx('анализ', (SELECT k FROM ws WHERE n = 1)) AS search_hashes;
