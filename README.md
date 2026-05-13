# FSM - Minimal Abstract Finite State Machine

Минимальная абстрактная реализация FSM (Finite State Machine) с поддержкой саг, чекпоинтирования и логирования. Фреймворк позволяет создавать различные pipeline-ы обработки данных с автоматическим сохранением прогресса и возможностью возобновления из чекпоинтов.

## Архитектура

```
src/
  commons/                      # Общие утилиты (не относящиеся к FSM)
    logging_config.py          # Настройка логирования
    
  fsm/                         # FSM фреймворк (переиспользуемое ядро)
    core.py                    # RunContext, SagaStep, SagaDefinition, SagaProgressStore
    saga.py                    # Saga executor с логированием и чекпоинтированием
    saga_factory.py            # SagaFactory для создания саг
    
  pipelines/                   # Конкретные реализации pipeline-ов
    text_pipeline/             # Пример: pipeline обработки текста (2 шага)
      models.py               # SagaInput, SagaState
      steps.py                # Preprocessing, Processing
    number_pipeline/           # Пример: pipeline обработки чисел (3 шага)
      models.py               # NumberInput, NumberState
      steps.py                # ParseNumbers, CalculateSum, FormatResult
      
  store/                       # Реализации хранилища прогресса
    inmem/
      inmemory_store.py       # In-memory хранилище (для тестирования)
    sql/
      sql_store.py            # SQL хранилище (stub)
      
  main/
    main.py                    # Документация доступных pipeline-ов
    text_pipeline_main.py      # Запуск text pipeline
    number_pipeline_main.py    # Запуск number pipeline
```

## Ключевые компоненты

### FSM Framework (`fsm/`)

**Основные классы и протоколы:**

- **`RunContext[TIn, TState]`** — контекст выполнения саги, содержит:
  - `run_id` — идентификатор запуска
  - `input` — входные данные
  - `state` — текущее состояние
  - `cursor` — текущий шаг

- **`SagaStep[TIn, TState]`** — протокол для шага саги
  - `id: str` — идентификатор шага
  - `async def run(ctx: RunContext) -> None` — выполнить шаг

- **`SagaDefinition[TIn, TState]`** — определение саги
  - `name: str` — имя саги
  - `steps: list[SagaStep]` — список шагов

- **`SagaProgressStore`** — протокол для хранилища прогресса
  - `async def load(run_id: str) -> dict` — загрузить сохраненный прогресс
  - `async def save(data: dict) -> None` — сохранить прогресс

- **`Saga[TIn, TState]`** — исполнитель саги
  - Поддержка возобновления из чекпоинтов
  - Логирование выполнения на уровне INFO
  - DEBUG логи состояния между шагами

### Common Utilities (`commons/`)

- **`setup_logging(level, log_file)`** — настройка логирования
  - Логирование в консоль (stdout)
  - Опциональное логирование в файл
  - Автоматическое создание директории логов

### Pipeline-specific Code (`pipelines/`)

Каждый pipeline — это отдельный пакет с:
- **`models.py`** — входные данные и состояние (SagaInput, SagaState)
- **`steps.py`** — конкретные реализации шагов (наследуют SagaStep)
- **`__init__.py`** — экспорт публичного API

**Текущие примеры:**
- **text_pipeline** — обработка текста: токенизация → подсчет токенов
- **number_pipeline** — обработка чисел: парсинг → сумма → форматирование

## Использование

### Запуск существующих pipeline-ов

```bash
# Text pipeline (2 шага)
python src/main/text_pipeline_main.py

# Number pipeline (3 шага)
python src/main/number_pipeline_main.py
```

### Создание нового pipeline

1. **Создать директорию pipeline-а:**
   ```bash
   mkdir src/pipelines/my_pipeline
   ```

2. **Определить модели данных** (`models.py`):
   ```python
   from pydantic import BaseModel

   class MyInput(BaseModel):
       """Входные данные"""
       raw_data: str

   class MyState(BaseModel):
       """Состояние pipeline"""
       processed: str | None = None
       result: str | None = None
   ```

3. **Реализовать шаги** (`steps.py`):
   ```python
   from dataclasses import dataclass
   from fsm.core import RunContext, SagaStep

   @dataclass(slots=True)
   class MyStep(SagaStep[MyInput, MyState]):
       id: str = "my_step"
       
       async def run(self, ctx: RunContext[MyInput, MyState]) -> None:
           ctx.state.processed = ctx.input.raw_data.upper()
   ```

4. **Создать точку входа** (`my_pipeline_main.py`):
   ```python
   import asyncio
   from commons import setup_logging
   from fsm.core import SagaDefinition
   from fsm.saga import Saga
   from pipelines.my_pipeline.models import MyInput, MyState
   from pipelines.my_pipeline.steps import MyStep
   from store.inmem.inmemory_store import InMemoryStore

   async def main() -> None:
       setup_logging(log_file="logs/my_pipeline.log")
       
       definition = SagaDefinition[MyInput, MyState](
           name="my_pipeline",
           steps=[MyStep()],
       )
       
       store = InMemoryStore()
       saga = Saga(definition, store, MyState)
       
       ctx = await saga.run(
           run_id="my-run-001",
           input=MyInput(raw_data="hello"),
           initial_state=MyState(),
       )
       
       print(f"Result: {ctx.state.processed}")

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

**Уровни логирования:**
- **INFO** — начало саги, выполнение шагов, сохранение чекпоинтов
- **DEBUG** — входные данные, состояние до/после шага

## Хранилище прогресса

Реализуется через протокол `SagaProgressStore`.

**Доступные реализации:**
- **`InMemoryStore`** — в памяти (для тестирования)
- **`SQLStore`** — SQL БД (stub, требует реализации)

**Использование:**
```python
from store.inmem.inmemory_store import InMemoryStore

store = InMemoryStore()
saga = Saga(definition, store, StateType)
```

## Разделение ответственности

| Пакет | Ответственность |
|-------|-----------------|
| `fsm/` | Абстрактное ядро FSM (переиспользуемое) |
| `commons/` | Общие утилиты (логирование, конфиги) |
| `pipelines/` | Конкретные реализации (данные + шаги) |
| `store/` | Хранилище прогресса |
| `main/` | Точки входа для каждого pipeline |

## Особенности

- ✓ **Protocol-based Design** — использование Python Protocols вместо абстрактных классов
- ✓ **Type-safe** — полная типизация через TypeVar и Generic
- ✓ **Checkpointing** — автоматическое сохранение прогресса после каждого шага
- ✓ **Resume support** — возобновление саги из сохраненного состояния
- ✓ **Logging** — встроенное логирование выполнения
- ✓ **Async/await** — поддержка асинхронных операций
- ✓ **Modular** — pipeline-ы полностью отделены от фреймворка

## Требования

- Python 3.13+
- pydantic>=2.7
- aiosqlite>=0.20.0 (для SQL хранилища)

## Примеры

Смотри:
- `src/main/text_pipeline_main.py` — pipeline с 2 шагами
- `src/main/number_pipeline_main.py` — pipeline с 3 шагами
