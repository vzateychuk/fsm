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
| pipeline-ingest | src/pipelines/ingest/ | 10-step markdown document ingestion pipeline      | BUSINESS_LOGIC |
| store-protocol  | src/store/store.py    | Store Protocol + SavedProgress TypedDict          | INFRA          |
| store-inmem     | src/store/inmem/      | In-memory Store implementation for testing        | INFRA          |
| store-sql       | src/store/sql/        | SQLite Store stub (unimplemented)                 | INFRA          |
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
| src/main/main.py | Ingest pipeline entry point; wires definition, store, runner | entrypoint |

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
