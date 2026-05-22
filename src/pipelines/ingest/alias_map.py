"""Re-export alias map from common package for backward compatibility.

This module is kept for backward compatibility with ingest pipeline.
All imports should be from common.alias_map going forward.
"""

from common.alias_map import ALIAS_MAP, STOPWORDS, UNITS_EXACT, UNITS_REGEX, is_stopword, is_unit

__all__ = ["ALIAS_MAP", "STOPWORDS", "UNITS_EXACT", "UNITS_REGEX", "is_unit", "is_stopword"]
