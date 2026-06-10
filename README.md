# FSM - Minimal Abstract Finite State Machine

Минимальная абстрактная реализация FSM (Finite State Machine) с поддержкой саг, чекпоинтирования и логирования. Фреймворк позволяет создавать различные pipeline-ы обработки данных с автоматическим сохранением прогресса и возможностью возобновления из чекпоинтов.

Текущая реализация включает **Ingest Pipeline** — 11-этапный pipeline обработки markdown-документов для индексирования в FTS5.

## Архитектура

```
src/
  commons/                      # Общие утилиты (не относящиеся к FSM)
    logging_config.py          # Настройка логирования с номерами строк
    
  fsm/                         # FSM фреймворк (переиспользуемое ядро)
    core.py                    # RunContext, SagaStep, StepAction, SagaDefinition, SagaProgressStore
    models.py                  # SagaInput, SagaData (базовые классы)
    saga.py                    # Saga - stateless executor с callbacks
    saga_runner.py             # SagaRunner - orchestrator (load/save/resume)
    
  pipelines/                   # Конкретные реализации pipeline-ов
    ingest/                    # Document ingestion pipeline (11 шагов)
      models.py               # IngestInput, IngestData
      steps.py                # LoadSource, PreprocessText, DetectSchema, ... UpdateFTS
      
  store/                       # Реализации хранилища прогресса
    inmem/
      inmemory_store.py       # In-memory хранилище (для тестирования)
    sql/
      sql_store.py            # SQL хранилище (stub)
      
  main/
    main.py                    # Запуск ingest pipeline
```

## Ключевые компоненты

### FSM Framework (`fsm/`)

**Основные классы и протоколы:**

- **`RunContext[TIn, TData]`** — контекст выполнения саги
  - `run_id` — идентификатор запуска
  - `input` — входные данные
  - `data` — текущие бизнес-данные контекста
  - `cursor` — текущий шаг

- **`SagaStep[TIn, TData]`** — протокол (interface) для шага саги
  - `id: str` — идентификатор шага
  - `desc: str | None = None` — опциональное описание шага
  - `async def run(ctx: RunContext) -> None` — выполнить шаг
  - **Дизайн:** Использует structural subtyping — любой класс с нужными атрибутами и методом `run()` автоматически удовлетворяет протоколу

- **`SagaInput`** — базовый класс для входных данных
  - Все pipeline-специфичные Input классы наследуют от неё

- **`SagaData`** — базовый класс для данных контекста
  - `desc: str | None = None` — опциональное описание текущего состояния
  - Содержит только бизнес-данные (промежуточные результаты)
  - Все pipeline-специфичные Data классы наследуют от неё

- **`SagaDefinition[TIn, TData]`** — определение саги
  - `name: str` — имя саги
  - `steps: list[SagaStep]` — список шагов

- **`SagaProgressStore`** — протокол для хранилища прогресса
  - `async def load(run_id: str) -> dict` — загрузить сохраненный прогресс
  - `async def save(data: dict) -> None` — сохранить прогресс

- **`Saga[TIn, TData]`** — stateless executor саги
  - Выполняет шаги саги
  - Вызывает callbacks перед/после шагов
  - НЕ отвечает за загрузку/сохранение

- **`SagaRunner[TIn, TData]`** — orchestrator саги
  - Загружает/создает pipeline из хранилища
  - Вызывает Saga для выполнения
  - Обрабатывает сохранение данных
  - Решает запустить новый или возобновить существующий pipeline

### Common Utilities (`commons/`)

- **`setup_logging(level, log_file, log_format)`** — настройка логирования
  - Логирование в консоль (stdout)
  - Опциональное логирование в файл
  - Формат по умолчанию включает номер строки: `name:lineno - level - message`
  - Автоматическое создание директории логов

### Pipeline-specific Code (`pipelines/`)

Каждый pipeline — это отдельный пакет с:
- **`models.py`** — входные данные и контекст данных (наследуют SagaInput/SagaData)
- **`steps.py`** — конкретные реализации шагов (наследуют StepAction)
- **`__init__.py`** — экспорт публичного API

**Текущая реализация:**
- **ingest** — обработка markdown-документов (10 шагов):
  1. LoadSource — загрузка файла
  2. PreprocessText — нормализация и SHA256 хеш
  3. DetectTargetSchema — определение категории из заголовка
  4. SplitControlBlocks — извлечение даты, очистка тела
  5. ParseToTokens — парсинг в токены
  6. BuildSectionPath — построение иерархии заголовков
  7. ChunkifyBlocks — группировка в логические блоки
  8. Tagging — извлечение ключевых терминов
  9. PersistDocument — сохранение метаданных и `raw_text` в БД (`source_path` = исходное имя файла)
  10. PersistChunks — сохранение блоков и синхронизация FTS5

Текст документа хранится только в `documents.raw_text`; отдельный filestore не используется. Orphan-файлы в `.data/filestore/` от старых версий можно удалить вручную.

## REST API (Backend)

### Запуск

```bash
uv sync

uv run python -m src.api.main
```

Сервер стартует на `http://localhost:8000`.

- Swagger UI: `http://localhost:8000/docs`
- API base URL: `http://localhost:8000/api/v1`

Переменные окружения (опционально): `HOST`, `PORT`, `DB_PATH`, `CORS_ORIGINS`.

### Основные операции

**Загрузить документ (Markdown):**
```bash
curl -X POST http://localhost:8000/api/v1/documents -F "file=@document.md"
```

**Создать сессию:**
```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" -d '{"title": "Новая сессия"}'
# -> {"session_id": "...", ...}
```

**Отправить сообщение:**
```bash
curl -X POST http://localhost:8000/api/v1/sessions/{session_id}/messages \
  -H "Content-Type: application/json" -d '{"content": "Ваш вопрос"}'
```

**Просмотреть историю сообщений:**
```bash
curl http://localhost:8000/api/v1/sessions/{session_id}/messages
```

### Все эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | /health | Проверка состояния |
| GET | /api/v1/profile | Профиль пациента |
| GET | /api/v1/sessions | Список сессий |
| POST | /api/v1/sessions | Создать сессию |
| GET | /api/v1/sessions/{id} | Получить сессию |
| PATCH | /api/v1/sessions/{id} | Переименовать / архивировать |
| DELETE | /api/v1/sessions/{id} | Удалить сессию |
| POST | /api/v1/sessions/{id}/messages | Отправить сообщение |
| GET | /api/v1/sessions/{id}/messages | История сообщений |
| POST | /api/v1/documents | Загрузить документ |
| GET | /api/v1/documents | Список документов |
| DELETE | /api/v1/documents/{id} | Удалить документ и чанки |

---

## Использование

### Запуск pipeline

```bash
# Ingest pipeline (11 шагов обработки markdown)
python src/main/cli.py
```

### Создание нового pipeline

1. **Создать директорию pipeline-а:**
   ```bash
   mkdir src/pipelines/my_pipeline
   ```

2. **Определить модели данных** (`models.py`):
   ```python
   from fsm.models import SagaInput, SagaData

   class MyInput(SagaInput):
       """Входные данные"""
       raw_data: str

   class MyData(SagaData):
       """Данные pipeline"""
       processed: str | None = None
       result: str | None = None
   ```

3. **Реализовать шаги** (`steps.py`):
   ```python
   from dataclasses import dataclass
   from fsm.core import RunContext

   @dataclass(slots=True)
   class MyStep:
       id = "my_step"
       desc = "Process input data"
       
       async def run(self, ctx: RunContext) -> None:
           ctx.data.processed = ctx.input.raw_data.upper()
   ```

4. **Создать точку входа** (`my_pipeline_main.py`):
   ```python
   import asyncio
   import logging
   from commons import setup_logging
   from fsm.core import SagaDefinition
   from fsm.saga_runner import SagaRunner
   from pipelines.my_pipeline.models import MyInput, MyData
   from pipelines.my_pipeline.steps import MyStep
   from store.inmem.inmemory_store import InMemoryStore

   async def main() -> None:
       setup_logging(log_file="logs/my_pipeline.log")
       logger = logging.getLogger(__name__)

       definition = SagaDefinition[MyInput, MyData](
           name="my_pipeline",
           steps=[MyStep()],
       )

       store = InMemoryStore()
       runner = SagaRunner(definition, store, MyData)

       logger.info("Starting pipeline execution")
       await runner.run(
           run_id="my-run-001",
           input=MyInput(raw_data="hello"),
           initial_state=MyData(),
       )
       logger.info("Pipeline execution completed")

   if __name__ == "__main__":
       asyncio.run(main())
   ```

## Логирование

Логирование настраивается через `commons.setup_logging()`:

```python
from commons import setup_logging

# INFO в консоль, DEBUG в файл
setup_logging(level=logging.INFO, log_file="logs/my_pipeline.log")
```

**Формат логов:** `module:line_number - logger_name - level - message`

Пример:
```
2026-05-14 01:53:48,693 - fsm.saga_runner:32 - INFO - Starting saga 'text_pipeline'
2026-05-14 01:53:48,693 - fsm.saga_runner:40 - INFO - Executing step 0: 'preprocessing'
```

**Уровни логирования:**
- **INFO** — начало саги, выполнение шагов, сохранение чекпоинтов
- **DEBUG** — входные данные, состояние до/после шага

## Архитектура выполнения

**Pipeline execution flow:**

1. `SagaRunner.run()` — orchestrator
   - Загружает сохраненный прогресс или создает новый контекст
   - Создает callbacks для pre/post шагов (сохранение состояния, логирование)
   - Вызывает `Saga.run()` с контекстом

2. `Saga.run()` — stateless executor
   - Выполняет шаги начиная с текущего cursor
   - Для каждого шага вызывает pre_step callback → выполняет шаг → вызывает post_step callback
   - НЕ отвечает за загрузку/сохранение

3. `StepAction.run()` — конкретный шаг
   - Изменяет данные на основе входных данных
   - Обновляет `ctx.data`
   - Может обновить `ctx.data.desc` для отслеживания прогресса

**Callbacks (custom logic):**
```python
async def pre_step(step_idx, ctx):
    # Логирование, валидация, etc.
    
async def post_step(step_idx, ctx):
    # Сохранение, уведомления, метрики, etc.
```

## Разделение ответственности

| Класс | Ответственность |
|-------|-----------------|
| `Saga` | Stateless executor - только выполнение шагов |
| `SagaRunner` | Orchestrator - load/save/resume pipeline |
| `StepAction` | Конкретная реализация шага |
| `SagaInput/SagaData` | Базовые классы для входных данных и контекста |

## Особенности

- ✓ **Protocol-based Design** — использование Python Protocols вместо абстрактных классов
- ✓ **Type-safe** — полная типизация через TypeVar и Generic
- ✓ **Stateless Executor** — Saga не зависит от хранилища
- ✓ **Callbacks** — расширяемость через pre/post step callbacks
- ✓ **Checkpointing** — автоматическое сохранение прогресса после каждого шага
- ✓ **Resume support** — возобновление саги из сохраненного состояния по run_id
- ✓ **State tracking** — каждое состояние имеет идентификатор (state_name)
- ✓ **Logging** — встроенное логирование с номерами строк
- ✓ **Async/await** — полная поддержка асинхронных операций
- ✓ **Modular** — pipeline-ы полностью отделены от фреймворка

## Требования

- Python 3.13+
- pydantic>=2.7
- aiosqlite>=0.20.0 (для SQL хранилища)

## Примеры

Смотри `src/main/main.py` — полный пример Ingest Pipeline с 11 шагами обработки markdown-документов.
