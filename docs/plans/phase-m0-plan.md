# phase-m0-plan.md — Medical Consultation Baseline (KB → Medical LLM)

Цель: построить устойчивый baseline-консультационный pipeline поверх уже реализованных FSM ingestion/retrieval, который дополняет запрос пациента контекстом из KnowledgeBase и делает 1 вызов medical-LLM.

Контекст (уже есть в проекте):
- Ingest FSM: Markdown → chunks + tags_text → SQLite FTS5 (`fsm-impl-plan-ingest-concept.md`)
- Retrieve FSM: query → normalization → alias expansion → BM25 → results (`fsm-impl-plan-retrieve-concept.md`)
- Общий SagaRunner/FSM-подход и vendor-agnostic LLM interface (`impl-plan.md`, prompts)

---

## Scope Phase M0 (Baseline, one-shot)
Включаем:
- user complaint → baseline retrieval (KB) → KBContextBundle → 1 вызов medical-LLM → ответ пользователю

Не включаем (позже):
- agentic KB requests (tool-like loop)
- interview/clarification loop
- verifier/critic revise loop
- web-search
- сложный парсинг ответа в строгую структуру (достаточно raw text)

---

## MVP Acceptance Criteria (Phase M0)
- [ ] Команда `consult` выполняет end-to-end: жалоба → retrieval → KBContextBundle → medical-LLM → ответ
- [ ] KBContextBundle формируется детерминированно, секциями, с лимитами по объёму
- [ ] Вход medical-LLM структурирован: “Key Findings” первым + явные заголовки секций
- [ ] Есть unit-тесты на KBContextBundle builder и integration-тест на consult pipeline с mock LLM
- [ ] Все тесты проходят в env=test без сети

---

## Step M0.1 — Consultation CLI skeleton
**Цель:** зафиксировать внешний интерфейс консультации.

**Сделать:**
- [ ] Добавить CLI команду: `advisor consult "<complaint>"`
- [ ] Логирование: отображать основные стадии (retrieve/bundle/llm-call)
- [ ] Stub-ответ, если pipeline ещё не подключён (временный)

**Готово, если:**
- [ ] команда запускается, парсит complaint, создаёт run context (минимально)

---

## Step M0.2 — Baseline retrieval strategy
**Цель:** deterministic baseline retrieval без “медицинских знаний” в orchestrator.

**Сделать:**
- [ ] Определить baseline стратегию retrieval (минимум 1–2 вызова retrieval FSM):
  - [ ] Query bundle: retrieval по complaint (нормализация/алиасы уже в retrieval FSM)
  - [ ] (Опционально) Recency bundle: retrieval “последние документы/чанки” (если доступно)
- [ ] Зафиксировать поведение при пустой выдаче (fallback: меньше фильтров, меньше ограничений)

**Готово, если:**
- [ ] retrieval вызывается, результаты возвращаются, объём контролируется `top_k`/лимитами

---

## Step M0.3 — KBContextBundle builder (структура + лимиты)
**Цель:** стандартный формат контекста для medical-LLM (anti lost-in-the-middle).

**KBContextBundle (концепт секций):**
- Key Findings (в начале)
- KB Excerpts (чанки, отсортированы по score)
- Provenance (минимальные ссылки на источники: doc/path/section)

**Сделать:**
- [ ] Dedupe результатов (по chunk identity)
- [ ] Ввести лимиты:
  - [ ] `kb_max_chunks` (top-k excerpts)
  - [ ] `kb_max_chars_total` (общий бюджет)
  - [ ] `kb_max_chars_per_excerpt` (усечение каждого excerpts)
  - [ ] `limit_per_document` (diversity; 0 = unlimited, уже корректно в текущем коде)
- [ ] Truncation policy:
  - [ ] Key Findings сохраняем всегда
  - [ ] Excerpts выкидываем снизу по rank при переполнении бюджета

**Готово, если:**
- [ ] bundle всегда укладывается в лимиты и имеет одинаковую структуру

---

## Step M0.4 — Medical LLM prompt (one-shot)
**Цель:** 1 запрос в medical-LLM с секционированным входом.

**Сделать:**
- [ ] Определить role prompt для medical-LLM (в prompts directory)
- [ ] Сформировать вход в LLM секциями:
  - [ ] Key Findings (first)
  - [ ] Complaint
  - [ ] KB Excerpts
  - [ ] Output requirements (uncertainties, red flags, questions for doctor)
- [ ] Один вызов medical-LLM, выводим raw text

**Готово, если:**
- [ ] medical-LLM получает контекст и возвращает ответ, который выводится пользователю

> Примечание: RU→EN перевод не включаем в M0 по умолчанию. Добавим позже только если качество без перевода недостаточно.

---

## Step M0.5 — End-to-end wiring + tests
**Цель:** собрать всё в один pipeline и зафиксировать тестами.

**Сделать:**
- [ ] Собрать consultation runner (по паттерну существующих FSM pipelines)
- [ ] Unit tests:
  - [ ] KBContextBundle builder: лимиты/сортировка/dedupe/формат секций
- [ ] Integration tests (env=test):
  - [ ] consult pipeline с Mock LLM (детерминированный ответ)
- [ ] Smoke test вручную (env=prod) на реальной medical-LLM

**Готово, если:**
- [ ] `advisor consult "<complaint>"` работает end-to-end
- [ ] тесты проходят без сети

---

## Phase M0.1 (next, not part of M0) — Agentic KB requests (tool-like loop)
После стабилизации M0 добавляем:
- [ ] KBQueryRequest (логический запрос дополнительных данных)
- [ ] configurable `max_kb_roundtrips`
- [ ] цикл: medical-LLM → KBQueryRequest → retrieval → medical-LLM → финальный ответ

---

## Notes (for future phases)
- Interview loop, verifier/critic, web-search и smart routing — отдельные фазы после M0/M0.1.
- Источник документов (raw_text vs filestore) — внутреннее дело KnowledgeBase и не влияет на консультационный контракт.