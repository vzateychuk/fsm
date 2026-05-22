## PROJECT

| FIELD        | VALUE                                                              |
|--------------|--------------------------------------------------------------------|
| name         | fsm                                                                |
| type         | library + CLI service                                              |
| architecture | layered pipeline (FSM-based saga runner with pluggable steps)      |
| languages    | Python >=3.13                                                      |
| frameworks   | Pydantic 2.x, asyncio, Typer, aiosqlite                           |
| build        | setuptools + uv                                                    |

---

## COMMANDS

| TASK      | COMMAND                             | NOTES                        |
|-----------|-------------------------------------|------------------------------|
| ingest    | python src/main/ingest.py <file.md> | index a markdown document    |
| consult   | advisor "<question>"                | declared in [project.scripts]|
| retrieve  | python src/main/retrieve.py <query> | debug/dev only               |
| test      | uv run pytest                       | asyncio_mode=auto            |
| lint      | uv run ruff check src tests         | E,F,I,B,UP; ignore E501      |
| typecheck | uv run mypy src                     | strict mode                  |

---

## RUNTIME

(skip - no runtime descriptor)

Python >=3.13 required per pyproject.toml. No Dockerfile or .python-version found.

---

## DEPENDENCIES

| PACKAGE        | VERSION        | PURPOSE                            |
|----------------|----------------|------------------------------------|
| pydantic       | >=2.7,<3       | Data models and pipeline state     |
| aiosqlite      | >=0.20.0,<0.22 | Async SQLite (knowledge + saga DB) |
| markdown-it-py | >=3.0,<4       | Markdown tokenizer for ingest      |
| PyYAML         | >=6.0,<7       | Config file loading                |
| openai         | >=1.30,<2      | OpenAI-compatible LLM HTTP client  |
| typer          | >=0.12,<1      | CLI entrypoints                    |

---

## ENV_CONFIG

| KEY      | REQUIRED | PURPOSE                                     |
|----------|----------|---------------------------------------------|
| DB_PATH  | no       | SQLite DB path (default: .data/db/ingest.db)|
| LOG_FILE | no       | Log file path (default: stdout)             |

---

## ENTRYPOINTS

| TYPE   | PATH                 |
|--------|----------------------|
| cli    | src/main/ingest.py   |
| cli    | src/main/consult.py  |
| script | src/main/retrieve.py |

---

## STRUCTURE (depth=2)

```
├── src/
│   ├── common/
│   ├── fsm/
│   ├── llm/
│   ├── main/
│   ├── pipelines/
│   │   ├── ingest/
│   │   ├── retrieval/
│   │   └── consult/
│   └── store/
│       ├── file/
│       ├── inmem/
│       └── sql/
├── tests/
│   ├── consult/
│   ├── fixtures/
│   ├── ingest/
│   ├── parsers/
│   ├── retrieval/
│   └── store/
├── config/
├── prompts/
│   └── consult/
├── scripts/
└── docs/
```

---

## MODULES

| MODULE               | PATH                                    | PURPOSE                                          | AI_TASK        |
|----------------------|-----------------------------------------|--------------------------------------------------|----------------|
| fsm-core             | src/fsm/                                | RunContext, SagaStep, SagaDefinition, Saga        | BUSINESS_LOGIC |
| llm                  | src/llm/                                | LLMClient protocol + OpenAI/mock implementations | INFRA          |
| common               | src/common/                             | Logging, types, normalizer, alias map            | DEV_TOOLING    |
| main-cli             | src/main/                               | CLI entrypoints: ingest, consult, retrieve       | CLI_AUTOMATION |
| ingest-pipeline      | src/pipelines/ingest/                   | S0-S10 document indexing steps                   | BUSINESS_LOGIC |
| retrieval-pipeline   | src/pipelines/retrieval/                | R0-R7 FTS query + BM25 ranking steps             | BUSINESS_LOGIC |
| consult-pipeline     | src/pipelines/consult/                  | C0-C4 LLM consultation steps                     | BUSINESS_LOGIC |
| store-saga-inmem     | src/store/inmem/                        | In-memory SagaStore (test/dev)                   | INFRA          |
| store-saga-sql       | src/store/sql/sql_store.py              | SQLite SagaStore (checkpoint progress)           | INFRA          |
| store-knowledge-sql  | src/store/sql/sqlite_knowledge_store.py | SQLite KnowledgeStore (docs/chunks/FTS5)         | INFRA          |
| store-file           | src/store/file/                         | LocalFileStore for source document files         | INFRA          |
| tests-ingest         | tests/ingest/                           | Ingest pipeline unit tests                       | TESTS          |
| tests-retrieval      | tests/retrieval/                        | Retrieval pipeline unit tests                    | TESTS          |
| tests-consult        | tests/consult/                          | Consultation pipeline unit tests                 | TESTS          |
| tests-parsers        | tests/parsers/                          | Markdown parser unit tests                       | TESTS          |
| tests-store          | tests/store/                            | Store implementation unit tests                  | TESTS          |

---

## FLOWS

### Ingest Pipeline (S0-S10)

| STEP | FROM              | TO                 | PURPOSE                              | NOTES                                             |
|------|-------------------|--------------------|--------------------------------------|---------------------------------------------------|
| 1    | CLI / SagaRunner  | LoadSource         | Read markdown file to raw_content    | src/pipelines/ingest/steps/load_source.py         |
| 2    | LoadSource        | PreprocessText     | Hash, normalize, strip BOM           | src/pipelines/ingest/steps/preprocess_text.py     |
| 3    | PreprocessText    | DetectTargetSchema | Identify document category           | src/pipelines/ingest/steps/detect_target_schema.py|
| 4    | DetectTargetSchema| SplitControlBlocks | Strip control block, extract date    | src/pipelines/ingest/steps/split_control_blocks.py|
| 5    | SplitControlBlocks| ParseToTokens      | Tokenize markdown via markdown-it-py | src/pipelines/ingest/steps/parse_to_tokens.py     |
| 6    | ParseToTokens     | ChunkifyBlocks     | Build section paths, chunk blocks    | src/pipelines/ingest/steps/chunkify_blocks.py     |

### Retrieval Pipeline (R0-R7)

| STEP | FROM            | TO             | PURPOSE                             | NOTES                                             |
|------|-----------------|----------------|-------------------------------------|---------------------------------------------------|
| 1    | RetrievalRunner | LoadRequest    | Load query into pipeline state      | src/pipelines/retrieval/steps/load_request.py     |
| 2    | LoadRequest     | NormalizeQuery | Normalize Russian text (e→e, etc.)  | src/pipelines/retrieval/steps/normalize_query.py  |
| 3    | NormalizeQuery  | ExpandAliases  | Expand medical aliases/synonyms     | src/pipelines/retrieval/steps/expand_aliases.py   |
| 4    | ExpandAliases   | BuildFtsQuery  | Build FTS5 MATCH expression         | src/pipelines/retrieval/steps/build_fts_query.py  |
| 5    | BuildFtsQuery   | SearchChunks   | BM25 search in SQLite FTS5          | src/pipelines/retrieval/steps/search_chunks.py    |
| 6    | SearchChunks    | OptionalEnrich | Group by doc + enrich with neighbors| src/pipelines/retrieval/steps/optional_enrich.py  |

### Consultation Pipeline (C0-C4)

| STEP | FROM             | TO               | PURPOSE                              | NOTES                                        |
|------|------------------|------------------|--------------------------------------|----------------------------------------------|
| 1    | ConsultRunner    | LoadRequest      | Store user_request in pipeline state | src/pipelines/consult/steps/load_request.py  |
| 2    | LoadRequest      | Retrieve         | Run retrieval pipeline for KB chunks | src/pipelines/consult/steps/retrieve.py      |
| 3    | Retrieve         | BuildBundle      | Format KB excerpts + provenance      | src/pipelines/consult/steps/build_bundle.py  |
| 4    | BuildBundle      | CallPatientQuery | Send system+user prompt to LLM       | src/pipelines/consult/steps/call_llm.py      |
| 5    | CallPatientQuery | FormatResponse   | Wrap LLM text in ConsultResponse     | src/pipelines/consult/steps/format_response.py|

---

## API_SURFACE

(skip - not applicable)

---

## API_CONSUMED

| SERVICE               | BASE_URL_CONFIG_KEY | OPERATIONS              | MODULE  |
|-----------------------|---------------------|-------------------------|---------|
| OpenAI-compatible LLM | base_url (llm.yaml) | chat.completions (POST) | src/llm |

---

## DATA_ENTITIES

| ENTITY            | PURPOSE                                              |
|-------------------|------------------------------------------------------|
| documents         | DB table: ingested docs with hash, category, date    |
| chunks            | DB table: chunked sections with kind/tags/path       |
| chunks_fts        | FTS5 virtual table: BM25 full-text search index      |
| saga_progress     | DB table: checkpoint cursor + serialized pipeline state |
| IngestData        | Pydantic pipeline state (S0-S9 field contracts)      |
| RetrievalData     | Pydantic pipeline state (R0-R7 field contracts)      |
| ConsultData       | Pydantic pipeline state (C0-C4 field contracts)      |
| ChunkSearchResult | BM25-ranked chunk retrieval result                   |
| DocumentMetadata  | Document summary (id, path, category, date)          |
| DocumentEvidence  | Retrieval result grouped by document + chunks        |
| ChunkTagged       | Chunk with tags_text produced by S7 Tagging          |
| SagaData          | Base Pydantic class for all pipeline state models    |
| SagaInput         | Base Pydantic class for all pipeline input models    |

---

## KEY_FILES

| FILE                                          | PURPOSE                                         | RELATED_MODULES                             |
|-----------------------------------------------|-------------------------------------------------|---------------------------------------------|
| pyproject.toml                                | Deps, scripts, ruff/mypy/pytest config          | all                                         |
| src/main/ingest.py                            | Ingest CLI entrypoint                           | ingest-pipeline, store-*                    |
| src/main/consult.py                           | Consultation CLI (advisor script)               | consult-pipeline, retrieval-pipeline, llm   |
| src/fsm/core.py                               | RunContext, SagaStep, SagaDefinition            | all pipelines                               |
| src/fsm/saga.py                               | Stateless step executor                         | all pipelines                               |
| src/fsm/saga_runner.py                        | Checkpointing orchestrator                      | ingest-pipeline, store-saga-sql             |
| src/store/sql/schema.sql                      | SQLite DDL (documents, chunks, FTS5, saga_progress) | store-*                                 |
| src/store/knowledge_store.py                  | KnowledgeStore Protocol                         | all pipelines, store-knowledge-sql          |
| src/store/sql/sqlite_knowledge_store.py       | SQLite KnowledgeStore implementation            | ingest-pipeline, retrieval-pipeline         |
| src/pipelines/ingest/models.py                | IngestData, ChunkTagged, IngestInput            | ingest-pipeline                             |
| src/pipelines/retrieval/runner.py             | RetrievalRunner (wires R0-R7)                   | retrieval-pipeline, consult-pipeline        |
| src/pipelines/consult/runner.py               | ConsultRunner (wires C0-C4)                     | consult-pipeline                            |
| config/llm.yaml                               | LLM endpoint, model, timeout config             | llm                                         |
| config/ingest.yaml                            | Admin section headings config                   | ingest-pipeline                             |
| prompts/consult/system.md                     | LLM system prompt for consultation              | consult-pipeline                            |

---

## CONVENTIONS

| RULE                                                | SOURCE          |
|-----------------------------------------------------|-----------------|
| Ruff lint: E, F, I, B, UP enforced; E501 ignored    | pyproject.toml  |
| mypy strict: disallow_untyped_defs, warn_return_any | pyproject.toml  |
| Generic types: TIn (input), TData (pipeline state)  | src/fsm/core.py |
| Pipeline state field: ctx.data (not ctx.state)      | src/fsm/core.py |
| Test files: test_*.py; asyncio_mode=auto            | pyproject.toml  |

---

<!-- Generated: 2026-05-23 -->
