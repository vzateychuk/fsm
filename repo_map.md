## PROJECT

| FIELD        | VALUE                                                                 |
|--------------|-----------------------------------------------------------------------|
| name         | fsm                                                                   |
| type         | library                                                               |
| architecture | modular pipeline (Saga/FSM pattern with resume checkpoints)           |
| languages    | Python >=3.13                                                         |
| frameworks   | Pydantic 2.x, aiosqlite (SQLite FTS5), openai SDK, typer              |
| build        | setuptools + uv                                                       |

---

## COMMANDS

| TASK       | COMMAND        | NOTES                                    |
|------------|----------------|------------------------------------------|
| cli        | advisor        | pyproject.toml [project.scripts]         |
| test       | pytest         | asyncio_mode=auto; testpaths=tests       |
| lint       | ruff check src/| rules E,F,I,B,UP; line-length=100       |
| type-check | mypy src/      | strict mode, python_version=3.11         |

---

## RUNTIME

| REQUIREMENT | VERSION | NOTES                          |
|-------------|---------|--------------------------------|
| Python      | >=3.13  | from pyproject.toml            |
| SQLite      | bundled | via aiosqlite; FTS5 required   |

*(No Dockerfile or docker-compose found.)*

---

## DEPENDENCIES

| PACKAGE        | VERSION        | PURPOSE                            |
|----------------|----------------|------------------------------------|
| pydantic       | >=2.7,<3       | Pipeline state models, validation  |
| aiosqlite      | >=0.20.0,<0.22 | Async SQLite driver (FTS5 store)   |
| markdown-it-py | >=3.0,<4       | Markdown tokenizer for ingest      |
| PyYAML         | >=6.0,<7       | Config file loading                |
| openai         | >=1.30,<2      | LLM client (OpenAI-compatible API) |
| typer          | >=0.12,<1      | CLI entry point (advisor)          |

---

## ENV_CONFIG

| KEY          | REQUIRED | PURPOSE                                        |
|--------------|----------|------------------------------------------------|
| DB_PATH      | no       | SQLite path (default: .data/db/ingest.db)      |
| LOG_FILE     | no       | Log output path (default: logs/ingest.log)     |
| FILESTORE_DIR| no       | Source file storage (default: .data/filestore) |
| INGEST_FILE  | no       | Input markdown path                            |
| INGEST_RUN_ID| no       | Resume existing ingest run by ID               |

*(LLM credentials — base_url, api_key, model — injected at construction of OpenAICompatibleClient; exact env key names not declared in source.)*

---

## ENTRYPOINTS

| TYPE   | PATH                 |
|--------|----------------------|
| script | src/main/ingest.py   |
| script | src/main/retrieve.py |
| script | src/main/consult.py  |

---

## STRUCTURE (depth=2)

```
├── src/
│   ├── fsm/
│   ├── common/
│   ├── llm/
│   ├── main/
│   ├── pipelines/
│   │   ├── ingest/
│   │   ├── retrieval/
│   │   └── consult/
│   └── store/
│       ├── sql/
│       ├── inmem/
│       └── file/
├── tests/
│   ├── consult/
│   ├── retrieval/
│   ├── parsers/
│   └── fixtures/
└── config/
```

---

## MODULES

| MODULE             | PATH                              | PURPOSE                                              | AI_TASK        |
|--------------------|-----------------------------------|------------------------------------------------------|----------------|
| fsm-core           | src/fsm/                          | RunContext, SagaStep, SagaDefinition, Saga, SagaRunner | BUSINESS_LOGIC |
| ingest-pipeline    | src/pipelines/ingest/             | 10-step markdown→SQLite ingestion pipeline           | BUSINESS_LOGIC |
| ingest-steps       | src/pipelines/ingest/steps/       | Steps S0–S9 (load, parse, chunk, tag, persist)       | BUSINESS_LOGIC |
| ingest-parsers     | src/pipelines/ingest/parsers/     | Markdown tokenizer (markdown-it-py wrapper)          | BUSINESS_LOGIC |
| retrieval-pipeline | src/pipelines/retrieval/          | BM25 retrieval pipeline: models, config, runner      | BUSINESS_LOGIC |
| retrieval-steps    | src/pipelines/retrieval/steps/    | Steps R0–R7 (normalize, aliases, FTS query, search)  | BUSINESS_LOGIC |
| consult-pipeline   | src/pipelines/consult/            | Medical consultation pipeline: models, config, bundle | BUSINESS_LOGIC |
| consult-steps      | src/pipelines/consult/steps/      | Steps C0–C4 (load, retrieve, bundle, LLM, format)    | BUSINESS_LOGIC |
| store-protocols    | src/store/                        | KnowledgeStore + Store protocol interfaces           | DATA_MODELS    |
| store-sql          | src/store/sql/                    | SqliteKnowledgeStore + SqlStore (aiosqlite + FTS5)   | INFRA          |
| store-inmem        | src/store/inmem/                  | In-memory SagaStore for tests/dev                    | INFRA          |
| store-file         | src/store/file/                   | LocalFileStore for source document persistence       | INFRA          |
| llm                | src/llm/                          | LLMClient Protocol + OpenAICompatibleClient + MockLLMClient | INFRA   |
| common             | src/common/                       | Logging, text normalizer, alias map, parsers         | INFRA          |
| runners            | src/main/                         | CLI runner scripts (ingest, retrieve, consult)       | CLI_AUTOMATION |
| tests-consult      | tests/consult/                    | Consult pipeline unit tests                          | TESTS          |
| tests-retrieval    | tests/retrieval/                  | Retrieval pipeline unit tests                        | TESTS          |
| tests-parsers      | tests/parsers/                    | Markdown parser unit tests                           | TESTS          |
| tests-root         | tests/                            | Tokenizer, document date, retrieval fixture tests    | TESTS          |

---

## FLOWS

### Ingest pipeline (S0–S9, with SagaRunner checkpoints)

| STEP | FROM               | TO                  | PURPOSE                              | NOTES                                              |
|------|--------------------|---------------------|--------------------------------------|----------------------------------------------------|
| 1    | IngestInput        | LoadSource          | Read raw markdown from disk          | src/pipelines/ingest/steps/load_source.py          |
| 2    | LoadSource         | PreprocessText      | NFKC normalize, compute SHA256       | src/pipelines/ingest/steps/preprocess_text.py      |
| 3    | PreprocessText     | DetectTargetSchema  | Extract category from frontmatter    | src/pipelines/ingest/steps/detect_target_schema.py |
| 4    | DetectTargetSchema | ParseToTokens       | Markdown → MdToken list              | src/pipelines/ingest/steps/parse_to_tokens.py      |
| 5    | ParseToTokens      | ChunkifyBlocks      | Section path → typed chunks          | src/pipelines/ingest/steps/chunkify_blocks.py      |
| 6    | ChunkifyBlocks     | PersistChunks       | Tag + save to SQLite + sync FTS5     | src/pipelines/ingest/steps/persist_chunks.py       |

### Retrieval pipeline (R0–R7, stateless)

| STEP | FROM             | TO               | PURPOSE                              | NOTES                                                |
|------|------------------|------------------|--------------------------------------|------------------------------------------------------|
| 1    | RetrieveRequest  | NormalizeQuery   | Lowercase, ё→е, strip punctuation    | src/pipelines/retrieval/steps/normalize_query.py     |
| 2    | NormalizeQuery   | ClassifyIntent   | Propagate request.category           | src/pipelines/retrieval/steps/classify_intent.py     |
| 3    | ClassifyIntent   | ExpandAliases    | Add synonym/alias terms              | src/pipelines/retrieval/steps/expand_aliases.py      |
| 4    | ExpandAliases    | BuildFtsQuery    | Build FTS5 MATCH expression          | src/pipelines/retrieval/steps/build_fts_query.py     |
| 5    | BuildFtsQuery    | SearchChunks     | BM25 search via SqliteKnowledgeStore | src/pipelines/retrieval/steps/search_chunks.py       |
| 6    | SearchChunks     | GroupByDocument  | Group chunks by document_id          | src/pipelines/retrieval/steps/group_by_document.py   |

### Consultation pipeline (C0–C4, stateless)

| STEP | FROM             | TO               | PURPOSE                              | NOTES                                              |
|------|------------------|------------------|--------------------------------------|----------------------------------------------------|
| 1    | ConsultRequest   | LoadRequest      | Populate ConsultData.user_request    | src/pipelines/consult/steps/load_request.py        |
| 2    | LoadRequest      | Retrieve         | BM25 query + recency bundle          | src/pipelines/consult/steps/retrieve.py            |
| 3    | Retrieve         | BuildBundle      | Assemble KBContextBundle             | src/pipelines/consult/steps/build_bundle.py        |
| 4    | BuildBundle      | CallPatientQuery | Send prompt to LLM                   | src/pipelines/consult/steps/call_llm_query.py      |
| 5    | CallPatientQuery | FormatResponse   | Wrap raw text in ConsultResponse     | src/pipelines/consult/steps/format_response.py     |

---

## API_CONSUMED

| SERVICE           | BASE_URL_CONFIG_KEY | OPERATIONS                  | MODULE |
|-------------------|---------------------|-----------------------------|--------|
| OpenAI-compatible | passed via env      | chat.completions.create     | llm    |

---

## DATA_ENTITIES

| ENTITY           | PURPOSE                                              |
|------------------|------------------------------------------------------|
| SagaInput        | Base Pydantic input type for all pipelines           |
| SagaData         | Base Pydantic state type for all pipeline contexts   |
| RunContext       | Execution context: run_id, cursor, input, data       |
| SagaDefinition   | Named ordered list of SagaStep instances             |
| SavedProgress    | Saga checkpoint TypedDict: run_id, cursor, state     |
| IngestInput      | Input to ingest pipeline: source_path                |
| IngestData       | Full ingest state from raw_content to chunk_ids      |
| ChunkTagged      | Chunk with tags_text (output of S7 Tagging)          |
| RetrieveRequest  | Retrieval query: text, category, filters, limits     |
| RetrievalData    | Retrieval FSM state: query → normalized → chunks     |
| RetrieveResponse | External retrieval result: chunks + documents        |
| DocumentEvidence | Retrieval result grouped by document                 |
| ConsultRequest   | Consultation input: user_request string              |
| ConsultData      | Consultation state: chunks, bundle, response         |
| KBContextBundle  | Formatted KB context for LLM prompt                  |
| ChunkSearchResult| BM25 search hit: text, rank, section, source info    |

---

## KEY_FILES

| FILE                                         | PURPOSE                                  | RELATED_MODULES                          |
|----------------------------------------------|------------------------------------------|------------------------------------------|
| pyproject.toml                               | Deps, scripts, ruff/mypy/pytest config   | all                                      |
| src/fsm/core.py                              | RunContext, SagaStep, SagaDefinition     | fsm-core, all pipelines                  |
| src/fsm/saga.py                              | Stateless step executor (Saga)           | fsm-core, all pipelines                  |
| src/fsm/saga_runner.py                       | Checkpointing orchestrator               | fsm-core, ingest-pipeline                |
| src/fsm/models.py                            | SagaInput, SagaData base models          | all pipelines                            |
| src/store/store.py                           | Store Protocol + SavedProgress           | store-sql, store-inmem                   |
| src/store/knowledge_store.py                 | KnowledgeStore Protocol + ChunkSearchResult | store-sql, ingest-steps, retrieval-steps |
| src/store/sql/schema.sql                     | SQLite DDL: documents, chunks, FTS5, saga_progress | store-sql                    |
| src/store/sql/sqlite_knowledge_store.py      | SqliteKnowledgeStore (FTS5, BM25)        | store-sql, all pipelines                 |
| src/llm/llm_client.py                        | LLMClient Protocol                       | llm, consult-pipeline                    |
| src/llm/openai_client.py                     | OpenAICompatibleClient implementation    | llm, consult-pipeline                    |
| src/pipelines/retrieval/runner.py            | RetrievalRunner (wires R0–R7)            | retrieval-pipeline, consult-pipeline     |
| src/pipelines/consult/runner.py              | ConsultRunner (wires C0–C4)              | consult-pipeline, runners                |
| src/main/ingest.py                           | Ingest CLI entrypoint                    | runners, ingest-pipeline                 |
| config/consult.yaml                          | Consultation pipeline tuning             | consult-pipeline                         |
| config/retrieve.yaml                         | BM25 weights and retrieval params        | retrieval-pipeline                       |

---

## CONVENTIONS

| RULE                                                        | SOURCE                  |
|-------------------------------------------------------------|-------------------------|
| mypy strict — all functions fully typed, no implicit Optional | pyproject.toml        |
| ruff B+UP enforced — no bugbear patterns, modern Python     | pyproject.toml          |
| Pipeline state accessed as ctx.data (not ctx.state)         | src/fsm/core.py         |
| Generic type vars: TIn (input), TData (pipeline state)      | src/fsm/core.py         |
| FTS5 sync always atomic inside PersistChunks (S9)           | src/store/sql/schema.sql|

---

<!-- Generated: 2026-05-22 -->
<!-- updated 2026-05-22: full rewrite — added consult pipeline, llm module, correct entrypoints, fixed env vars, removed non-existent main.py reference -->
