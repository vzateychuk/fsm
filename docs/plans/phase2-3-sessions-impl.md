# Phase 2–3 — Sessions & Compression: Implementation Plan

Выведен из решений, принятых в ходе проработки концепта.
Родительский документ: [med-ai-adviser-roadmap.md](med-ai-adviser-roadmap.md).

---

## Принятые решения (зафиксировано)

| # | Решение | Выбор |
|---|---------|-------|
| 1 | Хранение сессий | Две таблицы: `sessions` + `messages` |
| 2 | Системное сообщение | Пересобирается при открытии, не хранится |
| 3 | Роли сообщений | Все роли: user, assistant, tool |
| 4 | `tool_calls` | JSON-blob в колонке `tool_calls_json TEXT NULL` |
| 5 | Статусы сессии | `active / pinned / archived` — взаимоисключающие |
| 6 | Автозаголовок | Первые N символов первого user-сообщения |
| 7 | Загрузка истории | В CLI/API слое, передаётся в конструктор runner'а |
| 8 | Момент сохранения | После каждого хода целиком, одна транзакция |
| 9 | `InternalStore` методы | `upsert_session`, `get_session`, `list_sessions`, `delete_session`, `save_messages`, `load_messages` |
| 10 | Триггер компрессии | По числу ходов (`summarize_after_turns` в конфиге) |
| 11 | Хранение резюме | Колонка `summary TEXT NULL` в `sessions` |
| 12 | Полнота `messages` | Полная история всегда; window применяется при сборке контекста |
| 13 | Summarizer | Async-функция с rolling summary, запускается синхронно после хода |

---

## Схема БД (дополнение к schema.sql)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active', -- active | pinned | archived
    summary     TEXT,                           -- rolling summary, NULL до первой компрессии
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_status_updated
    ON sessions(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    seq             INTEGER NOT NULL,           -- порядок внутри сессии
    role            TEXT NOT NULL,              -- user | assistant | tool
    content         TEXT NOT NULL,
    tool_call_id    TEXT,                       -- для role=tool: ссылка на ToolCall.id
    tool_calls_json TEXT,                       -- для role=assistant: JSON array of ToolCall
    created_at      TEXT NOT NULL,
    UNIQUE(session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_messages_session_seq
    ON messages(session_id, seq);
```

---

## Модели данных

### `SessionRecord` (новый файл: `src/store/models.py`)

```python
@dataclass
class SessionRecord:
    session_id: str
    title: str
    status: str        # active | pinned | archived
    created_at: str
    updated_at: str
    summary: str | None = None
```

### `InternalStore` Protocol (`src/store/internal_store.py`)

```python
class InternalStore(Protocol):
    async def upsert_session(self, session: SessionRecord) -> None: ...
    async def get_session(self, session_id: str) -> SessionRecord | None: ...
    async def list_sessions(self, include_archived: bool = False) -> list[SessionRecord]: ...
    async def delete_session(self, session_id: str) -> None: ...

    async def save_messages(self, session_id: str, messages: list[Message]) -> None: ...
    async def load_messages(self, session_id: str) -> list[Message]: ...
```

---

## Изменения в `AgenticLoopRunner`

Добавить параметр `history` в конструктор (восстановление сессии):

```python
def __init__(
    self,
    llm_client: LLMClient,
    tool_executor: KBToolExecutor,
    system_message: str,
    loop_config: ChatConfig,
    history: list[Message] | None = None,   # новый параметр
) -> None:
    ...
    self._history: list[Message] = list(history) if history else []
    self._save_cursor: int = len(self._history)  # индекс последнего сохранённого сообщения
```

Добавить свойство для получения новых сообщений после хода:

```python
@property
def unsaved_messages(self) -> list[Message]:
    """Сообщения, добавленные с момента последнего сохранения."""
    return list(self._history[self._save_cursor:])

def mark_saved(self) -> None:
    """Сдвинуть курсор сохранения на текущую позицию."""
    self._save_cursor = len(self._history)
```

---

## Изменения в `ChatConfig` (Phase 3)

Добавить секцию `memory` в `config/chat.yaml` и `ChatConfig`:

```python
@dataclass
class MemoryConfig:
    window_turns: int          # сколько последних ходов передавать в LLM
    summarize_after_turns: int # каждые N ходов запускать Summarizer
```

---

## Сборка контекста для LLM (Phase 3)

Новая функция `build_context_messages` (вынести из `AgenticLoopRunner._call_llm`):

```python
def build_context_messages(
    system_message: str,
    history: list[Message],
    summary: str | None,
    window_turns: int,
) -> list[Message]:
    """
    system_message
    + Message(role='system', content=summary)  если summary не None
    + history[-window_turns * messages_per_turn:]
    """
```

`window_turns` — число пользовательских ходов; при подсчёте срезаем `history` по количеству `role=user` сообщений, а не по общему числу строк (каждый ход содержит несколько сообщений: user + tool calls + assistant).

---

## Summarizer (Phase 3)

Новый файл: `src/chat/summarizer.py`

```python
async def summarize(
    llm_client: LLMClient,
    previous_summary: str | None,
    messages_to_compress: list[Message],
) -> str:
    """
    Вызывает LLM с задачей сжать messages_to_compress в клиническое резюме.
    Если previous_summary есть — включает его как контекст для rolling summary.
    """
```

Промпт для Summarizer выносится в отдельный шаблон: `prompts/chat/summarize.md`.

---

## Порядок реализации

### Phase 2 — Persistent Sessions

1. `src/store/models.py` — `SessionRecord` dataclass.
2. `src/store/sql/schema.sql` — добавить DDL таблиц `sessions` и `messages`.
3. `src/store/internal_store.py` — заполнить Protocol методами.
4. `src/store/sql/sqlite_internal_store.py` — реализация `SqliteInternalStore`:
   - `upsert_session` / `get_session` / `list_sessions` / `delete_session`
   - `save_messages` (сериализация `tool_calls` → JSON)
   - `load_messages` (десериализация JSON → `list[Message]`)
5. `src/chat/agentic_loop.py` — добавить `history` в конструктор, `unsaved_messages`, `mark_saved`.
6. `src/main/chat.py` — интеграция:
   - флаг `--session <id>` для восстановления существующей сессии
   - создание новой сессии при старте
   - автозаголовок из первого сообщения
   - сохранение сообщений после каждого хода (`save_messages` + `mark_saved`)
   - операции управления: list / rename / archive / pin / delete (через subcommands или отдельный CLI)

**Критерий выхода Phase 2:** после перезапуска процесса сессия восстанавливается с той же историей; список сессий, переименование, архивирование работают через CLI.

---

### Phase 3 — Context & Compression

1. `src/chat/config.py` — добавить `MemoryConfig`, включить в `ChatConfig`.
2. `config/chat.yaml` — добавить секцию `memory` с дефолтами.
3. `src/chat/context_builder.py` — функция `build_context_messages`.
4. `src/chat/agentic_loop.py` — использовать `build_context_messages` вместо прямой передачи `_history`.
5. `prompts/chat/summarize.md` — промпт для Summarizer.
6. `src/chat/summarizer.py` — async-функция `summarize`.
7. `src/main/chat.py` — после каждого хода проверять порог `summarize_after_turns`; если достигнут — вызвать `summarize`, обновить `session.summary`, сохранить через `upsert_session`.

**Критерий выхода Phase 3:** диалог с числом ходов выше `window_turns` остаётся рабочим; в LLM-запрос не попадает вся история целиком; резюме обновляется по порогу; основная LLM не занимается сжатием вместо ответа пациенту.
