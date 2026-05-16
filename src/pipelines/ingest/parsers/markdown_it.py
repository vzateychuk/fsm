"""Markdown parsing utilities using markdown-it-py AST.

Converts markdown-it block tokens to structured MdToken list.
Handles: heading, paragraph, table, list, fence (code block).
"""

from collections.abc import Callable

from markdown_it import MarkdownIt
from markdown_it.token import Token

from pipelines.ingest.models import MdToken

_HandlerFn = Callable[[int, list[Token]], tuple[int, MdToken | None]]


def _extract_inline_text(inline_token: Token) -> str:
    """Extract plain-text content from inline token, removing markup.

    Handles: text, softbreak, hardbreak, code_inline.
    Skips: em_open/close, strong_open/close, link_open/close, image, etc.
    Link text is preserved via child text nodes.
    """
    if not inline_token.children:
        return inline_token.content

    parts: list[str] = []
    for child in inline_token.children:
        if child.type == "text":
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
        elif child.type == "code_inline":
            parts.append(child.content)

    return "".join(parts).strip()


def _collect_inline(block_tokens: list[Token], start: int, close_type: str) -> tuple[str, int]:
    """Walk from start+1 to close_type, join inline text, return (text, next_i).

    next_i points to the token after close_type.
    """
    parts: list[str] = []
    i = start + 1
    while i < len(block_tokens) and block_tokens[i].type != close_type:
        if block_tokens[i].type == "inline":
            parts.append(_extract_inline_text(block_tokens[i]))
        i += 1
    return " ".join(parts), i + 1  # +1 skips the close token


def _collect_row(block_tokens: list[Token], i: int) -> tuple[list[str], int]:
    """Walk from i to tr_close, collecting one cell text per th/td pair.

    i must point to the token immediately after tr_open.
    Returns (cells, next_i) where next_i is the token after tr_close.
    """
    cells: list[str] = []
    while i < len(block_tokens) and block_tokens[i].type != "tr_close":
        t = block_tokens[i].type
        if t in ("th_open", "td_open"):
            close = "th_close" if t == "th_open" else "td_close"
            text, i = _collect_inline(block_tokens, i, close)
            cells.append(text)
        else:
            i += 1
    return cells, i + 1  # +1 skips tr_close


def _parse_heading(i: int, block_tokens: list[Token]) -> tuple[int, MdToken | None]:
    level = int(block_tokens[i].tag[1])  # h1 -> 1, h2 -> 2, etc.
    content, next_i = _collect_inline(block_tokens, i, "heading_close")
    return next_i, MdToken(type="heading", content=content, level=level, markup="#" * level)


def _is_fact_paragraph(inline_token: Token) -> bool:
    """Return True if paragraph starts with **label**: pattern.

    Checks child sequence: strong_open -> (text...) -> strong_close -> text(starts with ":")
    Skips whitespace-only text nodes at beginning and between strong_close and colon.
    Label max 120 chars to avoid false positives on malformed markup.
    """
    children = inline_token.children or []
    if len(children) < 3:
        return False

    # Find first strong_open, skipping initial whitespace-only text nodes
    open_idx = next((idx for idx, c in enumerate(children) if c.type == "strong_open"), -1)
    if open_idx < 0:
        return False

    close_idx = next((idx for idx, c in enumerate(children[open_idx + 1:], open_idx + 1) if c.type == "strong_close"), -1)
    if close_idx < 0 or close_idx <= open_idx:
        return False

    label = "".join(c.content for c in children[open_idx + 1:close_idx] if c.type == "text").strip()
    if not label or len(label) > 120:
        return False

    for child in children[close_idx + 1:]:
        if child.type == "text":
            stripped = child.content.lstrip()
            if stripped.startswith(":"):
                return True
            if child.content.strip():
                return False
    return False


def _parse_paragraph(i: int, block_tokens: list[Token]) -> tuple[int, MdToken | None]:
    inline_tok = (
        block_tokens[i + 1]
        if i + 1 < len(block_tokens) and block_tokens[i + 1].type == "inline"
        else None
    )
    is_fact = _is_fact_paragraph(inline_tok) if inline_tok is not None else False
    content, next_i = _collect_inline(block_tokens, i, "paragraph_close")
    if not content:
        return next_i, None
    return next_i, MdToken(type="paragraph", content=content, subtype="fact" if is_fact else "")


def _parse_table(i: int, block_tokens: list[Token]) -> tuple[int, MdToken | None]:
    rows: list[str] = []
    i += 1  # skip table_open
    while i < len(block_tokens) and block_tokens[i].type != "table_close":
        if block_tokens[i].type == "tr_open":
            cells, i = _collect_row(block_tokens, i + 1)
            if cells:
                rows.append(" | ".join(cells))
        else:
            i += 1
    i += 1  # skip table_close
    return i, MdToken(type="table", content="\n".join(rows)) if rows else None


def _collect_list_item(block_tokens: list[Token], i: int) -> tuple[str, int]:
    """Collect all inline text from a single list_item.

    Walks from i (at list_item_open) to list_item_close.
    Collects inline text from paragraphs; skips nested lists entirely.
    Returns (item_text, next_i) where next_i is after list_item_close.
    """
    parts: list[str] = []
    i += 1  # skip list_item_open

    while i < len(block_tokens) and block_tokens[i].type != "list_item_close":
        t = block_tokens[i].type
        if t == "inline":
            parts.append(_extract_inline_text(block_tokens[i]))
        elif t in ("bullet_list_open", "ordered_list_open"):
            close_type = "bullet_list_close" if t == "bullet_list_open" else "ordered_list_close"
            while i < len(block_tokens) and block_tokens[i].type != close_type:
                i += 1
            i += 1  # skip list_close
            continue
        i += 1

    return " ".join(parts), i + 1  # +1 skips list_item_close


def _parse_list(i: int, block_tokens: list[Token]) -> tuple[int, MdToken | None]:
    close_type = "bullet_list_close" if block_tokens[i].type == "bullet_list_open" else "ordered_list_close"
    items: list[str] = []
    i += 1  # skip list_open

    while i < len(block_tokens) and block_tokens[i].type != close_type:
        if block_tokens[i].type == "list_item_open":
            text, i = _collect_list_item(block_tokens, i)
            if text:
                items.append(f"- {text}")
        else:
            i += 1

    return i + 1, MdToken(type="list", content="\n".join(items)) if items else None


def _parse_fence(i: int, block_tokens: list[Token]) -> tuple[int, MdToken | None]:
    token = block_tokens[i]
    content = token.content.strip() if token.content else ""
    lang = token.info.strip() if token.info else ""
    return i + 1, MdToken(type="fence", content=content, markup=lang) if content else None


_BLOCK_HANDLERS: dict[str, _HandlerFn] = {
    "heading_open": _parse_heading,
    "paragraph_open": _parse_paragraph,
    "table_open": _parse_table,
    "bullet_list_open": _parse_list,
    "ordered_list_open": _parse_list,
    "fence": _parse_fence,
}


def parse_markdown_to_tokens(md_body: str) -> list[MdToken]:
    """Parse markdown body to structured tokens using markdown-it-py.

    Args:
        md_body: Markdown text to parse.

    Returns:
        List of MdToken with type, content, level, and markup extracted.
    """
    md = MarkdownIt().enable("table")
    block_tokens = md.parse(md_body)
    tokens: list[MdToken] = []
    i = 0

    while i < len(block_tokens):
        handler = _BLOCK_HANDLERS.get(block_tokens[i].type)
        if handler:
            next_i, md_token = handler(i, block_tokens)
            if md_token:
                tokens.append(md_token)
            i = next_i
        else:
            i += 1

    return tokens
