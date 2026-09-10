"""Export generated study materials to various formats."""
import logging
from pathlib import Path

from .config import cfg
from .generate import Flashcard, QuizQuestion, Summary

logger = logging.getLogger(__name__)


def write_anki(cards: list[Flashcard], path: Path) -> None:
    """Write flashcards as a TSV file for Anki import."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [card.to_anki() for card in cards]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"Wrote {len(cards)} flashcards to {path}")


def write_quiz(questions: list[QuizQuestion], path: Path) -> None:
    """Write quiz questions as an HTML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>Quiz</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;max-width:800px;margin:40px auto;padding:0 20px}",
        ".q{background:#f8f9fa;border-radius:8px;padding:16px;margin:16px 0}",
        ".opt{margin:4px 0}",
        ".exp{display:none;background:#e8f5e9;padding:8px;border-radius:4px;margin-top:8px}",
        "button{background:#1976d2;color:#fff;border:0;padding:6px 12px;border-radius:4px;cursor:pointer}",
        "</style></head><body>",
        "<h1>Practice Quiz</h1>",
    ]
    for i, q in enumerate(questions, 1):
        html_parts.append(f"<div class='q'><p><strong>Q{i}. {q.question}</strong></p>")
        for j, opt in enumerate(q.options):
            html_parts.append(f"<div class='opt'>{chr(65+j)}. {opt}</div>")
        html_parts.append(
            f"<button onclick=\"this.nextElementSibling.style.display='block'\">Show Answer</button>"
        )
        html_parts.append(
            f"<div class='exp'><strong>Answer: {chr(65+q.answer_index)}</strong><br>{q.explanation}</div>"
        )
        html_parts.append("</div>")
    html_parts.append("</body></html>")
    path.write_text("\n".join(html_parts), encoding="utf-8")
    logger.info(f"Wrote {len(questions)} quiz questions to {path}")


def write_summaries(summaries: list[Summary], path: Path) -> None:
    """Write summaries as a Markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = ["# Summaries\n"]
    for s in summaries:
        parts.append(f"## {s.title}\n")
        parts.append(f"{s.summary}\n")
        if s.key_points:
            parts.append("**Key Points:**")
            for kp in s.key_points:
                parts.append(f"- {kp}")
            parts.append("")
        if s.analogy:
            parts.append(f"**Analogy:** {s.analogy}\n")
        if s.questions_to_test_yourself:
            parts.append("**Test Yourself:**")
            for q in s.questions_to_test_yourself:
                parts.append(f"- {q}")
            parts.append("")
    path.write_text("\n".join(parts), encoding="utf-8")
    logger.info(f"Wrote {len(summaries)} summaries to {path}")


def write_notebooklm_pack(summaries: list[Summary], output_dir: Path) -> None:
    """Write a NotebookLM source pack (per-chunk text + master prompt)."""
    pack_dir = output_dir / "notebooklm_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(summaries):
        text_path = pack_dir / f"chunk_{i:03d}.txt"
        text_path.write_text(
            f"# {s.title}\n\n{s.summary}\n\n"
            + "\n".join(f"- {kp}" for kp in s.key_points) + "\n",
            encoding="utf-8",
        )
    master = pack_dir / "_master_prompt.md"
    prompts = [s.notebooklm_prompt for s in summaries if s.notebooklm_prompt]
    master.write_text(
        "# NotebookLM Source Pack\n\n"
        + "Use these prompts to generate an audio overview for each chunk:\n\n"
        + "\n\n".join(f"## Chunk {i}\n{p}" for i, p in enumerate(prompts)),
        encoding="utf-8",
    )
    logger.info(f"Wrote NotebookLM pack to {pack_dir}")


def write_vault_bundle(summaries: list[Summary], concepts: list, vault_dir: Path) -> None:
    """Write summaries and concepts to a vault directory structure."""
    # Write summaries
    outputs_dir = vault_dir / "01_Active_Outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    for s in summaries:
        slug = s.title.lower().replace(" ", "_").replace("-", "_")
        summary_file = outputs_dir / f"{slug}.md"
        summary_file.write_text(
            f"# {s.title}\n\n{s.summary}\n\n"
            + "\n".join(f"- {kp}" for kp in s.key_points) + "\n",
            encoding="utf-8",
        )

    # Write concepts
    concepts_dir = vault_dir / "03_Concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    for c in concepts:
        slug = c.name.lower().replace(" ", "_").replace("-", "_")
        concept_file = concepts_dir / f"{slug}.md"
        concept_file.write_text(
            f"# {c.name}\n\n{c.definition}\n\n"
            f"**Related:** {', '.join(c.related_terms)}\n\n"
            f"**Confidence:** {c.confidence}\n\n"
            f"**Source:** {c.source}\n",
            encoding="utf-8",
        )
    logger.info(f"Wrote vault bundle to {vault_dir}")
