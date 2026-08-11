"""Generate study materials (cards, quizzes, summaries) from chunks."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console

from . import ai
from .chunker import Chunk

console = Console()

FLASHCARD_SYSTEM = (
    "You extract factual knowledge from study material. "
    "Return ONLY valid JSON: a list of objects with keys "
    '"question", "answer", "hint". Questions must be answerable from the text alone. '
    "No markdown, no commentary."
)

QUIZ_SYSTEM = (
    "You write practice quiz questions testing deep understanding. "
    "Return ONLY valid JSON: a list of objects with keys "
    '"question", "options" (4 strings, one correct), "answer_index" (0-3), "explanation". '
    "No markdown, no commentary."
)

SUMMARY_SYSTEM = (
    "You are a study summarizer. Return ONLY valid JSON with keys "
    '"title", "summary" (2-4 sentences), "key_points" (list of short strings), '
    '"analogy" (a memorable real-world analogy), "questions_to_test_yourself" (list of 3 questions), '
    '"notebooklm_prompt" (a short instruction for generating an audio overview from this chunk). '
    "No markdown, no commentary."
)

CONCEPT_SYSTEM = (
    "You extract core concepts from study material. Return ONLY valid JSON: "
    "a list of objects with keys 'name', 'definition', 'related_terms' (list), 'confidence' (float 0-1). "
    "Keep names short and precise. No markdown, no commentary."
)


@dataclass
class Flashcard:
    question: str
    answer: str
    hint: str = ""

    def to_anki(self) -> str:
        def esc(v):
            return str(v).replace("\t", " ").replace("\n", "<br>")

        return f"{esc(self.question)}\t{esc(self.answer)}\t{esc(self.hint)}"


@dataclass
class QuizQuestion:
    question: str
    options: list
    answer_index: int
    explanation: str


@dataclass
class Summary:
    title: str
    summary: str
    key_points: list
    analogy: str
    questions_to_test_yourself: list
    notebooklm_prompt: str


@dataclass
class Concept:
    name: str
    definition: str
    related_terms: list[str]
    confidence: float = 0.0
    source: str = ""


def _batched(chunks, n):
    for i in range(0, len(chunks), n):
        yield chunks[i:i + n]


def generate_flashcards(chunks, per_chunk=6, progress=True) -> list[Flashcard]:
    cards, failed = [], 0
    for chunk in chunks:
        n = per_chunk
        prompt = (
            f"Generate exactly {n} flashcards from this study material.\n\n"
            f"SOURCE: {chunk.source} (part {chunk.index})\n{chunk.text[:6000]}"
        )
        try:
            data = ai.extract_json(ai.complete(prompt, system=FLASHCARD_SYSTEM, temperature=0.4))
            if isinstance(data, dict):
                data = [data]
            for item in data[:n]:
                cards.append(Flashcard(item["question"], item["answer"], item.get("hint", "")))
        except Exception as e:  # noqa: BLE001
            failed += 1
            if progress:
                console.print(f"  [yellow]warn: chunk {chunk.source}#{chunk.index}: {e}[/yellow]")
    if progress:
        console.print(f"[green]generated {len(cards)} flashcards[/green]")
    return cards


def generate_quiz(chunks, num_questions=10, progress=True) -> list[QuizQuestion]:
    qs, failed = [], 0
    per = max(1, num_questions // max(1, len(chunks)))
    for chunk in chunks:
        prompt = (
            f"Write exactly {per} quiz questions from this study material.\n\n"
            f"SOURCE: {chunk.source} (part {chunk.index})\n{chunk.text[:6000]}"
        )
        try:
            data = ai.extract_json(ai.complete(prompt, system=QUIZ_SYSTEM, temperature=0.5))
            if isinstance(data, dict):
                data = [data]
            for item in data[:per]:
                qs.append(QuizQuestion(item["question"], item["options"], item["answer_index"], item.get("explanation", "")))
        except Exception as e:  # noqa: BLE001
            failed += 1
            if progress:
                console.print(f"  [yellow]warn: chunk {chunk.source}#{chunk.index}: {e}[/yellow]")
    if progress:
        console.print(f"[green]generated {len(qs)} quiz questions[/green]")
    return qs


def generate_summaries(chunks, progress=True) -> list[Summary]:
    out, failed = [], 0
    for chunk in chunks:
        prompt = f"Summarize this study material for learning.\n\nSOURCE: {chunk.source} (part {chunk.index})\n{chunk.text[:6000]}"
        try:
            data = ai.extract_json(ai.complete(prompt, system=SUMMARY_SYSTEM, temperature=0.5))
            out.append(Summary(
                data.get("title", f"{chunk.source} #{chunk.index}"),
                data.get("summary", ""),
                data.get("key_points", []),
                data.get("analogy", ""),
                data.get("questions_to_test_yourself", []),
                data.get("notebooklm_prompt", ""),
            ))
        except Exception as e:  # noqa: BLE001
            failed += 1
            if progress:
                console.print(f"  [yellow]warn: chunk {chunk.source}#{chunk.index}: {e}[/yellow]")
    if progress:
        console.print(f"[green]generated {len(out)} summaries[/green]")
    return out


def _fallback_concepts(chunk: Chunk) -> list[Concept]:
    text = chunk.text
    candidates = []
    for match in sorted(set(__import__('re').findall(r"\b[A-Z][A-Za-z0-9_\-]{2,}\b", text))):
        if len(match) < 4:
            continue
        candidates.append(match)
    if not candidates:
        tokens = [t.strip(".,;:!?()[]{}\"'") for t in text.replace("\n", " ").split() if len(t) > 4]
        candidates = sorted(set(tokens))[:5]

    concepts = []
    for name in candidates[:5]:
        concepts.append(Concept(
            name=name,
            definition=f"Key concept discussed in {chunk.source}.",
            related_terms=[chunk.source],
            confidence=0.5,
            source=chunk.source,
        ))
    return concepts


def extract_concepts(chunks, progress=True) -> list[Concept]:
    concepts: list[Concept] = []
    for chunk in chunks:
        prompt = (
            "Extract the core concepts from this study material. "
            f"SOURCE: {chunk.source} (part {chunk.index})\n{chunk.text[:6000]}"
        )
        try:
            data = ai.extract_json(ai.complete(prompt, system=CONCEPT_SYSTEM, temperature=0.4))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                concepts.append(Concept(
                    name=name,
                    definition=str(item.get("definition") or "").strip(),
                    related_terms=[str(t) for t in (item.get("related_terms") or [])][:6],
                    confidence=float(item.get("confidence") or 0.5),
                    source=chunk.source,
                ))
        except Exception as e:  # noqa: BLE001
            if progress:
                console.print(f"  [yellow]warn: concept extraction failed for {chunk.source}#{chunk.index}: {e}[/yellow]")
            concepts.extend(_fallback_concepts(chunk))

    deduped: list[Concept] = []
    seen = set()
    for concept in concepts:
        key = (concept.name.lower(), concept.source.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(concept)

    if progress:
        console.print(f"[green]generated {len(deduped)} concepts[/green]")
    return deduped


def save_json(obj, name: str) -> Path:
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def to_dict_list(cards) -> list:
    return [asdict(c) for c in cards]
