"""
Backward compatibility bridge.
Canonical location is now `lt.converters.docx`.
"""
from .converters.docx import HTMLToDocxConverter

__all__ = ["HTMLToDocxConverter"]
