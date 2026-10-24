"""Export study materials to DOCX."""
from pathlib import Path
from ..converters.docx import HTMLToDocxConverter


def write_docx(
    html_path: str | Path,
    output_docx_path: str | Path | None = None,
    enable_ai: bool = False,
    custom_ai_instructions: str | None = None
) -> Path:
    """Convert an HTML study guide or report to a styled DOCX document."""
    return HTMLToDocxConverter.convert(
        html_path=html_path,
        output_docx_path=output_docx_path,
        enable_ai=enable_ai,
        custom_ai_instructions=custom_ai_instructions,
    )
