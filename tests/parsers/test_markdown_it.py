"""Unit tests for parse_markdown_to_tokens.

Tests cover each block type (heading, paragraph, table, list, fence),
inline markup stripping, and edge cases. No mocks — all tests call
the public function with real markdown input.
"""


from pipelines.ingest.models import MdToken
from pipelines.ingest.parsers import parse_markdown_to_tokens

# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------


def test_h1() -> None:
    tokens = parse_markdown_to_tokens("# Hello")
    assert tokens == [MdToken(type="heading", content="Hello", level=1, markup="#")]


def test_h2() -> None:
    tokens = parse_markdown_to_tokens("## World")
    assert tokens == [MdToken(type="heading", content="World", level=2, markup="##")]


def test_h3_cyrillic() -> None:
    tokens = parse_markdown_to_tokens("### Привет мир")
    assert tokens == [MdToken(type="heading", content="Привет мир", level=3, markup="###")]


def test_heading_with_inline_bold_stripped() -> None:
    tokens = parse_markdown_to_tokens("# **Title**")
    assert tokens[0].content == "Title"


# ---------------------------------------------------------------------------
# Paragraphs — inline markup stripping
# ---------------------------------------------------------------------------


def test_paragraph_plain() -> None:
    tokens = parse_markdown_to_tokens("Simple text.")
    assert tokens == [MdToken(type="paragraph", content="Simple text.")]


def test_paragraph_bold_stripped() -> None:
    tokens = parse_markdown_to_tokens("**Bold** text")
    assert tokens[0].content == "Bold text"


def test_paragraph_italic_stripped() -> None:
    tokens = parse_markdown_to_tokens("_italic_ text")
    assert tokens[0].content == "italic text"


def test_paragraph_link_text_preserved() -> None:
    tokens = parse_markdown_to_tokens("[click here](http://example.com)")
    assert tokens[0].content == "click here"


def test_paragraph_code_inline_preserved() -> None:
    tokens = parse_markdown_to_tokens("Use `foo()` here")
    assert tokens[0].content == "Use foo() here"


def test_empty_paragraph_not_emitted() -> None:
    # markdown-it never emits a paragraph_open with no inline content,
    # but _parse_paragraph guards against it anyway
    tokens = parse_markdown_to_tokens("# A\n\n# B")
    assert all(t.type == "heading" for t in tokens)
    assert len(tokens) == 2


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


def test_table_headers_and_single_row() -> None:
    md = "| A | B |\n|---|---|\n| x | y |"
    tokens = parse_markdown_to_tokens(md)
    assert len(tokens) == 1
    assert tokens[0].type == "table"
    lines = tokens[0].content.split("\n")
    assert lines[0] == "A | B"
    assert lines[1] == "x | y"


def test_table_multirow() -> None:
    md = "| Param | Value |\n|---|---|\n| Hgb | 140 |\n| WBC | 6.5 |"
    tokens = parse_markdown_to_tokens(md)
    assert tokens[0].content.count("\n") == 2  # header + 2 data rows


def test_table_three_columns() -> None:
    md = "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |"
    tokens = parse_markdown_to_tokens(md)
    lines = tokens[0].content.split("\n")
    assert lines[0] == "A | B | C"
    assert lines[1] == "1 | 2 | 3"


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def test_bullet_list_items() -> None:
    tokens = parse_markdown_to_tokens("- item one\n- item two")
    assert tokens[0].type == "list"
    assert "- item one" in tokens[0].content
    assert "- item two" in tokens[0].content


def test_ordered_list_converted_to_bullet_format() -> None:
    tokens = parse_markdown_to_tokens("1. first\n2. second")
    assert tokens[0].type == "list"
    assert "- first" in tokens[0].content
    assert "- second" in tokens[0].content


def test_empty_list_not_emitted() -> None:
    # A list with no text content produces no token
    tokens = parse_markdown_to_tokens("- \n- ")
    assert tokens == [] or all(t.type != "list" for t in tokens)


def test_list_with_multiline_items() -> None:
    # Multi-line item (soft-wrapped) should stay as single bullet
    md = "- first line\n  continuation of first\n- second item"
    tokens = parse_markdown_to_tokens(md)
    assert tokens[0].type == "list"
    lines = tokens[0].content.split("\n")
    assert len(lines) == 2  # two items, not three
    assert "first line" in lines[0]
    assert "continuation" in lines[0]  # joined in one item


def test_nested_list_skipped() -> None:
    # Nested list should not break parent item parsing
    md = "- parent item\n  - nested child\n- next parent"
    tokens = parse_markdown_to_tokens(md)
    assert tokens[0].type == "list"
    lines = tokens[0].content.split("\n")
    assert len(lines) == 2  # two parent items
    assert "parent item" in lines[0]
    assert "next parent" in lines[1]
    # nested content should not appear at root level
    assert not any("nested child" in line for line in lines)


# ---------------------------------------------------------------------------
# Fence (code blocks)
# ---------------------------------------------------------------------------


def test_fence_content_and_language() -> None:
    tokens = parse_markdown_to_tokens("```python\nprint('hello')\n```")
    assert len(tokens) == 1
    assert tokens[0].type == "fence"
    assert "print('hello')" in tokens[0].content
    assert tokens[0].markup == "python"


def test_fence_no_language() -> None:
    tokens = parse_markdown_to_tokens("```\nsome code\n```")
    assert tokens[0].type == "fence"
    assert tokens[0].markup == ""


def test_empty_fence_not_emitted() -> None:
    tokens = parse_markdown_to_tokens("```\n```")
    assert tokens == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_string_returns_empty_list() -> None:
    assert parse_markdown_to_tokens("") == []


def test_mixed_content_preserves_order() -> None:
    md = "# Title\n\nSome text.\n\n- item"
    tokens = parse_markdown_to_tokens(md)
    assert [t.type for t in tokens] == ["heading", "paragraph", "list"]


def test_heading_followed_by_table() -> None:
    md = "## Results\n\n| X | Y |\n|---|---|\n| 1 | 2 |"
    tokens = parse_markdown_to_tokens(md)
    assert tokens[0].type == "heading"
    assert tokens[1].type == "table"


def test_multiple_headings_different_levels() -> None:
    md = "# H1\n\n## H2\n\n### H3"
    tokens = parse_markdown_to_tokens(md)
    assert [t.level for t in tokens] == [1, 2, 3]
    assert [t.markup for t in tokens] == ["#", "##", "###"]


# ---------------------------------------------------------------------------
# Inline: softbreak/hardbreak and mixed markup
# ---------------------------------------------------------------------------


def test_hardbreak_becomes_space() -> None:
    """Hardbreak (two spaces + newline) should become single space."""
    tokens = parse_markdown_to_tokens("a  \nb")
    assert tokens[0].content == "a b"


def test_softbreak_becomes_space() -> None:
    """Softbreak (newline in paragraph) should become space."""
    tokens = parse_markdown_to_tokens("a\nb")
    assert tokens[0].content == "a b"


def test_inline_mixed_bold_italic_link_text() -> None:
    """Multiple inline types: bold, italic, link, plain text."""
    tokens = parse_markdown_to_tokens("**A** _B_ [C](url) D")
    assert tokens[0].content == "A B C D"


def test_inline_code_preserved_with_markup() -> None:
    """Code with special chars should be preserved."""
    tokens = parse_markdown_to_tokens("`foo()` and `bar-baz`")
    assert tokens[0].content == "foo() and bar-baz"


# ---------------------------------------------------------------------------
# Tables: inline markup in cells
# ---------------------------------------------------------------------------


def test_table_cell_with_bold() -> None:
    """Bold in table cell should be stripped."""
    md = "| Label | Value |\n|---|---|\n| **Bold** | x |"
    tokens = parse_markdown_to_tokens(md)
    assert tokens[0].type == "table"
    assert "Bold | x" in tokens[0].content


def test_table_cell_with_link() -> None:
    """Link in table cell: only text preserved."""
    md = "| A | B |\n|---|---|\n| [link](url) | value |"
    tokens = parse_markdown_to_tokens(md)
    assert "link | value" in tokens[0].content


def test_table_cell_with_code() -> None:
    """Code in table cell should be preserved."""
    md = "| Param | Value |\n|---|---|\n| `foo()` | 1.34 |"
    tokens = parse_markdown_to_tokens(md)
    assert "foo() | 1.34" in tokens[0].content


def test_table_empty_cell_preserved() -> None:
    """Empty cell in table should preserve column alignment (with padding)."""
    md = "| A | B | C |\n|---|---|---|\n| 1 | | 3 |"
    tokens = parse_markdown_to_tokens(md)
    lines = tokens[0].content.split("\n")
    assert lines[1] == "1 |  | 3"  # empty cell has space padding


def test_table_all_empty_cells_in_row() -> None:
    """Row with all empty cells should still produce delimiters."""
    md = "| A | B |\n|---|---|\n| | |"
    tokens = parse_markdown_to_tokens(md)
    lines = tokens[0].content.split("\n")
    assert lines[1] == " | "


# ---------------------------------------------------------------------------
# Lists: inline emphasis in items
# ---------------------------------------------------------------------------


def test_list_item_with_bold() -> None:
    """Bold in list item should be stripped."""
    tokens = parse_markdown_to_tokens("- **Important**: note")
    assert tokens[0].content == "- Important: note"


def test_list_item_with_code() -> None:
    """Code in list item should be preserved."""
    tokens = parse_markdown_to_tokens("- Use `function()` here")
    assert tokens[0].content == "- Use function() here"


def test_list_items_with_mixed_markup() -> None:
    """Multiple items with various inline markup."""
    md = "- **A**: bold\n- _B_: italic\n- C: [link](url)"
    tokens = parse_markdown_to_tokens(md)
    lines = tokens[0].content.split("\n")
    assert len(lines) == 3
    assert "A: bold" in lines[0]
    assert "B: italic" in lines[1]
    assert "C: link" in lines[2]


# ---------------------------------------------------------------------------
# Ignored tokens: hr, html_block
# ---------------------------------------------------------------------------


def test_horizontal_rule_ignored() -> None:
    """Horizontal rule (---) should be ignored, not create token."""
    md = "# Heading\n\n---\n\nParagraph"
    tokens = parse_markdown_to_tokens(md)
    types = [t.type for t in tokens]
    assert types == ["heading", "paragraph"]
    assert all(t.type != "hr" for t in tokens)


def test_html_block_ignored_no_crash() -> None:
    """HTML block should be ignored gracefully."""
    md = "<div>HTML content</div>\n\nText"
    tokens = parse_markdown_to_tokens(md)
    # Should not crash; paragraph should be present
    assert any(t.type == "paragraph" and "Text" in t.content for t in tokens)


# ---------------------------------------------------------------------------
# Robustness: edge cases
# ---------------------------------------------------------------------------


def test_table_with_softbreak_in_cell() -> None:
    """Softbreak (without actual newline) in table cell becomes space."""
    # markdown-it: actual newline in cell creates new row; soft-wrap doesn't
    md = "| A |\n|---|\n| line1 line2 |"
    tokens = parse_markdown_to_tokens(md)
    assert tokens[0].type == "table"
    assert "line1 line2" in tokens[0].content


def test_deeply_nested_emphasis() -> None:
    """Nested emphasis should strip correctly."""
    tokens = parse_markdown_to_tokens("***bold italic***")
    assert tokens[0].content == "bold italic"


def test_link_with_special_chars_in_text() -> None:
    """Link text with special chars preserved."""
    tokens = parse_markdown_to_tokens("[click-here_123](url)")
    assert tokens[0].content == "click-here_123"

