"""Generate Markdown documents from text content.

This module provides a Markdown generator function that can be registered
with the OfficeController to handle "markdown" intent from natural language prompts.
"""

from pathlib import Path
from typing import Any, Optional


def generate_md(content: str, output_path: Optional[str | Path] = None) -> Path:
    """Generate a Markdown document from text content.
    
    Args:
        content: The text content to write to the Markdown document.
        output_path: Optional output path. If not provided, 
            a default path based on content title will be used.
    
    Returns:
        Path to the generated Markdown file.
    """
    # Handle empty content
    if not content or not content.strip():
        content = "# Document\n\n"
    
    # If content starts with #, treat as already formatted
    lines = content.split("\n")
    first_line = lines[0].strip()
    
    md_lines = []
    
    if first_line.startswith("#"):
        # Content already has markdown formatting
        md_lines = lines
    else:
        # Add title as heading
        title = lines[0] if lines else "Document"
        md_lines.append(f"# {title}")
        # Add remaining lines as paragraphs
        for line in lines[1:]:
            stripped = line.strip()
            if stripped:
                md_lines.append(stripped)
            else:
                md_lines.append("")
    
    # Determine output path
    if output_path is None:
        output_path = Path("output.md")
    else:
        output_path = Path(output_path)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write markdown content
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    
    return output_path


def detect_intent(prompt: str) -> dict[str, Any]:
    """Detect if the prompt is requesting Markdown generation.
    
    Args:
        prompt: The user's natural language input
    
    Returns:
        Dictionary with intent detection results
    """
    prompt_lower = prompt.lower().strip()
    
    # Check for Markdown-related keywords
    md_keywords = ["markdown", "md", "mark", "readme", "write md"]
    
    score = sum(1 for kw in md_keywords if kw in prompt_lower)
    total_keywords = len(md_keywords)
    confidence = score / total_keywords if total_keywords > 0 else 0.0
    
    if confidence > 0.15:
        return {
            "intent": "markdown",
            "confidence": round(confidence, 2),
            "details": {"format": "markdown"},
            "raw_prompt": prompt,
        }
    
    return {
        "intent": "text",
        "confidence": 0.0,
        "details": {"format": "plain"},
        "raw_prompt": prompt,
    }