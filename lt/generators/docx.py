"""Generate DOCX documents from text content.

This module provides a DOCX generator function that can be registered
with the OfficeController to handle "docx" intent from natural language prompts.
Supports markdown-style formatting: headings, bold, italic, bullets, numbered lists.
"""

from pathlib import Path

from docx import Document
from docx.shared import Pt


def parse_markdown_content(content: str) -> list:
    """Parse markdown-style content into (style, text) tuples.

    Supports:
    - ## Headings
    - **bold** text
    - *italic* text
    - - bullet points
    - 1. numbered lists
    - Plain paragraphs
    - Tables: | header | header | row 2 |
    - Code blocks: ```code```
    - Blockquotes: > text
    - Horizontal rules: ---

    Returns:
        List of (style, text) tuples.
    """
    import re

    paragraphs = []
    lines = content.split("\n")
    in_code_block = False
    code_lines = []

    for line in lines:
        stripped = line.strip()

        # Handle horizontal rules (--- on its own line)
        if re.match(r"^---$", stripped):
            paragraphs.append(("horizontal_rule", ""))
            continue

        # Handle code blocks ``` ````
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                code_lines = []
                continue
            else:
                # End of code block - add as code paragraph
                code_text = "\n".join(code_lines)
                paragraphs.append(("code", code_text))
                code_lines = []
                continue

        if in_code_block:
            code_lines.append(stripped)
            continue

        if not stripped:
            paragraphs.append(("paragraph", ""))
            continue

        # Handle headings ## through ######
        heading_match = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            style_map = {1: "heading_1", 2: "heading_2", 3: "heading_3"}
            paragraphs.append((style_map.get(level, "paragraph"), text))
            continue

        # Handle blockquotes > text
        if stripped.startswith("> "):
            text = stripped[2:].strip()
            paragraphs.append(("blockquote", text))
            continue

        # Handle table rows | cell | cell |
        # Table row format: | cell1 | cell2 | cell3 |
        # Regex: must start with |, has content between pipes, ends with |
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            cells = [c for c in cells if c]
            if cells:
                paragraphs.append(("table_row", cells))
                continue

        # Handle bullet points - or *
        if stripped.startswith("- ") or stripped.startswith("* "):
            paragraphs.append(("bullet", stripped[2:]))
            continue

        # Handle numbered lists 1. 2. etc.
        numbered_match = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if numbered_match:
            paragraphs.append(("numbered", stripped))
            continue

        # Handle bold **text**
        bold_match = re.match(r"^\*\*(.+?)\*\*", stripped)
        if bold_match:
            paragraphs.append(("bold", bold_match.group(1).strip()))
            continue

        # Handle italic *text* (but not **bold**)
        # Check for single asterisks not part of double asterisks
        if not bold_match:
            italic_match = re.match(r"^\*(?!\*)(.*?)\*(?!\*)$", stripped)
            if italic_match:
                inner = italic_match.group(1).strip()
                paragraphs.append(("italic", inner))
                continue

        # Default: plain paragraph
        paragraphs.append(("paragraph", stripped))

    return paragraphs


def apply_style_to_paragraph(doc: Document, style: str, text: str) -> None:
    """Apply a style to a paragraph in the DOCX document.

    Supported styles:
    - heading_1: docx heading level 1
    - heading_2: docx heading level 2
    - heading_3: docx heading level 3
    - bold: bold text
    - italic: italic text
    - bullet: list bullet style
    - numbered: list number style
    - paragraph: plain paragraph (default)
    """
    if style == "heading_1":
        doc.add_heading(text, level=1)
    elif style == "heading_2":
        doc.add_heading(text, level=2)
    elif style == "heading_3":
        doc.add_heading(text, level=3)
    elif style == "bold":
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
    elif style == "italic":
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.italic = True
    elif style == "bullet":
        p = doc.add_paragraph(text, style="List Bullet")
    elif style == "numbered":
        p = doc.add_paragraph(text, style="List Number")
    else:
        p = doc.add_paragraph(text)
        if p.runs:
            p.runs[0].font.name = "Calibri"
            p.runs[0].font.size = Pt(11)


def _next_output_path(base_name: str = "output_docx", ext: str = ".docx") -> Path:
    """Return the next available deterministic output path."""
    n = 0
    while True:
        candidate = Path(f"{base_name}{f'_{n}' if n else ''}{ext}")
        if not candidate.exists():
            return candidate
        n += 1


def docx_generator(prompt: str, intent_dict=None, output_path=None) -> dict:
    """Generate a DOCX document from a prompt and intent dict.

    intent_dict may be a dict (controller contract), a Path/str treated as the
    output path, or None. output_path may also be passed as a keyword.
    """
    # Normalize intent_dict: accept dict, Path/str (treated as output_path), or None
    if intent_dict is None:
        intent_dict = {}
    elif isinstance(intent_dict, (str, Path)):
        if output_path is None:
            output_path = Path(intent_dict)
        intent_dict = {}
    elif not isinstance(intent_dict, dict):
        intent_dict = {}

    content = intent_dict.get("details", {}).get("topic", prompt).strip()
    if not content:
        content = prompt.strip()
    if output_path is None:
        output_path = intent_dict.get("details", {}).get("output_path")
    output_path = Path(output_path) if output_path else None
    try:
        # Parse markdown-style content
        paragraphs = parse_markdown_content(content)

        # Create DOCX document
        doc = Document()

        # Buffer consecutive table rows into real docx tables
        table_rows: list = []

        def flush_table() -> None:
            nonlocal table_rows
            if not table_rows:
                return
            col_count = max(len(r) for r in table_rows)
            t = doc.add_table(rows=len(table_rows), cols=col_count)
            t.style = "Table Grid"
            for r_i, row in enumerate(table_rows):
                for c_i in range(col_count):
                    cell = t.cell(r_i, c_i)
                    cell.text = row[c_i] if c_i < len(row) else ""
            table_rows = []

        for style, text in paragraphs:
            if style == "table_row":
                table_rows.append(text)
                continue
            flush_table()
            apply_style_to_paragraph(doc, style, text)
        flush_table()

        # Save document
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output_path))
            generated_path = output_path
        else:
            generated_path = _next_output_path()
            generated_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(generated_path))

        return {
            "response": f"DOCX document generated: {generated_path}",
            "intent": intent_dict.get("intent", "docx"),
            "generated_path": str(generated_path),
            "intent_key": "docx",
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Generator error for docx intent: {e}")
        return {
            "response": f"Error generating DOCX: {e!s}",
            "intent": intent_dict.get("intent", "docx"),
            "error": str(e),
        }


def detect_intent(prompt: str) -> dict:
    """Detect if the prompt is requesting DOCX generation."""
    prompt_lower = prompt.lower().strip()
    docx_keywords = ["docx", "word", "document", "create doc", "write doc"]
    score = sum(1 for kw in docx_keywords if kw in prompt_lower)
    total_keywords = len(docx_keywords)
    confidence = score / total_keywords if total_keywords > 0 else 0.0
    if confidence > 0.15:
        return {
            "intent": "docx",
            "confidence": round(confidence, 2),
            "details": {"format": "docx"},
            "raw_prompt": prompt,
        }
    return {
        "intent": "text",
        "confidence": 0.0,
        "details": {"format": "plain"},
        "raw_prompt": prompt,
    }


generate_docx = docx_generator