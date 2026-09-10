"""Read learning material from the sources/ folder into plain text."""
import re
from pathlib import Path

from .config import cfg

PDF = (".pdf",)
TEXT = (".md", ".txt", ".markdown", ".rst")
HTML = (".html", ".htm")
DOCX = (".docx",)


class Source:
    def __init__(self, path: Path):
        self.path = path

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    def read(self) -> str:
        try:
            if self.extension in PDF:
                return self._read_pdf()
            if self.extension in DOCX:
                return self._read_docx()
            if self.extension in HTML:
                return self._read_html()
            if self.extension in TEXT:
                return self.path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Failed to read {self.path}: {e}") from e
        raise ValueError(f"Unsupported file type: {self.extension}")

    def _read_pdf(self) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(self.path))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            pages.append(f"\n--- [page {i}] ---\n{text}")

        joined = "\n".join(pages)
        # If pypdf found little or no text (scanned/image PDF), fall back to pdfplumber.
        if len(joined.strip()) < 100:
            try:
                import pdfplumber

                pages = []
                with pdfplumber.open(str(self.path)) as pdf:
                    for i, page in enumerate(pdf.pages, 1):
                        text = page.extract_text() or "[scanned image page - no text layer]"
                        pages.append(f"\n--- [page {i}] ---\n{text}")
                fallback = "\n".join(pages)
                if len(fallback.strip()) > len(joined.strip()):
                    return fallback
            except Exception:
                pass  # keep the pypdf result if pdfplumber also fails
        return joined

    def _read_docx(self) -> str:
        from docx import Document

        doc = Document(str(self.path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    def _read_html(self) -> str:
        text = self.path.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()


def list_sources(extra_paths=None) -> list[Source]:
    sources = []
    for d in [cfg.sources_dir, *(extra_paths or [])]:
        d = Path(d)
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix.lower() in PDF + TEXT + HTML + DOCX:
                sources.append(Source(p))
    return sources


def ingest(extra_paths=None, verbose=True) -> list[Source]:
    sources = list_sources(extra_paths)
    if verbose:
        for s in sources:
            size = len(s.read())
            print(f"  + {s.path.name} ({size:,} chars)")
    if not sources and verbose:
        print("  (no files found - drop PDFs / .md / .txt / .docx into sources/)")
    return sources
