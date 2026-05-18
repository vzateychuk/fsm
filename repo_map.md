## PROJECT

| FIELD        | VALUE                                                                    |
|--------------|--------------------------------------------------------------------------|
| name         | fsm                                                                      |
| type         | library + application                                                    |
| architecture | layered pipeline — FSM core + ingest pipeline + retrieval pipeline       |
| languages    | Python >=3.13                                                            |
| frameworks   | Pydantic 2.x, aiosqlite, markdown-it-py                                  |
| build        | setuptools>=69, uv                                                       |

---

## COMMANDS

| TASK        | COMMAND              | NOTES                                          |
|-------------|----------------------|------------------------------------------------|
| test        | pytest               | testpaths=tests, asyncio_mode=auto             |
| lint        | ruff check src/      | rules E,F,I,B,UP; line-length=100             |
| type-check  | mypy src/            | strict mode                                    |
| run-ingest  | python src/main/main.py | env: DB_PATH, INGEST_FILE, INGEST_RUN_ID    |

*(No [project.scripts] declared; commands from [tool.*] sections of pyproject.toml.)*

---

## RUNTIME

| REQUIREMENT | VERSION  | NOTES                         |
|-------------|----------|-------------------------------|
| Python      | >=3.13   | from pyproject.toml           |
| SQLite      | bundled  | via aiosqlite; FTS5 required  |

*(No Dockerfile or docker-compose found.)*

---

## DEPENDENCIES

| PACKAGE        | VERSION        | PURPOSE                           |
|----------------|----------------|-----------------------------------|
| pydantic       | >=2.7,<3       | pipeline state models/validation  |
| aiosqlite      | >=0.20.0,<0.22 | async SQLite driver               |
| markdown-it-py | >=3.0,<4       | Markdown token parsing            |
| PyYAML         | >=6.0,<7       | category/alias config loading     |

---

## ENV_CONFIG

| KEY                         | REQUIRED | PURPOSE                                        |
|-----------------------------|----------|------------------------------------------------|
| DB_PATH                     | no       | SQLite path (default: .data/db/ingest.db)      |
| FILESTORE_DIR               | no       | Source file storage (default: .data/filestore) |
| INGEST_FILE                 | no       | Input markdown path                            |
| INGEST_RUN_ID               | no       | Resume existing run by ID                      |
| LOG_FILE                    | no       | Log output path (default: logs/ingest.log)     |
| RETRIEVE_LIMIT              | no       | Max search results (default: 20)               |
| RETRIEVE_PRELIMIT           | no       | Pre-diversity result count (default: 200)      |
| RETRIEVE_LIMIT_PER_DOCUMENT | no       | Diversity cap per doc (default: 3)             |
| RETRIEVE_BM25_WEIGHTS       | no       | BM25 weights text/heading/section/tags (default: 1.0,2.5,2.0,3.5) |
| RETRIEVE_ENABLE_PREFIXES    | no       | FTS prefix matching (default: true)            |
| RETRIEVE_PREFIX_MIN_LEN     | no       | Min token length for prefix (default: 5)       |
| RETRIEVE_DOC_TYPE_MODE      | no       | soft/hard doc_type filter (default: soft)      |
| RETRIEVE_DEBUG              | no       | Enable retrieval debug output (default: false) |

---

## ENTRYPOINTS

| TYPE   | PATH              |
|--------|-------------------|
| script | src/main/main.py  |

---

## STRUCTURE (depth=2, store/ and pipelines/ expanded one level)

```
├── src/
│   ├── common/
│   ├── fsm/
│   ├── main/
│   ├── pipelines/
│   │   ├── ingest/
│   │   └── retrieval/
│   └── store/
│       ├── file/
│       ├── inmem/
│       └── sql/
├── tests/
│   ├── fixtures/
│   ├── parsers/
│   └── retrieval/
├── config/
└── docs/
```

---

## MODULES

| MODULE              | PATH                               | PURPOSE                                              | AI_TASK        |
|---------------------|------------------------------------|------------------------------------------------------|----------------|
| fsm-core            | src/fsm/                           | RunContext, SagaStep, SagaDefinition, Saga, SagaRunner | BUSINESS_LOGIC |
| fsm-models          | src/fsm/models.py                  | SagaInput, SagaData base Pydantic classes            | DATA_MODELS    |
| ingest-pipeline     | src/pipelines/ingest/              | 10-step markdown document indexing (S0–S9)           | BUSINESS_LOGIC |
| ingest-steps        | src/pipelines/ingest/steps/        | S0–S9 individual step implementations                | BUSINESS_LOGIC |
| ingest-parsers      | src/pipelines/ingest/parsers/      | markdown-it-py token parser                          | BUSINESS_LOGIC |
| retrieval-pipeline  | src/pipelines/retrieval/           | 8-step FTS5 query pipeline (R0–R7 implemented)       | BUSINESS_LOGIC |
| retrieval-steps     | src/pipelines/retrieval/steps/     | R0–R7 individual step implementations                | BUSINESS_LOGIC |
| store-protocols     | src/store/                         | Store, KnowledgeStore, FileStore protocols           | INFRA          |
| store-sql           | src/store/sql/                     | SqliteKnowledgeStore + SqlStore (aiosqlite + FTS5)   | INFRA          |
| store-inmem         | src/store/inmem/                   | In-memory SagaStore for tests                        | INFRA          |
| store-file          | src/store/file/                    | LocalFileStore (source file persistence)             | INFRA          |
| common              | src/common/                        | normalize_text, logging setup, schema_id parser      | BUSINESS_LOGIC |
| main-entrypoint     | src/main/                          | Ingest pipeline runner script                        | CLI_AUTOMATION |
| tests-retrieval     | tests/retrieval/                   | Retrieval pipeline and FTS query tests               | TESTS          |
| tests-parsers       | tests/parsers/                     | Markdown parser unit tests                           | TESTS          |
| tests-fixtures      | tests/fixtures/                    | Markdown fixtures + expected YAML outputs            | TESTS          |

---

## FLOWS

### Ingest Pipeline (S0–S9)

| STEP | FROM               | TO                 | PURPOSE                           | NOTES                                               |
|------|--------------------|--------------------|-----------------------------------|-----------------------------------------------------|
| 1    | IngestInput        | LoadSource         | Read markdown file from disk      | src/pipelines/ingest/steps/load_source.py           |
| 2    | LoadSource         | PreprocessText     | NFKC normalize, compute SHA256    | src/pipelines/ingest/steps/preprocess_text.py       |
| 3    | PreprocessText     | DetectTargetSchema | Match category from first line    | src/pipelines/ingest/steps/detect_target_schema.py  |
| 4    | DetectTargetSchema | ChunkifyBlocks     | Parse → section path → chunks     | src/pipelines/ingest/steps/chunkify_blocks.py       |
| 5    | ChunkifyBlocks     | Tagging            | Add tags_text to each chunk       | src/pipelines/ingest/steps/tagging.py               |
| 6    | Tagging            | PersistChunks      | Upsert chunks + sync FTS5 atomically | src/pipelines/ingest/steps/persist_chunks.py     |

### Retrieval Pipeline (R0–R7)

| STEP | FROM             | TO               | PURPOSE                            | NOTES                                               |
|------|------------------|------------------|------------------------------------|-----------------------------------------------------|
| 1    | RetrieveRequest  | NormalizeQuery   | NFKC + lowercase + ё→е             | src/pipelines/retrieval/steps/normalize_query.py    |
| 2    | NormalizeQuery   | ClassifyIntent   | Keyword-prefix intent heuristic    | src/pipelines/retrieval/steps/classify_intent.py    |
| 3    | ClassifyIntent   | BuildFtsQuery    | Expand aliases → FTS5 MATCH expr   | src/pipelines/retrieval/steps/build_fts_query.py    |
| 4    | BuildFtsQuery    | SearchChunks     | BM25 + diversity search            | src/pipelines/retrieval/steps/search_chunks.py      |
| 5    | SearchChunks     | GroupByDocument  | Group chunks by document_id        | src/pipelines/retrieval/steps/group_by_document.py  |
| 6    | GroupByDocument  | OptionalEnrich   | Load raw_text if include_full_docs | src/pipelines/retrieval/steps/optional_enrich.py    |

---

## DATA_ENTITIES

| ENTITY                     | PURPOSE                                                   |
|----------------------------|-----------------------------------------------------------|
| SagaStep                   | Protocol: id, desc, async run(ctx)                        |
| SagaDefinition             | Named ordered list of SagaStep instances                  |
| RunContext                 | Per-run state: run_id, cursor, input, data                |
| SagaData                   | Base Pydantic model for pipeline state                    |
| SagaInput                  | Base Pydantic model for pipeline input                    |
| Store                      | Protocol: load/save SavedProgress checkpoints             |
| SavedProgress              | TypedDict: run_id, saga_name, cursor, state               |
| KnowledgeStore             | Protocol: save_document, replace_chunks, search_chunks, get_documents_raw_text |
| FileStore                  | Protocol: save_source to file storage                     |
| ChunkSearchResult          | FTS5 BM25 search hit with rank (frozen dataclass)         |
| IngestInput                | source_path for ingest pipeline                           |
| IngestData                 | Ingest pipeline state S0–S9                               |
| ChunkTagged                | Chunk + tags_text (output of S7 Tagging)                  |
| RetrieveRequest            | Query + filters + limits for retrieval                    |
| RetrievalData              | Retrieval pipeline state R0–R7                            |
| IntentInfo                 | Intent detection: detected_type, confidence, keywords     |
| DocumentEvidence           | Grouped search result: doc metadata + chunks + full_text  |

---

## KEY_FILES

| FILE                                         | PURPOSE                                    | RELATED_MODULES                     |
|----------------------------------------------|--------------------------------------------|-------------------------------------|
| pyproject.toml                               | Dependencies, tool config (ruff/mypy/pytest)| all                                |
| src/main/main.py                             | Ingest pipeline entrypoint                 | ingest-pipeline, store-sql          |
| src/fsm/core.py                              | RunContext, SagaStep, SagaDefinition       | fsm-core, all pipelines             |
| src/fsm/saga_runner.py                       | Checkpointing orchestrator (resume)        | fsm-core, store-protocols           |
| src/fsm/saga.py                              | Stateless step executor                    | fsm-core, retrieval-pipeline        |
| src/fsm/models.py                            | SagaInput, SagaData base classes           | all pipelines                       |
| src/store/store.py                           | Store Protocol + SavedProgress             | store-sql, store-inmem, fsm-core    |
| src/store/knowledge_store.py                 | KnowledgeStore Protocol + ChunkSearchResult| store-sql, ingest-steps, retrieval-steps |
| src/store/filestore.py                       | FileStore Protocol                         | store-file, ingest-steps            |
| src/store/sql/schema.sql                     | SQLite DDL: documents, chunks, FTS5, saga_progress | store-sql               |
| src/store/sql/sqlite_knowledge_store.py      | SqliteKnowledgeStore: FTS5, BM25, raw_text fetch | store-sql                     |
| src/pipelines/ingest/models.py               | IngestInput, IngestData, ChunkTagged, IngestError | ingest-pipeline            |
| src/pipelines/ingest/steps/__init__.py       | Re-exports all 10 ingest step classes      | ingest-pipeline                     |
| src/pipelines/retrieval/models.py            | RetrieveRequest, RetrievalData, DocumentEvidence | retrieval-pipeline          |
| src/pipelines/retrieval/runner.py            | RetrievalRunner (wires R0–R7)              | retrieval-pipeline, store-sql       |
| src/pipelines/retrieval/config.py            | RetrievalConfig + from_env()               | retrieval-pipeline                  |
| src/pipelines/retrieval/steps/__init__.py    | Re-exports all 8 retrieval step classes    | retrieval-pipeline                  |
| src/common/normalizer.py                     | normalize_text(): shared by ingest + retrieval | common, ingest-steps, retrieval-steps |
| config/categories.yaml                       | Allowed document categories                | ingest-steps                        |
| config/aliases.yaml                          | Query term alias expansions                | retrieval-steps                     |

---

## CONVENTIONS

| RULE                                                          | SOURCE              |
|---------------------------------------------------------------|---------------------|
| mypy strict — all functions fully typed, no implicit Optional | pyproject.toml      |
| ruff B+UP enforced — no bugbear patterns, modern Python idioms| pyproject.toml      |
| Pipeline state accessed as ctx.data (not ctx.state)          | src/fsm/core.py     |
| Generic params: TIn (input type), TData (pipeline state type) | src/fsm/core.py    |
| FTS5 sync is always atomic inside PersistChunks (S9)         | src/store/sql/sqlite_knowledge_store.py |

---

<!-- Generated: 2026-05-17 -->
