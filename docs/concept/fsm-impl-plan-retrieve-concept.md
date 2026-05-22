# Retrieval из KnowledgeBase — концепция v2

Документ описывает, как **сохранённая в SQLite информация** (documents/chunks/chunks_fts + tags_text + section_path + kind) используется на этапе **извлечения релевантных фрагментов** (retrieval) для основного агента/медицинской LLM.

---

## 1) Источники данных и контракт хранилищ

### 1.1 KnowledgeStore (SQLite) — индекс

KnowledgeStore хранит:
- `documents`: `id`, `source_path`, `category`, `source_sha256`, `indexed_at`
  - В текущей реализации `raw_text` допускается (MVP-решение, не противоречит архитектуре).
- `chunks`: атомарные фрагменты — `kind`, `section_path`, `heading`, `text`, `tags_text`, `chunk_no`
- `chunks_fts`: FTS5 content-таблица по полям `text`, `heading`, `section_path`, `tags_text`

**Использование в retrieval:**
- `chunks_fts` — основной канал поиска: BM25-ранжирование с field boosting.
- `kind` — постфильтрация и мягкий буст (таблицы для лаб-запросов, списки для рекомендаций).
- `section_path` — улучшает точность попадания: запрос "рекомендации" → раздел с нужным breadcrumb.
- `tags_text` — расширенный поиск через алиасы (птг → паратгормон pth).

### 1.2 FileStore — исходные документы

Полные документы (markdown) хранятся в `.data/filestore/` и доступны по ключу `documents.source_path`.

Retrieval по умолчанию не загружает документ целиком — возвращает `source_path`. В текущей реализации (MVP) опциональная загрузка (`include_full_docs=True`) выполняется через `KnowledgeStore.get_documents_raw_text()` — читает поле `raw_text` из таблицы `documents` в SQLite.

Путь эволюции: при отказе от хранения `raw_text` в SQLite, R7 OptionalEnrich должен быть переведён на чтение по `source_path` из FileStore.

---

## 2) Контракт Retrieval (Request / Response)

### 2.1 RetrieveRequest (вход)

**Обязательные поля:**
- `query: str` — пользовательский запрос (RU/EN).

**Опциональные ограничения/подсказки:**
- `category: str | None` — подсказка для soft/hard фильтрации по категории документа.
- `document_id: str | None` — поиск внутри одного документа (UI "искать в открытом").
- `section_path_prefix: str | None` — ограничение по разделу.

**Параметры выдачи:**
- `limit: int` — итоговое количество chunks (default 20).
- `limit_per_document: int` — diversity-ограничение (default 3). `0` — diversity отключено: возвращать top-`limit` чанков по rank без ограничения на количество чанков с одного документа. Внимание: текущая реализация `search_chunks()` содержит баг — при `limit_per_document=0` условие `count >= 0` всегда истинно, выдача пустая. Требует исправления перед использованием.
- `prelimit: int` — oversampling кандидатов из FTS до применения diversity (default 200).

**Опциональная догрузка:**
- `context_window: int = 0` — сколько соседних чанков добрать вокруг каждого выбранного (0/1/2).
- `include_full_docs: bool = False` — загружать ли полный текст документа.

### 2.2 RetrieveResponse (выход)

- `query_original: str`
- `query_normalized: str`
- `fts_match: str` — финальная MATCH-строка (для отладки)
- `chunks: list[ChunkSearchResult]` — плоский список итоговых чанков после diversity
- `documents: list[DocumentEvidence]` — группировка по документам:
  - `document_id`, `source_path`, `category`, `chunks: list[ChunkSearchResult]`
- `debug: RetrievalDebug` (опционально):
  - intent classification, alias expansions, applied filters/boosts, timing по этапам

### 2.3 Rank semantics

BM25 в SQLite FTS5 возвращает **отрицательные значения**: чем более отрицательное — тем лучше ранжирование. Сортировка `ORDER BY rank ASC` корректна.

### 2.4 QueryPlan (internal-only)

QueryPlan — внутренний объект, который создаётся retrieval pipeline из `RetrieveRequest` и передаётся вниз по шагам. Во внешний интерфейс не возвращается и не хранится в БД.

| Поле | Откуда | Назначение |
|---|---|---|
| `query_original` | RetrieveRequest.query | как ввёл пользователь |
| `query_normalized` | R1 NormalizeQuery | NFKC + lower + ё→е |
| `intent` | R2 ClassifyIntent | detected_type, confidence |
| `expanded_terms` | R3 ExpandAliases | термины + OR-алиасы |
| `fts_match` | R4 BuildFtsQuery | FTS5 MATCH-строка для SQLite |
| `category` | RetrieveRequest / intent | SQL-фильтр по категории (или None) |
| `document_id` | RetrieveRequest | SQL-фильтр по документу (или None) |
| `kinds` | RetrieveRequest | SQL-фильтр по видам чанков (или None) |
| `section_path_prefix` | RetrieveRequest | SQL-фильтр по пути (или None) |
| `limit` | RetrieveRequest | итоговый лимит чанков |
| `prelimit` | RetrieveRequest | oversampling из FTS |
| `limit_per_document` | RetrieveRequest | diversity-ограничение (0 = выключено) |

`fts_match` — единственная строка, которую QueryPlan передаёт в `KnowledgeStore`. Store не знает ни о нормализации, ни об alias-expansion — всё это выполнено в pipeline до вызова store.

---

## 3) Retrieval pipeline (детерминированный MVP)

### 3.0 Терминология запроса

Во избежание смешения понятий в коде и документации:

- `query_original` — строка как ввёл пользователь.
- `query_normalized` — после нормализации (NFKC, lower, ё→е); используется для intent detection и alias lookup.
- `fts_match` — FTS5 MATCH DSL строка: создаётся в R4 BuildFtsQuery, хранится в `QueryPlan.fts_match`, передаётся в `KnowledgeStore.search_chunks()`, возвращается в `RetrieveResponse.fts_match` для отладки. Содержит OR-термины, prefix-символы (`*`), экранированные спецсимволы.

Человеческий запрос никогда не передаётся в store напрямую.

### Шаг R0. Принять RetrieveRequest

Принять пользовательский запрос через `RetrieveRequest`. Примеры входных запросов:
- "Где у меня упоминался H. pylori?"
- "Найди все рекомендации кардиолога"
- "Что было по венам ног — где есть рефлюкс?"

### Шаг R1. Нормализация запроса

Применить ту же нормализацию, что и в ingest S1 (NFKC, lower, ё→е), чтобы не было рассинхрона с индексом.

Результат: `query_normalized`.

### Шаг R2. Передача явной категории из запроса

Если `request.category` задан — оборачивается в `IntentInfo(detected_type=category, confidence=1.0, matched_keywords=[])`.
Если не задан — `intent = None`: SearchChunks выполняет поиск по всем категориям.

Нет эвристики и ключевых слов: категория задаётся явно вызывающей стороной.
При `RETRIEVE_CATEGORY_MODE=soft` (default) category не используется как SQL-фильтр — только в debug.

Результат: `IntentInfo | None`.

### Шаг R3. Alias expansion через OR

Тот же alias-map, что при индексации, применяется к запросу — но термины объединяются через **OR** (не AND), чтобы не ухудшать recall:
- `птг` → `птг OR паратгормон OR pth`
- `фгдс` → `фгдс OR эгдс OR гастроскопия`
- `лпнп` → `лпнп OR ldl`

Результат: `expanded_terms: list[str]`.

### Шаг R4. Построение безопасной FTS MATCH-строки

Правила:
- Склеить OR-термы в MATCH-строку.
- Для ключевых русских терминов добавить prefix `*` при длине слова >= `RETRIEVE_PREFIX_MIN_LEN` (default 5): `протруз*`, `почечн*`, `ишеми*`.
- Не добавлять `*` к коротким словам (МРТ, ПТГ, ЭКГ и т.п.).
- Экранировать специальные символы FTS5 (`"`, `(`, `)`, `-` и т.д.).

Пример: запрос "мрт протрузия" → `мрт OR протруз*`.

Результат: `fts_match: str` — финальная MATCH-строка (в `QueryPlan`, `RetrievalData`, и `RetrieveResponse`).

### Шаг R5. FTS5 поиск по chunks (oversampling)

Запрос к `chunks_fts` с BM25 и field weights:

| Поле | Вес |
|---|---|
| `text` | 1.0 |
| `heading` | 2.5 |
| `section_path` | 2.0 |
| `tags_text` | 3.5 |

SQL-паттерн:
```sql
SELECT c.chunk_id, c.document_id, c.kind, c.section_path, c.heading, c.text,
       d.source_path, d.category, bm25(chunks_fts, 1.0, 2.5, 2.0, 3.5) AS rank
FROM chunks_fts
JOIN chunks c ON chunks_fts.rowid = c.chunk_pk
JOIN documents d ON c.document_id = d.id
WHERE chunks_fts MATCH ?
  [AND d.category = ?]              -- только при RETRIEVE_CATEGORY_MODE = 'hard'
  [AND c.document_id = ?]           -- при поиске внутри конкретного документа
  [AND c.kind IN (...)]             -- при фильтрации по виду чанка
  [AND c.section_path LIKE ? || '%'] -- при section_path_prefix
ORDER BY rank ASC
LIMIT <prelimit>
```

Опциональная category фильтрация определяется настройкой `RETRIEVE_CATEGORY_MODE`:
- `"soft"` (default): не фильтровать (нет WHERE-фильтра по category).
- `"hard"`: применять `WHERE category = ?` если category задан в запросе.

`KnowledgeStore.search_chunks()` принимает:
- `query` = `fts_match` (FTS5 MATCH DSL строка из QueryPlan)
- SQL-фильтры: `category`, `document_id`, `kinds`, `section_path_prefix`
- Параметры выдачи: `limit`, `prelimit`, `limit_per_document`, `bm25_weights`

Store не выполняет нормализацию, alias-expansion и prefix rules — это делает retrieval pipeline до вызова store.

Результат: `final_chunks` — список чанков после diversity, не более `limit`, rank ASC. Внутри store: SQL выбирает top-`prelimit`, затем применяется `limit_per_document`-фильтр.

### Шаг R6. Группировка по документам

`KnowledgeStore.search_chunks()` уже применила diversity внутри (SQL top-`prelimit` → Python-фильтр `limit_per_document` → топ-`limit`) и вернула готовый список `ChunkSearchResult`. Шаг R6 выполняет только группировку:

1. Взять `final_chunks` (заполнен шагом R5 SEARCH_CHUNKS) — список чанков после diversity.
2. Сгруппировать по `document_id` → `list[DocumentEvidence]`.

Это ключевая MVP-фича: без diversity один длинный документ вытесняет все остальные. `limit_per_document=0` отключает ограничение.

Примечание о soft mode: `RETRIEVE_CATEGORY_MODE=soft` означает "не добавлять WHERE-фильтр по category". Soft = нет фильтра. Hard = WHERE-фильтр по category.

Опциональный heuristic boost (мягкое переранжирование по kind/section_path) — пост-MVP, в MVP не реализован:
- запрос про "рекомендации" → поднять chunks с `kind=list` и `section_path LIKE '%рекомендации%'`
- запрос про "анализ/показатель" → поднять `kind=table`
- запрос про "диагноз" → поднять `kind=fact`

При переходе к архитектуре "diversity в retrieval pipeline" boost становится частью R6 вместе с diversity.

Результат: `final_chunks` + `documents`.

### Шаг R7. Опциональное обогащение

Управляется параметрами запроса:

- `context_window > 0`: для каждого выбранного чанка загрузить соседние чанки (`chunk_no ± context_window`) из таблицы `chunks` через `KnowledgeStore.get_neighbor_chunks()`. Соседи (без самого найденного чанка) сохраняются в `DocumentEvidence.context_chunks[chunk_id]`. `rank` соседних чанков равен `0.0` — позиционное извлечение, не BM25.
- `include_full_docs = True`: загрузить полный текст документа через `KnowledgeStore.get_documents_raw_text()` — читает `raw_text` из таблицы `documents` в SQLite. Результат записывается в `DocumentEvidence.full_text`.

По умолчанию оба флага `False` — retrieval возвращает только релевантные чанки.

### Шаг R8. Возврат RetrieveResponse

Возвращаемая структура (runtime, не сохраняется в БД):
- `query_original`, `query_normalized`, `fts_match`
- `chunks: list[ChunkSearchResult]` — отсортированы по score
- `documents: list[DocumentEvidence]` — каждый содержит `document_id`, `source_path`, `category`, вложенные chunks
- `debug: RetrievalDebug` — при `RETRIEVE_DEBUG=true`

---

## 4) Retrieval как FSM pipeline

Retrieval реализуется как FSM subagent, аналогичный ingest pipeline (переиспользует `SagaRunner`).

### 4.1 Состояния

| Состояние | Шаг |
|---|---|
| R0 | LOAD_REQUEST |
| R1 | NORMALIZE_QUERY |
| R2 | CLASSIFY_INTENT |
| R3 | EXPAND_ALIASES |
| R4 | BUILD_FTS_QUERY |
| R5 | SEARCH_CHUNKS (KnowledgeStore) |
| R6 | GROUP_BY_DOCUMENT (diversity выполнена внутри search_chunks) |
| R7 | OPTIONAL_ENRICH (context window / full docs) |
| R8 | DONE |

### 4.2 RetrievalData — state contract

| Поле | Заполняет | Тип |
|---|---|---|
| `query_original` | R0 | `str` |
| `query_normalized` | R1 | `str` |
| `intent` | R2 | `IntentInfo \| None` |
| `expanded_terms` | R3 | `list[str]` |
| `fts_match` | R4 | `str` |
| `final_chunks` | R5 SEARCH_CHUNKS | `list[ChunkSearchResult]` | результат `search_chunks()` с уже применённой diversity; может быть пустым |
| `documents` | R6 GROUP_BY_DOCUMENT | `list[DocumentEvidence]` | группировка `final_chunks` по `document_id` |
| `debug` | все | `dict` |

---

## 5) Поиск внутри выбранного документа

Если UI/агент уже выбрал документ и нужен поиск внутри него:
- `search_chunks(query, document_id=<id>)` — добавляется фильтр `WHERE document_id = ?`
- `limit_per_document` теряет смысл (документ один), `limit` можно увеличить

Опциональная фича, не меняющая общую архитектуру retrieval.

---

## 6) Параметры через env

### 6.1 Подключения

| Переменная | Default | Описание |
|---|---|---|
| `DB_PATH` | `ingest.db` | Путь к SQLite (KnowledgeStore) |

### 6.2 Retrieval настройки

| Переменная | Default | Описание |
|---|---|---|
| `RETRIEVE_LIMIT` | `20` | Итоговое кол-во chunks |
| `RETRIEVE_PRELIMIT` | `200` | Oversampling из FTS |
| `RETRIEVE_LIMIT_PER_DOCUMENT` | `3` | Diversity: чанков на документ |
| `RETRIEVE_BM25_WEIGHTS` | `"1.0,2.5,2.0,3.5"` | Веса полей: text/heading/section_path/tags_text |
| `RETRIEVE_ENABLE_PREFIXES` | `true` | Добавлять `*` к русским терминам |
| `RETRIEVE_PREFIX_MIN_LEN` | `5` | Минимальная длина слова для prefix |
| `RETRIEVE_CATEGORY_MODE` | `"soft"` | `soft` — нет фильтра; `hard` — WHERE-фильтр по category |

### 6.3 Debug и логирование

| Переменная | Default | Описание |
|---|---|---|
| `RETRIEVE_DEBUG` | `false` | Возвращать fts_match/expansions/timings |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

---

## 7) Типовые примеры работы на реальных документах

### 7.1 ФГДС — "H. pylori"

Запрос "h. pylori":
- FTS вернёт чанк из таблицы NBI-исследование и fact-чанк "Клиническое значение".
- fact обычно ранжируется выше (компактный текст, прямое совпадение).

### 7.2 УЗИ вен — "рефлюкс / БПВ"

Запрос "патологический рефлюкс бпв справа":
- Попадёт в table-чанки "Большая подкожная вена (БПВ)".
- `section_path` "Правая нижняя конечность > БПВ" даёт дополнительную точность.

### 7.3 Лабораторные панели — "ПТГ / ПСА / ЛПНП"

- Запрос "птг": благодаря `tags_text` (алиасы: паратгормон, pth) найдёт все варианты написания.
- Запрос "лпнп": alias expansion добавляет ldl; FTS найдёт обе формы.

### 7.4 Консультация кардиолога — "назначения"

- Запрос "что назначил кардиолог обследования":
  - Буст на `section_path LIKE '%рекомендации%обследован%'` + `kind=list` вернёт нужные списки.

### 7.5 МРТ поясницы — "протрузия L4-L5"

- Запрос "l4-5 протрузия" → prefix `протруз*` покрывает протрузия/протрузии.
- Числа в `chunk.text` (не в `tags_text`) обеспечивают FTS-поиск по "l4-5".

---

## 8) Ограничения MVP (что работает хуже)

**Семантические синонимы без алиасов:**
- "цефалгия" vs "головная боль" — если нет в alias-map и нет в тексте, FTS не найдёт.

**Опечатки:**
- FTS5 не fuzzy. Добавление fuzzy-слоя (rapidfuzz по словарю) — отдельное решение вне MVP.

**Чисто числовые запросы:**
- Числа запрещены в `tags_text` (намеренно), но остаются в `chunk.text`. FTS по числам нестабилен (зависит от токенизатора). Лучше искать по названию показателя ("птг") и дополнительно уточнять дату.

---

## 9) Что нужно для production-ready retrieval

Минимально достаточный набор:
- Одинаковая нормализация запроса и индекса (S1).
- Alias-map с OR-expansion (одни и те же словари при индексации и поиске).
- BM25 с field weights + мягкий буст по `kind` / `section_path`.
- Diversity (`limit_per_document` + `prelimit`) — обязательно.
- Управляемое optional enrich (флаги `context_window`, `include_full_docs`).
- `RETRIEVE_DEBUG=true` для диагностики в разработке.

**Архитектурный выбор MVP:** diversity реализована внутри `KnowledgeStore.search_chunks()` (а не в шаге R6 retrieval pipeline). Это упрощает FSM: R6 выполняет только группировку. Компромисс — store знает о параметрах выдачи.

**Путь эволюции:** когда понадобятся режимы буста (по kind/section_path) или fine-grained переранжирование, рекомендуется перейти к разделению: `search_candidates(prelimit)` в store возвращает топ-K по BM25 без diversity; R6 в retrieval FSM применяет diversity + бусты + группировку.
