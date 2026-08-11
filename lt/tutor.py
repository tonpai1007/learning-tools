"""RAG tutor: retrieves relevant chunks and answers in Socratic style."""
import re
from collections import Counter

from rich.console import Console
from rich.markdown import Markdown

from . import ai
from .chunker import Chunk

console = Console()

TUTOR_SYSTEM = """You are a patient Socratic tutor. Use ONLY the provided study material to answer.
- Cite which source(s) you used.
- If the material doesn't answer the question, say so and suggest what to read.
- After answering, ask ONE follow-up question to check understanding."""


def _tokenize(text: str) -> Counter:
    return Counter(re.findall(r"[a-z0-9']+", text.lower()))


def _rank_chunks(query: str, chunks: list[Chunk], k: int) -> list[Chunk]:
    q = _tokenize(query)
    scored = []
    for c in chunks:
        overlap = sum(min(q[w], n) for w, n in _tokenize(c.text).items() if w in q)
        bonus = 1.0 if c.title.split()[0].lower() in query.lower() else 0.0
        scored.append((overlap + bonus, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:k]]


class Tutor:
    def __init__(self, chunks: list[Chunk], k: int | None = None):
        self.chunks = chunks
        self.k = k or 6
        self.history: list[dict] = []

    def ask(self, question: str) -> str:
        context_chunks = _rank_chunks(question, self.chunks, self.k)
        context = "\n\n".join(f"[{c.source}, part {c.index}]\n{c.text}" for c in context_chunks)
        self.history.append({"role": "user", "content": question})
        messages = [
            {"role": "system", "content": TUTOR_SYSTEM + "\n\nSTUDY MATERIAL:\n" + context},
            *self.history[-10:],
        ]
        answer = ai.chat(messages, temperature=0.6)
        self.history.append({"role": "assistant", "content": answer})
        return answer


def run_interactive(chunks: list[Chunk], k: int | None = None) -> None:
    tutor = Tutor(chunks, k)
    console.print("[cyan]Tutor ready. Commands:[/cyan] exit | sources | topics\n")
    while True:
        try:
            q = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            break
        if q.lower() in {"sources", "topics"}:
            names = sorted({c.source for c in chunks})
            console.print("Loaded sources:")
            for n in names:
                console.print(f"  - {n}")
            continue
        console.print("[dim]thinking...[/dim]")
        answer = tutor.ask(q)
        console.print(Markdown(answer))
        print()
