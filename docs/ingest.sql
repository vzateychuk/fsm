/*
Ниже — готовые SQL-запросы для retrieval после ingest (documents + chunks + FTS)
- documents(id, source_path, source_sha256, doc_type, raw_text, created_at, ...)
- chunks(id, document_id, chunk_no, section_path, heading, chunk_kind, text, tags_text, ...)
- chunks_fts (FTS5) с колонками text, heading, section_path, tags_text и связью rowid -> chunks.rowid (или content='chunks')
*/

-- 0.1. Сколько документов/чанков
select * from documents d;

SELECT d.id, d.category, d.document_date, d.source_path, d.document_date, d.raw_text FROM documents d;

/* Удалить документ вместе с чанками
-- f0f374689c45dec11b947bfd2a465a5f
INSERT INTO chunks_fts(chunks_fts, rowid, text, heading, section_path, tags_text)
SELECT 'delete', c.chunk_pk, c.text, c.heading, c.section_path, c.tags_text
FROM chunks c WHERE c.document_id = '9ce71063d8139388ba35bcb01174c8cf';
DELETE FROM chunks WHERE document_id = '9ce71063d8139388ba35bcb01174c8cf';
DELETE FROM documents WHERE id = '9ce71063d8139388ba35bcb01174c8cf';
*/

SELECT COUNT(*) AS documents_count FROM documents;
SELECT COUNT(*) AS chunks_count FROM chunks;

-- 0.2. Документы по типу (lab/diagnostic/consultation)
SELECT doc_type, COUNT(*) AS n
FROM documents
GROUP BY doc_type
ORDER BY n DESC;

-- 0.3) Получить список документов по типу/файлу
SELECT id, source_path, doc_type, raw_text 
FROM documents
WHERE doc_type = 'Консультация'
ORDER BY source_path;

SELECT id, source_path, doc_type
FROM documents
WHERE source_path LIKE '%lumbar-mri%'
ORDER BY source_path;

-- 0.4. Чанки по kind  (по document_id)
SELECT * FROM chunks

SELECT chunk_no, kind, section_path, heading, text
FROM chunks c
WHERE document_id = '43efe0a9ea1d15b93687850dbbaa9763'
AND c.kind = 'table' 
ORDER BY chunk_no;

------ 3) FTS-поиск по chunks (главные запросы)

/* 
 * 3.1. Базовый поиск по тексту/заголовкам/путям/тегам
 * Примеры :q:
 * птг OR паратгормон OR pth
 * "h. pylori" OR pylori OR helicobacter
 * "бедренная вена" AND диаметр
 * эхокардиография OR эхокг
 */

SELECT
  c.document_id,
  bm25(chunks_fts, 4.0, 2.0, 1.5, 3.0) AS score,
  d.source_path,
  d.category,
  c.chunk_no,
  c.kind,
  c.section_path,
  c.heading,
  c.text,
  c.tags_text

  bm25(chunks_fts, 1.0, 2.5, 2.0, 3.5) AS score,
  
SELECT
  c.document_id,
  bm25(chunks_fts, 3.0, 2.0, 1.0, 1.5) AS score,
  d.category,
  c.chunk_no,
  c.kind,
  c.section_path,
  c.heading,
  c.tags_text
FROM chunks_fts
JOIN chunks c ON c.rowid = chunks_fts.rowid
JOIN documents d ON d.id = c.document_id
WHERE chunks_fts MATCH 'болит* OR живот* OR справа* OR температура*'
ORDER BY score ASC
LIMIT 10;

SELECT
  c.document_id,
  bm25(chunks_fts, 3.0, 2.0, 1.0, 1.5) AS score,
  d.category,
  c.chunk_no,
  c.kind,
  c.heading,
  length(c.text) AS text_len,
  c.text
FROM chunks_fts
JOIN chunks c ON c.rowid = chunks_fts.rowid
JOIN documents d ON d.id = c.document_id
WHERE c.document_id IN ('9ce71063d8139388ba35bcb01174c8cf')
-- AND chunks_fts MATCH 'болит* OR живот* OR справа* OR температура*'
ORDER BY score ASC
LIMIT 20;

SELECT c.document_id, bm25(chunks_fts, 4.0, 2.0, 1.5, 3.0) AS score, d.source_path, c.chunk_no, c.kind, c.section_path, c.text
FROM chunks_fts
JOIN chunks c ON c.rowid = chunks_fts.rowid
JOIN documents d ON d.id = c.document_id
WHERE chunks_fts MATCH 'section_path:образ жизни'
ORDER BY bm25(chunks_fts) 
LIMIT 50;

/*
4) Комбинация FTS + фильтр по doc_type
4.1. Найти по запросу только lab документы
*/

SELECT c.document_id, d.source_path, c.chunk_no, c.kind, c.section_path, c.text, bm25(chunks_fts, 4.0, 2.0, 1.5, 3.0) AS score
FROM chunks_fts
JOIN chunks c ON c.rowid = chunks_fts.rowid
JOIN documents d ON d.id = c.document_id
WHERE chunks_fts MATCH 'лпнп'
  AND d.doc_type = 'Анализы'
ORDER BY score
LIMIT 10;


/*
5) Типовые retrieval-запросы под ваши файлы
5.1. ПТГ / паратгормон (2019/2024/2025 lab)
'птг OR паратгормон OR pth'
'"h. pylori" OR pylori OR helicobacter'
'фгдс OR эгдс OR эзофагогастродуоденоскопия'
'(рефлюкс OR "патологический рефлюкс") AND (бпв OR "большая подкожная")'
'(экг OR электрокардиография) AND (вольтаж OR "снижен")'
'section_path:рекомендации OR heading:рекомендации'
*/
SELECT c.document_id, bm25(chunks_fts, 4.0, 2.0, 1.5, 3.0) AS score, d.source_path, c.chunk_no, c.section_path, c.kind, c.text
FROM chunks_fts
JOIN chunks c ON c.rowid = chunks_fts.rowid
JOIN documents d ON d.id = c.document_id
-- WHERE chunks_fts MATCH 'section_path:рекомендации OR heading:рекомендации'
WHERE chunks_fts MATCH 'экг OR электрокардиография*'
ORDER BY bm25(chunks_fts, 4.0, 2.0, 1.5, 3.0)
LIMIT 10;

/*
6) Поиск “внутри документа”: найти все chunks по одной ветке section_path
Например, в consultation_deep.md все, что связано с “Коронарография”:
*/
SELECT chunk_no, c.kind, section_path, text
FROM chunks c
WHERE document_id = '2cb48f12ba25017eea1fa61dc4f79211'
  -- AND section_path LIKE '%пищевод%'
ORDER BY chunk_no;

/*
 * 7) Найти только “fact” чанки (полезно для clinical meaning)
 */

SELECT d.source_path, c.section_path, c.text
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE c.kind = 'fact'
ORDER BY d.source_path, c.chunk_no
LIMIT 30;


--------------------

SELECT f."rank", f."text" , f.heading , f.section_path , f.tags_text 
FROM chunks_fts f
WHERE f.chunks_fts MATCH 'боль OR живот* OR температура* OR диагноз* OR консультация*' 
ORDER BY rank LIMIT 5;

SELECT document_id, COUNT(*) as chunk_count FROM chunks 
WHERE document_id IN (
  SELECT DISTINCT c.document_id FROM chunks c
  JOIN chunks_fts f ON c.chunk_pk = f.rowid
  WHERE f.chunks_fts MATCH 'протруз*'
)
GROUP BY document_id;


-- Количество символов в чанках:

SELECT 
    d.category,
    COUNT(c.chunk_id) as chunk_count,
    ROUND(AVG(length(c.text))) as avg_chars,
    MIN(length(c.text)) as min_chars,
    MAX(length(c.text)) as max_chars
FROM chunks c
JOIN documents d ON c.document_id = d.id
GROUP BY d.category
ORDER BY avg_chars DESC

--SELECT c.chunk_id, c.document_id, c.chunk_no, c.kind, c.text, c.section_path, c.heading, c.tags_text, d.source_path, d.category, d.document_date, bm25(chunks_fts, ?, ?, ?, ?) AS rank FROM chunks_fts JOIN chunks c ON chunks_fts.rowid = c.chunk_pk JOIN documents d ON c.document_id = d.id WHERE chunks_fts MATCH ? AND d.document_date >= ? AND d.document_date <= ? AND c.kind != 'meta' ORDER BY rank, d.document_date DESC LIMIT ?


SELECT chunk_no, kind, heading FROM chunks WHERE document_id = '2cb48f12ba25017eea1fa61dc4f79211' ORDER BY chunk_no;


SELECT f."rank", f."text" , f.heading , f.section_path , f.tags_text 
FROM chunks_fts f
WHERE f.chunks_fts MATCH 'живот*' 
ORDER BY rank LIMIT 5;

SELECT * FROM sessions s 
WHERE s.session_id = '54f88f08-a11f-48a2-bb06-ce8433ac0270'
-- WHERE s.session_id = 'c4df51a5-4fcd-404d-a019-bdbe145812f4'

SELECT * FROM messages m 
WHERE m.session_id = '54f88f08-a11f-48a2-bb06-ce8433ac0270'
-- WHERE m.session_id = 'c4df51a5-4fcd-404d-a019-bdbe145812f4'
AND m."role" = 'user'

SELECT * FROM documents d 
WHERE d.id = '2cb48f12ba25017eea1fa61dc4f79211'