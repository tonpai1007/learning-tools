"""Split ingested text into overlapping knowledge chunks."""
import re
from dataclasses import dataclass

from .config import cfg

SPLIT_RE = re.compile(r"(?m)^\s*#{1,3}\s.*$|^\s*[-*]\s|^---\s*\[page", re.M)


@dataclass
class Chunk:
    source: str
    index: int
    text: str

    @property
    def title(self) -> str:
        first = next((l.strip() for l in self.text.splitlines() if l.strip()), "") or f"{self.source}#{self.index}"
        return first[:70]


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(text: str, source: str, chunk_tokens: int | None = None, overlap: int | None = None) -> list[Chunk]:
    csize = chunk_tokens or cfg.chunker().get("chunk_tokens", 1200)
    ov = overlap or cfg.chunker().get("overlap_tokens", 120)
    block = csize
    step = max(1, block - ov)

    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    merged = []
    cur = ""
    for p in paragraphs:
        if cur and _approx_tokens(cur) + _approx_tokens(p) > block:
            merged.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        merged.append(cur)

    chunks = []
    for i, para in enumerate(merged):
        if _approx_tokens(para) <= block:
            chunks.append(Chunk(source, i + 1, para))
            continue
        for j in range(0, len(para), step):
            piece = para[j:j + block]
            if len(piece) > 80:
                chunks.append(Chunk(source, i + 1, piece))
    return chunks


def chunk_sources(sources: list, **kw) -> list[Chunk]:
    chunks = []
    for s in sources:
        text = s.read()
        chunks.extend(chunk_text(text, s.name, **kw))
    return chunks
