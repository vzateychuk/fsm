"""Markdown parsing utilities using markdown-it-py AST.

Converts markdown-it block tokens to structured MdToken list.
Handles: heading, paragraph, table, list, fence (code block).
"""

from markdown_it import MarkdownIt

from pipelines.ingest.models import MdToken


def parse_markdown_to_tokens(md_body: str) -> list[MdToken]:
    """Parse markdown body to structured tokens using markdown-it-py.

    Args:
        md_body: Markdown text to parse

    Returns:
        List of MdToken with type, content, level, markup extracted
    """
    md = MarkdownIt()
    block_tokens = md.parse(md_body)
    tokens: list[MdToken] = []
    i = 0

    while i < len(block_tokens):
        token = block_tokens[i]

        if token.type == "heading_open":
            new_i, md_token = _parse_heading(i, block_tokens)
            if md_token:
                tokens.append(md_token)
            i = new_i

        elif token.type == "paragraph_open":
            new_i, md_token = _parse_paragraph(i, block_tokens)
            if md_token:
                tokens.append(md_token)
            i = new_i

        elif token.type == "table_open":
            new_i, md_token = _parse_table(i, block_tokens)
            if md_token:
                tokens.append(md_token)
            i = new_i

        elif token.type in ("bullet_list_open", "ordered_list_open"):
            new_i, md_token = _parse_list(i, block_tokens)
            if md_token:
                tokens.append(md_token)
            i = new_i

        elif token.type == "fence":
            new_i, md_token = _parse_fence(i, block_tokens)
            if md_token:
                tokens.append(md_token)
            i = new_i

        else:
            i += 1

    return tokens


def _parse_heading(i: int, block_tokens: list) -> tuple[int, MdToken | None]:
    """Parse heading_open ... heading_close block.

    Args:
        i: Index of heading_open token
        block_tokens: List of all block tokens

    Returns:
        (next_index, MdToken) or (next_index, None) if empty
    """
    token = block_tokens[i]
    level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.
    content_parts = []
    j = i + 1

    # Collect all inline content until heading_close
    while j < len(block_tokens) and block_tokens[j].type != "heading_close":
        if block_tokens[j].type == "inline":
            content_parts.append(_extract_inline_text(block_tokens[j]))
        j += 1

    content = " ".join(content_parts)
    markup = "#" * level

    # Skip to heading_close and move past it
    while i < len(block_tokens) and block_tokens[i].type != "heading_close":
        i += 1
    i += 1

    return i, MdToken(type="heading", content=content, level=level, markup=markup)


def _parse_paragraph(i: int, block_tokens: list) -> tuple[int, MdToken | None]:
    """Parse paragraph_open ... paragraph_close block.

    Args:
        i: Index of paragraph_open token
        block_tokens: List of all block tokens

    Returns:
        (next_index, MdToken) or (next_index, None) if empty
    """
    content_parts = []
    j = i + 1

    # Collect all inline content until paragraph_close
    while j < len(block_tokens) and block_tokens[j].type != "paragraph_close":
        if block_tokens[j].type == "inline":
            content_parts.append(_extract_inline_text(block_tokens[j]))
        j += 1

    content = " ".join(content_parts)

    # Skip to paragraph_close and move past it
    while i < len(block_tokens) and block_tokens[i].type != "paragraph_close":
        i += 1
    i += 1

    return i, MdToken(type="paragraph", content=content) if content else (i, None)


def _parse_table(i: int, block_tokens: list) -> tuple[int, MdToken | None]:
    """Parse table_open ... table_close block.

    Collects rows and cells, preserving structure as pipe-separated columns.
    Handles th (header) and td (data) cells correctly.

    Args:
        i: Index of table_open token
        block_tokens: List of all block tokens

    Returns:
        (next_index, MdToken) or (next_index, None) if no rows
    """
    table_rows = []
    i += 1

    while i < len(block_tokens) and block_tokens[i].type != "table_close":
        if block_tokens[i].type == "tr_open":
            row_cells = []
            i += 1

            while i < len(block_tokens) and block_tokens[i].type != "tr_close":
                if block_tokens[i].type == "th_open":
                    # Collect cell content until th_close
                    cell_parts = []
                    i += 1
                    while i < len(block_tokens) and block_tokens[i].type != "th_close":
                        if block_tokens[i].type == "inline":
                            cell_parts.append(_extract_inline_text(block_tokens[i]))
                        i += 1
                    row_cells.append(" ".join(cell_parts))
                    i += 1  # Skip th_close

                elif block_tokens[i].type == "td_open":
                    # Collect cell content until td_close
                    cell_parts = []
                    i += 1
                    while i < len(block_tokens) and block_tokens[i].type != "td_close":
                        if block_tokens[i].type == "inline":
                            cell_parts.append(_extract_inline_text(block_tokens[i]))
                        i += 1
                    row_cells.append(" ".join(cell_parts))
                    i += 1  # Skip td_close

                else:
                    i += 1

            if row_cells:
                table_rows.append(" | ".join(row_cells))
            i += 1  # Skip tr_close
        else:
            i += 1

    i += 1  # Skip table_close

    return i, MdToken(type="table", content="\n".join(table_rows)) if table_rows else (i, None)


def _parse_list(i: int, block_tokens: list) -> tuple[int, MdToken | None]:
    """Parse bullet_list_open/ordered_list_open ... *_list_close block.

    Args:
        i: Index of *_list_open token
        block_tokens: List of all block tokens

    Returns:
        (next_index, MdToken) or (next_index, None) if empty
    """
    token = block_tokens[i]
    is_bullet = token.type == "bullet_list_open"
    close_type = "bullet_list_close" if is_bullet else "ordered_list_close"
    list_content = []
    i += 1

    while i < len(block_tokens) and block_tokens[i].type != close_type:
        if block_tokens[i].type == "inline":
            item_text = _extract_inline_text(block_tokens[i])
            if item_text:
                list_content.append(f"- {item_text}")
        i += 1

    i += 1  # Skip list_close

    return i, MdToken(type="list", content="\n".join(list_content)) if list_content else (i, None)


def _parse_fence(i: int, block_tokens: list) -> tuple[int, MdToken | None]:
    """Parse fence (code block) token.

    Args:
        i: Index of fence token
        block_tokens: List of all block tokens

    Returns:
        (next_index, MdToken) or (next_index, None) if empty
    """
    token = block_tokens[i]
    content = token.content.strip() if token.content else ""
    lang = token.info.strip() if token.info else ""

    i += 1

    return i, MdToken(type="fence", content=content, markup=lang) if content else (i, None)


def _extract_inline_text(inline_token) -> str:
    """Extract plain-text content from inline token, removing markup.

    Handles: text, softbreak, hardbreak, code_inline.
    Skips: markup tokens (em_open, strong_open, link_open, image, etc.)
    Link text is preserved via child text nodes.

    Args:
        inline_token: Inline token from markdown-it

    Returns:
        Plain text content without formatting markup
    """
    if not inline_token or not inline_token.children:
        return inline_token.content if inline_token else ""

    text_parts = []
    for child in inline_token.children:
        if child.type == "text":
            text_parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            text_parts.append(" ")
        elif child.type == "code_inline":
            text_parts.append(child.content)
        # Skip: em_open/close, strong_open/close, link_open/close, image, etc.
        # Link text already captured in child text nodes

    return "".join(text_parts).strip()
