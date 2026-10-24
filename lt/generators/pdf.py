"""Generate PDF documents from text content.

This module provides a PDF generator function that can be registered
with the OfficeController to handle "pdf" intent from natural language prompts.
"""

from pathlib import Path
from typing import Any, Optional

from fpdf import FPDF


def generate_pdf(content: str, output_path: Optional[str | Path] = None) -> Path:
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