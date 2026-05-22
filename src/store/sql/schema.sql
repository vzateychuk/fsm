CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    category TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    document_date TEXT NOT NULL,
    raw_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_pk INTEGER PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    document_id TEXT NOT NULL REFERENCES documents(id),
    chunk_no INTEGER NOT NULL,
    section_path TEXT,
    heading TEXT,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    tags_text TEXT,
    UNIQUE(document_id, chunk_no)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_kind ON chunks(kind);
CREATE INDEX IF NOT EXISTS idx_chunks_section_path ON chunks(section_path);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, heading, section_path, tags_text,
    content='chunks',
    content_rowid='chunk_pk'
);

CREATE TABLE IF NOT EXISTS saga_progress (
    run_id TEXT PRIMARY KEY,
    saga_name TEXT NOT NULL,
    cursor INTEGER NOT NULL,
    state TEXT NOT NULL,
    source_path TEXT
);
