# Repo Map — fsm

## PROJECT

| FIELD        | VALUE                                                                         |
|--------------|-------------------------------------------------------------------------------|
| name         | fsm                                                                           |
| version      | 0.1.0                                                                         |
| type         | service                                                                       |
| description  | Async typed Saga/pipeline runner — Med AI Adviser backend                     |
| languages    | Python >=3.13                                                                 |
| frameworks   | FastAPI 0.111, Uvicorn, aiosqlite, Pydantic 2.x                              |
| build        | setuptools + uv                                                               |

---

## COMMANDS

| TASK      | COMMAND              | NOTES                                  |
|-----------|----------------------|----------------------------------------|
| serve     | `uv run serve`       | Start FastAPI HTTP server              |
| chat      | `uv run chat`        | Agentic consultation REPL (CLI)        |
| advisor   | `uv run advisor`     | One-shot retrieval+LLM consult (CLI)   |
| test      | `uv run pytest`      | Run full test suite                    |
| lint      | `uv run ruff check`  | Lint with ruff                         |
| typecheck | `uv run mypy src/`   | Strict static type check               |

---

## RUNTIME

| REQUIREMENT | VERSION    | NOTES                                        |
|-------------|------------|----------------------------------------------|
| Python      | >=3.13     | from pyproject.toml requires-python          |
| SQLite      | built-in   | via aiosqlite; path from DB_PATH env var     |
| Uvicorn     | >=0.29     | ASGI server with standard extras             |
| LLM API     | OpenAI-compatible | NVIDIA NIM by default; any OpenAI-compat endpoint |

*(No Dockerfile, docker-compose.yml, or .python-version found.)*

---

## DEPENDENCIES

| PACKAGE           | VERSION        | PURPOSE                          |
|-------------------|----------------|----------------------------------|
| fastapi           | >=0.111,<1     | REST API framework               |
| uvicorn[standard] | >=0.29,<1      | ASGI server                      |
| pydantic          | >=2.7,<3       | Data models, config validation   |
| aiosqlite         | >=0.20.0,<0.22 | Async SQLite access              |
| openai            | >=1.30,<2      | OpenAI-compatible LLM client     |
| markdown-it-py    | >=3.0,<4       | Markdown parsing for ingest      |
| PyYAML            | >=6.0,<7       | YAML config loading              |
| typer             | >=0.12,<1      | CLI entry points                 |
| python-multipart  | >=0.0.9        | Multipart file upload            |

---

## ENV_CONFIG

| KEY            | REQUIRED | PURPOSE                                           |
|----------------|----------|---------------------------------------------------|
| NVIDIA_API_KEY | yes      | LLM provider API key (referenced in config/llm.yaml) |
| DB_PATH        | no       | SQLite file path (default: .data/db/ingest.db)    |
| FILESTORE_DIR  | no       | Uploaded files dir (default: .data/filestore)     |
| CORS_ORIGINS   | no       | Comma-separated allowed origins (default: *)      |
| HOST           | no       | Uvicorn bind host (default: 0.0.0.0)              |
| PORT           | no       | Uvicorn bind port (default: 8000)                 |
| RELOAD         | no       | Uvicorn hot-reload for dev (default: false)       |
| LOG_FILE       | no       | Optional log file path                            |

---

## ENTRYPOINTS

| TYPE   | PATH                    | NOTES                                     |
|--------|-------------------------|-------------------------------------------|
| server | src/api/main.py:main    | Adds src/ to sys.path; calls uvicorn.run  |
| webapp | src/api/app.py:app      | FastAPI app; lifespan creates AppContext  |
| cli    | src/main/chat.py:app    | Typer CLI — agentic REPL (temporary)      |
| cli    | src/main/consult.py:app | Typer CLI — one-shot consult (temporary)  |
| cli    | src/main/ingest.py      | Typer CLI — indexes Markdown files        |

---

## STRUCTURE (depth=2)

```
fsm/
├── config/               # YAML config for all subsystems
├── docs/                 # Concept docs, plans
├── prompts/              # LLM prompt templates (chat/, consult/)
├── scripts/              # Utility scripts
├── src/
│   ├── api/              # FastAPI HTTP layer
│   │   └── routers/      # Route handlers by domain
│   ├── chat/             # Agentic loop, context, tools, retriever
│   ├── common/           # Shared: logging, patient, normalizer, types
│   ├── fsm/              # Saga framework core
│   ├── llm/              # LLM client abstractions
│   ├── main/             # CLI entry points (temporary)
│   ├── pipelines/        # Ingest and retrieval pipeline implementations
│   │   ├── ingest/
│   │   └── retrieval/
│   ├── services/         # Application services + domain errors
│   └── store/            # Persistence protocols + SQL/inmem/file impls
│       ├── sql/
│       ├── inmem/
│       └── file/
└── tests/                # pytest suite
```

---

## MODULES

| MODULE              | PATH                       | PURPOSE                                              | AI_TASK        |
|---------------------|----------------------------|------------------------------------------------------|----------------|
| services            | src/services/              | ChatService, IngestService, SessionsService, ProfileService | BUSINESS_LOGIC |
| services.errors     | src/services/errors.py     | Domain exception hierarchy mapped to HTTP status codes | API_CHANGES  |
| api                 | src/api/                   | FastAPI app, lifespan, CORS, global exception handler | API_CHANGES   |
| api.routers         | src/api/routers/           | Route handlers: health, sessions, chat, documents, profile | API_CHANGES |
| api.factory         | src/api/factory.py         | AppContext + create_app_context() — single wiring point | CONFIG       |
| api.deps            | src/api/deps.py            | FastAPI Depends extractors from app.state.ctx        | API_CHANGES    |
| api.schemas         | src/api/schemas.py         | Pydantic DTOs: Session, Message, Document, Profile, Error | DATA_MODELS |
| api.config          | src/api/config.py          | ApiConfig loaded from config/api.yaml                | CONFIG         |
| chat                | src/chat/                  | AgenticLoopRunner, context builder, summarizer, tool executor | BUSINESS_LOGIC |
| fsm                 | src/fsm/                   | Saga framework: RunContext, SagaStep, SagaDefinition, SagaRunner | BUSINESS_LOGIC |
| llm                 | src/llm/                   | LLMClient protocol, OpenAI client, RetryLLMClient    | INFRA          |
| pipelines.ingest    | src/pipelines/ingest/      | 10-step ingest saga (S0-S9): parse, chunk, tag, persist | BUSINESS_LOGIC |
| pipelines.retrieval | src/pipelines/retrieval/   | BM25/FTS5 retrieval runner + query builder           | BUSINESS_LOGIC |
| store               | src/store/                 | KnowledgeStore, InternalStore, SagaStore protocols + models | DATA_MODELS |
| store.sql           | src/store/sql/             | SQLite implementations of all stores + schema.sql    | INFRA          |
| store.inmem         | src/store/inmem/           | In-memory store for tests                            | TESTS          |
| store.file          | src/store/file/            | LocalFileStore — persist uploaded Markdown files     | INFRA          |
| common              | src/common/                | Logging, PatientInfo, normalizer, types, parsers     | CONFIG         |
| main                | src/main/                  | Temporary CLI entry points                           | CLI_AUTOMATION |
| config              | config/                    | YAML config: api, llm, chat, retrieve, ingest, patient | CONFIG       |
| prompts             | prompts/                   | LLM prompt templates (system, user, summarize)       | CONFIG         |
| tests               | tests/                     | pytest tests: store, ingest, retrieval, consult, parsers | TESTS      |

---

## FLOWS

### HTTP Chat Turn

| STEP | FROM                      | TO                          | PURPOSE                            | NOTES                                     |
|------|---------------------------|-----------------------------|------------------------------------|-------------------------------------------|
| 1    | client                    | routers/chat.py             | POST /api/v1/sessions/{id}/messages | src/api/routers/chat.py                  |
| 2    | routers/chat.py           | ChatService.send_message    | Delegate to application service    | src/services/chat.py                      |
| 3    | ChatService               | InternalStore               | Load session + message history     | src/store/sql/sqlite_internal_store.py    |
| 4    | ChatService               | AgenticLoopRunner.run       | Multi-turn LLM loop + tool calls   | src/chat/agentic_loop.py                  |
| 5    | AgenticLoopRunner         | InternalStore.save_messages | Persist turn atomically            | src/store/sql/sqlite_internal_store.py    |
| 6    | ChatService               | ChatTurnResponse            | Return assistant message DTO       | src/api/schemas.py                        |

### Document Upload + Ingest

| STEP | FROM                      | TO                              | PURPOSE                       | NOTES                                        |
|------|---------------------------|---------------------------------|-------------------------------|----------------------------------------------|
| 1    | client                    | routers/documents.py            | POST /api/v1/documents (multipart) | src/api/routers/documents.py            |
| 2    | routers/documents.py      | IngestService.ingest_document   | Delegate to service           | src/services/ingest.py                       |
| 3    | IngestService             | KnowledgeStore.find_by_sha256   | Dedup check before pipeline   | src/store/sql/sqlite_knowledge_store.py      |
| 4    | IngestService             | SagaRunner.run                  | 10-step ingest saga           | src/fsm/saga_runner.py                       |
| 5    | SagaRunner (PersistChunks)| SqliteKnowledgeStore            | Save doc + chunks + FTS sync  | src/store/sql/sqlite_knowledge_store.py      |
| 6    | IngestService             | DocumentDTO                     | Return indexed document metadata | src/api/schemas.py                        |

### Startup (Lifespan)

| STEP | FROM            | TO                        | PURPOSE                         | NOTES                 |
|------|-----------------|---------------------------|---------------------------------|-----------------------|
| 1    | uvicorn         | src/api/app.py:_lifespan  | Application startup hook        | src/api/app.py        |
| 2    | _lifespan       | create_app_context()      | Wire all dependencies           | src/api/factory.py    |
| 3    | create_app_context | ensure_schema(db_path) | Idempotent DDL init             | src/api/factory.py:67 |
| 4    | create_app_context | AppContext             | Stores + LLM + services ready   | src/api/factory.py    |
| 5    | _lifespan       | app.state.ctx = AppContext | Inject into FastAPI app state  | src/api/app.py        |

---

## API_SURFACE

| METHOD | PATH                           | HANDLER              | DESCRIPTION                          |
|--------|--------------------------------|----------------------|--------------------------------------|
| GET    | /health                        | routers/health.py    | Health check → {status: ok}          |
| GET    | /api/v1/sessions               | routers/sessions.py  | List sessions; ?status=active|archived |
| POST   | /api/v1/sessions               | routers/sessions.py  | Create session; body {title}         |
| GET    | /api/v1/sessions/{id}          | routers/sessions.py  | Get session by ID                    |
| PATCH  | /api/v1/sessions/{id}          | routers/sessions.py  | Update title and/or status           |
| DELETE | /api/v1/sessions/{id}          | routers/sessions.py  | Delete session and all messages      |
| POST   | /api/v1/sessions/{id}/messages | routers/chat.py      | Send chat turn; returns assistant message |
| GET    | /api/v1/sessions/{id}/messages | routers/chat.py      | List messages; ?limit&offset         |
| POST   | /api/v1/documents              | routers/documents.py | Upload + ingest Markdown (multipart) |
| GET    | /api/v1/documents              | routers/documents.py | List all indexed documents           |
| GET    | /api/v1/profile                | routers/profile.py   | Read-only patient profile            |

---

## API_CONSUMED

| SERVICE                    | BASE_URL (config/llm.yaml)              | OPERATIONS              | MODULE   |
|----------------------------|-----------------------------------------|-------------------------|----------|
| NVIDIA NIM (OpenAI-compat) | https://integrate.api.nvidia.com/v1     | chat completions (sync) | src/llm/ |

---

## DATA_ENTITIES

| ENTITY          | STORAGE                      | KEY FIELDS                                                          |
|-----------------|------------------------------|---------------------------------------------------------------------|
| documents       | SQLite — documents           | id (PK), source_sha256, category, document_date, indexed_at, raw_text |
| chunks          | SQLite — chunks              | chunk_id (UNIQUE), document_id (FK), chunk_no, section_path, kind, text, tags_text |
| chunks_fts      | SQLite — chunks_fts (FTS5)   | Virtual; text, heading, section_path, tags_text (content=chunks)   |
| saga_progress   | SQLite — saga_progress       | run_id (PK), saga_name, cursor, state, source_path                  |
| sessions        | SQLite — sessions            | session_id (PK), title, status, summary, created_at, updated_at    |
| messages        | SQLite — messages            | message_id (PK), session_id (FK), seq, role, content, tool_calls_json |
| uploaded files  | LocalFileStore (filesystem)  | Markdown files under FILESTORE_DIR                                  |
| DocumentMetadata| dataclass                    | document_id, source_path, category, document_date, indexed_at      |
| SessionRecord   | dataclass                    | session_id, title, status, summary, created_at, updated_at         |
| MessageRecord   | dataclass                    | message_id, session_id, role, content, created_at                  |

---

## KEY_FILES

| FILE                          | PURPOSE                                           | RELATED_MODULES               |
|-------------------------------|---------------------------------------------------|-------------------------------|
| pyproject.toml                | Dependencies, scripts, ruff/mypy config           | all                           |
| src/api/app.py                | FastAPI app; middleware, routers, exception handler | api, services               |
| src/api/factory.py            | AppContext creation — single dependency wiring point | api, services, store, llm  |
| src/api/schemas.py            | All Pydantic request/response DTOs                | api.routers                   |
| src/api/deps.py               | FastAPI Depends extractors from app.state.ctx     | api.routers                   |
| src/services/errors.py        | Domain exception hierarchy with HTTP status codes | services, api                 |
| src/fsm/core.py               | RunContext, SagaStep (Protocol), SagaDefinition   | fsm, pipelines                |
| src/fsm/saga_runner.py        | SagaRunner: checkpoint load/create/resume/save    | fsm, pipelines, services      |
| src/store/sql/schema.sql      | Complete DDL — all tables and indexes             | store.sql                     |
| src/store/knowledge_store.py  | KnowledgeStore Protocol + DocumentMetadata, DocSummary | store, chat, services    |
| src/store/internal_store.py   | InternalStore Protocol — sessions and messages    | store, services.chat          |
| src/store/models.py           | SessionRecord and MessageRecord dataclasses       | store, services               |
| src/chat/agentic_loop.py      | AgenticLoopRunner: multi-turn LLM + compression   | chat, services.chat           |
| src/llm/retry_client.py       | RetryLLMClient + RetryConfig: exponential backoff | llm, api.factory              |
| config/llm.yaml               | LLM endpoint, model, timeout, retry settings      | llm, api.factory              |
| config/api.yaml               | HTTP layer: timeout, upload limit, pagination     | api.factory, api.config       |
| config/chat.yaml              | Agentic loop, recency window, memory/compression  | chat, services.chat           |

---

## CONVENTIONS

| RULE                                                                          | SOURCE             |
|-------------------------------------------------------------------------------|--------------------|
| mypy strict: disallow_untyped_defs, no_implicit_optional, warn_return_any     | pyproject.toml     |
| ruff select E,F,I,B,UP; line-length 100; E501 ignored                        | pyproject.toml     |
| Services layer: zero mutual imports; no FastAPI types in services             | src/services/      |
| Error contract: raise AppError subclass in services; handler maps to {code, message, details} | src/services/errors.py |
| DTOs only in src/api/schemas.py; services use domain dataclasses              | src/api/schemas.py |

---

<!-- Generated: 2026-06-04 -->
