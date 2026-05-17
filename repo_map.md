## PROJECT
| FIELD        | VALUE |
|--------------|-------|
| name         | fsm |
| type         | Python library — async pipeline runner |
| architecture | Saga pattern with checkpointing; layered (framework / pipeline / store) |
| languages    | Python >=3.13 |
| frameworks   | Pydantic 2.x, asyncio, aiosqlite |
| build        | setuptools + uv |

---

## COMMANDS
| TASK       | COMMAND           | NOTES |
|------------|-------------------|-------|
| test       | pytest            | configured: asyncio_mode=auto, testpaths=tests/ |
| lint       | ruff check src/   | configured: select E,F,I,B,UP; line-length 100 |
| type-check | mypy src/         | configured: strict=true, python_version 3.11 |

*(No [project.scripts] declared. Commands above are dev-tool invocations configured in [tool.*] sections of pyproject.toml.)*

---

## RUNTIME
(skip - no runtime descriptor)

---

## DEPENDENCIES
| PACKAGE        | VERSION        | PURPOSE |
|----------------|----------------|---------|
| pydantic       | >=2.7,<3       | Data models and validation for SagaData/SagaInput |
| aiosqlite      | >=0.20.0,<0.22 | Async SQLite for SQLStore (stub) |
| markdown-it-py | >=3.0,<4       | Markdown token parsing in ingest pipeline |

---

## ENV_CONFIG
| VARIABLE    | DEFAULT | REQUIRED | SOURCE |
|-------------|---------|----------|--------|
| LOG_FILE    | logs/ingest.log | No | src/main/main.py, src/commons/logging_config.py |
| INGEST_FILE | tests/fixtures/ingest/consultation_deep.md | No | src/main/main.py |
| DB_PATH     | .data/db/ingest.db | No | src/main/main.py — SQLite path for KnowledgeStore |

<!-- updated 2026-05-17: added DB_PATH -->

---

## ENTRYPOINTS
| TYPE   | PATH |
|--------|------|
| script | src/main/main.py |

---

## STRUCTURE (depth=2)
```
src/
  fsm/              # Framework core
  commons/          # Shared logging utility
  common/           # Shared parsers (schema_id)
  pipelines/
    ingest/         # 10-step markdown document ingest pipeline
  store/
    inmem/          # In-memory Store implementation
    sql/            # SQLite Store stub
  main/             # Entry point scripts
tests/
  fixtures/
    ingest/         # Markdown fixture files + expected YAML outputs
```

---

## MODULES
| MODULE          | PATH                  | PURPOSE                                           | AI_TASK        |
|-----------------|-----------------------|---------------------------------------------------|----------------|
| fsm-core        | src/fsm/              | RunContext, SagaStep, SagaDefinition, Saga, SagaRunner | BUSINESS_LOGIC |
| fsm-models      | src/fsm/models.py     | Base Pydantic classes SagaInput, SagaData         | DATA_MODELS    |
| pipeline-ingest | src/pipelines/ingest/ | S0–S10: markdown ingest; S8–S10 persist to SQLite  | BUSINESS_LOGIC |
| store-protocol  | src/store/store.py    | Store Protocol + SavedProgress TypedDict          | INFRA          |
| store-inmem     | src/store/inmem/      | In-memory Store implementation for testing        | INFRA          |
| store-sql       | src/store/sql/        | SqlStore (checkpoint) + SqliteKnowledgeStore (docs/chunks/FTS) | INFRA |
| knowledge-store | src/store/knowledge_store.py | KnowledgeStore Protocol, ChunkSearchResult | INFRA     |
| commons         | src/commons/          | Logging setup utility                             | DEV_TOOLING    |
| common-utils    | src/common/           | Shared parsers (schema_id extractor)              | BUSINESS_LOGIC |
| entrypoint      | src/main/             | Ingest pipeline entry point script                | CLI_AUTOMATION |
| ingest-fixtures | tests/fixtures/ingest/| Markdown inputs + expected YAML for ingest tests  | TESTS          |

---

## FLOWS
(skip - single linear step-based runner; no middleware layers)

---

## DATA_ENTITIES
| CONTRACT                    | PURPOSE |
|-----------------------------|---------|
| RunContext[TIn, TData]      | Execution context: run_id, cursor, input, data |
| SagaStep[TIn, TData]        | Protocol for a pipeline step: id, desc, async run(ctx) |
| SagaDefinition[TIn, TData]  | Named ordered list of SagaSteps |
| Saga[TIn, TData]            | Stateless executor; iterates steps from cursor; fires pre/post callbacks |
| SagaRunner[TIn, TData]      | Orchestrator: load/create context, run Saga, save checkpoint after each step |
| Store (Protocol)            | Async load/save interface for SavedProgress |
| SavedProgress (TypedDict)   | Serialised checkpoint: run_id, saga_name, cursor, state dict |
| SagaInput (BaseModel)       | Base class for pipeline input types |
| SagaData (BaseModel)        | Base class for pipeline state data types |
| IngestInput                 | Ingest pipeline input: source_path |
| IngestData                  | Ingest pipeline state: raw_content through tokens, chunks, to document_id |
| IngestError                 | Domain exception with error code (E_READ_FAIL, E_NO_SCHEMA_ID, etc.) |
| KnowledgeStore (Protocol)   | save_document, replace_document_chunks, search_chunks |
| ChunkSearchResult           | BM25 search hit: chunk_id, text, section_path, source_path, rank |
| ChunkTagged                 | TypedDict: Chunk + tags_text (output of S7 Tagging) |
| DocType / ChunkKind         | Literals: lab/diagnostic/consultation; table/list/fact/section |

---

## KEY_FILES
| FILE | PURPOSE | RELATED_MODULES |
|------|---------|-----------------|
| pyproject.toml | Project metadata, deps, pytest/ruff/mypy config | all |
| src/fsm/core.py | Core contracts: RunContext, SagaStep, SagaDefinition | fsm-core |
| src/fsm/saga.py | Stateless Saga executor with pre/post callbacks | fsm-core |
| src/fsm/saga_runner.py | Orchestrator: checkpoint load/save/resume | fsm-core, store-protocol |
| src/fsm/models.py | SagaInput, SagaData base Pydantic models | fsm-models |
| src/store/store.py | Store Protocol + SavedProgress TypedDict | store-protocol |
| src/store/inmem/inmemory_store.py | In-memory Store implementation | store-inmem |
| src/store/sql/sql_store.py | SQLite Store stub (unimplemented) | store-sql |
| src/pipelines/ingest/models.py | IngestInput, IngestData, MdToken, BlockEvent, Chunk, IngestError | pipeline-ingest |
| src/pipelines/ingest/steps/__init__.py | Exports all 10 ingest step classes | pipeline-ingest |
| src/commons/logging_config.py | setup_logging(); respects LOG_FILE env var | commons |
| src/store/knowledge_store.py | KnowledgeStore Protocol, ChunkSearchResult, DocType, ChunkKind | knowledge-store |
| src/store/sql/sqlite_knowledge_store.py | SqliteKnowledgeStore: aiosqlite, FTS5, replace_document_chunks | store-sql |
| src/store/sql/schema.sql | DDL: documents, chunks (chunk_pk PK), chunks_fts (FTS5 content table) | store-sql |
| src/main/main.py | Ingest pipeline entry point; wires definition, store, runner | entrypoint |

<!-- updated 2026-05-17: added knowledge-store and schema.sql key files -->

---

## CONVENTIONS
| RULE | SOURCE |
|------|--------|
| Generic names: TIn (input type), TData (state type) | src/fsm/core.py |
| Pipeline state field is ctx.data, NOT ctx.state | src/fsm/core.py |
| SagaStep is a Protocol — use structural subtyping, not inheritance | src/fsm/core.py |
| Step classes declare ClassVar id/desc; implement async run(ctx) | src/fsm/core.py |
| Strict mypy; ruff E,F,I,B,UP; line-length 100; asyncio_mode=auto | pyproject.toml |

---

<!-- Generated: 2026-05-15 -->
<!-- Updated: 2026-05-17: DB_PATH env var; knowledge-store module; KnowledgeStore/ChunkSearchResult/ChunkTagged entities; schema.sql key files; store-sql description updated -->
