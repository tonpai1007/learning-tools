"""Converters package for learning-tools (HTML to DOCX, PDF text extraction, thesis MD to DOCX)."""
from .docx import HTMLToDocxConverter, extract_docx_context, insert_docx_picture
from .pdf import extract_pdf_to_text
from .thesis_docx import convert_thesis_md

__all__ = [
    "HTMLToDocxConverter",
    "extract_docx_context",
    "insert_docx_picture",
    "extract_pdf_to_text",
    "convert_thesis_md",
]
