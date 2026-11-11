-- Нагрузочные данные: 2000 пространств по 100 документов + 1 пространство на 10000 документов
SET search_path = app, public;
CREATE TEMP TABLE titles(t text);
INSERT INTO titles VALUES ('Общий анализ крови'),('Биохимический анализ крови'),('Липидограмма'),('Заключение терапевта'),
('УЗИ почек и мочевого пузыря'),('ЭКГ покоя'),('Анализ мочи общий'),('Гормоны щитовидной железы'),('Заключение кардиолога'),
('МРТ коленного сустава'),('Рентген грудной клетки'),('Коагулограмма'),('Ферритин'),('Витамин D'),('Заключение невролога'),
('УЗИ брюшной полости'),('Холтер ЭКГ суточный'),('Гликированный гемоглобин'),('Выписка из стационара'),('Прививочный сертификат');
CREATE FUNCTION pg_temp.bidx(title text, k bytea) RETURNS bigint[] LANGUAGE sql IMMUTABLE AS $$
  SELECT array_agg(DISTINCT ('x'||encode(substr(hmac(convert_to(g,'UTF8'), k, 'sha256'),1,8),'hex'))::bit(64)::bigint)
  FROM unnest(show_trgm(lower(replace(title,'ё','е')))) g $$;
INSERT INTO workspaces (id, dek_ciphertext, kek_key_id)
SELECT gen_random_uuid(), gen_random_bytes(64), 'abj-kek-1' FROM generate_series(1,2001);
CREATE TEMP TABLE ws AS SELECT id, row_number() OVER (ORDER BY id) n, gen_random_bytes(32) k FROM workspaces;
INSERT INTO documents (id, workspace_id, type_code, title_ct, title_bidx, note_ct, document_date, uploaded_at)
SELECT gen_random_uuid(), ws.id, (ARRAY['analysis','conclusion','other'])[1 + (g % 3)],
       gen_random_bytes(29 + octet_length(tt.t)), pg_temp.bidx(tt.t, ws.k),
       CASE WHEN g % 4 = 0 THEN gen_random_bytes(80) END,
       CASE WHEN g % 12 = 0 THEN NULL ELSE DATE '2024-01-01' + (g % 1000) - (g % 365) END,
       TIMESTAMPTZ '2024-01-01' + (g % 1000) * interval '1 day' + random() * interval '20 hours'
FROM ws CROSS JOIN LATERAL generate_series(1, CASE WHEN ws.n = 1 THEN 10000 ELSE 100 END) g
CROSS JOIN LATERAL (SELECT t FROM titles OFFSET (g * 7 + ws.n) % 20 LIMIT 1) tt;
-- Удалённые: 3%
UPDATE documents SET deleted_at = now() WHERE random() < 0.03;
ANALYZE;
CREATE TABLE public.seed_info AS SELECT (SELECT id FROM ws WHERE n=1) heavy, (SELECT k FROM ws WHERE n=1) heavy_key,
  (SELECT workspace_id FROM documents GROUP BY workspace_id HAVING count(*) < 200 LIMIT 1) normal, (SELECT count(*) FROM documents) docs;
