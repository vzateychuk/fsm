"""Extract document date from markdown content markers, YAML metadata, or filename.

Priority order (first non-None wins):
1. Content markers — pass 1 (preferred): '**Дата:**', '**Дата анализа:**', etc.
2. Content markers — pass 2 (fallback): configurable suffixes (see ingest.yaml date_suffix_fallback)
3. YAML metadata block: --- date: 2023-02-24 ---
4. Filename stem: configurable regex patterns (see ingest.yaml filename_date_patterns)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from common.normalizer import normalize_text

_CONTENT_DATE_RE = re.compile(
    r"[\*]{1,2}\s*Дата(?P<suffix>[^\*]*?)[\*]{1,2}\s*:?\s*(?P<date>\d{4}-\d{2}-\d{2}|\d{2}[./]\d{2}[./]\d{4}(?:\s+\d{2}:\d{2})?)",
    re.IGNORECASE,
)

_CONTENT_SCAN_LIMIT = 30

_DEFAULT_FILENAME_DATE_PATTERNS: tuple[str, ...] = (
    r"^(\d{4}-\d{2}-\d{2})[_\-]",
    r"(\d{8})$",
)


@dataclass(frozen=True, slots=True)
class DocumentDateSuffixConfig:
    """Configurable rules for document date extraction (ingest.yaml)."""

    hard_excluded: tuple[str, ...]
    fallback: tuple[str, ...]
    filename_patterns: tuple[str, ...]

    @classmethod
    def defaults(cls) -> DocumentDateSuffixConfig:
        return cls(
            hard_excluded=("рождения", "отправки", "печати"),
            fallback=("валидации", "заказа"),
            filename_patterns=_DEFAULT_FILENAME_DATE_PATTERNS,
        )

    @classmethod
    def from_yaml_mapping(cls, data: dict) -> DocumentDateSuffixConfig:
        defaults = cls.defaults()
        hard = data.get("date_suffix_hard_excluded")
        fallback = data.get("date_suffix_fallback")
        filename_patterns = data.get("filename_date_patterns")
        return cls(
            hard_excluded=_normalize_suffix_list(hard) if hard is not None else defaults.hard_excluded,
            fallback=_normalize_suffix_list(fallback) if fallback is not None else defaults.fallback,
            filename_patterns=tuple(filename_patterns)
            if filename_patterns is not None
            else defaults.filename_patterns,
        )

    def compiled_filename_patterns(self) -> tuple[re.Pattern[str], ...]:
        compiled: list[re.Pattern[str]] = []
        for pattern in self.filename_patterns:
            try:
                compiled.append(re.compile(pattern))
            except re.error as exc:
                raise ValueError(f"Invalid filename_date_patterns regex: {pattern!r}") from exc
        return tuple(compiled)


def _normalize_suffix_list(items: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(normalize_text(str(s).strip()) for s in items if str(s).strip())


def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD."""
    date_part = date_str.split()[0]

    if len(date_part) == 8 and date_part.isdigit():
        return f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"

    if "." in date_part or "/" in date_part:
        separator = "." if "." in date_part else "/"
        parts = date_part.split(separator)
        if len(parts) == 3:
            day, month, year = parts
            if len(year) == 2:
                year = "20" + year
            return f"{year}-{month:0>2}-{day:0>2}"

    return date_part


def _is_hard_excluded(suffix: str, config: DocumentDateSuffixConfig) -> bool:
    return any(token in suffix for token in config.hard_excluded)


def _is_fallback(suffix: str, config: DocumentDateSuffixConfig) -> bool:
    return any(token in suffix for token in config.fallback)


def _extract_from_content(content: str, config: DocumentDateSuffixConfig) -> str | None:
    """Extract date from markdown header: preferred markers first, then fallback suffixes."""
    lines = content.split("\n")[:_CONTENT_SCAN_LIMIT]

    for line in lines:
        for match in _CONTENT_DATE_RE.finditer(line):
            suffix = match.group("suffix").strip().lower()
            if _is_hard_excluded(suffix, config) or _is_fallback(suffix, config):
                continue
            return _normalize_date(match.group("date"))

    for fb_token in config.fallback:
        for line in lines:
            for match in _CONTENT_DATE_RE.finditer(line):
                suffix = match.group("suffix").strip().lower()
                if _is_hard_excluded(suffix, config):
                    continue
                if fb_token in suffix:
                    return _normalize_date(match.group("date"))

    return None


def _extract_from_filename(
    source_path: str | Path | None,
    config: DocumentDateSuffixConfig,
) -> str | None:
    if source_path is None:
        return None
    stem = Path(source_path).stem
    for pattern in config.compiled_filename_patterns():
        match = pattern.search(stem)
        if match:
            return _normalize_date(match.group(1))
    return None


def _extract_from_yaml_metadata(content: str) -> str | None:
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None

    yaml_end: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            yaml_end = i
            break
    if yaml_end is None:
        return None

    yaml_text = "\n".join(lines[1:yaml_end])
    try:
        metadata = yaml.safe_load(yaml_text) or {}
    except Exception:
        return None
    if not isinstance(metadata, dict):
        return None

    date_val = metadata.get("date") or metadata.get("document_date") or metadata.get("visit_date")
    if date_val is None:
        return None
    if isinstance(date_val, date):
        return date_val.isoformat()
    return _normalize_date(str(date_val))


def extract_document_date(
    content: str,
    source_path: str | Path | None = None,
    *,
    date_config: DocumentDateSuffixConfig | None = None,
) -> str | None:
    """Extract document date with priority: content > YAML metadata > filename."""
    config = date_config or DocumentDateSuffixConfig.defaults()
    return (
        _extract_from_content(content, config)
        or _extract_from_yaml_metadata(content)
        or _extract_from_filename(source_path, config)
    )
