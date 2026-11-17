"""Generate PDF documents from text content.

This module provides a PDF generator function that can be registered
with the OfficeController to handle "pdf" intent from natural language prompts.
"""

from pathlib import Path
from typing import Any

from fpdf import FPDF


def parse_markdown_content(content: str) -> list:
    """Parse markdown-style content into (style, text) tuples for PDF generation.

    Supports:
    - ## Headings
    - **bold** text
    - *italic* text
    - - bullet points
    - 1. numbered lists
    - Plain paragraphs
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
            paragraphs.append(("hr", ""))
            continue

        # Handle code blocks ``` ```
        if stripped.startswith("```") or stripped.startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                code_lines = []
                continue
            else:
                # End of code block
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
            # Map markdown level to PDF font size
            style_map = {
                1: ("Title", 20),
                2: ("Heading", 16),
                3: ("Heading", 14),
                4: ("Subheading", 12),
            }
            pdf_style, font_size = style_map.get(level, ("Body", 11))
            paragraphs.append((pdf_style, text, font_size))
            continue

        # Handle blockquotes > text
        if stripped.startswith("> "):
            text = stripped[2:].strip()
            paragraphs.append(("blockquote", text))
            continue

        # Handle table rows | cell | cell |
        table_row_match = re.match(r"^\|(.+?)\|(.+?)\|(.*)", stripped)
        if table_row_match:
            # This is a table row - we'll add it as a simple paragraph noting the table
            cells = [cell.strip() for cell in table_row_match.groups()]
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

        # Default paragraph
        paragraphs.append(("paragraph", stripped))

    return paragraphs


def generate_pdf(content: str, output_path: str | Path | None = None) -> Path:
    """Generate a PDF document from plain text content.
    
    Args:
        content: The text content to write to the PDF document.
        output_path: Optional output path. If not provided, 
            a default path based on content title will be used.
    
    Returns:
        Path to the generated PDF file.
    """
    pdf = FPDF()
    pdf.add_page()
    
    # Handle font deprecation - use helvetica as fallback
    try:
        pdf.set_font("Arial", size=11)
    except Exception:
        pdf.set_font("Helvetica", size=11)
    
    # Split content into lines and add each as a cell
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if i == 0:
            # First line as title (bold)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(200, 10, txt=line, ln=1, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Arial", size=11)
            pdf.cell(200, 10, txt=line, ln=1, new_x="LMARGIN", new_y="NEXT")
    
    # Determine output path
    if output_path is None:
        output_path = Path("output.pdf")
    else:
        output_path = Path(output_path)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    pdf.output(str(output_path))
    return output_path


def detect_intent(prompt: str) -> dict[str, Any]:
    """Detect if the prompt is requesting PDF generation.
    
    Args:
        prompt: The user's natural language input
    
    Returns:
        Dictionary with intent detection results
    """
    prompt_lower = prompt.lower().strip()
    
    # Check for PDF-related keywords
    pdf_keywords = ["pdf", "portable", "document", "write pdf", "create pdf"]
    
    score = sum(1 for kw in pdf_keywords if kw in prompt_lower)
    total_keywords = len(pdf_keywords)
    confidence = score / total_keywords if total_keywords > 0 else 0.0
    
    if confidence > 0.15:
        return {
            "intent": "pdf",
            "confidence": round(confidence, 2),
            "details": {"format": "pdf"},
            "raw_prompt": prompt,
        }
    
    return {
        "intent": "text",
        "confidence": 0.0,
        "details": {"format": "plain"},
        "raw_prompt": prompt,
    }
