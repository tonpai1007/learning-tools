"""RAG tutor: retrieves relevant chunks, invokes MDIE deterministic physics, and answers in Socratic style."""
import re
from collections import Counter

from rich.console import Console
from rich.markdown import Markdown

from . import ai
from .chunker import Chunk
from .integrations.mdie import MDIEPhysicsClient

console = Console()

TUTOR_SYSTEM = """You are a patient Socratic engineering tutor. Use the provided study material and verified deterministic physics calculations to answer.
- Cite which source(s) you used.
- When verified physics calculations from MDIE are present, reference those exact numbers and formulas (do not guess or hallucinate numerical stress/deflection values).
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
        self.physics = MDIEPhysicsClient()

    def ask(self, question: str) -> str:
        # Check for deterministic physics calculations from MDIE
        physics_context = self.physics.query_physics_hook(question)

        context_chunks = _rank_chunks(question, self.chunks, self.k)
        context_parts = []
        if physics_context:
            context_parts.append(physics_context)
        if context_chunks:
            context_parts.append("\n\n".join(f"[{c.source}, part {c.index}]\n{c.text}" for c in context_chunks))
        context = "\n\n".join(context_parts)

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
    console.print("[cyan]Tutor ready. Commands:[/cyan] exit | sources | topics | solve <chair|tower|girder|query>\n")
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
        if q.lower().startswith("solve") or q.lower().startswith("/solve"):
            parts = q.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "chair"
            phys_res = tutor.physics.query_physics_hook(target)
            if not phys_res and target in ["chair", "tower", "girder"]:
                res_dict = tutor.physics.solve_3d_fea(target)
                phys_res = (
                    f"3D FEA Direct Stiffness ({target.upper()}):\n"
                    f"Max Von Mises: {res_dict.get('max_von_mises_mpa'):.1f} MPa\n"
                    f"Max Displacement: {res_dict.get('max_displacement_mm'):.2f} mm\n"
                    f"Min Safety Factor: {res_dict.get('min_safety_factor'):.2f}\n"
                    f"Passed: {res_dict.get('passed')}"
                )
            console.print(f"[bold cyan]MDIE Solver Result:[/bold cyan]\n{phys_res or 'No physics match'}\n")
            continue
        console.print("[dim]thinking...[/dim]")
        answer = tutor.ask(q)
        console.print(Markdown(answer))
        print()
