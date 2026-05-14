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

## ENTRYPOINTS

| TYPE   | PATH                         |
|--------|------------------------------|
| script | src/main/text_pipeline_main.py |
| script | src/main/number_pipeline_main.py |
| script | src/main/ingest_main.py        |

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
│   ├── text_pipeline/
│   ├── number_pipeline/
│   └── ingest/
├── store/
│   ├── inmem/
│   └── sql/
└── main/
tests/
logs/
```

---

## MODULES

| MODULE           | PATH                         | PURPOSE                                    | AI_TASK        |
|------------------|------------------------------|--------------------------------------------|----------------|
| fsm-core         | src/fsm/                     | Framework abstractions: RunContext, Saga, SagaRunner | BUSINESS_LOGIC |
| commons          | src/commons/                 | Shared logging utilities                   | DEV_TOOLING    |
| text-pipeline    | src/pipelines/text_pipeline/ | Text processing pipeline (2 steps)         | BUSINESS_LOGIC |
| number-pipeline  | src/pipelines/number_pipeline/ | Number processing pipeline (3 steps)       | BUSINESS_LOGIC |
| ingest           | src/pipelines/ingest/        | Document ingestion FTS pipeline (11 steps) | BUSINESS_LOGIC |
| store            | src/store/                   | SagaProgressStore protocol + SavedProgress | INFRA          |
| store-inmem      | src/store/inmem/             | In-memory store for testing                | INFRA          |
| store-sql        | src/store/sql/               | SQL store stub (aiosqlite, TODO)           | INFRA          |
| main-scripts     | src/main/                    | Pipeline entry points and run examples     | CLI_AUTOMATION |
| tests            | tests/                       | Test suite (currently empty)               | TESTS          |

---

## FLOWS

### Pipeline execution flow

| STEP | FROM              | TO                 | PURPOSE                             | NOTES                        |
|------|-------------------|--------------------|-------------------------------------|------------------------------|
| 1    | caller            | SagaRunner.run     | Start saga with run_id and input    | src/fsm/saga_runner.py:23    |
| 2    | SagaRunner        | store.load         | Load saved checkpoint by run_id     | src/fsm/saga_runner.py:76    |
| 3    | SagaRunner        | Saga.run           | Execute steps from cursor position  | src/fsm/saga.py:21           |
| 4    | Saga.run          | StepAction.run     | Execute single step, update ctx     | src/fsm/saga.py:35           |
| 5    | post_step_callback| store.save         | Persist checkpoint after each step  | src/fsm/saga_runner.py:47    |

---

## FEATURE_MAP

| FEATURE         | ROUTE | HANDLER                      | SERVICE              | MODEL                   |
|-----------------|-------|------------------------------|----------------------|-------------------------|
| text-pipeline   | -     | src/main/text_pipeline_main.py | Saga, SagaRunner | TextInput, TextData     |
| number-pipeline | -     | src/main/number_pipeline_main.py | Saga, SagaRunner | NumberInput, NumberData |
| ingest          | -     | src/main/ingest_main.py      | Saga, SagaRunner | IngestInput, IngestData |

---

## DATA_ENTITIES

| ENTITY            | PURPOSE                                         |
|-------------------|-------------------------------------------------|
| SagaInput         | Base Pydantic class for pipeline input data     |
| SagaData          | Base Pydantic class for pipeline context/state  |
| RunContext        | Execution context: run_id, cursor, input, data  |
| SagaDefinition    | Pipeline definition: name + ordered steps list  |
| SagaProgressStore | Protocol for checkpoint load/save               |
| SavedProgress     | TypedDict: run_id, saga_name, cursor, state     |
| TextInput         | Text pipeline input (raw_text)                  |
| TextData          | Text pipeline state (text, tokens, result)      |
| NumberInput       | Number pipeline input (raw_numbers string)      |
| NumberData        | Number pipeline state (numbers, sum, result)    |
| IngestInput       | Ingest pipeline input (source_path)             |
| IngestData        | Ingest pipeline state (11 processing fields)    |

---

## KEY_FILES

| FILE                                    | PURPOSE                              | RELATED_MODULES              |
|-----------------------------------------|--------------------------------------|------------------------------|
| pyproject.toml                          | Dependencies, build, tool config     | all                          |
| src/fsm/core.py                         | Core abstractions and protocols      | fsm-core, all pipelines      |
| src/fsm/models.py                       | Base SagaInput/SagaData classes      | fsm-core, all pipelines      |
| src/fsm/saga.py                         | Stateless Saga executor              | fsm-core                     |
| src/fsm/saga_runner.py                  | Orchestrator with checkpoint support | fsm-core, store              |
| src/store/store.py                      | Store protocol and SavedProgress     | store, store-inmem, store-sql|
| src/store/inmem/inmemory_store.py       | In-memory store implementation       | store-inmem, main-scripts    |
| src/store/sql/sql_store.py              | SQL store stub (aiosqlite)           | store-sql                    |
| src/commons/logging_config.py           | Logging setup utility                | commons, main-scripts        |
| src/main/text_pipeline_main.py       | Text pipeline entry point       | text-pipeline, main-scripts   |
| src/main/number_pipeline_main.py     | Number pipeline entry point     | number-pipeline, main-scripts  |
| src/main/ingest_main.py              | Ingest pipeline entry point     | ingest, main-scripts           |
| README.md                               | Architecture and usage docs          | all                          |

---

## CONVENTIONS

| RULE                                          | SOURCE         |
|-----------------------------------------------|----------------|
| strict mypy: disallow_untyped_defs, warn_return_any | pyproject.toml |
| ruff rules: E, F, I (isort), B (bugbear), UP (pyupgrade) | pyproject.toml |
| pytest asyncio_mode = "auto" for all async tests | pyproject.toml |

---

<!-- Generated: 2026-05-14 -->
