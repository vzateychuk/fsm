from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RetrievalConfig:
    """Retrieval pipeline configuration.

    Load from config/retrieve.yaml using load() method, or create programmatically.
    Pass a single instance into RetrievalRunner; steps receive it via constructor.

    Contains only retrieval system parameters (BM25 weights, prefix matching, category filtering).
    Consultation-specific usage parameters (limits, diversity cap) are stored in ConsultConfig.retrieval.
    """

    # Количество строк BM25, которые SQLite возвращает до применения diversity-фильтра.
    # Должен быть >= limit; чем больше значение, тем точнее diversity, но дороже запрос.
    # Применяется в R5 SearchChunks как параметр prelimit в KnowledgeStore.search_chunks().
    prelimit: int = 200

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

    @classmethod
    def load(cls, config_path: Path) -> RetrievalConfig:
        """Load config from YAML file.

        Args:
            config_path: Path to retrieve.yaml configuration file.

        Returns:
            RetrievalConfig instance with values from YAML.
        """
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls(
            prelimit=data.get("prelimit", 200),
            bm25_weights=tuple(data.get("bm25_weights", (1.0, 2.5, 2.0, 3.5))),
            enable_prefixes=data.get("enable_prefixes", True),
            prefix_min_len=data.get("prefix_min_len", 5),
            category_mode=data.get("category_mode", "soft"),
        )

