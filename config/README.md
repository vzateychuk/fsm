# Configuration Files

This directory contains application configuration files in YAML format.

## Overview

Configuration is loaded at application startup and used by both **ingest** and **retrieval** pipelines to normalize medical terminology, filter noise, and expand search queries.

```
Ingest Pipeline               Retrieval Pipeline
    ↓                              ↓
    └─→ config/aliases.yaml ←─┘
           ├─ aliases
           ├─ stopwords
           ├─ units_exact
           └─ units_regex
```

---

## aliases.yaml

**Purpose:** Central registry of medical terminology mappings, stopwords, and measurement units.

**Used by:**
- **Ingest S7 Tagging** — filters low-signal tokens during chunk tagging
- **Retrieval R3 ExpandAliases** — expands query terms with synonyms

**Location:** `src/common/alias_map.py` loads and validates this file at module import time.

---

### Section: `aliases`

Medical terminology synonyms and alternate names.

**What it does:**
- During **ingest tagging**: `ALIAS_MAP` is checked to tag chunks with domain-specific synonyms
- During **retrieval**: Query terms are expanded with synonyms using OR logic

**Format:**
```yaml
aliases:
  TERM: [ALIAS_1, ALIAS_2, ...]
```

**Example:**
```yaml
aliases:
  фгдс: ["эгдс"]              # Reverse endoscopy ↔ Esophagogastroduodenoscopy
  экг: ["электрокардиография"]  # ECG ↔ Electrocardiography
  лпнп: ["ldl"]               # LDL cholesterol (Russian) ↔ (English)
  ldl: ["лпнп"]               # Reverse mapping required
```

**Rules:**
- Define bidirectional mappings (if `a → b`, also define `b → a`)
- Keep values as lists, even for single aliases
- Use lowercase, normalized form (ё→е already applied by normalizer)

**When to add:**
- New disease/procedure name
- New diagnostic acronym
- New medication/substance name
- Medical term with common abbreviation (e.g., "МРТ" for "магнитно-резонансная томография")

---

### Section: `stopwords`

Tokens to ignore during indexing and retrieval.

**What it does:**
- During **ingest tagging**: tokens matching `is_stopword()` are dropped before creating chunk tags
- During **retrieval**: *not directly used* (but loaded for consistency)

**Format:**
```yaml
stopwords:
  - WORD_1
  - WORD_2
```

**Example:**
```yaml
stopwords:
  - для        # Russian preposition "for"
  - при        # Russian preposition "at, during"
  - the        # English article
  - and        # English conjunction
```

**Rules:**
- Use lowercase, normalized form (ё→е, leading/trailing spaces removed)
- Add both Russian and English when applicable

**When to add:**
- Common preposition/conjunction not in list
- High-frequency article in either language
- Word that appears in many documents but carries no semantic meaning

**Current filter chain in tagging:**
1. Length check: `len(token) >= 3`
2. Digit check: no digits allowed in token
3. Units check: `not is_unit(token)`
4. **Stopwords check:** `not is_stopword(token)` ← This file
5. Invalid chars check: no punctuation in token

---

### Section: `units_exact`

Exact measurement units (mass, volume, time, lab concentrations, etc.).

**What it does:**
- During **ingest tagging**: tokens matching `units_exact` are dropped
- Purpose: Skip measurement values like "5 мл", "200 мг" — they're data, not semantics

**Format:**
```yaml
units_exact:
  - UNIT_1
  - UNIT_2
```

**Example:**
```yaml
units_exact:
  - кг        # kilogram
  - мл        # milliliter
  - мм        # millimeter
  - мин       # minute
  - ммоль/л   # millimol per liter (lab unit)
```

**Rules:**
- Include common variations (e.g., both `мл` and `ml`)
- Include compound units like `mg/ml`
- Use exact string match (no wildcards here; use `units_regex` for patterns)

**When to add:**
- New measurement unit encountered in documents
- Lab-specific unit (e.g., `ед/мл`, `нг/мл`)
- Common abbreviation for a unit (e.g., `уд/мин` for pulse rate)

---

### Section: `units_regex`

Regex patterns for complex measurement units with variable prefixes.

**What it does:**
- During **ingest tagging**: tokens matching any pattern are dropped
- Purpose: Match variations like "мкме/мл" (micro-enzyme units per ml)

**Format:**
```yaml
units_regex:
  - "^REGEX_PATTERN_1$"
  - "^REGEX_PATTERN_2$"
```

**Example:**
```yaml
units_regex:
  - "^(мк)?ме/мл$"       # matches: ме/мл, мкме/мл
  - "^(мк)?моль/л$"      # matches: моль/л, мкмоль/л
  - "^(пг|нг|мг|мкг)/мл$"  # matches: пг/мл, нг/мл, мг/мл, мкг/мл
```

**Rules:**
- Use `^...$` anchors (exact match)
- Use `(мк)?` for optional "микро-" prefix
- Use `|` for alternation (e.g., `пг|нг|мг`)
- Test regex before adding (use `python -c "import re; re.compile('pattern')"`)

**When to add:**
- Complex unit with variable prefixes
- Lab unit with multiple forms
- Medical parameter with different measurement scales

**Invalid regex handling:**
If a pattern is invalid, you'll see:
```
ValueError: Invalid regex pattern in config: ...
```
Check syntax in `units_regex` section.

---

## Loading and Validation

**When:** At application startup (module import time)
**Where:** `src/common/alias_map.py` → `_initialize_config()`

**Validation checks:**
- File exists at `config/aliases.yaml`
- Root keys exist: `aliases`, `stopwords`, `units_exact`, `units_regex`
- `aliases` is a dict
- `stopwords` is a list
- `units_exact` is a list
- `units_regex` is a list of valid regex patterns

**Error examples:**

```python
# Missing file
FileNotFoundError: Configuration file not found: config/aliases.yaml

# Invalid structure
ValueError: 'aliases' must be a dictionary

# Invalid regex
ValueError: Invalid regex pattern in config: unterminated character set
```

---

## Usage in Code

### Ingest Pipeline

```python
# src/pipelines/ingest/steps/tagging.py
from common.alias_map import ALIAS_MAP, is_stopword, is_unit

def _keep(token: str) -> bool:
    return (
        len(token) >= 3
        and not any(c.isdigit() for c in token)
        and not is_unit(token)        # ← checks units_exact and units_regex
        and not is_stopword(token)    # ← checks stopwords
        and not any(c in _INVALID_CHARS for c in token)
    )

# Later: use ALIAS_MAP for tagging
tags = ALIAS_MAP.get(token, [])  # Get aliases for this token
```

### Retrieval Pipeline

```python
# src/pipelines/retrieval/steps.py → R3 ExpandAliases
from common.alias_map import ALIAS_MAP

expanded = []
for token in query_tokens:
    expanded.append(token)
    for alias in ALIAS_MAP.get(token, []):
        expanded.append(alias)  # Add synonyms for OR-expansion in FTS

# Result: "птг анализ" → expanded_terms = ["птг", "pth", "анализ"]
# FTS query: "птг OR pth OR анализ"
```

---

## Adding New Entries

### Example 1: New Disease

**Requirement:** Add support for "инсульт" (stroke) with English synonym.

```yaml
aliases:
  инсульт: ["stroke"]
  stroke: ["инсульт"]
```

**Effect:**
- Ingest: Chunks tagged with "инсульт" also tagged with "stroke"
- Retrieval: Query "stroke" expands to "stroke OR инсульт"

### Example 2: New Lab Unit

**Requirement:** Add support for "МЕ/дл" (International Units per deciliter).

```yaml
units_exact:
  - ме/дл      # Add exact unit

units_regex:
  - "^(мкме|ме)/дл$"  # Add pattern for micro variants
```

**Effect:**
- Tagging drops "50 МЕ/дл" → token "ме/дл" removed
- No chunk indexed for measurement values

### Example 3: New Stopword

**Requirement:** "который" (which) appears in many documents but adds no meaning.

```yaml
stopwords:
  - который
```

**Effect:**
- Tagging drops "который" tokens
- Improves signal-to-noise ratio in chunk tags

---

## Debugging

### Check if config loaded correctly

```bash
cd src
python -c "from common.alias_map import ALIAS_MAP, STOPWORDS, UNITS_EXACT; \
  print(f'Aliases: {len(ALIAS_MAP)}'); \
  print(f'Stopwords: {len(STOPWORDS)}'); \
  print(f'Units: {len(UNITS_EXACT)}')"
```

**Output:**
```
Aliases: 14
Stopwords: 31
Units: 35
```

### Test a specific token

```bash
python -c "import sys; sys.path.insert(0, 'src'); \
  from common.alias_map import is_stopword, is_unit; \
  print(f'is_stopword(\"для\"): {is_stopword(\"для\")}'); \
  print(f'is_unit(\"мл\"): {is_unit(\"мл\")}')"
```

### Validate YAML syntax

```bash
python -c "import yaml; yaml.safe_load(open('config/aliases.yaml'))"
```

If no error: YAML is valid.

---

## Future Enhancements

1. **Environment-specific configs** — e.g., `config/aliases.prod.yaml` for production-only terms
2. **Hot reload** — Reload config without restarting the app
3. **Config versioning** — Track changes to aliases over time
4. **Per-pipeline config** — Separate aliases for ingest vs retrieval if needed
5. **Database-backed config** — Load from database instead of files for easier updates

---

## Related Files

- `src/common/alias_map.py` — Python module that loads and uses this config
- `src/pipelines/ingest/alias_map.py` — Re-exports for backward compatibility
- `src/pipelines/retrieval/alias_map.py` — Re-exports for backward compatibility

## Testing

```bash
# Run tests that use aliases
pytest tests/retrieval/test_retrieval.py -v

# All tests
pytest tests/ -v
```

All 67 tests pass with current configuration ✓
