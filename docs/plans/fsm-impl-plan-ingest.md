# Ingest Pipeline — Implementation Plan

## Исходное состояние

Реализован базовый FSM framework (`RunContext`, `Saga`, `SagaRunner`, `Store` Protocol) и pipeline S0–S10 (11 шагов) с заглушками: нормализация неполная, markdown-парсинг упрощённый, persistence симулируется. Концепт-документ требует полной реализации S0–S10.

Концепт-документ: `docs/concept/fsm-pipeline-docs-chunks-tags-store.md`

---

## Порядок фаз и логика приоритетов

Фазы упорядочены по принципу "как можно раньше получить работающий extraction":

```
Phase 0  — спецификация и подготовка (артефакты, не код)
Phase 1  — стабилизация + минимальная нормализация (BOM/CRLF)
Phase 2  — markdown-it-py парсинг
Phase 3  — BuildSectionPath
Phase 4  — kind-based chunkification
Phase 5  — tagging
─────────── EXTRACTION VALIDATION CHECKPOINT ───────────
Phase 6  — полная нормализация текста (NFKC/lower/ё→е)
Phase 7  — детекция схемы + доменные ошибки
Phase 8  — SQLite persistence
```

Фазы 6 и 7 **не блокируют** начало проверки алгоритма извлечения. До Phase 6 pipeline работает на тексте с минимальной нормализацией (Phase 1); `target_schema` до Phase 7 хардкодится или передаётся через `IngestInput`. Это сознательный компромисс: валидировать extraction раньше, нормализацию и schema detection достраивать параллельно или после.

---

## Phase 0: Спецификация и подготовка

**Цель:** зафиксировать контракты до начала реализации — что и где хранится, что можно перезапускать, на каких данных проверять. Артефакты этой фазы используются всеми последующими.

---

### 0.1 State contract freeze — инварианты IngestData

Для каждого поля `IngestData` зафиксировать: какой шаг заполняет, тип после шага, инвариант. Оформить как таблицу-артефакт (markdown или TypedDict-комментарий в `models.py`).

| Поле | Заполняет | Тип после шага | Инвариант |
|---|---|---|---|
| `raw_content` | S0 LoadSource | `str` | не `None`; содержит исходный текст файла |
| `file_hash` | S1 PreprocessText | `str` | не `None`; ровно 64 hex-символа (SHA256) |
| `target_schema` | S2 DetectTargetSchema | `str` | не `None`; значение ∈ `{lab, diagnostic, consultation}` |
| `metadata_block` | S3 SplitControlBlocks | `str \| None` | `None` допустим; если заполнен — YAML-подобный текст |
| `md_body` | S3 SplitControlBlocks | `str` | не `None`; не содержит строку `target schema id:` |
| `tokens` | S4 ParseToTokens | `list[MdToken]` | может быть пустым; `E_MD_PARSE_FAIL` при сбое парсера |
| `block_events` | S5 BuildSectionPath | `list[BlockEvent]` | содержит события для всех блоков, участвующих в chunkification; каждый event имеет `section_path: str` (допускается пустая) и `heading: str \| None` |
| `chunks` | S6 ChunkifyBlocks | `list[Chunk]` | `len >= 1`; иначе `E_EMPTY_CHUNKS` |
| `tagged_chunks` | S7 Tagging | `list[Chunk]` | `len == len(chunks)`; каждый элемент имеет непустой `tags_text` |
| `canonical_source_path` | S8 PersistSourceFile | `str` | не `None`; ключ в FileStore, используется как `documents.source_path` |
| `document_id` | S9 PersistDocument | `str` | не `None`; детерминирован от `file_hash` |
| `chunk_ids` | S10 PersistChunks | `list[str]` | `len == len(tagged_chunks)`; FTS синхронизирован атомарно внутри S10 |

*Результат:* таблица зафиксирована в плане и продублирована как docstring или комментарий в `models.py`. None-guards в Phase 1 пишутся строго по этой таблице — не по интуиции.

**Проверка:** для каждого поля из таблицы существует конкретный шаг, который устанавливает его; нет полей без ответственного шага и нет шагов, читающих поле раньше, чем оно заполняется.

---

### 0.2 Idempotency rules — правила перезапуска шагов

Зафиксировать для каждого шага: безопасен ли повторный запуск и почему. Это определяет поведение при resume из чекпоинта.

**Чистые шаги (pure) — безопасны для повторного исполнения:**

| Шаг | Основание |
|---|---|
| S0 LoadSource | читает файл, пишет только в `ctx.data` |
| S1 PreprocessText | детерминированное преобразование строки |
| S2 DetectTargetSchema | чтение + regex, нет side effects |
| S3 SplitControlBlocks | строковые операции |
| S4 ParseToTokens | парсер без состояния |
| S5 BuildSectionPath | вычисление из токенов |
| S6 ChunkifyBlocks | трансформация токенов в чанки |
| S7 Tagging | детерминированный алгоритм + alias map |

**Шаги с side effects — должны быть идемпотентны по ключу:**

| Шаг | Ключ идемпотентности | Механизм |
|---|---|---|
| S8 PersistSourceFile | `source_sha256` | write-if-not-exists (или overwrite) |
| S9 PersistDocument | `document_id` (= `file_hash[:32]`) | `INSERT OR REPLACE` |
| S10 PersistChunks | `document_id` | `DELETE WHERE document_id + INSERT + SYNC_FTS` (в одной операции) |

**Классификация ошибок:**

- *Перезапускаемые* (transient): `E_READ_FAIL` (файл временно недоступен), `E_DB_FAIL` (сбой соединения) — resume из того же cursor имеет смысл.
- *Фатальные* (требуют исправления источника): `E_NO_SCHEMA_ID`, `E_SCHEMA_INVALID`, `E_MD_PARSE_FAIL`, `E_EMPTY_CHUNKS` — перезапуск без изменения входного файла бессмысленен.

*Результат:* таблица зафиксирована в плане. При реализации S8–S10 разработчик знает заранее, какой SQL-паттерн применять.

**Проверка:** прервать pipeline на шаге S9 (убить процесс после INSERT нескольких чанков), перезапустить с тем же `run_id` — результат в БД эквивалентен непрерывному запуску; дублей нет.

---

### 0.3 Golden dataset — эталонный набор для проверки алгоритмов

Создать минимальный набор тестовых документов в `tests/fixtures/ingest/` до начала реализации Phase 2. Каждый документ сопровождается эталонным JSON с ожидаемыми результатами.

**Наблюдения по реальным документам из `.data/ingest`:**

Реальные документы (ФГДС, lab-панели, консультации) показывают единообразную структуру:
- Первая строка: `Target Schema ID: <value>` (не `%%schema`)
- Почти нет plain-параграфов — контент это таблицы, факт-абзацы (`**Label**: value`), списки с фактами (`- **Label**: value`)
- metadata-блок **в конце** документа после `---`, не в начале как YAML frontmatter
- Глубина заголовков до H4 (consultation: H1→H2→H3→H4); section_path = 3+ уровней
- Факт-паттерн `**Label**:` встречается внутри LIST-элементов — не только как начало параграфа

**Набор fixtures (скорректирован под реальные docs):**

| Файл | Что покрывает | target_schema |
|---|---|---|
| `diagnostic_tables.md` | H1/H2/H3 + таблицы 3 col (Параметр/Результат/Статус) + факт-абзацы **Label**: + metadata в конце | `diagnostic` |
| `lab_panel.md` | H2-секции по категориям + таблицы 5 col + списки с **Label**: + динамика | `lab` |
| `consultation_deep.md` | H1/H2/H3/H4 (section_path 3+ уровней) + списки + metadata в конце | `consultation` |
| `minimal_valid.md` | `Target Schema ID:` + один абзац + пустой metadata-блок в конце | `consultation` |
| `no_schema_id.md` | документ без строки `Target Schema ID:` | — (ожидается `E_NO_SCHEMA_ID`) |

**Важные edge cases для fixture-документов:**
- `- **ФИО**: Иванов` — факт внутри LIST-элемента; kind = `list` (не `fact`). Зафиксировать как ожидаемое поведение.
- Таблица под H3 с 2-уровневым section_path — проверяет корректность breadcrumb для вложенных секций.
- metadata-блок в конце: `---\n\nmetadata:\n  key: value` — S3 должен его вырезать из `md_body`.

**Структура эталонного YAML** (`expected_diagnostic_tables.yaml`):
```yaml
# diagnostic_tables.md: H1 + H2 + H3 с таблицами и факт-абзацами
# каждый H2 стартует новый чанк; таблицы под H3 идут отдельными чанками
target_schema: diagnostic
chunks_count: 4
chunk_kinds:
  - table   # параметры исследования
  - table   # результаты > пищевод
  - fact    # клиническое значение > первый факт-абзац
  - section # рекомендации
section_paths_present:
  - параметры исследования
  - результаты исследования > пищевод
  - клиническое значение
tags_text_contains:
  - diagnostic
  - клиническое
```

*Результат:* fixture-набор создан и зафиксирован в репозитории до реализации Phase 2. До Phase 9 проверка ручная — запустить pipeline, сравнить `ctx.data` глазами с YAML. В Phase 9 сравнение автоматизируется pytest-тестами.

**Проверка:** запустить pipeline на каждом fixture-документе вручную, сравнить `ctx.data` с эталонным YAML по полям `target_schema`, `chunks_count`, `chunk_kinds`, `section_paths_present`.

---

### 0.4 Entry point — спецификация батч-запуска

Зафиксировать контракт точки входа до реализации: как именно файлы попадают в pipeline.

**Поведение:**

- `INGEST_DIR` (ENV, default: `./.data/ingest`) — директория с входными `.md`-файлами.
- При запуске `main.py` сканирует директорию, находит все `*.md`-файлы, запускает pipeline для каждого по очереди.
- `run_id` для каждого файла = детерминированный хэш от пути файла (или имя файла без расширения) — чтобы resume работал корректно при повторном запуске.
- При ошибке на одном файле (`IngestError`, `IOError`) — логировать и продолжать со следующим файлом; не прерывать батч.
- По завершении вывести итоговый счётчик: обработано / пропущено / с ошибкой.

**Что не входит в S0–S10:** сканирование директории и цикл по файлам живут в `main.py`, не в шагах pipeline. S0 (`LoadSource`) по-прежнему получает один `source_path`.

*Результат:* спека зафиксирована; `main.py` в Phase 1 реализует батч-запуск по этому контракту (заменяет текущий hardcoded sample).

**Проверка:** `INGEST_DIR=tests/fixtures/ingest python src/main/main.py` — pipeline отрабатывает на всех fixture-файлах; файлы с ожидаемыми ошибками (`no_schema_id.md`) логируются как skipped, батч не прерывается.
``

---

## Phase 1: Стабилизация текущего кода

**Цель:** pipeline не падает с `AttributeError` на реальных данных; mypy/ruff проходят без ошибок. Phase 1 также включает минимальную нормализацию (BOM/CRLF) — достаточную для корректной работы markdown-it-py в Phase 2.

### Шаги

**1.1 None-guards во всех шагах**
Добавить явные проверки перед каждым обращением к полю, которое заполняется предыдущим шагом (`raw_content`, `md_body`, `file_hash`). При `None` бросать `RuntimeError` с указанием какой шаг должен был заполнить поле.
*Результат:* попытка запустить pipeline с пустым `IngestData()` начиная с шага 2 даёт понятное сообщение об ошибке, а не `AttributeError`.

**1.2 Минимальная нормализация (BOM, CRLF, bare `\r`)**
Дополнить `PreprocessText`: убрать BOM, нормализовать `\r\n` и одиночный `\r` до `\n`. Это минимум, необходимый для стабильного парсинга markdown-it-py на любых входных файлах.
*Результат:* файлы с любым вариантом переносов строк (LF/CRLF/CR) дают одинаковую структуру `md_body`.

**1.3 `ClassVar` аннотации для `id` и `desc`**
Во всех step-классах объявить `id: ClassVar[str]` и `desc: ClassVar[str | None]`.
*Результат:* `mypy src/` выходит с кодом 0 без ошибок по Protocol compliance.

**1.4 Run invariants — постшаговые проверки**
По контрактной таблице из Phase 0.1 добавить вспомогательную функцию `assert_invariants(data: IngestData, after_step: str)`, которая проверяет, что поля, обязанные быть заполнены к этому шагу, не равны `None`. Вызывается только при тестовом/debug-запуске (флаг или отдельная обёртка — не в production-флоу).
*Результат:* при пропущенном поле функция бросает `AssertionError` с именем поля и шага, который обязан его заполнить.

**1.5 Smoke subset из golden dataset**
Из golden dataset (Phase 0.3) выделить smoke subset: 3 файла — `minimal_valid.md`, `diagnostic_tables.md`, `lab_panel.md`. Создать их в рамках Phase 0.3 (единственный источник правды); Phase 1 только запускает на них pipeline как smoke check.
Coarse-ожидания: `raw_content` не пустой, `tokens` не пустой, `chunks_count >= 1`.
*Результат:* pipeline на smoke subset проходит до конца без ошибок; coarse-ожидания выполнены.

### Проверка Phase 1

`python src/main/main.py` на sample документе отрабатывает до конца; `mypy src/` — 0 ошибок; `ruff check src/` — 0 ошибок. Pipeline на 3 базовых fixtures (minimal, with_list, with_table) не падает; coarse-результаты соответствуют ожидаемым.

---

## Phase 2: Реальный markdown-парсинг (S4 upgrade)

**Цель:** `ParseToTokens` использует `markdown-it-py` и возвращает структурированные блочные токены (heading, paragraph, table, list) вместо regex-построчного парсинга. С этого момента возможна проверка extraction на fixture-наборе.

### Шаги

**2.1 Добавить зависимость**
Добавить `markdown-it-py` в `[project.dependencies]` в `pyproject.toml`.
*Результат:* `import markdown_it` работает в проекте.

**2.2 Схема токена**
Зафиксировать TypedDict `MdToken` в `models.py`: поля `type` (heading/paragraph/table/list/fence), `content`, `level` (для heading), `markup`.
*Результат:* `IngestData.tokens` получает тип `list[MdToken]`; mypy доволен.

**2.3 Реализовать парсинг**
В `ParseToTokens.run` обойти AST markdown-it-py и получить список блочных элементов документа (heading, paragraph, list, table, fence) с извлечённым plain-text содержимым без потерь текста. Inline-разметка (bold, italic, links) снимается; текст сохраняется полностью.
*Результат:* документ с заголовком `# Введение`, таблицей и списком → `ctx.data.tokens` содержит три токена с типами `heading`, `table`, `list`.

**2.4 Fatal при сбое**
Обернуть в try/except, бросать `IngestError(E_MD_PARSE_FAIL)`.
*Результат:* сломанный `md_body` → `IngestError(E_MD_PARSE_FAIL)`, а не необработанный exception.

### Проверка Phase 2

Подать `md_body` с `# Title\n\nparagraph\n\n| a | b |\n| - | - |\n| 1 | 2 |` → `len(ctx.data.tokens) == 3`, типы: `["heading", "paragraph", "table"]`. Абзац с inline-разметкой (`**жирный**, _курсив_, [ссылка](url)`) → токен типа `paragraph`, поле `content` содержит текст без потерь (inline-теги сняты, текст сохранён). Запустить на fixture `simple_sections.md`, сравнить количество токенов с эталоном.

---

## Phase 3: BuildSectionPath — отдельный шаг (S5)

**Цель:** логика breadcrumb-контекста выделена в самостоятельный шаг; `ChunkifyBlocks` получает готовые block_events с `section_path` и `heading` для каждого блока. Выход S5 — event stream: каждый не-heading блок получает `section_path`, вычисленный из контекста. Это закрывает текущую проблему: `ChunkifyBlocks` в `steps.py:110–127` самостоятельно вычисляет "финальный breadcrumb" — логика, которая никому не нужна внутри шага chunkification.

### Шаги

**3.1 Добавить поле `block_events` в `IngestData`**
`block_events: list[BlockEvent]` (TypedDict: `{token, section_path, heading}`).
*Результат:* поле доступно для записи из S5 и чтения из S6.

**3.2 Создать класс `BuildSectionPath`**
Алгоритм стека заголовков: при встрече `heading`-токена обновить стек до нужной глубины; для каждого не-heading токена вычислить `section_path` как путь от корня к текущему заголовку и `heading` как последний заголовок в стеке (или `None`).
*Результат:* класс добавлен в `steps.py`; `main.py` обновлён.

**3.3 Обновить `ChunkifyBlocks`**
Читать `ctx.data.block_events` вместо `ctx.data.tokens`; heading-токены встроены в каждый event и не требуют отдельной обработки внутри шага.
*Результат:* `ChunkifyBlocks` перестаёт дублировать логику секционирования.

**3.4 Обновить `main.py`**
Вставить `BuildSectionPath()` после `ParseToTokens()` и до `ChunkifyBlocks()`.
*Результат:* pipeline имеет 11 шагов.

### Проверка Phase 3

Документ с иерархией `# H1 / ## H2 / paragraph` → `ctx.data.block_events` содержит event для paragraph с `section_path = "H1 > H2"` и `heading = "H2"`. Запустить на всём fixture-наборе, убедиться что `section_paths_present` из эталонных JSON соответствуют реальным.

---

## Phase 4: Kind-based chunkification (S6 upgrade)

**Цель:** `ChunkifyBlocks` классифицирует блоки по семантическому типу (table/list/fact/section) и делит длинные section-чанки.

### Шаги

**4.1 Классификация kind**
Для каждого block_event:
- `table` → `kind = "table"`
- `list` → `kind = "list"`
- paragraph начинающийся с паттерна `**Label**:` → `kind = "fact"`
- остальные paragraphs → `kind = "section"`

Эвристики классификации могут уточняться по мере появления реальных документов; единственное жёсткое требование — детерминизм: одинаковый вход всегда даёт одинаковый `kind`.
*Результат:* chunk-объекты имеют поле `kind`.

**4.2 Сплит длинных section-чанков**
Если текст section-чанка превышает установленный порог — разбить по границам абзацев; каждый подчанк наследует `section_path`, `heading`, `kind`.
*Результат:* нет section-чанков длиннее порога; count chunks увеличивается для длинных разделов.

**4.3 Обновить схему `IngestData.chunks`**
Каждый chunk: `{kind, text, section_path, heading, chunk_no}`. Зафиксировать как TypedDict `Chunk` в `models.py`.
*Результат:* mypy проверяет структуру чанков; `list[dict]` заменён на `list[Chunk]`.

**4.4 `E_EMPTY_CHUNKS`**
Если по итогу `len(chunks) == 0` → `IngestError(E_EMPTY_CHUNKS)`.
*Результат:* документ без тела даёт явную ошибку.

### Проверка Phase 4

- Документ с `**Заключение**: ателектаз` → chunk с `kind="fact"`
- Документ с таблицей → chunk с `kind="table"`
- `long_section.md` → несколько chunks с `kind="section"`
- Сравнить `chunk_kinds` со всеми эталонными JSON из fixture-набора.

---

## Phase 5: Детерминированный tagging (S7 upgrade)

**Цель:** `Tagging` формирует `tags_text` по спецификации: tokenization → фильтрация → alias expansion → dedup+sort.

### Шаги

**5.1 Tokenizer**
Реализовать функцию токенизации текста. Требования: детерминизм (одинаковый вход → одинаковый набор токенов), поддержка кириллицы и латиницы, корректная обработка составных терминов (дефисы, слэши), удаление пунктуации.
*Результат:* поведение токенизатора покрыто fixture-набором; повторный запуск на одном входе даёт идентичный результат.

**5.2 Фильтры**
Числа, единицы измерения и стоп-слова (списки в константах) удалять из набора токенов.
*Результат:* токены-числа и единицы не попадают в `tags_text`.

**5.3 Alias map**
Создать `src/pipelines/ingest/alias_map.py` с константой `ALIAS_MAP: dict[str, list[str]]`. Начальный набор: несколько медицинских терминов. При встрече токена из словаря — добавить все связанные токены.
*Результат:* известные медицинские аббревиатуры расширяются в `tags_text`.

**5.4 Сборка tags_text**
Для каждого chunk: собрать токены из `doc_type` + `kind` + токенизированных `section_path` и `heading`; применить фильтры + alias expansion; дедуплицировать, отсортировать, объединить в строку.
*Результат:* `tags_text` детерминирован: два запуска с одинаковым входом дают идентичный результат.

### Проверка Phase 5

Повторный запуск на одном fixture-документе → `tags_text` побайтово совпадает. Проверить `tags_text_contains` из эталонных JSON по всему fixture-набору.

---

## — EXTRACTION VALIDATION CHECKPOINT —

После Phase 5 pipeline производит полный набор артефактов extraction: `tokens`, `block_events`, `chunks` с kind/section_path, `tagged_chunks` с `tags_text`. Persistence на этом этапе — InMemoryStore (заглушки S8–S10).

**Что проверить перед переходом к Phase 6:**
- Прогнать все fixture-документы, сверить с эталонными YAML.
- Убедиться, что `section_path` корректны для реальных медицинских документов.
- Убедиться, что `kind`-классификация адекватна (особенно `fact` для `**Label**:`).
- Оценить качество `tags_text`: есть ли нужные термины, нет ли шума.

Если extraction требует корректировок — итерировать Phase 3–5 до удовлетворительного результата, не ожидая Phase 6–8.

---

## Phase 6: Нормализация текста (S1 — полная реализация)

**Цель:** `PreprocessText` соответствует спецификации S1: детерминированный текст для дедупликации и FTS. Не блокирует extraction — применяется поверх минимальной нормализации из Phase 1.

### Шаги

**6.1 Unicode NFKC**
Применить `unicodedata.normalize("NFKC", content)` после BOM/CRLF.
*Результат:* лигатуры и нестандартные Unicode-символы раскладываются в каноническую форму.

**6.2 Решение: поисковая нормализация — отдельно от контента**

Lowercase и ё→е — это *поисковая нормализация*, не общая обработка текста. Она применяется только к представлению, которое уходит в FTS, tagging и schema detection — не к тексту, который хранится для display или будущего extraction.

Два варианта реализации:

- **Вариант A — одно поле `raw_content`** (NFKC + lower + ё→е). Проще, но теряет оригинальный регистр. Влечёт риски при добавлении extraction именованных сущностей или аббревиатур, чувствительных к регистру.
- **Вариант B — два поля**: `raw_content_canonical` (NFKC + нормализация переносов, без lower) и `raw_content_normalized` (+ lower + ё→е). Canonical — для хранения и display; normalized — для schema detection, tagging, FTS. Безопаснее при развитии pipeline.

Вариант фиксируется явно до реализации шага. При выборе Варианта A — указать в `models.py` как осознанный компромисс.
*Результат:* `IngestData` содержит либо одно, либо два поля с явными именами и назначением; поисковая нормализация не затрагивает extraction-логику.

**6.3 Нормализация символов**
Заменить `ё→е` и аналогичные омонимы; зафиксировать словарь замен в отдельном модуле `normalizer.py`.
*Результат:* варианты написания одного слова дают одинаковый хэш и одинаковые токены при tagging.

**6.4 Порядок операций и база для file_hash**
Зафиксировать порядок: BOM-strip → `\r\n`/`\r` → NFKC → (lower + char replacements, если Вариант A) → SHA256. Явно определить, от какого представления считается `file_hash`.
*Результат:* SHA256 детерминирован; при повторной подаче того же файла `file_hash` совпадает.

### Проверка Phase 6

Подать один и тот же файл в вариантах CRLF/LF и с символом `ё` — `ctx.data.file_hash` совпадает. Перепрогнать fixture-набор, убедиться что `chunks_count` и `section_paths_present` не изменились (нормализация не ломает extraction).

---

## Phase 7: Детекция схемы (S2 upgrade) + обновление S3

**Цель:** `DetectTargetSchema` читает `Target Schema ID:` из заголовка документа; валидирует значение; бросает доменные ошибки. `SplitControlBlocks` убирает строку схемы из тела. Не блокирует extraction — до этой фазы `target_schema` задаётся через `IngestInput` или хардкодится.

**Breaking change:** текущий код (`steps.py`) использует формат `%%schema_name` в первой строке. Phase 7 заменяет его на `Target Schema ID: <value>` в теле документа. Существующие sample-документы (включая `sample_document.md` в `main.py`) требуют обновления формата заголовка.

### Шаги

**7.1 Доменные исключения**
Создать класс `IngestError(Exception)` с атрибутом `code: str`. Определить коды: `E_NO_SCHEMA_ID`, `E_SCHEMA_INVALID`, `E_READ_FAIL`, `E_MD_PARSE_FAIL`, `E_EMPTY_CHUNKS`.
*Результат:* все шаги бросают `IngestError` с кодом вместо `ValueError`/`RuntimeError` для ожидаемых сбоев.

**7.2 Парсинг `Target Schema ID:`**
В `DetectTargetSchema` сканировать первые 30 строк нормализованного текста на паттерн `target schema id:\s*(\w+)`. Записывать в `ctx.data.target_schema`.
*Результат:* файл с `Target Schema ID: lab` → `ctx.data.target_schema = "lab"`.

**7.3 Валидация значения**
Допустимые значения: `{"lab", "diagnostic", "consultation"}`. Не найдено → `E_NO_SCHEMA_ID`. Найдено, но не из списка → `E_SCHEMA_INVALID`.
*Результат:* три testcase: корректный файл, файл без заголовка, файл с неизвестным значением — каждый даёт ожидаемый исход.

**7.4 Обновить `SplitControlBlocks`**
Убрать `%%`-логику; вырезать строку `target schema id:...` из тела перед формированием `md_body`. Обработать metadata-блок: в реальных документах он расположен в **конце** после `---` (не frontmatter в начале). Паттерн: найти последний `---`, за которым следует `metadata:` — вырезать этот блок из `md_body`.
*Результат:* `ctx.data.md_body` не содержит строку `target schema id:` и не содержит metadata-блок.

### Проверка Phase 7

- `Target Schema ID: lab` → pipeline продолжает, `target_schema = "lab"`
- без заголовка → `IngestError(E_NO_SCHEMA_ID)`
- `Target Schema ID: xray` → `IngestError(E_SCHEMA_INVALID)`
- fixture `no_schema_id.md` даёт ожидаемую ошибку.

---

## Phase 8: SQLite persistence (S8–S10 + SqlStore + FileStore)

**Цель:** `PersistSourceFile`, `PersistDocument`, `PersistChunks` записывают в FileStore и SQLite БД; `SqlStore` сохраняет checkpoint саги. FTS синхронизируется внутри `PersistChunks`, отдельного шага `UpdateFTS` нет.

**Не является блокирующей для extraction:** качество extraction (chunks, section_path, kind, tags_text) полностью проверяется на InMemoryStore до этой фазы. Phase 8 реализуется после прохождения Extraction Validation Checkpoint.

### Шаги

**8.1 DDL схема**
Создать `src/store/sql/schema.sql`:
- `documents(id, source_path, source_sha256, doc_type, indexed_at)` — без `raw_text`
- `chunks(chunk_pk INTEGER PRIMARY KEY, chunk_id TEXT UNIQUE, document_id, chunk_no, section_path, heading, kind, text, tags_text, UNIQUE(document_id, chunk_no))`
- `chunks_fts` как FTS5 content table: `content='chunks', content_rowid='chunk_pk'`; поля: `text`, `heading`, `section_path`, `tags_text`
- `saga_progress(run_id, saga_name, cursor, state)` для `SqlStore`

*Результат:* `sqlite3 ingest.db < schema.sql` создаёт все таблицы без ошибок.

**8.2 `SqlStore`**
Реализовать `load()` и `save()` через `aiosqlite`; создавать таблицу `saga_progress` при первом подключении.
*Результат:* `InMemoryStore` заменяется на `SqlStore(db_path)` в `main.py`; checkpoint сохраняется в БД и pipeline возобновляется после прерывания.

**8.3 `PersistSourceFile`**
Сохранить исходный markdown в файловое хранилище. Вход: `ctx.data.raw_content`, `ctx.input.source_path`. Выход: `canonical_source_path` (ключ в FileStore). Идемпотентность по `source_sha256`: write-if-not-exists допустим, overwrite — тоже (выбор при реализации).
*Результат:* `ctx.data.canonical_source_path` заполнен; файл доступен по ключу.

**8.4 `PersistDocument`**
Upsert в `documents`: `INSERT OR REPLACE`; `document_id = sha256[:32]`; `source_path = ctx.data.canonical_source_path`.
*Результат:* `SELECT * FROM documents` возвращает 1 строку с корректными `source_path`, `doc_type`, `source_sha256`.

**8.5 `PersistChunks` (= `replace_document_chunks` + SyncFTS)**
Выполняется как единая операция (в одной транзакции):
1. `DELETE FROM chunks_fts WHERE rowid IN (SELECT chunk_pk FROM chunks WHERE document_id = ?)`
2. `DELETE FROM chunks WHERE document_id = ?`
3. Batch INSERT новых чанков; `chunk_id` — детерминированный хэш от `doc_id + section_path + kind + text`; присвоить `chunk_no`
4. `INSERT INTO chunks_fts(rowid, text, heading, section_path, tags_text) SELECT chunk_pk, ... FROM chunks WHERE document_id = ?`

`chunk_no` назначается по порядку вставки. Отдельного шага `UpdateFTS` нет: FTS всегда синхронизирован после `PersistChunks`.
*Результат:* `SELECT COUNT(*) FROM chunks` совпадает с `len(ctx.data.chunk_ids)`; FTS актуален без отдельного шага.

**8.6 `db_path` через ENV**
`DB_PATH` env var (default: `ingest.db`) в `main.py`; добавить в `ENV_CONFIG` в `repo_map.md`.
*Результат:* `DB_PATH=/tmp/test.db python src/main/main.py` создаёт БД по указанному пути.

### Проверка Phase 8

Запустить pipeline → проверить через `sqlite3 ingest.db`:
```sql
SELECT id, doc_type FROM documents;
-- выводит 1 строку

SELECT COUNT(*) FROM chunks;
-- выводит N > 0

SELECT text FROM chunks_fts WHERE chunks_fts MATCH 'sample';
-- возвращает релевантный чанк
```

---

## Phase 9: Тесты

**Цель:** автоматически проверить корректность extraction (S0–S7) и persistence (S8–S10) на fixture-наборе. Phase 8 должна быть завершена.

### Шаги

**9.1 Тестовая инфраструктура**
Создать хелпер `tests/helpers.py`: запускает pipeline на указанном fixture-файле через `InMemoryStore`, возвращает `ctx.data`. Загружает соответствующий `expected_*.yaml` из той же директории.
*Результат:* один вызов `run_fixture("simple_sections.md")` возвращает `ctx.data` и `expected` — готово к сравнению.

**9.2 Extraction-тесты (S0–S7)**
Для каждого fixture из smoke subset (`minimal_valid`, `with_list`, `with_table`, `simple_sections`, `long_section`): запустить pipeline, сравнить `ctx.data` с `expected_*.yaml` по полям `chunks_count`, `chunk_kinds`, `section_paths_present`, `tags_text_contains`.
*Результат:* `pytest tests/` — все extraction-тесты зелёные.

**9.3 Тесты ошибок**
Для `no_schema_id.md` — pipeline бросает `IngestError(E_NO_SCHEMA_ID)`. Аналогично для других fatal-кейсов из Phase 0.2.
*Результат:* ожидаемые исключения пойманы; неожиданные — нет.

**9.4 Идемпотентность**
Запустить pipeline дважды на одном документе с одним `run_id` через `SqlStore`. Сравнить `ctx.data` обоих запусков — результаты идентичны; в БД нет дублей.
*Результат:* `SELECT COUNT(*) FROM chunks WHERE document_id = ?` возвращает одинаковое значение после первого и второго запуска.

**9.5 Resume**
Прервать pipeline на S9 (мок бросает исключение после первого INSERT). Перезапустить с тем же `run_id`. Убедиться, что pipeline завершился успешно и результат эквивалентен непрерывному запуску.
*Результат:* resume работает без дублей и без потерь данных.

### Проверка Phase 9

`pytest tests/ -v` — все тесты зелёные; нет ни одного теста, который проверяет только что `ctx.data is not None`.

---

## Итоговая последовательность шагов pipeline

| # | Шаг | Что производит |
|---|-----|----------------|
| S0 | LoadSource | `raw_content` |
| S1 | PreprocessText | `raw_content_canonical` (NFKC + нормализация переносов), `file_hash` (SHA256 от canonical); при Варианте A — одно поле `raw_content` |
| S2 | DetectTargetSchema | `target_schema` ∈ {lab, diagnostic, consultation} |
| S3 | SplitControlBlocks | `metadata_block`, `md_body` |
| S4 | ParseToTokens | `tokens` (markdown-it-py AST) |
| S5 | BuildSectionPath | `block_events` (token + section_path + heading) |
| S6 | ChunkifyBlocks | `chunks` (kind + text + section_path + heading) |
| S7 | Tagging | `tagged_chunks` (chunks + tags_text) |
| S8 | PersistSourceFile | `canonical_source_path`, файл сохранён в FileStore |
| S9 | PersistDocument | `document_id`, запись в `documents` |
| S10 | PersistChunks + SyncFTS | `chunk_ids`, записи в `chunks`; `chunks_fts` синхронизирован в той же транзакции |
