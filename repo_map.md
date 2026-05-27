# Repo Map — fsm

## PROJECT

| FIELD        | VALUE                                                                  |
|--------------|-----------------------------------------------------------------------|
| name         | fsm                                                                    |
| type         | library + CLI service                                                 |
| architecture | layered pipeline (FSM-based saga runner + agentic chat loop)          |
| languages    | Python >=3.13                                                        |
| frameworks   | Pydantic 2.x, asyncio, Typer, aiosqlite                              |
| build        | setuptools + uv                                                       |

---

## COMMANDS

| TASK      | COMMAND                        | NOTES                                 |
|-----------|--------------------------------|---------------------------------------|
| ingest    | python src/main/ingest.py       | index markdown document to SQLite KB   |
| consult   | advisor consult "<question>"   | one-shot M0 pipeline                  |
| chat      | chat                           | agentic M1 REPL ([project.scripts])   |
| retrieve  | python src/main/retrieve.py    | debug retrieval (dev only)             |
| test      | uv run pytest                  | asyncio_mode=auto                     |
| lint      | uv run ruff check src tests    | E,F,I,B,UP; ignore E501               |
| typecheck | uv run mypy src                | strict mode                           |

---

## RUNTIME

(skip - no Docker / .python-version; .venv present)

---

## ENTRYPOINTS

| TYPE   | PATH                    | PURPOSE                           |
|--------|-------------------------|-----------------------------------|
| cli    | src/main/ingest.py      | S0–S9 document indexing pipeline  |
| cli    | src/main/consult.py     | M0 one-shot consultation (advisor) |
| cli    | src/main/chat.py        | M1 agentic chat REPL              |
| script | src/main/retrieve.py    | retrieval debug utility           |

---

## STRUCTURE (depth=2)

```
src/
├── chat/                 # M1 agentic loop (new)
├── common/               # shared domain models
├── fsm/                  # saga runner core
├── llm/                  # LLM client protocol + implementations
├── main/                 # CLI entrypoints
├── pipelines/
│   ├── consult/          # M0 consultation pipeline
│   ├── ingest/           # S0–S9 ingest pipeline
│   └── retrieval/        # BM25 retrieval runner
└── store/
    ├── file/             # local file storage
    ├── inmem/            # in-memory saga store
    └── sql/              # SQLite KB + saga store
```

---

## MODULES

| MODULE              | PATH                              | PURPOSE                                           | AI_TASK        |
|---------------------|-----------------------------------|---------------------------------------------------|----------------|
| fsm-core            | src/fsm/                          | RunContext, SagaStep, SagaDefinition, SagaRunner   | BUSINESS_LOGIC |
| llm                 | src/llm/                          | LLMClient protocol + OpenAI/mock implementations  | INFRA          |
| chat-agentic        | src/chat/                         | M1 agentic loop: AgenticLoopRunner, BaselineRetriever, KBToolExecutor | BUSINESS_LOGIC |
| common              | src/common/                       | PatientInfo, KBContextBundleBuilder (shared)      | BUSINESS_LOGIC |
| main-cli            | src/main/                         | CLI entrypoints: ingest, consult, chat            | CLI_AUTOMATION |
| ingest-pipeline     | src/pipelines/ingest/             | S0–S9 document indexing steps                    | BUSINESS_LOGIC |
| retrieval-pipeline  | src/pipelines/retrieval/          | RetrievalRunner, BM25 FTS5 queries                 | BUSINESS_LOGIC |
| consult-pipeline    | src/pipelines/consult/            | M0 one-shot consultation pipeline (C0–C4)          | BUSINESS_LOGIC |
| store-saga-inmem    | src/store/inmem/                  | in-memory SagaStore (test/dev)                     | INFRA          |
| store-saga-sql       | src/store/sql/sql_store.py        | SQLite SagaStore (checkpoint progress)             | INFRA          |
| store-knowledge-sql | src/store/sql/sqlite_knowledge_store.py | SQLite KnowledgeStore (docs/chunks/FTS5)     | INFRA          |
| store-file          | src/store/file/                   | LocalFileStore for source document files           | INFRA          |

---

## KEY_FILES

| FILE                                          | PURPOSE                                         | RELATED MODULES                    |
|-----------------------------------------------|-------------------------------------------------|------------------------------------|
| pyproject.toml                                | deps, scripts, ruff/mypy/pytest config          | all                                |
| config/chat.yaml                              | M1 agentic loop config (roundtrips, budgets)   | src/chat/                          |
| config/retrieve.yaml                          | BM25 weights, usage params (query_top_k, etc.)   | src/chat/, src/pipelines/consult/  |
| config/llm.yaml                               | LLM endpoint + model config                     | src/llm/                           |
| config/patient.yaml                           | Patient demographics for prompts               | src/chat/, src/pipelines/consult/  |
| prompts/chat/system.md                        | M1 system prompt template (Patient Info, Index) | src/chat/                          |
| prompts/chat/user.md                          | M1 user prompt template (Initial KB Excerpts)  | src/chat/                          |
| src/chat/agentic_loop.py                      | AgenticLoopRunner (tool-call loop orchestrator) | src/chat/                          |
| src/chat/baseline_retriever.py                | BaselineRetriever (query + recency bundle)      | src/chat/                          |
| src/chat/tool_executor.py                     | KBToolExecutor (kb.search_chunks, kb.get_document) | src/chat/                       |
| src/chat/config.py                             | ChatConfig, AgenticLoopConfig, RecencyConfig    | src/chat/                          |
| src/common/patient.py                        | PatientInfo (shared domain model)               | src/chat/, src/pipelines/consult/ |
| src/common/bundle_builder.py                  | KBContextBundleBuilder (shared context builder) | src/chat/, src/pipelines/consult/  |
| src/llm/models.py                             | ToolDefinition, ToolCall, Message, ChatResponse | src/llm/, src/chat/                |
| src/store/knowledge_store.py                  | KnowledgeStore Protocol                         | all pipelines                      |
| src/store/sql/schema.sql                      | SQLite DDL (documents, chunks, FTS5, saga)     | store-knowledge-sql, store-saga-sql|
| src/fsm/core.py                               | RunContext, SagaStep, SagaDefinition            | all pipelines                      |
| tests/                                        | unit tests (ingest, retrieval, consult, store)   | —                                 |

---

## DEPENDENCIES

| PACKAGE        | VERSION       | PURPOSE                            |
|----------------|---------------|------------------------------------|
| pydantic       | >=2.7,<3      | data models and pipeline state     |
| aiosqlite      | >=0.20,<0.22  | async SQLite (knowledge + saga DB) |
| markdown-it-py | >=3.0,<4      | markdown tokenizer for ingest       |
| PyYAML         | >=6.0,<7      | config file loading                |
| openai         | >=1.30,<2     | OpenAI-compatible LLM HTTP client  |
| typer          | >=0.12,<1     | CLI entrypoints                    |

---

## ENV_CONFIG

| KEY      | REQUIRED | PURPOSE                                          |
|----------|----------|--------------------------------------------------|
| DB_PATH  | no       | SQLite KB path (default: .data/db/ingest.db)     |
| LOG_FILE | no       | log file path (default: stdout)                  |

---

## FLOWS

### Ingest Pipeline (S0–S9)

| STEP | FROM              | TO                 | PURPOSE                       |
|------|-------------------|--------------------|-------------------------------|
| 0    | CLI / SagaRunner  | LoadSource         | read markdown file            |
| 1    | LoadSource        | PreprocessText     | hash, normalize, strip BOM   |
| 2    | PreprocessText    | DetectTargetSchema | identify document category    |
| 3    | DetectTargetSchema | SplitControlBlocks | strip control block, extract date |
| 4    | SplitControlBlocks | ParseToTokens      | tokenize via markdown-it-py  |
| 5    | ParseToTokens     | BuildSectionPath   | build section paths           |
| 6    | BuildSectionPath  | ChunkifyBlocks     | group tokens into chunks      |
| 7    | ChunkifyBlocks    | Tagging            | annotate chunks with domain tags |
| 8    | Tagging           | PersistDocument    | insert document into DB       |
| 9    | PersistDocument   | PersistChunks      | bulk insert chunks + FTS sync |

### Consult Pipeline (M0, one-shot)

| STEP | FROM        | TO             | PURPOSE                      |
|------|-------------|----------------|------------------------------|
| C0   | LoadRequest | Retrieve       | accept user complaint        |
| C1   | Retrieve    | BuildBundle    | query + recency retrieval    |
| C2   | BuildBundle | CallLLM        | KBContextBundle assembly     |
| C3   | CallLLM     | FormatResponse | single medical-LLM call      |
| C4   | FormatResponse | (done)       | raw text output              |

### Agentic Chat Loop (M1)

| STEP | FROM                 | TO                  | PURPOSE                                  |
|------|----------------------|---------------------|------------------------------------------|
| 0    | chat.py (1st turn)   | BaselineRetriever   | query bundle + recency bundle → KB Excerpts |
| 1    | AgenticLoopRunner    | LLM API             | system + history + tools definitions     |
| 2    | LLM API              | KBToolExecutor      | kb.search_chunks, kb.get_document        |
| 3    | KBToolExecutor       | RetrievalRunner/Store | search or full document fetch          |
| 4    | AgenticLoopRunner    | Chat REPL           | final assistant text per turn            |

---

## DATA_ENTITIES

| ENTITY            | PURPOSE                                              |
|-------------------|------------------------------------------------------|
| documents         | DB table: ingested docs with hash, category, date    |
| chunks            | DB table: chunked sections with kind/tags/path       |
| chunks_fts        | FTS5 virtual table: BM25 full-text search index      |
| saga_progress     | DB table: checkpoint cursor + serialized pipeline state |
| IngestData        | Pydantic pipeline state (S0–S9 field contracts)      |
| RetrievalData     | Pydantic pipeline state (R0–R7 field contracts)       |
| ConsultData       | Pydantic pipeline state (C0–C4 field contracts)     |
| ChunkSearchResult | BM25-ranked chunk retrieval result                   |
| DocSummary        | document metadata (id, date, category, sections)     |
| PatientInfo       | patient demographics (shared between M0 and M1)    |
| KBContextBundle   | formatted KB context for LLM (top_chunks + kb_excerpts) |
| SagaData          | base Pydantic class for all pipeline state models    |

---

## CONVENTIONS

| RULE                                              | SOURCE          |
|---------------------------------------------------|-----------------|
| Ruff lint: E, F, I, B, UP enforced; E501 ignored  | pyproject.toml  |
| mypy strict: disallow_untyped_defs, warn_return_any | pyproject.toml  |
| Generic types: TIn (input), TData (pipeline state) | src/fsm/core.py  |
| Pipeline state field: ctx.data (not ctx.state)     | src/fsm/core.py  |
| Test files: test_*.py; asyncio_mode=auto           | pyproject.toml   |
| Tool definitions defined in tool_executor module   | src/chat/tool_executor.py |

---

## GAPS (M1 Phase M1 Spec)

| ITEM                                  | STATUS   | NOTES                                           |
|---------------------------------------|----------|-------------------------------------------------|
| AgenticLoopRunner                     | done     | src/chat/agentic_loop.py                        |
| BaselineRetriever                     | done     | src/chat/baseline_retriever.py                 |
| KBToolExecutor                        | done     | src/chat/tool_executor.py                       |
| PatientInfo in src/common/            | done     | src/common/patient.py                           |
| KBContextBundleBuilder in src/common/ | done     | src/common/bundle_builder.py                   |
| config/chat.yaml                      | done     | agentic_loop + recency + bundle config          |
| prompts/chat/system.md                | done     | Patient Info + Medical Records Index + policy  |
| prompts/chat/user.md                  | done     | Initial KB Excerpts template                    |
| Medical Records Index in system prompt | done     | _format_document_index() in chat.py             |
| tests/chat/test_agentic_loop.py        | NOT DONE | no tests for agentic loop scenarios              |

---

<!-- Updated: 2026-05-27 (full M1 implementation scan: AgenticLoopRunner, BaselineRetriever, KBToolExecutor, shared PatientInfo + KBContextBundleBuilder, prompts/chat/) -->