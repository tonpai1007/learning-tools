"""PDF extraction tools."""
from __future__ import annotations

from pathlib import Path


def extract_pdf_to_text(pdf_path: str | Path, output_txt_path: str | Path | None = None) -> str:
    """Extract full text and metadata from a PDF file."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    import pdfplumber

    lines: list[str] = [
        f"FILE: {pdf_path}",
    ]
    with pdfplumber.open(pdf_path) as pdf:
        lines.append(f"TOTAL PAGES: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or "[NO TEXT - image page]"
            images = page.images
            lines.append(f"\n{'='*60}")
            lines.append(f"PAGE {i+1} (images: {len(images)})")
            lines.append(f"{'='*60}")
            lines.append(text)

    full_text = "\n".join(lines)
    if output_txt_path:
        out_p = Path(output_txt_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(full_text, encoding="utf-8")

    return full_text
