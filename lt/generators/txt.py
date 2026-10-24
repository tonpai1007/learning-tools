"""Generate TXT (plain text) documents from text content.

This module provides a TXT generator function that can be registered
with the OfficeController to handle "txt" intent from natural language prompts.
"""

from pathlib import Path
from typing import Any, Optional


def generate_txt(content: str, output_path: Optional[str | Path] = None) -> Path:
    """Generate a TXT document from plain text content.
    
    Args:
        content: The text content to write to the TXT document.
        output_path: Optional output path. If not provided, 
            a default path based on content title will be used.
    
    Returns:
        Path to the generated TXT file.
    """
    # Determine output path
    if output_path is None:
        output_path = Path("output.txt")
    else:
        output_path = Path(output_path)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write content to file
    output_path.write_text(content, encoding='utf-8')
    return output_path


def detect_intent(prompt: str) -> dict[str, Any]:
    """Detect if the prompt is requesting TXT generation.
    
    Args:
        prompt: The user's natural language input
    
    Returns:
        Dictionary with intent detection results
    """
    prompt_lower = prompt.lower().strip()
    
    # Check for TXT-related keywords
    txt_keywords = ["txt", "text", "plain", "write file", "save as"]
    
    score = sum(1 for kw in txt_keywords if kw in prompt_lower)
    total_keywords = len(txt_keywords)
    confidence = score / total_keywords if total_keywords > 0 else 0.0
    
    if confidence > 0.15:
        return {
            "intent": "txt",
            "confidence": round(confidence, 2),
            "details": {"format": "txt"},
            "raw_prompt": prompt,
        }
    
    return {
        "intent": "text",
        "confidence": 0.0,
        "details": {"format": "plain"},
        "raw_prompt": prompt,
    }