# Phase M1 Spec — Agentic Consultation Loop

Документ описывает разработку интерактивной агентской консультации (Phase M1):
**управляемый agentic цикл**, в котором medical-LLM:
- может запрашивать дополнительные фрагменты истории пациента из KB через tools,
- может задавать уточняющие вопросы пациенту,
- ведёт диалог (чат-консультацию) без искусственного "закрытия" со стороны orchestrator.

---

## A) Цель Phase M1

Реализовать **agentic loop** в стиле Claude/OpenAI как отдельный компонент системы:

- модель может инициировать `tool_calls` для дозапроса данных из KnowledgeBase,
- модель может задавать уточняющие вопросы пациенту,
- модель выдаёт диагностический анализ и рекомендации **на каждом turn** (не существует отдельного "финального ответа" как состояния системы),
- orchestrator выполняет tool calls, поддерживает интерактивный ввод ответов пациента (CLI) и применяет лимиты (guardrails).

Ключевые свойства:

1. **Agentic tool loop** — модель может сделать несколько последовательных дозапросов к KB (через tool calls) в рамках одного пользовательского turn, прежде чем продолжить анализ.
2. **Tool allowlist = 1 tool** — разрешён только `kb.search_chunks`.
3. **Ответ модели — человекочитаемый текст** — orchestrator не парсит текст для управления циклом. Управление циклом выполняется по наличию `tool_calls`.
4. **Mini-interview (1–3 уточняющих вопроса)** — модель может задавать уточняющие вопросы пациенту; orchestrator в CLI собирает ответы и добавляет их в историю как user turns.
5. **Контроль контекста** — бюджеты на tool results, чтобы не переполнять context window.

---

## B) Архитектура

### B.1 Пакет `src/chat/`

Agentic chat — **не pipeline**. Это stateful диалоговая сессия с условным циклом. Реализуется как отдельный пакет вне `src/pipelines/`.

```
src/
├── chat/
│   ├── config.py              — ChatConfig (agentic loop + retrieval usage + recency)
│   ├── models.py              — ChatSession, tool input/output models
│   ├── baseline_retriever.py  — BaselineRetriever (query bundle + recency bundle)
│   ├── tool_executor.py       — KBToolExecutor
│   └── agentic_loop.py        — AgenticLoopRunner
├── common/
│   └── ...                    — PatientInfo, KBContextBundleBuilder перемещаются сюда (shared)
├── main/
│   └── chat.py                — CLI entrypoint (REPL)
└── pipelines/
    └── retrieval/             — переиспользуется как есть
```

`src/chat/` зависит от `src/llm/`, `src/pipelines/retrieval/`, `src/store/` и `src/common/`.
Не зависит от `src/fsm/` и `src/pipelines/consult/`.

`PatientInfo` — доменная модель пациента, не конфигурация pipeline. Она перемещается из
`src/pipelines/consult/config.py` в `src/common/` и становится shared: оба пакета
(`src/pipelines/consult/` и `src/chat/`) импортируют её оттуда.

`KBContextBundleBuilder` — утилита сборки KBContextBundle из query и recency чанков. Перемещается из
`src/pipelines/consult/bundle_builder.py` в `src/common/bundle_builder.py`. Это позволяет
`BaselineRetriever` переиспользовать логику без зависимости от `src/pipelines/consult/`.

### B.2 Место в системе

```
Пациент (stdin)
    │
    ▼
chat.py  (CLI REPL)
    │  создаёт и держит сессию
    ├──► BaselineRetriever      ◄─── query bundle + recency bundle
    │        ├──► RetrievalRunner    (src/pipelines/retrieval/)
    │        └──► KnowledgeStore     (src/store/)  — прямой доступ для recency
    │
    ▼
AgenticLoopRunner          ◄─── владелец: history, system_message
    │
    ├──► LLMClient          (src/llm/)
    │
    └──► KBToolExecutor
             │
             ▼
         RetrievalRunner    (src/pipelines/retrieval/)
             │
             ▼
         KnowledgeStore     (src/store/)
```

### B.3 Инициализация сессии

При старте `chat` CLI:
1. Читается `PatientInfo` из `config/patient.yaml`.
2. Читается шаблон `prompts/chat/system.md`, форматируется с `PatientInfo` → готовая строка `system_message`.
3. Создаётся `AgenticLoopRunner(llm_client, tool_executor, system_message, loop_config)`.
4. Создаётся `BaselineRetriever(retrieval_runner, store, chat_config)`.
5. Выполняется baseline retrieval по первой жалобе пациента через `BaselineRetriever.run(query)`:
   - **query bundle**: `RetrievalRunner` — BM25 поиск по тексту жалобы с date window
   - **recency bundle**: прямой запрос к `KnowledgeStore.list_documents_by_date()` — N последних документов вне зависимости от содержания запроса
   Recency bundle необходим, так как свежие документы (анализы, выписки) должны всегда попадать в контекст, даже если их текст не совпадает с BM25-запросом. Модель не может компенсировать это через tool calls, не зная что искать.
6. Результат baseline retrieval формирует первый user message → передаётся в `AgenticLoopRunner.run(user_message)`.

---

## C) Агентский цикл

### C.1 Принцип работы (Claude/OpenAI-style)

На каждом assistant turn orchestrator проверяет, запросила ли модель инструменты:

- **Если присутствуют `tool_calls`** → orchestrator выполняет tools, добавляет результаты как `tool` сообщения в историю и вызывает модель снова (следующий виток).
- **Если `tool_calls` отсутствуют** → orchestrator выводит `assistant.content` пользователю и ожидает следующий user message (диалог продолжается по желанию пользователя).

Важно:
- **Primary signal** для продолжения tool loop — наличие `tool_calls`; `stop_reason/finish_reason` является вторичным и может отличаться между провайдерами.
- `end_turn` / `stop` означает "модель завершила текущий assistant turn и не запрашивает tools в этом turn".
- Это не означает "конец диалога" и не означает, что консультация завершена.
- Завершение диалога определяется только внешним условием (пользователь завершил сессию / перестал отвечать / достигнуты лимиты сессии).
- **Промежуточный `assistant.content` не показывается пользователю.** Если в assistant turn присутствуют `tool_calls`, то `assistant.content` этого turn сохраняется в `history`, но не выводится в CLI. Пользователь видит только `assistant.content` того turn, в котором `tool_calls` отсутствуют (финальный turn цикла). Промежуточный текст (thinking out loud модели перед вызовом инструмента) записывается в лог для анализа.

### C.2 Взаимодействие Пациент — CLI — LLM — KB

1) **Пациент → CLI**
   Пациент вводит жалобу (или отвечает на ранее заданные вопросы).

2) **CLI → KB (baseline retrieval)**
   CLI запускает `BaselineRetriever.run(query)`:
   - query bundle: `RetrievalRunner` (BM25) по тексту жалобы с date window
   - recency bundle: прямой запрос `KnowledgeStore.list_documents_by_date()` — N последних документов

3) **KB → CLI**
   KB возвращает `KBContextBundle` (excerpts + provenance/refs).

4) **CLI → AgenticLoopRunner (первый вызов)**
   CLI формирует user message: Patient Request + Top Excerpts + Additional KB Evidence + Sources.
   Передаёт в `AgenticLoopRunner.run(user_message)`.

5) **AgenticLoopRunner → LLM (первый вызов)**
   Отправляет `system_message` + `history` + новый user message в LLM.

6) **LLM → AgenticLoopRunner (assistant turn)**
   LLM возвращает человекочитаемый текст консультации (`assistant.content`) и **может** дополнительно вернуть `tool_calls` (разрешён только `kb.search_chunks`).

7) **AgenticLoopRunner проверяет `tool_calls`**
   - Если `tool_calls` **есть** → переход к шагу 8
   - Если `tool_calls` **нет** → переход к шагу 11

8) **AgenticLoopRunner → KBToolExecutor (исполнение tools)**
   Для каждого `kb.search_chunks`:
   - валидировать вход (query, optional category/date window, limit)
   - применить budgets/лимиты
   - выполнить поиск через `RetrievalRunner`

9) **KB → AgenticLoopRunner (tool results)**
   Возвращаются результаты в компактном формате:
   - excerpts + refs (doc_id#chunk_no | date | category | section_path)
   - в пределах ограничений по количеству и размеру.

   Если поиск не вернул результатов, `KBToolExecutor` формирует tool result:
   `No matches found for query: "<query>"`.
   Этот результат **обязательно добавляется в историю** как `tool` message — пропустить его нельзя,
   так как каждый `tool_call` в assistant message должен иметь соответствующий `tool` result
   (требование протокола Anthropic/OpenAI API). Цикл продолжается: модель видит пустой результат
   и сама решает — уточнить запрос, попробовать другой, или перейти к финальному ответу.

10) **AgenticLoopRunner → LLM (следующий виток)**
    Добавляет `assistant` + `tool` messages в `history` и повторно вызывает LLM.
    Цикл продолжается, пока:
    - LLM снова запрашивает tools **и** лимит `max_kb_roundtrips` не исчерпан, или
    - LLM перестаёт запрашивать tools.

11) **AgenticLoopRunner → CLI (вывод текста)**
    Если `tool_calls` отсутствуют, возвращает `assistant.content` в CLI.
    CLI выводит текст пациенту.

12) **CLI ожидает следующий user message**
    Диалог не "закрывается" автоматически. Следующее сообщение пациента — его жалоба, уточнение или ответ на вопросы — запускает новую итерацию.

**Правило M1 (questions deferred):** вопросы пациенту из `assistant.content` показываются **только после завершения tool-loop** (т.е. когда `tool_calls` отсутствуют или достигнут `max_kb_roundtrips`).

13) **Лимит tool loop (guardrail)**
    Если достигнут `max_kb_roundtrips`, AgenticLoopRunner:
    - прекращает исполнять новые tool calls,
    - при повторном запросе tools возвращает tool error result ("tool budget exhausted") и делает финальный вызов LLM,
    - ожидает, что LLM явно обозначит неопределённости и ограничения из-за недостающих данных.

### C.3 Ограничения цикла

- Максимальное число дополнительных обращений к KB задаётся конфигом (`max_kb_roundtrips`).
- В одном assistant turn модель может запросить несколько инструментов (tool_calls — массив), но действует allowlist:
  - разрешён только `kb.search_chunks`,
  - ограничивается количество tool_calls за один turn (`max_tool_calls_per_turn`) и общий объём tool results (`max_tool_chunks`, `max_tool_total_chars`).
- Orchestrator **не блокирует tool-loop** ожиданием ответов пациента: вопросы пациенту выводятся только после завершения выполнения tools.

---

## D) Tool: kb.search_chunks

### D.1 Назначение

`kb.search_chunks` — единственный разрешённый инструмент в Phase M1.

Назначение:
- целенаправленно извлечь дополнительные фрагменты (chunks) из истории пациента в KnowledgeBase,
- когда medical-LLM считает текущего контекста недостаточно для уточнения гипотезы или рекомендаций.

`ToolDefinition.description` (передаётся в `tools` field API-запроса):
```
Search the patient's medical history in the knowledge base.
Call this when the current context is insufficient to refine your differential diagnosis.
Provide a focused query; optionally filter by category and date window.
```

Поведенческая инструкция "когда вызывать инструмент" размещается в `ToolDefinition.description`,
а не в system prompt — чтобы не дублировать информацию, которую модель уже получает из `tools` field.

### D.2 Параметры запроса (M1)

- **query** (обязательно) — строка для поиска (симптомы, термины, показатели).
  Пример: `"лейкоциты нейтрофилы воспаление"`

- **category** (опционально) — фильтр по типу документа в KB:
  `Анализы`, `Диагноз`, `Консультация`, `Исследование`, `Операция`, `Выписка`

- **from_date** (опционально) — нижняя граница по `document_date` (YYYY-MM-DD)

- **to_date** (опционально) — верхняя граница по `document_date` (YYYY-MM-DD)

- **limit** (обязательно) — сколько результатов вернуть (целое число)

Ограничения:
- LLM не может управлять diversity (`limit_per_document`); это фиксируется в конфигурации retrieval.
- LLM не может задавать фильтры по `chunk kind` или `section_path` в M1.

### D.3 Политика KBToolExecutor (enforcement)

Перед выполнением поиска `KBToolExecutor` обязан:
- проверить allowlist: отклонять все tool names кроме `kb.search_chunks` (вернуть tool error result, не бросать исключение)
- проверить allowlist категории (если category задана)
- валидировать формат дат: если `from_date` или `to_date` не соответствуют формату `YYYY-MM-DD` —
  вернуть tool error result: `"Invalid date format, expected YYYY-MM-DD"`
- валидировать порядок диапазона: если `from_date > to_date` —
  вернуть tool error result: `"Invalid date range: from_date must be <= to_date"`
  (автокоррекция перестановкой не применяется — модель должна получить явный сигнал об ошибке)
- ограничить `limit` сверху: `min(requested_limit, max_tool_chunks)` — молча, без ошибки
  (модель не знает внутреннего лимита оркестратора, поэтому cap применяется молча)
- если в одном assistant turn `tool_calls` > `max_tool_calls_per_turn` — выполнить первые N, остальные отклонить с tool error result

`max_tool_chunks` применяется на входе (до retrieval) — это cap на количество запрашиваемых результатов.
`max_tool_total_chars` применяется на выходе (при формировании tool result) — это cap на суммарный объём текста.
Оба бюджета работают в одном проходе при формировании tool result (см. D.4).

### D.4 Формат tool result

Tool result должен быть компактным, секционированным, удобным для цитирования по `<doc_id>#chunk_<k>`.

Структура:
- `## Top Matches`
- `## Additional Matches` (если есть место по бюджету)

Каждый excerpt начинается с ref-заголовка:

```
<doc_id>#chunk_<k> | <document_date> | <category> | <section_path>
```

Политика формирования tool result (единый проход по обоим бюджетам):
1. Включать чанки в порядке rank.
2. Остановиться, когда достигнут count = `max_tool_chunks` ИЛИ накопленный объём = `max_tool_total_chars`.
3. Если последний включённый чанк не вошёл целиком по символам — обрезать его с пометкой `[truncated]`.
4. Чанки, не вошедшие в бюджет, опускаются без упоминания.

Компрессия, склейка и перефразирование чанков запрещены: модель цитирует источники по идентификатору, текст должен точно соответствовать оригиналу.

Если результатов нет:
```
No matches found for query: "<query>"
```

---

## E) Ответ модели

### E.1 Содержание (человекочитаемый формат)

В каждом assistant turn модель выдаёт человекочитаемый (markdown) ответ, который может содержать:

- **Дифференциальная диагностика** — список гипотез с оценкой вероятности (possible / probable / likely) и краткими аргументами за/против каждой гипотезы.

- **Доказательства из KB** — при использовании данных из KnowledgeBase модель ссылается на excerpts по `<doc_id>#chunk_<k>`.

- **Что не хватает (неопределённости)** — какие данные отсутствуют и почему это ограничивает точность вывода.

- **Red flags и срочность** (опционально) — признаки, требующие срочной помощи, и рекомендация "когда":
  - немедленно (неотложка),
  - сегодня (дежурный врач),
  - планово в ближайшие дни,
  - наблюдение дома (если применимо и безопасно).

- **Вопросы пациенту** (опционально) — 1–3 наиболее приоритетных уточнения, которые реально могут изменить дифференциал.

- **Вопросы врачу** (опционально) — что уточнить на очном приёме и какие обследования уместны.

- **Рекомендации/следующие шаги** (опционально) — что можно сделать сейчас, что мониторить и при каких изменениях пересмотреть оценку.

### E.2 Принцип (качество и ответственность)

- Модель не уходит в общий совет "обратитесь к врачу" без конкретики. Если нужен врач — указывает почему, насколько срочно и какие признаки являются триггерами.
- Модель не придумывает факты о пациенте, которых нет в `Patient Info` и KB excerpts.
- Модель явно указывает ограничения/неопределённости.

---

## F) Системный промпт

### F.1 Расположение

`prompts/chat/system.md` — шаблон, форматируется с `PatientInfo` при инициализации сессии.

### F.2 Содержание

```text
You are a medical consultation assistant.

## Patient Info
Age: {age}
Sex: {sex}
Chronic conditions: {chronic_conditions}
Current medications: {current_medications}
Allergies: {allergies}

Use ONLY the above Patient Info and patient KB excerpts. Do NOT invent patient facts.
If information is missing, state it explicitly.

## Evidence references
Each excerpt is prefixed with:
<doc_id>#chunk_<k> | <document_date> | <category> | <section_path>

Fields:
- doc_id        — unique identifier of the source document
- chunk_k       — chunk number within that document (0-based)
- document_date — date the medical record was created (YYYY-MM-DD)
- category      — document type
- section_path  — heading hierarchy within the document

Rules:
- When you use evidence from the KB, cite it as '<doc_id>#chunk_<k>'.
- Treat KB excerpts as patient history.

## Response format
Provide a structured, patient-readable answer including:
- Differential diagnosis with uncertainty labels (possible/probable/likely) and brief evidence citations
- Red flags and when to seek urgent care (optional)
- Questions for the patient (1–3 most important, optional)
- Questions for the doctor / suggested exams to discuss (optional)
- Explicit uncertainties (what is missing)

Use clear headings and concise bullet points or a short table where helpful.
```

### F.3 User message (первый turn)

Шаблон `prompts/chat/user.md`:

```text
## Patient Request

{user_request}

## Top Relevant Excerpts (KB)

{top_chunks}

## Additional KB Evidence

{kb_excerpts}
```

`Patient Info` находится в system message и не повторяется в каждом user turn.

---

## G) CLI: chat

### G.1 Команда

```
chat                                   # объявлен в [project.scripts]
```

### G.2 Флаги

```
--config PATH    путь к config/chat.yaml (default: config/chat.yaml)
--env ENUM       prod | test (default: prod)
```

### G.3 Поведение

1. Инициализация: загрузить конфиг, создать `AgenticLoopRunner`.
2. Запросить первую жалобу пациента (`> `).
3. Выполнить baseline retrieval по жалобе.
4. Сформировать первый user message из результатов retrieval и передать в `AgenticLoopRunner.run(user_message)`.
5. Вывести ответ модели.
6. Перейти к шагу 2 (REPL: читать следующий ввод пациента).
7. Завершить сессию при EOF (`Ctrl+D`) или команде `quit`/`exit`.

Примечание: начиная со второго turn пациента baseline retrieval повторяется по новому вводу — чтобы контекст KB соответствовал текущей теме разговора.

---

## H) Конфигурация

Файл `config/chat.yaml`. Загружается `ChatConfig`. Дополнительно загружаются `config/llm.yaml` (LLMConfig) и `config/retrieve.yaml` (RetrievalConfig) — они общие для всех компонентов системы.

Usage-параметры запроса к retrieval (`query_top_k`, `query_limit_per_document`, `lookback_days`) хранятся в `config/retrieve.yaml` и читаются через `RetrievalConfig`. Отдельной секции `retrieval:` в `chat.yaml` нет — дублирования не требуется.

Секция `agentic_loop`:

| Параметр | Рекомендуемое значение | Описание |
|---|---|---|
| `max_kb_roundtrips` | 3 | Максимальное число roundtrips к KB за один user turn |
| `max_tool_calls_per_turn` | 1 | Максимальное число tool_calls в одном assistant turn |
| `max_tool_chunks` | 5 | Лимит чанков на один tool call (cap для `limit`) |
| `max_tool_total_chars` | 4000 | Лимит символов суммарно в одном tool result |

Секция `recency` (параметры recency bundle):

| Параметр | Рекомендуемое значение | Описание |
|---|---|---|
| `max_docs` | 3 | Максимальное число последних документов |
| `db_fetch_limit` | 5 | Fetch limit для DB-запроса (буфер поверх max_docs) |
| `chunks_per_doc` | 2 | Число первых чанков из каждого документа |

Секции `bundle` и `excerpts` (формирование и форматирование baseline context):

| Параметр | Рекомендуемое значение | Описание |
|---|---|---|
| `bundle.max_total_chunks` | 20 | Hard limit на общее число чанков в baseline bundle |
| `bundle.max_total_chars` | 12000 | Hard limit на суммарный объём символов в baseline bundle |
| `excerpts.top_chunks_count` | 5 | Число top-ranked чанков в секции Top Excerpts |
| `excerpts.top_chunks_lines` | 30 | Лимит строк на чанк в секции Top Excerpts |
| `excerpts.max_lines_default` | 20 | Лимит строк по умолчанию для Additional KB Evidence |

---

## I) Критерии готовности (Acceptance)

- `chat` CLI запускается, принимает ввод пациента и выводит ответ модели в цикле.

- Первый user turn включает результаты baseline retrieval (top excerpts + additional KB evidence).

- AgenticLoopRunner корректно обрабатывает `tool_calls`:
  - если `tool_calls` присутствуют → выполняет tools через `KBToolExecutor`, добавляет tool results как `tool` messages и вызывает LLM снова;
  - если `tool_calls` отсутствуют → возвращает `assistant.content` в CLI.

- Tool allowlist соблюдается:
  - разрешён только `kb.search_chunks`;
  - любые другие tool requests отклоняются (возвращается tool error result, цикл не падает).

- Лимиты цикла соблюдаются:
  - цикл корректно останавливает исполнение tools при достижении `max_kb_roundtrips`;
  - при превышении лимита tool requests возвращается tool error result ("tool budget exhausted"), делается финальный вызов LLM, диалог продолжается.

- Формат tool results корректен и компактен:
  - результаты содержат excerpt refs вида `doc_id#chunk_k | date | category | section_path`;
  - соблюдаются budgets (`max_tool_chunks`, `max_tool_total_chars`).

- Ответ модели (каждый assistant turn) является человекочитаемым и содержит:
  - дифференциальная диагностика с оценкой неопределённости,
  - явные неопределённости (что отсутствует).

- Если KB ничего не нашёл по запросу:
  - `KBToolExecutor` возвращает "No matches…" как tool result,
  - цикл не падает, модель продолжает на основе имеющегося контекста.

- Для `env=test` существуют интеграционные тесты, покрывающие сценарии:
  - без tool_calls,
  - с 1+ tool_calls,
  - с достижением `max_kb_roundtrips`,
  - с empty tool result,
  - с попыткой запроса запрещённого tool.

---

## J) Состав работ Phase M1

### Этап 0 — Рефактор shared компонентов

Предварительный рефактор, не зависит от остальных этапов. Выполняется первым.

**PatientInfo → src/common/:**
- Переместить класс `PatientInfo` из `src/pipelines/consult/config.py` в `src/common/patient.py`
- Обновить импорт в `src/pipelines/consult/config.py`: `from src.common.patient import PatientInfo`

**KBContextBundleBuilder → src/common/:**
- Переместить `KBContextBundleBuilder` из `src/pipelines/consult/bundle_builder.py` в `src/common/bundle_builder.py`
- Обобщить конструктор `KBContextBundleBuilder`: принимать `BundleConfig` и `ExcerptsConfig` напрямую, а не `ConsultConfig` целиком, чтобы не создавать зависимость от `src/pipelines/consult/`
- Обновить импорт в `src/pipelines/consult/build_bundle.py`: `from src.common.bundle_builder import KBContextBundleBuilder`

**RetrievalConfig — добавить usage-параметры:**
- Добавить в `RetrievalConfig` (`src/pipelines/retrieval/config.py`) три поля: `query_top_k: int`, `query_limit_per_document: int`, `lookback_days: int`
- Добавить соответствующие значения в `config/retrieve.yaml`
- Удалить `RetrievalUsageConfig` из `src/pipelines/consult/config.py` и секцию `retrieval:` из `config/consult.yaml`
- Обновить `src/pipelines/consult/steps/retrieve.py`: читать `query_top_k`, `query_limit_per_document`, `lookback_days` из `RetrievalConfig` вместо `ConsultConfig.retrieval`

Поведение `src/pipelines/consult/` не меняется.

### Этап 1 — LLM layer: поддержка tool_calls

Файлы: `src/llm/`

- `models.py`: добавить `ToolDefinition`, `ToolCall`, `ToolResult`; расширить `ChatRequest` полем `tools: list[ToolDefinition]`; расширить `ChatResponse` полем `tool_calls: list[ToolCall]`
- `openai_client.py`: передавать `tools` в запрос; читать `tool_calls` из ответа наряду с `content`
- `mock.py`: поддержать возврат `tool_calls` в mock-ответах (нужно для тестов этапа 4)

### Этап 2 — KBToolExecutor

Новый файл `src/chat/tool_executor.py`. Зависит от этапа 1.

- Allowlist: отклонять все tool names кроме `kb.search_chunks`
- Валидация входа: category из allowlist, корректность дат, порядок диапазона
- Cap `limit`: `min(requested_limit, max_tool_chunks)`
- Маппинг параметров tool call → `RetrieveRequest`, вызов `RetrievalRunner`
- Бюджет `max_tool_total_chars`: усечение результатов
- Формат tool result: секционированный текст с ref-заголовками
- Пустой результат: `No matches found for query: "<query>"`

### Этап 3 — AgenticLoopRunner и ChatConfig

Файлы: `src/chat/agentic_loop.py`, `src/chat/config.py`, `src/chat/models.py`. Зависит от этапов 1 и 2.

`AgenticLoopRunner`:
- Конструктор принимает: `llm_client`, `tool_executor`, `system_message: str`, `loop_config: ChatConfig`
- Инициализирует `self._history: list[Message] = []`
- Метод `run(user_message: str) -> str` — вызывается на каждый turn пациента:
  - Добавляет user message в `self._history`
  - Запускает цикл: вызов LLM → проверка `tool_calls` → исполнение через `KBToolExecutor` → добавление `assistant` + `tool` messages в историю → повтор
  - Останавливается когда `tool_calls` отсутствуют или достигнут `max_kb_roundtrips`
  - При достижении лимита: добавляет tool error result в историю, делает финальный вызов LLM
  - Возвращает финальный `assistant.content`

### Этап 4 — BaselineRetriever, CLI `chat` и промпты

Файлы: `src/chat/baseline_retriever.py`, `src/main/chat.py`, `prompts/chat/system.md`, `prompts/chat/user.md`, `config/chat.yaml`. Зависит от этапа 3.

`BaselineRetriever`:
- Конструктор принимает: `retrieval_runner: RetrievalRunner`, `store: KnowledgeStore`, `retrieval_config: RetrievalConfig`, `chat_config: ChatConfig`
- Метод `run(query: str) -> KBContextBundle`:
  - query bundle: вызов `RetrievalRunner` с `query_top_k`, `query_limit_per_document`, `lookback_days` из `retrieval_config`
  - recency bundle: `store.list_documents_by_date(limit=chat_config.recency.db_fetch_limit)` → первые `max_docs` документов → `store.get_document_chunks(doc_id, chunks_per_doc)`
  - объединяет результаты, применяет `bundle` и `excerpts` лимиты из `chat_config`, возвращает `KBContextBundle`

`src/main/chat.py`:
- REPL-цикл: инициализация → stdin loop → `BaselineRetriever.run` → формирование user message → `AgenticLoopRunner.run` → вывод
- Загружает: `config/chat.yaml` (ChatConfig), `config/llm.yaml` (LLMConfig), `config/retrieve.yaml` (RetrievalConfig), `config/patient.yaml` (PatientInfo)

Остальное:
- `prompts/chat/system.md`: системный промпт (текст из раздела F.2)
- `prompts/chat/user.md`: шаблон user message (текст из раздела F.3)
- `config/chat.yaml`: конфигурация (значения из раздела H)
- Зарегистрировать `chat` в `[project.scripts]` в `pyproject.toml`

### Этап 5 — Тестирование

Файл: `tests/chat/test_agentic_loop.py`. Зависит от этапов 1–3.

| Сценарий | Поведение mock LLM | Проверяемый результат |
|---|---|---|
| Без tool_calls | Сразу text-ответ | 0 roundtrips, текст возвращён |
| 1 roundtrip | tool_call → text-ответ | 1 roundtrip, tool executor вызван, результат в истории |
| max_kb_roundtrips исчерпан | Всегда tool_calls | Цикл остановлен на лимите, error result отправлен LLM, финальный ответ получен |
| Empty tool result | tool_call → text | KB вернул 0 результатов, "No matches…" в истории, цикл не упал |
| Запрещённый tool | Запрашивает `web_search` | Error tool result возвращён, цикл не упал, история корректна |
