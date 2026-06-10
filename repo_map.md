## PROJECT

| FIELD        | VALUE |
|--------------|-------|
| name         | fsm |
| type         | application |
| architecture | pipeline-driven FastAPI + CLI + SQLite |
| languages    | Python 3.13 |
| frameworks   | FastAPI, Typer, Pydantic, Uvicorn, aiosqlite |
| build        | uv + setuptools |

---

## COMMANDS

| TASK   | COMMAND | NOTES |
|--------|---------|-------|
| serve  | `uv run serve` | HTTP API server |
| advisor | `uv run advisor <file.md>` | Ingest markdown |
| chat   | `uv run chat` | Interactive chat REPL |

---

## STRUCTURE (depth=2)

config/
docs/
prompts/
scripts/
src/
  api/
    routers/
  chat/
  common/
    utils/
  fsm/
  llm/
  main/
  pipelines/
    consult/
    ingest/
    retrieval/
  services/
  store/
    file/
    inmem/
    sql/
tests/
  consult/
  fixtures/
  ingest/
  parsers/
  retrieval/
  store/

---

## RUNTIME

| Component | Version |
|-----------|---------|
| Python | 3.13+ |
| Package manager | uv |
| Build backend | setuptools |
| Web server | Uvicorn |
| Database | SQLite |

---

## ENTRYPOINTS

| Type | File | Purpose |
|------|------|---------|
| server | `src/api/main.py` | Starts Uvicorn |
| app | `src/api/app.py` | Module-level FastAPI app |
| cli | `src/main/ingest.py` | Ingest pipeline runner |
| cli | `src/main/consult.py` | Consultation pipeline runner |
| cli | `src/main/chat.py` | Interactive consultation REPL |
| script | `src/main/retrieve.py` | Retrieval debug runner |

---

## MODULES

| MODULE | PATH | PURPOSE | AI_TASK |
|--------|------|---------|---------|
| api | `src/api` | HTTP layer and routers | API_CHANGES |
| chat | `src/chat` | Agentic chat orchestration | BUSINESS_LOGIC |
| common | `src/common` | Shared parsers and utilities | DEV_TOOLING |
| fsm | `src/fsm` | Generic saga execution core | BUSINESS_LOGIC |
| llm | `src/llm` | Vendor-neutral LLM clients | INFRA |
| main | `src/main` | CLI entrypoints | CLI_AUTOMATION |
| pipelines.consult | `src/pipelines/consult` | Medical consultation flow | BUSINESS_LOGIC |
| pipelines.ingest | `src/pipelines/ingest` | Markdown ingestion flow | BUSINESS_LOGIC |
| pipelines.retrieval | `src/pipelines/retrieval` | BM25 retrieval flow | BUSINESS_LOGIC |
| services | `src/services` | App service layer | BUSINESS_LOGIC |
| store | `src/store` | Internal and knowledge storage | INFRA |
| tests | `tests` | Automated test suite | TESTS |
| config | `config` | YAML runtime settings | CONFIG |
| docs | `docs` | Design and roadmap notes | DEV_TOOLING |
| prompts | `prompts` | Prompt templates | CONFIG |
| scripts | `scripts` | Shell helpers | CLI_AUTOMATION |

---

## KEY_FILES

| FILE | PURPOSE |
|------|---------|
| `pyproject.toml` | Dependencies, scripts, tooling |
| `README.md` | Project overview and usage |
| `src/api/main.py` | Uvicorn startup wrapper |
| `src/api/app.py` | FastAPI app factory |
| `src/api/factory.py` | Wires stores, LLM, services |
| `src/llm/config.py` | Shared LLM config loader |
| `src/store/sql/schema.sql` | SQLite schema bootstrap |
| `src/main/ingest.py` | Markdown ingest CLI |
| `src/main/consult.py` | Consult CLI |
| `src/main/chat.py` | Chat REPL CLI |
| `src/main/retrieve.py` | Retrieval debug script |
| `config/llm.yaml` | Default LLM endpoint config |
| `config/retrieve.yaml` | Retrieval tuning config |
| `config/chat.yaml` | Chat loop tuning config |
| `config/consult.yaml` | Consult pipeline tuning config |

---

## DEPENDENCIES (top 8)

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | `>=2.7,<3` | Typed models |
| aiosqlite | `>=0.20.0,<0.22` | Async SQLite access |
| markdown-it-py | `>=3.0,<4` | Markdown parsing |
| PyYAML | `>=6.0,<7` | YAML config loading |
| openai | `>=1.30,<2` | OpenAI-compatible client |
| typer | `>=0.12,<1` | CLI entrypoints |
| fastapi | `>=0.111,<1` | HTTP API framework |
| uvicorn[standard] | `>=0.29,<1` | ASGI server |

---

## ENV_CONFIG

| Key | Required | Purpose |
|-----|----------|---------|
| `HOST` | no | Uvicorn bind host |
| `PORT` | no | Uvicorn bind port |
| `RELOAD` | no | Uvicorn autoreload flag |
| `DB_PATH` | no | SQLite database path |
| `CORS_ORIGINS` | no | Allowed browser origins |
| `LOG_FILE` | no | Optional log file path |
| `NVIDIA_API_KEY` | no | NVIDIA LLM API key |

---

## API_SURFACE

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/api/v1/profile` | Patient profile |
| GET | `/api/v1/sessions` | List sessions |
| POST | `/api/v1/sessions` | Create session |
| GET | `/api/v1/sessions/{session_id}` | Get session |
| PATCH | `/api/v1/sessions/{session_id}` | Update session |
| DELETE | `/api/v1/sessions/{session_id}` | Delete session |
| POST | `/api/v1/sessions/{session_id}/messages` | Send chat message |
| GET | `/api/v1/sessions/{session_id}/messages` | List messages |
| POST | `/api/v1/documents` | Upload document |
| GET | `/api/v1/documents` | List documents |

---

## CONVENTIONS

- Python 3.13+ required.
- Ruff line length is 100.
- Mypy runs in strict mode.
- Tests live under `tests/` and use pytest.
- FastAPI app is module-level for Uvicorn import.
