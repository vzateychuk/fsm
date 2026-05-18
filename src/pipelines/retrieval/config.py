from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class RetrievalConfig:
    """Retrieval pipeline configuration.

    All parameters can be overridden via environment variables (see from_env()).
    Pass a single instance into RetrievalRunner; steps receive it via constructor.
    """

    # Максимальное количество ChunkSearchResult в итоговом ответе.
    # Применяется в R5 SearchChunks как параметр limit в KnowledgeStore.search_chunks().
    limit: int = 20

    # Количество строк BM25, которые SQLite возвращает до применения diversity-фильтра.
    # Должен быть >= limit; чем больше значение, тем точнее diversity, но дороже запрос.
    # Применяется в R5 SearchChunks как параметр prelimit в KnowledgeStore.search_chunks().
    prelimit: int = 200

    # Максимум чанков от одного документа в итоговом списке (diversity cap).
    # 0 отключает ограничение — все результаты из prelimit попадают в ответ.
    # Применяется в R5 SearchChunks как параметр limit_per_document в KnowledgeStore.search_chunks().
    limit_per_document: int = 3

    # Веса BM25 для четырёх индексированных колонок FTS5 в порядке:
    # (text, heading, section_path, tags_text).
    # Больший вес — сильнее влияет на ранжирование.
    # Применяется в SqliteKnowledgeStore как аргументы функции bm25() в SQL-запросе.
    bm25_weights: tuple[float, float, float, float] = field(
        default_factory=lambda: (1.0, 2.5, 2.0, 3.5)
    )

    # Включить суффикс * (prefix match) для токенов в FTS5 MATCH-строке.
    # Если True, токен длиной >= prefix_min_len, состоящий только из кириллицы,
    # получает trailing wildcard: "протруз*" найдёт "протрузия", "протрузии" и т.д.
    # Применяется в R4 BuildFtsQuery → build_fts_match().
    enable_prefixes: bool = True

    # Минимальная длина токена (в символах) для добавления prefix wildcard.
    # Короткие токены (< prefix_min_len) передаются в FTS5 как точное совпадение,
    # чтобы избежать взрыва результатов по однобуквенным и двубуквенным префиксам.
    # Применяется в R4 BuildFtsQuery → build_fts_match().
    prefix_min_len: int = 5

    # Режим фильтрации по категории документа в R5 SearchChunks:
    # "soft" — категория из intent используется только для debug, SQL-фильтр не применяется;
    # "hard" — если intent определён, category передаётся в KnowledgeStore.search_chunks()
    #          как SQL WHERE d.category = ?, ограничивая поиск одной категорией.
    category_mode: str = "soft"   # "soft" | "hard"

    # Включить debug-режим: на каждом шаге pipeline заполняется ctx.data.debug
    # и вызывается logger.debug() с промежуточными значениями.
    # В RetrieveResponse поле debug возвращается только когда этот флаг True.
    # Устанавливается через переменную окружения RETRIEVE_DEBUG=true.
    debug: bool = False

    @classmethod
    def from_env(cls) -> RetrievalConfig:
        """Build config from environment variables.

        RETRIEVE_LIMIT              default 20
        RETRIEVE_PRELIMIT           default 200
        RETRIEVE_LIMIT_PER_DOCUMENT default 3
        RETRIEVE_BM25_WEIGHTS       default "1.0,2.5,2.0,3.5"  (text/heading/section_path/tags_text)
        RETRIEVE_ENABLE_PREFIXES    default "true"
        RETRIEVE_PREFIX_MIN_LEN     default 5
        RETRIEVE_CATEGORY_MODE      default "soft"  ("soft" | "hard")
        RETRIEVE_DEBUG              default "false"
        """
        weights_str = os.getenv("RETRIEVE_BM25_WEIGHTS", "1.0,2.5,2.0,3.5")
        raw = [float(w.strip()) for w in weights_str.split(",")]
        if len(raw) != 4:
            raise ValueError(
                f"RETRIEVE_BM25_WEIGHTS must contain exactly 4 comma-separated values, "
                f"got: {weights_str!r}"
            )
        weights: tuple[float, float, float, float] = (raw[0], raw[1], raw[2], raw[3])

        return cls(
            limit=int(os.getenv("RETRIEVE_LIMIT", "20")),
            prelimit=int(os.getenv("RETRIEVE_PRELIMIT", "200")),
            limit_per_document=int(os.getenv("RETRIEVE_LIMIT_PER_DOCUMENT", "3")),
            bm25_weights=weights,
            enable_prefixes=os.getenv("RETRIEVE_ENABLE_PREFIXES", "true").lower() == "true",
            prefix_min_len=int(os.getenv("RETRIEVE_PREFIX_MIN_LEN", "5")),
            category_mode=os.getenv("RETRIEVE_CATEGORY_MODE", "soft"),
            debug=os.getenv("RETRIEVE_DEBUG", "false").lower() == "true",
        )
