"""Generate study materials (cards, quizzes, summaries) from chunks.

Supports parallel API calls and progress tracking.
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from . import ai
from .chunker import Chunk

console = Console()
logger = logging.getLogger(__name__)

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


def _generate_flashcards_for_chunk(chunk: Chunk, per_chunk: int) -> list[Flashcard]:
    """Generate flashcards for a single chunk. Returns list of Flashcard."""
    n = per_chunk
    prompt = (
        f"Generate exactly {n} flashcards from this study material.\n\n"
        f"SOURCE: {chunk.source} (part {chunk.index})\n{chunk.text[:6000]}"
    )
    try:
        data = ai.extract_json(ai.complete(prompt, system=FLASHCARD_SYSTEM, temperature=0.4))
        if isinstance(data, dict):
            data = [data]
        cards = []
        for item in data[:n]:
            cards.append(Flashcard(item["question"], item["answer"], item.get("hint", "")))
        return cards
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Flashcard generation failed for {chunk.source}#{chunk.index}: {e}")
        return []


def _generate_quiz_for_chunk(chunk: Chunk, per_chunk: int) -> list[QuizQuestion]:
    """Generate quiz questions for a single chunk. Returns list of QuizQuestion."""
    prompt = (
        f"Write exactly {per_chunk} quiz questions from this study material.\n\n"
        f"SOURCE: {chunk.source} (part {chunk.index})\n{chunk.text[:6000]}"
    )
    try:
        data = ai.extract_json(ai.complete(prompt, system=QUIZ_SYSTEM, temperature=0.5))
        if isinstance(data, dict):
            data = [data]
        questions = []
        for item in data[:per_chunk]:
            questions.append(QuizQuestion(
                item["question"], item["options"], item["answer_index"], item.get("explanation", "")
            ))
        return questions
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Quiz generation failed for {chunk.source}#{chunk.index}: {e}")
        return []


def _generate_summary_for_chunk(chunk: Chunk) -> Summary | None:
    """Generate summary for a single chunk. Returns Summary or None."""
    prompt = f"Summarize this study material for learning.\n\nSOURCE: {chunk.source} (part {chunk.index})\n{chunk.text[:6000]}"
    try:
        data = ai.extract_json(ai.complete(prompt, system=SUMMARY_SYSTEM, temperature=0.5))
        return Summary(
            data.get("title", f"{chunk.source} #{chunk.index}"),
            data.get("summary", ""),
            data.get("key_points", []),
            data.get("analogy", ""),
            data.get("questions_to_test_yourself", []),
            data.get("notebooklm_prompt", ""),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Summary generation failed for {chunk.source}#{chunk.index}: {e}")
        return None


def _extract_concepts_for_chunk(chunk: Chunk) -> list[Concept]:
    """Extract concepts for a single chunk. Returns list of Concept."""
    prompt = (
        "Extract the core concepts from this study material. "
        f"SOURCE: {chunk.source} (part {chunk.index})\n{chunk.text[:6000]}"
    )
    try:
        data = ai.extract_json(ai.complete(prompt, system=CONCEPT_SYSTEM, temperature=0.4))
        items = data if isinstance(data, list) else [data]
        concepts = []
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
        return concepts
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Concept extraction failed for {chunk.source}#{chunk.index}: {e}")
        return _fallback_concepts(chunk)


def generate_flashcards(chunks: list[Chunk], per_chunk: int = 6, progress: bool = True,
                        max_workers: int | None = None) -> list[Flashcard]:
    """Generate flashcards from chunks, optionally in parallel."""
    if not chunks:
        return []

    # For small chunk counts, don't bother with parallelism
    if len(chunks) <= 2 or max_workers == 1:
        return _generate_flashcards_sequential(chunks, per_chunk, progress)

    cards = []
    failed = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        disable=not progress,
    ) as pbar:
        task = pbar.add_task("Generating flashcards", total=len(chunks))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_generate_flashcards_for_chunk, chunk, per_chunk): chunk
                for chunk in chunks
            }
            for future in as_completed(futures):
                chunk = futures[future]
                try:
                    result = future.result()
                    cards.extend(result)
                except Exception as e:
                    failed += 1
                    logger.warning(f"Chunk {chunk.source}#{chunk.index} failed: {e}")
                pbar.advance(task)

    if progress:
        console.print(f"[green]Generated {len(cards)} flashcards[/green]")
        if failed:
            console.print(f"[yellow]{failed} chunks failed[/yellow]")
    return cards


def _generate_flashcards_sequential(chunks: list[Chunk], per_chunk: int, progress: bool) -> list[Flashcard]:
    """Sequential fallback for small chunk counts."""
    cards = []
    failed = 0
    for chunk in chunks:
        try:
            result = _generate_flashcards_for_chunk(chunk, per_chunk)
            cards.extend(result)
        except Exception as e:
            failed += 1
            if progress:
                console.print(f"  [yellow]warn: chunk {chunk.source}#{chunk.index}: {e}[/yellow]")
    if progress:
        console.print(f"[green]Generated {len(cards)} flashcards[/green]")
    return cards


def generate_quiz(chunks: list[Chunk], num_questions: int = 10, progress: bool = True,
                  max_workers: int | None = None) -> list[QuizQuestion]:
    """Generate quiz questions from chunks, optionally in parallel."""
    if not chunks:
        return []

    per = max(1, num_questions // max(1, len(chunks)))

    if len(chunks) <= 2 or max_workers == 1:
        return _generate_quiz_sequential(chunks, per, progress)

    qs = []
    failed = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        disable=not progress,
    ) as pbar:
        task = pbar.add_task("Generating quiz", total=len(chunks))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_generate_quiz_for_chunk, chunk, per): chunk
                for chunk in chunks
            }
            for future in as_completed(futures):
                chunk = futures[future]
                try:
                    result = future.result()
                    qs.extend(result)
                except Exception as e:
                    failed += 1
                    logger.warning(f"Chunk {chunk.source}#{chunk.index} failed: {e}")
                pbar.advance(task)

    if progress:
        console.print(f"[green]Generated {len(qs)} quiz questions[/green]")
        if failed:
            console.print(f"[yellow]{failed} chunks failed[/yellow]")
    return qs


def _generate_quiz_sequential(chunks: list[Chunk], per: int, progress: bool) -> list[QuizQuestion]:
    """Sequential fallback for small chunk counts."""
    qs = []
    failed = 0
    for chunk in chunks:
        try:
            result = _generate_quiz_for_chunk(chunk, per)
            qs.extend(result)
        except Exception as e:
            failed += 1
            if progress:
                console.print(f"  [yellow]warn: chunk {chunk.source}#{chunk.index}: {e}[/yellow]")
    if progress:
        console.print(f"[green]Generated {len(qs)} quiz questions[/green]")
    return qs


def generate_summaries(chunks: list[Chunk], progress: bool = True,
                       max_workers: int | None = None) -> list[Summary]:
    """Generate summaries from chunks, optionally in parallel."""
    if not chunks:
        return []

    if len(chunks) <= 2 or max_workers == 1:
        return _generate_summaries_sequential(chunks, progress)

    out = []
    failed = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        disable=not progress,
    ) as pbar:
        task = pbar.add_task("Generating summaries", total=len(chunks))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_generate_summary_for_chunk, chunk): chunk
                for chunk in chunks
            }
            for future in as_completed(futures):
                chunk = futures[future]
                try:
                    result = future.result()
                    if result:
                        out.append(result)
                except Exception as e:
                    failed += 1
                    logger.warning(f"Chunk {chunk.source}#{chunk.index} failed: {e}")
                pbar.advance(task)

    if progress:
        console.print(f"[green]Generated {len(out)} summaries[/green]")
        if failed:
            console.print(f"[yellow]{failed} chunks failed[/yellow]")
    return out


def _generate_summaries_sequential(chunks: list[Chunk], progress: bool) -> list[Summary]:
    """Sequential fallback for small chunk counts."""
    out = []
    failed = 0
    for chunk in chunks:
        try:
            result = _generate_summary_for_chunk(chunk)
            if result:
                out.append(result)
        except Exception as e:
            failed += 1
            if progress:
                console.print(f"  [yellow]warn: chunk {chunk.source}#{chunk.index}: {e}[/yellow]")
    if progress:
        console.print(f"[green]Generated {len(out)} summaries[/green]")
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


def extract_concepts(chunks: list[Chunk], progress: bool = True,
                     max_workers: int | None = None) -> list[Concept]:
    """Extract concepts from chunks, optionally in parallel."""
    if not chunks:
        return []

    if len(chunks) <= 2 or max_workers == 1:
        return _extract_concepts_sequential(chunks, progress)

    all_concepts: list[Concept] = []
    failed = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        disable=not progress,
    ) as pbar:
        task = pbar.add_task("Extracting concepts", total=len(chunks))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_extract_concepts_for_chunk, chunk): chunk
                for chunk in chunks
            }
            for future in as_completed(futures):
                chunk = futures[future]
                try:
                    result = future.result()
                    all_concepts.extend(result)
                except Exception as e:
                    failed += 1
                    logger.warning(f"Chunk {chunk.source}#{chunk.index} failed: {e}")
                pbar.advance(task)

    # Deduplicate
    deduped: list[Concept] = []
    seen = set()
    for concept in all_concepts:
        key = (concept.name.lower(), concept.source.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(concept)

    if progress:
        console.print(f"[green]Extracted {len(deduped)} concepts[/green]")
        if failed:
            console.print(f"[yellow]{failed} chunks failed[/yellow]")
    return deduped


def _extract_concepts_sequential(chunks: list[Chunk], progress: bool) -> list[Concept]:
    """Sequential fallback for small chunk counts."""
    concepts: list[Concept] = []
    for chunk in chunks:
        try:
            result = _extract_concepts_for_chunk(chunk)
            concepts.extend(result)
        except Exception as e:
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
        console.print(f"[green]Extracted {len(deduped)} concepts[/green]")
    return deduped


def save_json(obj, name: str) -> Path:
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def to_dict_list(cards) -> list:
    return [asdict(c) for c in cards]