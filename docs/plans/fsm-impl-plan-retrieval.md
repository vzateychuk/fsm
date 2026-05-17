# Retrieval Engine — Implementation Plan

## Исходное состояние

Реализован ingest pipeline S0–S9 (FTS синхронизируется атомарно внутри S9 PersistChunks), SQLite KnowledgeStore с FTS5, FileStore для исходников. Индексированы медицинские документы (lab, diagnostic, consultation). Retrieval-слой отсутствует.

Концепт-документ: `docs/concept/kd-search-retrieve-data-from-strore.md`

---

## Порядок фаз

```
Phase R0 — контракты и каркас FSM
Phase R1 — query processing (normalize / intent / aliases / FTS builder)
Phase R2 — KB search + diversity (интеграция с KnowledgeStore)
Phase R3 — optional enrich (FileStore, context window)
Phase R4 — тесты и CLI
```

Фазы R0–R2 составляют MVP: retrieval работает детерминированно без LLM. Фаза R3 опциональна. Фаза R4 финализирует regression-набор.

---

## Phase R0: Контракты и каркас FSM

**Цель:** зафиксировать все контракты до реализации — структуры данных, state contract, параметры. Артефакты этой фазы используются всеми последующими.

---

### R0.1 RetrievalData — state contract

Аналог `IngestData` для retrieval pipeline.

| Поле | Заполняет | Тип | Инвариант |
|---|---|---|---|
| `query_original` | R0 LOAD_REQUEST | `str` | не пустой |
| `query_normalized` | R1 NORMALIZE_QUERY | `str` | не `None` |
| `intent` | R2 CLASSIFY_INTENT | `IntentInfo \| None` | `None` допустим |
| `expanded_terms` | R3 EXPAND_ALIASES | `list[str]` | `len >= 1` (минимум исходный запрос) |
| `fts_match` | R4 BUILD_FTS_QUERY | `str` | не пустой, безопасная MATCH-строка; = `QueryPlan.fts_match`; в `RetrieveResponse` поле называется `fts_match` |
| `final_chunks` | R5 SEARCH_CHUNKS | `list[ChunkSearchResult]` | результат `search_chunks()` с уже применённой diversity; может быть пустым |
| `documents` | R6 GROUP_BY_DOCUMENT | `list[DocumentEvidence]` | группировка `final_chunks` по `document_id` |
| `debug` | все | `dict` | опционально; заполняется при `RETRIEVE_DEBUG=true` |

*Результат:* `RetrievalData` зафиксирован как dataclass/TypedDict в `src/pipelines/retrieval/models.py`. None-guards в шагах пишутся строго по этой таблице.

**Проверка:** `mypy src/pipelines/retrieval/` — 0 ошибок на контрактах.

---

### R0.2 RetrieveRequest / RetrieveResponse

Зафиксировать входной/выходной контракт в `src/pipelines/retrieval/models.py`.

`RetrieveRequest` — внешний контракт: принимает subagent, CLI, или API-клиент. Внутри pipeline он преобразуется в `QueryPlan` (см. R0.6), который несёт подготовленный `fts_match` и SQL-фильтры.

**RetrieveRequest:**
- `query: str` — обязательное
- `doc_type_hint: str | None = None`
- `document_id: str | None = None`
- `section_path_prefix: str | None = None`
- `limit: int = 20`
- `limit_per_document: int = 3`
- `prelimit: int = 200`
- `context_window: int = 0`
- `include_full_docs: bool = False`

**ChunkSearchResult:**
- `chunk_id: str`
- `document_id: str`
- `doc_type: str`
- `kind: str`
- `section_path: str`
- `heading: str | None`
- `text: str`
- `rank: float`

**DocumentEvidence:**
- `document_id: str`
- `source_path: str`
- `doc_type: str`
- `chunks: list[ChunkSearchResult]`

**RetrieveResponse:**
- `query_original: str`
- `query_normalized: str`
- `fts_match: str`
- `chunks: list[ChunkSearchResult]`
- `documents: list[DocumentEvidence]`
- `debug: dict | None`

*Результат:* все типы объявлены; `mypy` доволен; нет `dict[str, Any]` без имён.

---

### R0.3 IntentInfo — результат intent detection

```python
@dataclass
class IntentInfo:
    detected_type: str | None      # "lab" | "diagnostic" | "consultation" | None
    confidence: float              # 0.0–1.0
    matched_keywords: list[str]
```

*Результат:* тип объявлен в `models.py`; используется в `RetrievalData.intent`.

---

### R0.4 RetrievalConfig — параметры из env

Создать `src/pipelines/retrieval/config.py`:

```python
@dataclass
class RetrievalConfig:
    limit: int                 # RETRIEVE_LIMIT, default 20
    prelimit: int              # RETRIEVE_PRELIMIT, default 200
    limit_per_document: int    # RETRIEVE_LIMIT_PER_DOCUMENT, default 3
    bm25_weights: tuple[float, float, float, float]  # RETRIEVE_BM25_WEIGHTS
    enable_prefixes: bool      # RETRIEVE_ENABLE_PREFIXES, default True
    prefix_min_len: int        # RETRIEVE_PREFIX_MIN_LEN, default 5
    doc_type_mode: str         # RETRIEVE_DOC_TYPE_MODE: "soft" | "hard"
    debug: bool                # RETRIEVE_DEBUG, default False
```

Фабричная функция `RetrievalConfig.from_env()` читает переменные окружения.

*Результат:* конфиг создаётся один раз при старте; все шаги получают его через `RunContext` или DI; нет `os.getenv()` внутри шагов.

**Проверка:** `RETRIEVE_LIMIT=5 python -c "from src.pipelines.retrieval.config import RetrievalConfig; print(RetrievalConfig.from_env().limit)"` выводит `5`.

---

### R0.5 FSM каркас retrieval

Создать `src/pipelines/retrieval/` по образцу `src/pipelines/ingest/`:

```
src/pipelines/retrieval/
  __init__.py
  models.py          # RetrievalData, RetrieveRequest, RetrieveResponse, IntentInfo
  config.py          # RetrievalConfig
  steps.py           # классы шагов R0–R7
  alias_map.py       # импорт из ingest или общий модуль
  fts_query.py       # prepare_fts_query(), sanitize_query()
  runner.py          # RetrievalRunner: настройка SagaDefinition и запуск
```

Шаги R0–R8 реализуются как заглушки (`pass`), возвращающие данные без изменений. Pipeline запускается без ошибок на пустом запросе.

*Результат:* `python -c "from src.pipelines.retrieval.runner import RetrievalRunner"` — импорт без ошибок.

---

### R0.6 QueryPlan — internal contract

Создать dataclass `QueryPlan` в `src/pipelines/retrieval/models.py`. Это внутренний объект pipeline — не возвращается в ответе и не хранится в БД.

```python
@dataclass
class QueryPlan:
    query_original: str
    query_normalized: str = ""
    intent: IntentInfo | None = None
    expanded_terms: list[str] = field(default_factory=list)
    fts_match: str = ""                   # FTS5 MATCH expression; единственная строка → store
    doc_type: str | None = None           # SQL-фильтр (из intent или RetrieveRequest.doc_type_hint)
    document_id: str | None = None        # SQL-фильтр
    kinds: set[str] | None = None         # SQL-фильтр
    section_path_prefix: str | None = None  # SQL-фильтр
    limit: int = 20
    prelimit: int = 200
    limit_per_document: int = 3           # 0 = diversity выключена
```

Шаги R1–R4 заполняют `QueryPlan` поступательно. В R5 `QueryPlan.fts_match` передаётся в `KnowledgeStore.search_chunks()` вместе с SQL-фильтрами.

Инварианты перед вызовом `search_chunks()`:
- `fts_match` не пуст
- `limit > 0`, `prelimit >= limit`

*Результат:* `QueryPlan` объявлен в `models.py`; шаги R1–R4 обновляют его; в R5 поля `fts_match` + фильтры передаются в store без дополнительной обработки. `mypy` доволен.

**Проверка:** `QueryPlan(query_original="птг")` создаётся без ошибок; поля с defaults инициализированы корректно.

---

## Phase R1: Query processing

**Цель:** запрос нормализован, intent определён (эвристика), alias expansion выполнена через OR, построена безопасная FTS MATCH-строка.

---

### R1.1 Normalize query (реиспользование ingest S1)

В шаге `NormalizeQuery` применить ту же функцию нормализации, что в ingest S1:
- NFKC
- lowercase
- ё → е
- strip leading/trailing whitespace

*Результат:* `query_normalized` заполнен; единый нормализатор в `src/common/normalizer.py` используется и ingest, и retrieval.

**Проверка:** `"Протрузия МРТ\r\n"` → `"протрузия мрт"`.

---

### R1.2 Intent detection (эвристика)

В шаге `ClassifyIntent` реализовать словарь ключевых слов → `doc_type`:

```python
INTENT_KEYWORDS = {
    "lab": ["анализ", "показатель", "норма", "результат", "кровь", "моча", "биохими"],
    "diagnostic": ["узи", "мрт", "кт", "рентген", "фгдс", "эгдс", "гастроскопи"],
    "consultation": ["рекомендаци", "назначени", "диагноз", "консультаци", "лечени"],
}
```

Confidence = доля совпавших слов от общего числа слов в запросе (простая эвристика). Если `doc_type_hint` в запросе задан явно — использовать его без классификации.

*Результат:* `ctx.data.intent` заполнен; `detected_type = None` при неопределённости.

`detected_type` используется только как подсказка. При `RETRIEVE_DOC_TYPE_MODE=soft` (default) он не добавляется ни в SQL-фильтр, ни в boost — только в debug. Жёсткий фильтр (`hard`) не рекомендуется для keyword-intent: медицинские документы типа `consultation` часто содержат упоминания диагностических процедур (УЗИ, МРТ).

**Проверка:** запрос "мрт поясницы" → `detected_type = "diagnostic"`, `matched_keywords = ["мрт"]`.

---

### R1.3 Alias expansion (OR)

В шаге `ExpandAliases` применить alias-map (импортировать из ingest или общий модуль) к токенам `query_normalized`. Каждый найденный токен заменяется OR-группой:

```
"птг" → ["птг", "паратгормон", "pth"]
"фгдс" → ["фгдс", "эгдс", "гастроскопи"]
"лпнп" → ["лпнп", "ldl"]
```

Токены, отсутствующие в alias-map, сохраняются как есть.

*Результат:* `ctx.data.expanded_terms` содержит все термины (оригинальные + алиасы).

**Проверка:** `"птг"` → `["птг", "паратгормон", "pth"]`. Запрос без совпадений в alias-map → `expanded_terms = [исходный токен]`.

---

### R1.4 FTS query builder (`fts_query.py`)

Создать `src/pipelines/retrieval/fts_query.py` с функцией `build_fts_match(terms, config)`:

**Логика:**
1. Для каждого термина из `expanded_terms`:
   - Экранировать специальные символы FTS5: `"`, `(`, `)`, `-`, `*`.
   - Если `config.enable_prefixes` и `len(term) >= config.prefix_min_len` и термин кириллический — добавить `*`.
2. Объединить термины через `OR`.
3. Если `document_id` задан в запросе — фильтр добавляется на уровне SQL, не в MATCH-строку.

Примеры:
- `["мрт", "протрузия"]` → `"мрт OR протруз*"`
- `["птг", "паратгормон", "pth"]` → `"птг OR паратгормон OR pth"`
- `["h. pylori"]` → `'"h. pylori"'` (фраза в кавычках)

Builder записывает результат в `QueryPlan.fts_match` (не возвращает отдельную строку). При `config.debug=True` дополнительно сохраняет в `ctx.data.debug`: какие алиасы были добавлены, к каким токенам применено prefix-правило и почему.

*Результат:* `ctx.data.fts_match` содержит безопасную MATCH-строку; та же строка попадает в `RetrieveResponse.fts_match`. Человеческий запрос никогда не передаётся в `KnowledgeStore` напрямую.

**Проверка:** unit-тесты в `tests/retrieval/test_fts_query.py` — минимум 8 кейсов: пустой запрос, один термин без алиасов, термин с алиасами, кириллица с prefix, латиница без prefix, фраза со спецсимволами, короткое слово (без prefix), термин длиной ровно `prefix_min_len`.

---

## Phase R2: KB search + diversity

**Цель:** интеграция с KnowledgeStore, diversity post-processing, группировка по документам.

---

### R2.0 Предварительные исправления SqliteKnowledgeStore

До реализации R5–R6 необходимо устранить два несоответствия в `sqlite_knowledge_store.py`, иначе regression-тесты будут нестабильны.

**BM25 field weights (блокер для ранжирования):**
Текущий код: `bm25(chunks_fts) AS rank` — без весов.
Требуемое: `bm25(chunks_fts, 1.0, 2.5, 2.0, 3.5) AS rank` (text / heading / section_path / tags_text).
Без правки ранжирование отличается от задокументированного; regression-тесты Phase R4 не сойдутся.

**Семантика `limit_per_document=0` (блокер для diversity-тестов):**
Текущий баг: `if count >= limit_per_document` при значении `0` даёт `0 >= 0 == True` — вся выдача пустая.
Требуемое: при `limit_per_document <= 0` не применять diversity-фильтр, вернуть top-`limit` по rank без ограничения на количество чанков из одного документа.

*Результат:* оба исправления задокументированы и внесены до написания R5 и тестов Phase R4.

---

### R2.1 KnowledgeStore.search_chunks() — контракт и расположение diversity

**Архитектурное решение:** diversity реализована внутри `search_chunks()` (в store), а не в отдельном шаге R6. Это позволяет избежать загрузки лишних данных в память и упрощает retrieval pipeline. Шаг R6 выполняет только группировку по `document_id`.

Фактическая сигнатура `search_chunks()`:

```python
async def search_chunks(
    self,
    query: str,                         # pre-built FTS MATCH string
    *,
    doc_type: DocType | None = None,
    document_id: str | None = None,
    kinds: set[ChunkKind] | None = None,
    section_path_prefix: str | None = None,
    limit: int = 20,                    # итоговый лимит после diversity
    limit_per_document: int = 3,        # diversity: чанков на документ (0 = без ограничения)
    prelimit: int = 200,                # oversampling из FTS до diversity
) -> list[ChunkSearchResult]:
```

Параметр `query` в `search_chunks()` — это `fts_match` из `QueryPlan` (FTS5 MATCH DSL строка), не сырой пользовательский запрос. Store не выполняет нормализацию, alias-expansion и prefix rules.

Retrieval subagent отвечает за построение `query` через `build_fts_match()`. `search_chunks()` самостоятельно:
1. Выполняет SQL с `ORDER BY rank LIMIT prelimit`
2. Применяет diversity post-processing в Python (`limit_per_document`, `limit`; `0` = без ограничения)
3. Возвращает готовый список `ChunkSearchResult`

SQL внутри метода:
```sql
SELECT c.chunk_id, c.document_id, c.kind, c.section_path, c.heading, c.text,
       d.source_path, d.doc_type, bm25(chunks_fts, 1.0, 2.5, 2.0, 3.5) AS rank
FROM chunks_fts
JOIN chunks c ON chunks_fts.rowid = c.chunk_pk
JOIN documents d ON c.document_id = d.id
WHERE chunks_fts MATCH ?
  [AND d.doc_type = ?]           -- при hard mode
  [AND c.document_id = ?]        -- при поиске внутри документа
ORDER BY rank ASC
LIMIT <prelimit>
```

*Результат:* метод уже реализован в `SqliteKnowledgeStore`; retrieval pipeline вызывает его без дополнительного diversity-слоя.

**Проверка:** `await store.search_chunks("протруз*", prelimit=50, limit=10, limit_per_document=3)` возвращает не более 3 чанков на документ, суммарно не более 10.

---

### R2.2 SearchChunks — шаг R5

Шаг вызывает `KnowledgeStore.search_chunks(ctx.data.fts_match, ...)` и записывает результат в `ctx.data.final_chunks`.

При `doc_type_mode = "hard"` и заполненном `ctx.data.intent.detected_type` — передаёт `doc_type` в запрос. При `"soft"` — не передаёт.

*Результат:* `ctx.data.final_chunks` содержит результат `search_chunks()` с уже применённой diversity — не более `limit` чанков, rank ASC.

**Проверка:** запрос "протрузия" на реальной БД возвращает финальные чанки (post-diversity); `rank` у всех отрицательный.

---

### R2.3 GroupByDocument — шаг R6

`search_chunks()` уже применяет diversity (limit_per_document + prelimit) и возвращает готовый `list[ChunkSearchResult]`. Шаг R6 выполняет только группировку по `document_id`:

```python
def group_by_document(chunks: list[ChunkSearchResult]) -> list[DocumentEvidence]:
    groups: dict[str, DocumentEvidence] = {}
    for chunk in chunks:
        if chunk.document_id not in groups:
            groups[chunk.document_id] = DocumentEvidence(
                document_id=chunk.document_id,
                source_path=chunk.source_path,
                doc_type=chunk.doc_type,
                chunks=[],
            )
        groups[chunk.document_id].chunks.append(chunk)
    return list(groups.values())
```

*Результат:* `ctx.data.documents` = группировка `final_chunks` по `document_id`; `final_chunks` уже заполнен шагом R5 SEARCH_CHUNKS.

**Проверка:** при 3 чанках из doc_A и 2 чанках из doc_B, `documents` содержит 2 элемента с `len(chunks) == 3` и `len(chunks) == 2` соответственно.

---

### R2.4 Debug output

При `RETRIEVE_DEBUG=true` (или `config.debug=True`) записывать в `ctx.data.debug`:
- `intent`: `detected_type`, `confidence`, `matched_keywords`
- `alias_expansions`: словарь `{term: [aliases]}`
- `fts_match`: финальная MATCH-строка
- `candidates_count`: количество кандидатов до diversity
- `final_count`: количество после diversity
- `timings`: `{step_name: ms}` для каждого шага R1–R6

*Результат:* `RetrieveResponse.debug` содержит словарь с перечисленными ключами.

---

### R2.5 Debug API — raw BM25 кандидаты

Для диагностики качества индекса и query builder'а необходим способ получить сырые BM25-результаты до применения diversity. Без этого невозможно понять: плохой запрос или плохая diversity-настройка.

Два варианта (выбрать один при реализации):

**Вариант A — флаг `raw_candidates=True` в `search_chunks()`:**
При установке флага store возвращает top-`prelimit` по BM25 без diversity-фильтра.

**Вариант B — отдельный метод `search_candidates()` в KnowledgeStore:**
```python
async def search_candidates(
    self,
    fts_match: str,
    *,
    doc_type: str | None = None,
    document_id: str | None = None,
    prelimit: int = 200,
) -> list[ChunkSearchResult]:
```
Возвращает top-`prelimit` по BM25 без diversity. Явно разделяет контракты: `search_candidates` = сырой поиск, `search_chunks` = поиск + diversity.

Для MVP предпочтителен Вариант B как более явный. Вариант A минимизирует изменения в store.

*Результат:* зафиксировано в плане; реализуется при первой необходимости диагностики поиска или отладки alias-map.

**Проверка:** вызов debug API на реальной БД возвращает неотфильтрованный top-50 по BM25; ранги всех результатов отрицательные.

---

## Phase R3: Optional enrich (опционально, после MVP)

**Цель:** поддержка `context_window` и `include_full_docs` в шаге R7.

---

### R3.1 Context window

Добавить метод в `KnowledgeStore`:

```python
async def get_chunks_range(
    self,
    document_id: str,
    from_no: int,
    to_no: int,
) -> list[ChunkSearchResult]:
```

В шаге `OptionalEnrich`: для каждого chunk из `final_chunks` загрузить соседние чанки в диапазоне `[chunk_no - context_window, chunk_no + context_window]`. Дедуплицировать по `chunk_id`.

*Результат:* при `context_window=1` к каждому выбранному чанку добавляются до 2 соседних (если существуют).

---

### R3.2 Include full docs

Добавить метод в `FileStore` (или использовать существующий `get(source_path)`):

```python
async def get_document(self, source_path: str) -> str | None:
```

В шаге `OptionalEnrich` при `include_full_docs=True`: для каждого `DocumentEvidence` загрузить markdown по `source_path`; добавить в `DocumentEvidence.full_text`.

*Результат:* при `include_full_docs=True` каждый `DocumentEvidence` содержит `full_text: str | None`.

**Предусловие:** `documents.source_path` должен быть ключом FileStore. Это гарантируется правильной реализацией ingest S8 PersistSourceFile + S9 PersistDocument: `PersistDocument` обязан записывать `source_path = ctx.data.filestore_path` (ключ FileStore), а не `ctx.input.source_path`. Если ingest пишет исходный путь вместо FileStore-ключа, загрузка полного документа будет нестабильной.

---

## Phase R4: Тесты и CLI

**Цель:** regression-набор на 3 документах; CLI-команда для ручной диагностики.

---

### R4.1 Fixture-набор запросов

Создать `tests/retrieval/fixtures/` с regression-кейсами.

**Kidney colic doc (`consultation`):**
- `"почка"` → top document: kidney_colic; chunks содержат "почк*"
- `"почечная колика"` → top document: kidney_colic; `kind=fact` или `kind=section`
- `"диклофенак"` → chunk с упоминанием препарата
- `"узи почек"` → table-chunk с параметрами УЗИ

**Lumbar MRI doc (`diagnostic`):**
- `"мрт"` → top document: lumbar_mri
- `"протрузия"` → chunk с `section_path` уровня L4-L5 или аналогичного
- `"остеохондроз"` → chunk с упоминанием диагноза
- `"нервные корешки"` → chunk с анатомическими терминами

**ECG doc (`diagnostic`):**
- `"экг"` → top document: ecg
- `"чсс"` → chunk с данными о частоте сердечных сокращений
- `"ритм сердца"` → chunk из раздела с ритмом
- `"ишемия"` → chunk с диагностическим заключением

**Ожидание для всех кейсов:** `len(final_chunks) >= 1`; top document по кол-ву chunks соответствует тематике запроса.

---

### R4.2 Тесты retrieval pipeline

`tests/retrieval/test_retrieval.py`:

**test_normalize_query:**
- `"Протрузия МРТ\r\n"` → `"протрузия мрт"`
- `"ПТГ"` → `"птг"`
- `"Ёлка"` → `"елка"` (ё → е)

**test_alias_expansion:**
- `"птг"` → expanded_terms содержит `"птг"` и `"паратгормон"` и `"pth"`
- `"экг"` → содержит `"экг"` и `"электрокардиограф*"` (или алиас из alias_map)
- термин без алиаса → expanded_terms = `[term]`

**test_fts_query_builder:**
- 8 кейсов из R1.4 + проверка что результат — валидная строка (нет непарных кавычек)

**test_diversity:**
- 10 кандидатов из одного документа, `limit_per_document=3` → `final_chunks` содержит ровно 3
- 5 кандидатов из двух документов (по 5), `limit_per_document=3`, `limit=4` → 3 из первого + 1 из второго (или 2+2 в зависимости от rank)

**test_regression_kidney_colic (integration):**
- Запрос `"почечная колика"` → `len(final_chunks) >= 1`; `documents[0].source_path` содержит `"kidney"` (или `"colic"` — зависит от имени файла в fixtures)

**test_regression_lumbar_mri (integration):**
- Запрос `"протрузия"` → `len(final_chunks) >= 1`

**test_regression_ecg (integration):**
- Запрос `"экг"` → `len(final_chunks) >= 1`

Интеграционные тесты требуют тестовой БД с проиндексированными тремя документами. Тестовый фикстур: создать in-memory SQLite (`:memory:`), запустить ingest на трёх документах-образцах, затем выполнить retrieval.

*Результат:* `pytest tests/retrieval/ -v` — все тесты зелёные.

**Проверка Phase R4:** `pytest tests/retrieval/ -v --tb=short` — 0 failures, 0 errors.

---

### R4.3 CLI-команда

Создать `src/main/retrieve.py` — точка входа для ручной диагностики:

```
python src/main/retrieve.py "протрузия дисков"
```

Вывод:
```
Query: "протрузия дисков"
Normalized: "протрузия дисков"
FTS MATCH: "протруз*"

Documents (3):
  [1] lumbar_mri_2023-01-11.md (diagnostic) — 3 chunks
      [rank=-12.4] section_path: МРТ поясничного отдела > Уровень L4-5
                   "Протрузия диска до 4 мм..."
      ...
  [2] kidney_colic_...md (consultation) — 1 chunk
      ...
```

Опции:
- `--limit N` — кол-во chunks
- `--debug` — включить debug output (fts_match, expansions, timings)
- `--doc-type lab|diagnostic|consultation` — явный hint

*Результат:* CLI работает; при пустом результате выводит "No results found".

---

## Итоговая последовательность шагов retrieval pipeline

| # | Шаг | Что производит |
|---|---|---|
| R0 | LoadRequest | `query_original` из `RetrieveRequest` |
| R1 | NormalizeQuery | `query_normalized` (NFKC + lower + ё→е) |
| R2 | ClassifyIntent | `intent` (detected_type, confidence, matched_keywords) |
| R3 | ExpandAliases | `expanded_terms` (оригинальные + OR-алиасы) |
| R4 | BuildFtsQuery | `fts_match` (безопасная MATCH-строка с prefix) |
| R5 | SearchChunks | `final_chunks` = результат `search_chunks()` после diversity, rank ASC |
| R6 | GroupByDocument | `documents` — группировка `final_chunks` по `document_id` |
| R7 | OptionalEnrich | `full_text` или context chunks (при включённых флагах) |
| R8 | Done | `RetrieveResponse` |

---

## Файловая структура

```
src/
  pipelines/
    retrieval/
      __init__.py
      models.py          # RetrievalData, RetrieveRequest, RetrieveResponse,
                         # ChunkSearchResult, DocumentEvidence, IntentInfo
      config.py          # RetrievalConfig, from_env()
      steps.py           # R0-LoadRequest ... R7-OptionalEnrich
      fts_query.py       # build_fts_match(), sanitize_fts_term()
      runner.py          # RetrievalRunner (SagaDefinition + run())
  main/
    retrieve.py          # CLI точка входа

tests/
  retrieval/
    fixtures/            # образцы документов для integration tests
    test_fts_query.py    # unit-тесты builder (8+ кейсов)
    test_retrieval.py    # unit + integration тесты
    conftest.py          # фикстур in-memory БД с проиндексированными docs
```
