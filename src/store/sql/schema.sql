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

CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    summary     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_status_updated
    ON sessions(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    seq             INTEGER NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    tool_call_id    TEXT,
    tool_calls_json TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_messages_session_seq
    ON messages(session_id, seq);
