## PROJECT

| FIELD        | VALUE                                                                 |
|--------------|-----------------------------------------------------------------------|
| name         | fsm                                                                   |
| type         | library                                                               |
| architecture | layered (fsm-core / pipelines / store / entrypoints)                  |
| languages    | Python >=3.13                                                         |
| frameworks   | Pydantic 2.x, asyncio                                                 |
| build        | setuptools, uv                                                        |

---

## COMMANDS

| TASK        | COMMAND                 | NOTES                              |
|-------------|-------------------------|------------------------------------|
| test        | pytest                  | configured in pyproject.toml       |
| lint        | ruff check src/         | rules: E,F,I,B,UP; from pyproject  |
| type-check  | mypy src/               | strict mode; from pyproject        |

*(No [project.scripts] entries; commands derived from tool config in pyproject.toml.)*

---

## RUNTIME

| REQUIREMENT | VERSION    | NOTES                             |
|-------------|------------|-----------------------------------|
| Python      | >=3.13     | requires-python in pyproject.toml |

*(No Dockerfile, docker-compose, .python-version, or web server config found.)*

---

## DEPENDENCIES

| PACKAGE    | VERSION          | PURPOSE                              |
|------------|------------------|--------------------------------------|
| pydantic   | >=2.7,<3         | Data validation, model serialization |
| aiosqlite  | >=0.20.0,<0.22   | Async SQLite for SQL progress store  |

---

## ENV_CONFIG

| KEY         | REQUIRED | PURPOSE                                        |
|-------------|----------|------------------------------------------------|
| LOG_FILE    | no       | Log output path (default: logs/ingest.log)     |
| INGEST_FILE | no       | Input .md file path (default: tests/fixtures/ingest/consultation_deep.md) |

*(source: src/main/main.py:33,63)*

---

## ENTRYPOINTS

| TYPE   | PATH            |
|--------|-----------------|
| script | src/main/main.py |

---

## STRUCTURE (depth=2)

```
src/
├── fsm/
│   ├── core.py
│   ├── models.py
│   ├── saga.py
│   └── saga_runner.py
├── commons/
│   └── logging_config.py
├── pipelines/
│   └── ingest/
│       └── steps/
├── store/
│   ├── inmem/
│   └── sql/
└── main/
tests/
├── fixtures/
│   └── ingest/
logs/
```

---

## MODULES

| MODULE        | PATH                          | PURPOSE                                              | AI_TASK        |
|---------------|-------------------------------|------------------------------------------------------|----------------|
| fsm-core      | src/fsm/                      | Framework abstractions: RunContext, Saga, SagaRunner | BUSINESS_LOGIC |
| commons       | src/commons/                  | Shared logging utilities                             | DEV_TOOLING    |
| ingest        | src/pipelines/ingest/         | Ingest pipeline: models, IngestData contract         | DATA_MODELS    |
| ingest-steps  | src/pipelines/ingest/steps/   | 10 concrete pipeline steps (S0–S9)                   | BUSINESS_LOGIC |
| store         | src/store/                    | Store protocol + SavedProgress TypedDict             | INFRA          |
| store-inmem   | src/store/inmem/              | In-memory store for testing                          | INFRA          |
| store-sql     | src/store/sql/                | SQL store stub (aiosqlite, TODO)                     | INFRA          |
| main          | src/main/                     | Pipeline entry point                                 | CLI_AUTOMATION |
| fixtures      | tests/fixtures/ingest/        | Golden dataset: .md inputs + expected_*.yaml         | TESTS          |
| tests         | tests/                        | Test suite (currently empty)                         | TESTS          |

---

## FLOWS

### Pipeline execution flow

| STEP | FROM              | TO                 | PURPOSE                             | NOTES                        |
|------|-------------------|--------------------|-------------------------------------|------------------------------|
| 1    | caller            | SagaRunner.run     | Start saga with run_id and input    | src/fsm/saga_runner.py:23    |
| 2    | SagaRunner        | store.load         | Load saved checkpoint by run_id     | src/fsm/saga_runner.py:76    |
| 3    | SagaRunner        | Saga.run           | Execute steps from cursor position  | src/fsm/saga.py:21           |
| 4    | Saga.run          | SagaStep.run       | Execute single step, update ctx     | src/fsm/saga.py:35           |
| 5    | post_step_callback| store.save         | Persist checkpoint after each step  | src/fsm/saga_runner.py:47    |

---

## FEATURE_MAP

| FEATURE | ROUTE | HANDLER           | SERVICE       | MODEL                   |
|---------|-------|-------------------|---------------|-------------------------|
| ingest  | -     | src/main/main.py  | Saga, SagaRunner | IngestInput, IngestData |

---

## DATA_ENTITIES

| ENTITY            | PURPOSE                                                  |
|-------------------|----------------------------------------------------------|
| SagaInput         | Base Pydantic class for pipeline input data              |
| SagaData          | Base Pydantic class for pipeline context/state           |
| RunContext        | Execution context: run_id, cursor, input, data           |
| SagaDefinition    | Pipeline definition: name + ordered steps list           |
| Store             | Protocol for checkpoint load/save                        |
| SavedProgress     | TypedDict: run_id, saga_name, cursor, state              |
| IngestInput       | Ingest pipeline input (source_path)                      |
| IngestData        | Ingest pipeline state with Phase 0.1 field contracts     |
| MdToken           | TypedDict: markdown token (type, content, level, markup) |
| BlockEvent        | TypedDict: token + section_path + heading from S5        |
| Chunk             | TypedDict: kind/text/section_path/heading/chunk_no/tags  |
| IngestError       | Domain exception with error code (transient vs fatal)    |

---

## KEY_FILES

| FILE                                          | PURPOSE                                    | RELATED_MODULES               |
|-----------------------------------------------|--------------------------------------------|-------------------------------|
| pyproject.toml                                | Dependencies, build, tool config           | all                           |
| src/fsm/core.py                               | Core abstractions and protocols            | fsm-core, all pipelines       |
| src/fsm/models.py                             | Base SagaInput/SagaData classes            | fsm-core, all pipelines       |
| src/fsm/saga.py                               | Stateless Saga executor                    | fsm-core                      |
| src/fsm/saga_runner.py                        | Orchestrator with checkpoint support       | fsm-core, store               |
| src/pipelines/ingest/models.py                | IngestData contract + domain types         | ingest, ingest-steps          |
| src/pipelines/ingest/steps/__init__.py        | Step exports barrel (S0–S9)                | ingest-steps, main            |
| src/store/store.py                            | Store protocol and SavedProgress           | store, store-inmem, store-sql |
| src/store/inmem/inmemory_store.py             | In-memory store implementation             | store-inmem, main             |
| src/store/sql/sql_store.py                    | SQL store stub (aiosqlite)                 | store-sql                     |
| src/commons/logging_config.py                 | Logging setup utility                      | commons, main                 |
| src/main/main.py                              | Ingest pipeline entry point                | ingest, main                  |
| README.md                                     | Architecture and usage docs                | all                           |

---

## CONVENTIONS

| RULE                                          | SOURCE         |
|-----------------------------------------------|----------------|
| strict mypy: disallow_untyped_defs, warn_return_any | pyproject.toml |
| ruff rules: E, F, I (isort), B (bugbear), UP (pyupgrade) | pyproject.toml |
| pytest asyncio_mode = "auto" for all async tests | pyproject.toml |

---

<!-- Generated: 2026-05-14 -->
<!-- updated 2026-05-14: SagaProgressStore→Store in DATA_ENTITIES; StepAction→SagaStep in FLOWS; ingest 11→10 steps; added ENV_CONFIG -->
<!-- updated 2026-05-14: Phase 0 — added ingest-steps/fixtures modules; MdToken/BlockEvent/Chunk/IngestError entities; INGEST_FILE env; steps/__init__.py key file; updated STRUCTURE tree -->
