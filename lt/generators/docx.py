"""Generate DOCX documents from text content.

This module provides a DOCX generator function that can be registered
with the OfficeController to handle "docx" intent from natural language prompts.
"""

from pathlib import Path
from typing import Any, Optional

from docx import Document
from docx.shared import Pt


def generate_docx(content: str, output_path: Optional[str | Path] = None) -> Path:
    """Generate a DOCX document from plain text content.
    
    Args:
        content: The text content to write to the DOCX document.
        output_path: Optional output path. If not provided, 
            a default path based on content title will be used.
    
    Returns:
        Path to the generated DOCX file.
    """
    doc = Document()
    
    # Setup default style
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)
    
    # Add title (first line)
    title_text = content.split("\n")[0] if content else "Document"
    title = doc.add_heading(title_text, level=1)
    
    # Add content paragraphs (remaining lines)
    lines = content.split("\n")
    for i, line in enumerate(lines[1:], 1):  # Skip the first line used as title
        if line.strip():
            paragraph = doc.add_paragraph(line.strip())
            paragraph.paragraph_format.space_after = Pt(6)
        else:
            doc.add_paragraph().paragraph_format.space_after = Pt(6)
    
    # Determine output path
    if output_path is None:
        output_path = Path("output.docx")
    else:
        output_path = Path(output_path)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    doc.save(str(output_path))
    return output_path


def generate_with_gpt(prompt: str, output_path: Optional[str | Path] = None) -> dict[str, Any]:
    """Generate a DOCX document using GPT for content creation.

    Note: This function uses the prompt directly as content since
    the GPT integration requires external AI service configuration.
    For standalone use, the prompt is used as the document content.

    Args:
        prompt: The user's natural language input describing what to generate.
        output_path: Optional output path. If not provided, uses "output.docx".

    Returns:
        Dictionary with generation results including the file path.
    """
    # Use the prompt as the generated content
    generated_content = prompt.strip()

    # Generate DOCX from the content
    generated_path = generate_docx(generated_content, output_path)

    return {
        "response": f"DOCX document generated: {generated_path}",
        "generated_path": str(generated_path),
        "generated_content": generated_content,
        "intent": "docx",
        "generation_method": "prompt",
    }


def docx_generator(prompt: str, intent_dict: dict[str, Any]) -> dict[str, Any]:
    """Generator function compatible with OfficeController's expected signature.
    
    The OfficeController calls generators with (prompt, intent_dict).
    This wrapper extracts the content from the prompt or intent details,
    generates the DOCX, and returns a response dictionary.
    
    Args:
        prompt: The user's natural language input
        intent_dict: The detected intent dictionary containing format, etc.
    
    Returns:
        Dictionary with generation results
    """
    # Extract content from prompt or use default
    # Try to get the actual content after the intent keywords
    prompt_lower = prompt.lower().strip()
    
    # Remove common docx-related keywords to get the actual content
    for kw in ["docx", "word", "document", "create doc", "write doc"]:
        prompt_lower = prompt_lower.replace(kw, "").strip()
    
    # Use the prompt as content, or extract details if available
    content = intent_dict.get("details", {}).get("topic", prompt).strip()
    if not content:
        content = prompt.strip()
    
    # Determine output path from intent details or use default
    output_path = intent_dict.get("details", {}).get("output_path")
    if output_path:
        output_path = Path(output_path)
    else:
        output_path = None
    
    # Generate the DOCX
    try:
        generated_path = generate_docx(content, output_path)
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
            "response": f"Error generating DOCX: {str(e)}",
            "intent": intent_dict.get("intent", "docx"),
            "error": str(e),
        }


def detect_intent(prompt: str) -> dict[str, Any]:
    """Detect if the prompt is requesting DOCX generation.
    
    Args:
        prompt: The user's natural language input
    
    Returns:
        Dictionary with intent detection results
    """
    prompt_lower = prompt.lower().strip()
    
    # Check for DOCX-related keywords (also defined in lt.intents.INTENT_KEYWORDS)
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