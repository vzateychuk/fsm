## PROJECT

| FIELD        | VALUE                                                              |
|--------------|--------------------------------------------------------------------|
| name         | fsm                                                               |
| type         | application                                                       |
| architecture | layered + pipeline-driven (FastAPI + CLI + SQLite)                |
| languages    | Python 3.13, TypeScript                                           |
| frameworks   | FastAPI, Uvicorn, Pydantic, Typer (backend); React 19, Vite (UI) |
| build        | uv + setuptools (backend); npm (frontend)                          |

---

## COMMANDS

| TASK   | COMMAND              | NOTES                            |
|--------|----------------------|----------------------------------|
| serve  | `uv run serve`       | HTTP API server                  |
| advisor| `uv run advisor`     | Consult pipeline CLI             |
| chat   | `uv run chat`        | Interactive consultation REPL     |
| build  | `npm run build`      | Frontend production build        |
| dev    | `npm run dev`        | Frontend dev server              |
| check  | `npm run check`      | Frontend: gen API + typecheck    |
| test   | `pytest`             | Backend test suite               |

*(From pyproject.toml [project.scripts] and frontend/package.json.)*

---

## RUNTIME

| REQUIREMENT | VERSION | NOTES                           |
|-------------|---------|----------------------------------|
| Python      | 3.13+   | from requires-python             |
| SQLite      | -       | aiosqlite async driver           |
| Node.js     | -       | frontend dev only                |
| Web server  | Uvicorn | ASGI server                      |

*(No Dockerfile or docker-compose. Python 3.13+ required. No hard runtime descriptor for Node.)*

---

## DEPENDENCIES

| PACKAGE           | VERSION      | PURPOSE                         |
|-------------------|--------------|---------------------------------|
| fastapi           | >=0.111,<1   | HTTP API framework              |
| pydantic          | >=2.7,<3     | Typed models                    |
| uvicorn[standard] | >=0.29,<1    | ASGI server                    |
| aiosqlite         | >=0.20,<0.22 | Async SQLite access             |
| openai            | >=1.30,<2    | OpenAI-compatible LLM client    |
| typer             | >=0.12,<1    | CLI entrypoints                |
| markdown-it-py    | >=3.0,<4     | Markdown parsing                |
| PyYAML            | >=6.0,<7     | YAML config loading             |
| argon2-cffi       | >=23.1,<26   | Password hashing (auth)           |

*(Top production deps from pyproject.toml [project.dependencies].)*

---

## ENV_CONFIG

| KEY              | REQUIRED | PURPOSE                              |
|------------------|----------|--------------------------------------|
| HOST             | no       | Uvicorn bind host                    |
| PORT             | no       | Uvicorn bind port                    |
| RELOAD           | no       | Uvicorn autoreload flag              |
| AUTH_ENABLED     | no       | `false` = single-user mode (USERNAME) |
| USERNAME         | no       | User slug when AUTH_ENABLED=false    |
| DB_PATH          | no       | User SQLite path (single-user mode)  |
| USER_DB_ROOT     | no       | Directory for per-user DB files      |
| SYSTEM_DB_PATH   | no       | Accounts/sessions system DB          |
| COOKIE_SECURE    | no       | Secure flag on session cookie        |
| CORS_ORIGINS     | no       | Allowed browser origins              |
| LOG_FILE         | no       | Optional log file path               |
| NVIDIA_API_KEY   | no       | NVIDIA LLM API key (for config/llm-nvidia.yaml) |

*(From src/api/main.py, src/api/user_resolver.py, src/api/user_db_paths.py, src/api/cookies.py.)*

---

## ENTRYPOINTS

| TYPE              | PATH                     | PURPOSE                    |
|-------------------|--------------------------|----------------------------|
| server            | src/api/main.py          | Uvicorn startup wrapper    |
| app               | src/api/app.py           | Module-level FastAPI app   |
| cli               | src/main/chat.py         | Chat REPL CLI              |
| cli               | src/main/ingest.py       | Ingest pipeline CLI        |
| script            | src/main/consult.py      | Consult pipeline runner     |
| script            | scripts/migrate_pilot_to_default.py | Pilot DB migration |

---

## STRUCTURE (depth=2)

```
src/
  api/          routers/, app.py, factory.py, deps.py, user_context.py,
                user_resolver.py, user_db_paths.py, schema_init.py, cookies.py
  chat/         agentic_loop.py, tool_executor.py, baseline_retriever.py
  common/      utils/parsers/, logging_config.py, patient.py, username.py
  fsm/         core.py, saga.py, saga_runner.py, models.py
  llm/         openai_client.py, retry_client.py, config.py
  main/        chat.py, ingest.py, consult.py, retrieve.py
  pipelines/
    consult/   runner.py, steps/call_llm.py, format_response.py, ...
    ingest/    steps/ (10 steps), models.py, config.py
    retrieval/ runner.py, steps/search_chunks.py, classify_intent.py, ...
  services/    chat.py, documents.py, sessions.py, profile.py, auth.py, errors.py
  store/       sql/sqlite_internal_store.py, sqlite_system_store.py, schema.sql, system_schema.sql
config/        api.yaml, llm.yaml, chat.yaml, retrieve.yaml, patient.yaml
frontend/src/  app/, features/chat, documents, profile, layout/, core/
prompts/       chat/system.md, user.md
scripts/       (shell helpers)
tests/         consult/, ingest/, parsers/, retrieval/, store/, fixtures/
```

---

## MODULES

| MODULE              | PATH                    | PURPOSE                          | AI_TASK        |
|---------------------|-------------------------|----------------------------------|----------------|
| api                 | src/api                 | HTTP layer and routers           | API_CHANGES    |
| chat                | src/chat                | Agentic loop orchestration       | BUSINESS_LOGIC |
| fsm                 | src/fsm                 | Generic saga execution core      | BUSINESS_LOGIC |
| llm                 | src/llm                 | Vendor-neutral LLM clients       | INFRA          |
| pipelines.consult    | src/pipelines/consult   | Consultation flow (LLM call)      | BUSINESS_LOGIC |
| pipelines.ingest     | src/pipelines/ingest   | 10-step document ingestion       | BUSINESS_LOGIC |
| pipelines.retrieval  | src/pipelines/retrieval | BM25+FTS retrieval flow          | BUSINESS_LOGIC |
| services            | src/services            | App service layer                | BUSINESS_LOGIC |
| services.auth       | src/services/auth.py    | Registration, login, sessions    | BUSINESS_LOGIC |
| api.auth            | src/api/user_resolver.py| HTTP user resolution + deps      | API_CHANGES    |
| store               | src/store               | Internal and knowledge storage   | INFRA          |
| common              | src/common              | Shared utilities, parsers, logging| DEV_TOOLING    |
| frontend            | frontend                | React 19 SPA, auth guards        | FRONTEND       |
| frontend.auth         | frontend/src/features/auth | Login, register, authErrors   | FRONTEND       |
| config              | config                  | YAML runtime settings             | CONFIG         |
| prompts             | prompts                 | Prompt templates                 | CONFIG         |
| tests               | tests                   | Automated test suite             | TESTS          |

---

## FLOWS

| HTTP Request Flow              |              |                                  |                       | NOTES                    |
| STEP | FROM                    | TO                       | PURPOSE                    |                          |
|------|-------------------------|--------------------------|-----------------------------|--------------------------|
| 1    | client                  | CORS middleware          | Set allowed origins         | src/api/app.py          |
| 2    | CORS middleware         | RequestIDMiddleware      | Inject X-Request-ID header  | src/api/middleware.py   |
| 3    | RequestIDMiddleware     | Router                   | Route to handler            | src/api/app.py          |
| 4    | Router                  | resolve_user_context     | Cookie → session → user DB  | src/api/user_resolver.py|
| 5    | Router                  | require_complete_profile | 403 if profile incomplete   | src/api/deps.py         |
| 6    | Router                  | SessionService/ChatService| Execute business logic      | src/api/routers/*.py    |
| 7    | Service                 | SqliteInternalStore / SystemStore | Per-user + system SQLite | src/store/sql/*.py      |
| 8    | Service                 | client                   | Return JSON response        | FastAPI automatic        |

---

## API_SURFACE

| ROUTE_GROUP | PATH_PREFIX            | PURPOSE                        |
|-------------|------------------------|--------------------------------|
| health      | /health                | Health check                   |
| auth        | /api/v1/auth           | Register, login, logout, me    |
| profile     | /api/v1/profile        | Patient profile GET/PATCH      |
| sessions    | /api/v1/sessions       | Session CRUD + messages        |
| chat        | /api/v1/sessions/{id}/messages | Send/receive messages |
| documents   | /api/v1/documents      | Document upload and listing    |

*(All routes from src/api/routers/*.py. No global path prefix — each router defines its own prefix.)*

---

## API_CONSUMED

| SERVICE      | BASE_URL_CONFIG_KEY | OPERATIONS            | MODULE       |
|--------------|---------------------|-----------------------|--------------|
| Ollama/NVIDIA| llm.base_url        | Completion, chat      | llm          |

*(src/llm/openai_client.py. External LLM via OpenAI-compatible API. No other outbound integrations.)*

---

## FEATURE_MAP

| FEATURE   | ROUTE                     | HANDLER          | SERVICE          | MODEL          |
|-----------|---------------------------|------------------|------------------|----------------|
| health    | GET /health               | health router    | -                | -              |
| auth      | POST /api/v1/auth/*       | auth router      | AuthService      | AccountRecord  |
| profile   | GET /api/v1/profile       | profile router   | ProfileService   | PatientInfo    |
| sessions  | /api/v1/sessions          | sessions router  | SessionsService  | SessionRecord  |
| chat      | POST /api/v1/sessions/{id}/messages | chat router | ChatService | MessageRecord  |
| documents | /api/v1/documents         | documents router | IngestService    | Document       |

---

## DATA_ENTITIES

| ENTITY          | PURPOSE                                    |
|-----------------|--------------------------------------------|
| SessionRecord   | Persistent chat consultation session       |
| MessageRecord   | User/assistant message with metadata       |
| Document        | Indexed markdown document metadata          |
| Chunk           | Document text chunk with heading/section   |
| SagaProgress    | Saga checkpoint (run_id, cursor, state)    |
| PatientInfo     | Patient demographics (user DB user_profile) |
| AccountRecord   | Registered user + db_path in system DB       |
| AuthSessionRecord | HttpOnly session in system DB              |
| IngestData      | Ingest pipeline context (10 fields)        |
| IngestInput     | Ingest pipeline input                      |

*(From schema.sql, store/models.py, pipelines/ingest/models.py.)*

---

## KEY_FILES

| FILE                       | PURPOSE                                   | RELATED_MODULES             |
|----------------------------|-------------------------------------------|------------------------------|
| pyproject.toml             | Backend deps, scripts, tooling config     | all                          |
| frontend/package.json      | Frontend deps and scripts                 | frontend                     |
| src/api/main.py            | Uvicorn entry point                       | api                          |
| src/api/app.py             | FastAPI app factory with CORS/exception   | api, services                |
| src/api/factory.py         | SharedContext + UserContextFactory        | all services                 |
| src/api/user_context.py    | Per-user service bundle (UserContext)     | api, services                |
| src/api/user_resolver.py   | Cookie/session → UserContext (HTTP)       | api, services/auth           |
| src/api/user_db_paths.py   | USER_DB_ROOT, DB_PATH resolution          | api                          |
| src/api/schema_init.py     | Idempotent user/system schema bootstrap   | store                        |
| src/api/cookies.py           | session_id cookie (Secure, HttpOnly)      | api/routers/auth             |
| src/api/deps.py            | get_user_context, require_complete_profile| api                          |
| src/services/auth.py       | Register, login, session rotation         | store/sqlite_system_store    |
| src/store/sql/sqlite_system_store.py | accounts + auth_sessions in system.db | store, auth          |
| src/api/routers/auth.py    | /api/v1/auth/* endpoints                  | services/auth                |
| src/api/routers/*.py       | HTTP route handlers                       | services                     |
| src/services/chat.py       | Agentic chat orchestration                | chat, llm, store             |
| src/fsm/core.py            | Saga run context and step protocol        | pipelines                    |
| src/fsm/saga_runner.py     | Saga orchestrator with checkpointing      | pipelines                    |
| src/store/sql/schema.sql   | SQLite schema (documents, chunks, sessions, messages, saga_progress) | store, services |
| config/llm.yaml            | LLM endpoint and retry config             | llm                          |
| config/patient.yaml        | Patient demographics for consultation     | services/profile             |
| config/api.yaml            | API layer config (timeouts, pagination)   | api                          |
| prompts/chat/system.md     | System prompt template for LLM            | chat                         |
| frontend/src/main.tsx      | React SPA entry point                     | frontend                     |

---

## CONVENTIONS

| RULE                                | SOURCE                |
|-------------------------------------|-----------------------|
| Python 3.13+ required               | pyproject.toml        |
| Ruff line-length = 100             | pyproject.toml        |
| Mypy strict mode enabled            | pyproject.toml        |
| Tests live under tests/ with pytest | pyproject.toml        |
| FastAPI app is module-level variable| src/api/app.py        |
| Config loaded from YAML files       | src/api/factory.py    |

*(From pyproject.toml [tool.ruff], [tool.mypy]; confirmed from src/api/app.py.)*

---

<!-- Updated: 2026-06-11 (Phase 6–7 auth, per-user DB) -->