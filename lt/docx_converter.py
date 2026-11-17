"""
Backward compatibility bridge.
Canonical location is now `lt.converters.docx`.
"""
from .converters.docx import HTMLToDocxConverter, extract_docx_context, insert_docx_picture

__all__ = ["HTMLToDocxConverter", "extract_docx_context", "insert_docx_picture"]
