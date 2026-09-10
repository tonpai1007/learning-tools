"""Generate an HTML study guide (concepts, formulas, exam patterns) from study sources.

Supports parallel API calls and progress tracking.
"""
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from . import ai
from .chunker import Chunk

console = Console()
logger = logging.getLogger(__name__)

# System prompts for the AI study-guide pipeline -------------------------------

CONCEPT_SYSTEM = (
    "You are a study-guide writer. From the study material, extract the most important "
    "concepts. Return ONLY valid JSON: a list of objects with keys "
    '"name", "definition", "why_it_matters". '
    "Keep definitions precise and exam-focused. No markdown, no commentary."
)

FORMULA_SYSTEM = (
    "You are a study-guide writer. From the study material, extract every key formula "
    "or equation. Return ONLY valid JSON: a list of objects with keys "
    '"name", "formula", "symbols" (string explaining each symbol), "when_to_use". '
    "No markdown, no commentary."
)

WORKED_EXAMPLE_SYSTEM = (
    "You are a study-guide writer. From the study material, build ONE representative "
    "worked example that shows how to apply the core formulas. "
    "Return ONLY valid JSON: an object with keys "
    '"title", "givens" (list of strings), "steps" (list of step-by-step strings), '
    '"answer", "exam_tip". No markdown, no commentary.'
)

PRACTICE_SYSTEM = (
    "You are a study-guide writer. From the study material, write practice questions "
    "that mirror typical exam problems. Return ONLY valid JSON: a list of objects with keys "
    '"question" (the full problem statement), "hint", "answer" (the full solution). '
    "No markdown, no commentary."
)

FLASHCARD_SYSTEM = (
    "You extract factual knowledge from study material. "
    "Return ONLY valid JSON: a list of objects with keys "
    '"question", "answer", "hint". Questions must be answerable from the text alone. '
    "No markdown, no commentary."
)

QUICK_FACTS_SYSTEM = (
    "You are a study-guide writer. From the study material, extract a list of quick "
    "memory-aid facts that students should remember before an exam. "
    "Return ONLY valid JSON: a list of short strings (max 2 sentences each). "
    "No markdown, no commentary."
)


# Data classes -----------------------------------------------------------------

@dataclass
class ConceptEntry:
    name: str
    definition: str
    why_it_matters: str


@dataclass
class FormulaEntry:
    name: str
    formula: str
    symbols: str
    when_to_use: str


@dataclass
class WorkedExample:
    title: str
    givens: list[str]
    steps: list[str]
    answer: str
    exam_tip: str


@dataclass
class PracticeQuestion:
    question: str
    hint: str
    answer: str


@dataclass
class ChapterGuide:
    title: str
    concepts: list[ConceptEntry]
    formulas: list[FormulaEntry]
    worked_example: WorkedExample | None
    practice: list[PracticeQuestion]
    quick_facts: list[str]


# Helpers ----------------------------------------------------------------------

def _safe_get_text(chunk: Chunk, limit: int = 6000) -> str:
    """Return a cleaned, bounded slice of a chunk for prompting."""
    text = chunk.text[:limit]
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or "[empty chunk]"


def _ask(prompt: str, system: str, temperature: float = 0.4):
    """Wrapper around ai.complete that returns parsed JSON."""
    raw = ai.complete(prompt, system=system, temperature=temperature)
    return ai.extract_json(raw)


def _extract_list(data):
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


# Per-chapter generation -------------------------------------------------------

def _build_concepts(chunks: list[Chunk]) -> list[ConceptEntry]:
    """Ask the AI for the most important concepts across the chapter chunks."""
    concepts: list[ConceptEntry] = []
    # Sample up to 3 chunks to keep context manageable
    sampled = chunks[:3]
    for chunk in sampled:
        prompt = (
            "Extract the most important exam-relevant concepts from this study material. "
            "Focus on definitions and distinctions a student must know.\n\n"
            f"SOURCE: {chunk.source} (part {chunk.index})\n{_safe_get_text(chunk)}"
        )
        try:
            data = _ask(prompt, CONCEPT_SYSTEM)
            for item in _extract_list(data):
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                concepts.append(ConceptEntry(
                    name=name,
                    definition=str(item.get("definition") or "").strip(),
                    why_it_matters=str(item.get("why_it_matters") or "").strip(),
                ))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Concepts for {chunk.source}#{chunk.index}: {e}")

    # Deduplicate by name
    seen = set()
    deduped = []
    for c in concepts:
        key = c.name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def _build_formulas(chunks: list[Chunk]) -> list[FormulaEntry]:
    formulas: list[FormulaEntry] = []
    sampled = chunks[:3]
    for chunk in sampled:
        prompt = (
            "Extract every key formula/equation a student needs for an exam from this "
            "material. Include the formula, symbol meanings, and when to use it.\n\n"
            f"SOURCE: {chunk.source} (part {chunk.index})\n{_safe_get_text(chunk)}"
        )
        try:
            data = _ask(prompt, FORMULA_SYSTEM)
            for item in _extract_list(data):
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                formulas.append(FormulaEntry(
                    name=name,
                    formula=str(item.get("formula") or "").strip(),
                    symbols=str(item.get("symbols") or "").strip(),
                    when_to_use=str(item.get("when_to_use") or "").strip(),
                ))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Formulas for {chunk.source}#{chunk.index}: {e}")

    seen = set()
    deduped = []
    for f in formulas:
        key = (f.name.lower(), f.formula.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    return deduped


def _build_worked_example(chunks: list[Chunk]) -> WorkedExample | None:
    if not chunks:
        return None
    chunk = chunks[0]  # use the first/only chapter chunk for the worked example
    prompt = (
        "Create ONE representative worked example that ties together the main formulas "
        "from this study material. Make it realistic and step-by-step, similar to an exam "
        "problem.\n\n"
        f"SOURCE: {chunk.source} (part {chunk.index})\n{_safe_get_text(chunk)}"
    )
    try:
        data = _ask(prompt, WORKED_EXAMPLE_SYSTEM, temperature=0.5)
        if not isinstance(data, dict):
            return None
        return WorkedExample(
            title=str(data.get("title") or "Worked Example"),
            givens=[str(g) for g in data.get("givens") or []][:8],
            steps=[str(s) for s in data.get("steps") or []][:15],
            answer=str(data.get("answer") or ""),
            exam_tip=str(data.get("exam_tip") or ""),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Worked example: {e}")
        return None


def _build_practice(chunks: list[Chunk], num: int = 4) -> list[PracticeQuestion]:
    practice: list[PracticeQuestion] = []
    sampled = chunks[:2]
    target = num // max(1, len(sampled))
    for chunk in sampled:
        if target <= 0:
            break
        prompt = (
            f"Write exactly {target} exam-style practice problems from this study "
            "material, with full solutions. The problems should test the key formulas "
            "and concepts a student must know.\n\n"
            f"SOURCE: {chunk.source} (part {chunk.index})\n{_safe_get_text(chunk)}"
        )
        try:
            data = _ask(prompt, PRACTICE_SYSTEM, temperature=0.6)
            for item in _extract_list(data):
                question = str(item.get("question") or "").strip()
                if not question:
                    continue
                practice.append(PracticeQuestion(
                    question=question,
                    hint=str(item.get("hint") or ""),
                    answer=str(item.get("answer") or ""),
                ))
                if len(practice) >= num:
                    break
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Practice for {chunk.source}#{chunk.index}: {e}")
    return practice[:num]


def _build_quick_facts(chunks: list[Chunk]) -> list[str]:
    facts: list[str] = []
    sampled = chunks[3:] if len(chunks) > 3 else chunks  # use remaining chunks
    if not sampled:
        sampled = chunks[:1]
    for chunk in sampled[:2]:
        prompt = (
            "Extract quick memory-aid facts a student must memorize before an exam "
            "from this study material. Keep each to 1-2 short sentences.\n\n"
            f"SOURCE: {chunk.source} (part {chunk.index})\n{_safe_get_text(chunk)}"
        )
        try:
            data = _ask(prompt, QUICK_FACTS_SYSTEM)
            if isinstance(data, list):
                facts.extend(str(x).strip() for x in data if str(x).strip())
            elif isinstance(data, dict):
                for key in ("facts", "items", "quick_facts"):
                    vals = data.get(key)
                    if isinstance(vals, list):
                        facts.extend(str(x).strip() for x in vals if str(x).strip())
                        break
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Quick facts for {chunk.source}#{chunk.index}: {e}")

    seen = set()
    deduped = []
    for f in facts:
        if f.lower() in seen:
            continue
        seen.add(f.lower())
        deduped.append(f)
    return deduped


# Parallel chapter builder -----------------------------------------------------

def _build_chapter_guide_parallel(args: tuple) -> ChapterGuide:
    """Build a single chapter guide. Takes a tuple for ThreadPoolExecutor compatibility."""
    chunks, title, num_practice = args
    return _build_chapter_guide_internal(chunks, title, num_practice)


def _build_chapter_guide_internal(chunks: list[Chunk], title: str | None = None,
                                   num_practice: int = 4) -> ChapterGuide:
    """Build a full ChapterGuide from a set of chunks belonging to one source."""
    guide_title = title or (chunks[0].source if chunks else "Study Guide")

    concepts = _build_concepts(chunks)
    formulas = _build_formulas(chunks)
    example = _build_worked_example(chunks)
    practice = _build_practice(chunks, num=num_practice)
    quick_facts = _build_quick_facts(chunks)

    return ChapterGuide(
        title=guide_title,
        concepts=concepts,
        formulas=formulas,
        worked_example=example,
        practice=practice,
        quick_facts=quick_facts,
    )


# Public API -------------------------------------------------------------------

def build_chapter_guide(chunks: list[Chunk], title: str | None = None,
                        num_practice: int = 4) -> ChapterGuide:
    """Build a full ChapterGuide from a set of chunks belonging to one source."""
    return _build_chapter_guide_internal(chunks, title, num_practice)


def build_guides(chunks: list[Chunk],
                  group_by: str = "source",
                  num_practice: int = 4,
                  max_workers: int | None = None) -> list[ChapterGuide]:
    """Group chunks by source name and build one ChapterGuide per group.

    With group_by="source" (the default) each source file becomes one chapter,
    matching the typical 'one PDF per chapter' setup.

    If max_workers is set, builds guides in parallel.
    """
    groups: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        groups.setdefault(chunk.source, []).append(chunk)

    if not groups:
        return []

    # For small numbers of groups, don't bother with parallelism
    if len(groups) <= 1 or max_workers == 1:
        guides = []
        for source, group_chunks in groups.items():
            console.print(f"  [cyan]Building guide for '{source}'...[/cyan]")
            guides.append(_build_chapter_guide_internal(group_chunks, title=source, num_practice=num_practice))
        return guides

    # Parallel execution
    guides = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as pbar:
        task = pbar.add_task("Building study guides", total=len(groups))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _build_chapter_guide_internal,
                    group_chunks,
                    source,
                    num_practice,
                ): source
                for source, group_chunks in groups.items()
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    guide = future.result()
                    guides.append(guide)
                except Exception as e:
                    logger.warning(f"Guide for '{source}' failed: {e}")
                    guides.append(ChapterGuide(
                        title=source,
                        concepts=[],
                        formulas=[],
                        worked_example=None,
                        practice=[],
                        quick_facts=[],
                    ))
                pbar.advance(task)

    return guides


def to_dict_list(guides: list[ChapterGuide]) -> list[dict]:
    return [asdict(g) for g in guides]


# HTML rendering ---------------------------------------------------------------

def _esc(value) -> str:
    return html.escape(str(value))


def _render_concepts(concepts: list[ConceptEntry]) -> str:
    if not concepts:
        return "<p><em>No concepts extracted.</em></p>"
    rows = []
    for c in concepts:
        rows.append(
            "<tr>"
            f"<td><strong>{_esc(c.name)}</strong></td>"
            f"<td>{_esc(c.definition)}</td>"
            f"<td>{_esc(c.why_it_matters)}</td>"
            "</tr>"
        )
    return (
        "<h3>Key Concepts</h3>"
        "<table><tr><th>Concept</th><th>Definition</th><th>Why It Matters</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _render_formulas(formulas: list[FormulaEntry]) -> str:
    if not formulas:
        return ""
    rows = []
    for f in formulas:
        rows.append(
            "<tr>"
            f"<td><strong>{_esc(f.name)}</strong></td>"
            f"<td class='formula'>{_esc(f.formula)}</td>"
            f"<td>{_esc(f.symbols)}</td>"
            f"<td>{_esc(f.when_to_use)}</td>"
            "</tr>"
        )
    return (
        "<h3>Key Formulas</h3>"
        "<table><tr><th>Name</th><th>Formula</th><th>Symbols</th><th>When to Use</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _render_worked_example(ex: WorkedExample | None) -> str:
    if ex is None:
        return ""
    givens = "".join(f"<li>{_esc(g)}</li>" for g in ex.givens) or "<li>—</li>"
    steps = "".join(f"<li>{_esc(s)}</li>" for s in ex.steps) or "<li>—</li>"
    return (
        "<h3>Worked Example</h3>"
        f"<h4>{_esc(ex.title)}</h4>"
        "<p><strong>Given:</strong></p><ul>" + givens + "</ul>"
        "<p><strong>Steps:</strong></p><ol>" + steps + "</ol>"
        f"<div class='answer-box'><strong>Answer:</strong> {_esc(ex.answer)}</div>"
        f"<div class='tip-box'><strong>Exam tip:</strong> {_esc(ex.exam_tip)}</div>"
    )


def _render_practice(practice: list[PracticeQuestion]) -> str:
    if not practice:
        return ""
    blocks = []
    for i, p in enumerate(practice, 1):
        blocks.append(
            "<div class='practice'>"
            f"<p><strong>{i}. {_esc(p.question)}</strong></p>"
            f"<details><summary>Hint</summary><p>{_esc(p.hint)}</p></details>"
            f"<details><summary>Solution</summary><p>{_esc(p.answer)}</p></details>"
            "</div>"
        )
    return "<h3>Practice Problems</h3>" + "".join(blocks)


def _render_quick_facts(facts: list[str]) -> str:
    if not facts:
        return ""
    items = "".join(f"<li>{_esc(f)}</li>" for f in facts)
    return "<h3>Quick Memory Aids</h3><ul class='facts'>" + items + "</ul>"


def render_html(guides: list[ChapterGuide], title: str = "Study Guide") -> Path:
    """Render the guides to a polished, printable HTML file in the output dir."""
    chapter_html = []
    for idx, guide in enumerate(guides, 1):
        chapter_html.append(
            "<section>"
            f"<h2>{idx}. {_esc(guide.title)}</h2>"
            + _render_concepts(guide.concepts)
            + _render_formulas(guide.formulas)
            + _render_worked_example(guide.worked_example)
            + _render_practice(guide.practice)
            + _render_quick_facts(guide.quick_facts)
            + "</section>"
        )

    page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>""" + _esc(title) + """</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f4f6f9; color: #1a1a2e; line-height: 1.6; margin: 0; }
  .container { max-width: 1000px; margin: 0 auto; padding: 20px; }
  header { background: linear-gradient(135deg, #1a1a2e, #0f3460); color: white; padding: 36px 20px; text-align: center; }
  header h1 { margin: 0 0 6px; }
  header p { opacity: .85; margin: 0; }
  section { background: white; border-radius: 12px; padding: 28px; margin: 22px 0; box-shadow: 0 2px 10px rgba(0,0,0,.06); }
  h2 { color: #0f3460; border-bottom: 3px solid #e94560; padding-bottom: 8px; }
  h3 { color: #16213e; margin: 22px 0 8px; }
  h4 { color: #e94560; margin: 12px 0 6px; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: .95em; }
  th { background: #0f3460; color: white; padding: 8px; text-align: left; }
  td { padding: 8px; border-bottom: 1px solid #eee; vertical-align: top; }
  tr:nth-child(even) { background: #f8f9fc; }
  .formula { font-family: 'Cambria Math', Georgia, serif; font-size: 1.05em; white-space: pre-wrap; }
  .answer-box { background: #d4edda; border-left: 4px solid #28a745; padding: 10px 14px; margin: 10px 0; border-radius: 0 6px 6px 0; }
  .tip-box { background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px 14px; margin: 10px 0; border-radius: 0 6px 6px 0; }
  .practice { border: 1px solid #ddd; border-radius: 8px; padding: 14px; margin: 12px 0; background: #fafbfe; }
  details { margin: 6px 0; }
  summary { cursor: pointer; font-weight: 600; color: #0f3460; }
  ul.facts li { margin: 6px 0; }
  @media print { body { background: white; } section { box-shadow: none; border: 1px solid #ddd; page-break-inside: avoid; } header { color: black; background: white; } }
</style>
</head>
<body>
<header>
  <h1>📚 """ + _esc(title) + """</h1>
  <p>Generated by learning-tools — concepts, formulas, worked examples, and practice</p>
</header>
<div class="container">
""" + "\n".join(chapter_html) + """
<footer style="text-align:center;color:#888;padding:24px;">
  <p>Good luck with your exam! 🍀</p>
</footer>
</div>
</body>
</html>"""

    from .config import cfg
    out_path = cfg.output_dir / "study_guide.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    console.print(f"[green]Study guide -> {out_path}[/green]  (open in your browser)")
    return out_path