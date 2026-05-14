# FSM - Minimal Abstract Finite State Machine

Минимальная абстрактная реализация FSM (Finite State Machine) с поддержкой саг, чекпоинтирования и логирования. Фреймворк позволяет создавать различные pipeline-ы обработки данных с автоматическим сохранением прогресса и возможностью возобновления из чекпоинтов.

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
    text_pipeline/             # Пример: pipeline обработки текста (2 шага)
      models.py               # TextInput, TextData (наследуют SagaInput/SagaData)
      steps.py                # Preprocessing, Processing (наследуют StepAction)
    number_pipeline/           # Пример: pipeline обработки чисел (3 шага)
      models.py               # NumberInput, NumberData
      steps.py                # ParseNumbers, CalculateSum, FormatResult
      
  store/                       # Реализации хранилища прогресса
    inmem/
      inmemory_store.py       # In-memory хранилище (для тестирования)
    sql/
      sql_store.py            # SQL хранилище (stub)
      
  main/
    text_pipeline_main.py      # Запуск text pipeline
    number_pipeline_main.py    # Запуск number pipeline
```

## Ключевые компоненты

### FSM Framework (`fsm/`)

**Основные классы и протоколы:**

- **`RunContext[TIn, TState]`** — контекст выполнения саги
  - `run_id` — идентификатор запуска
  - `input` — входные данные
  - `state` — текущее состояние
  - `cursor` — текущий шаг

- **`SagaStep[TIn, TData]`** — протокол (interface) для шага саги
  - `id: str` — идентификатор шага (определяется подклассом)
  - `async def run(ctx: RunContext) -> None` — выполнить шаг
  - Определяет контракт, который должны реализовать все шаги

- **`StepAction[TIn, TData]`** — базовый класс для конкретных шагов
  - Имплементирует `SagaStep` протокол
  - Служит parent-класс для всех шагов в pipeline-ах
  - Конкретные подклассы определяют `id = "step_name"` с конкретным значением
  - **Дизайн:** `id` определяется только в подклассах — каждый шаг имеет свой уникальный id

- **`SagaInput`** — базовый класс для входных данных
  - Все pipeline-специфичные Input классы наследуют от неё

- **`SagaData`** — базовый класс для данных контекста
  - Содержит только бизнес-данные (промежуточные результаты)
  - Все pipeline-специфичные Data классы наследуют от неё

- **`SagaDefinition[TIn, TState]`** — определение саги
  - `name: str` — имя саги
  - `steps: list[SagaStep]` — список шагов

- **`SagaProgressStore`** — протокол для хранилища прогресса
  - `async def load(run_id: str) -> dict` — загрузить сохраненный прогресс
  - `async def save(data: dict) -> None` — сохранить прогресс

- **`Saga[TIn, TState]`** — stateless executor саги
  - Выполняет шаги саги
  - Вызывает callbacks перед/после шагов
  - НЕ отвечает за загрузку/сохранение

- **`SagaRunner[TIn, TState]`** — orchestrator саги
  - Загружает/создает pipeline из хранилища
  - Вызывает Saga для выполнения
  - Обрабатывает сохранение состояния
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
   from fsm.core import RunContext, StepAction

   @dataclass(slots=True)
   class MyStep(StepAction[MyInput, MyData]):
       id = "my_step"
       
       async def run(self, ctx: RunContext[MyInput, MyData]) -> None:
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
   - Изменяет состояние на основе входных данных
   - Обновляет `ctx.state`

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

Смотри:
- `src/main/text_pipeline_main.py` — pipeline с 2 шагами
- `src/main/number_pipeline_main.py` — pipeline с 3 шагами
