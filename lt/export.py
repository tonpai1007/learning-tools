"""Export study materials: Anki TSV, HTML quiz, markdown summaries, NotebookLM source pack."""
import html
import re
from pathlib import Path

from rich.console import Console

from .generate import Concept, Flashcard, QuizQuestion, Summary

console = Console()


def write_anki(cards: list[Flashcard], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("#separator:tab\n#html:true\n#tags column:4\n")
        for c in cards:
            f.write(c.to_anki() + "\tlearnforge\n")
    console.print(f"[green]Anki deck -> {path}[/green]  (import into Anki: File > Import)")


def write_quiz(questions: list[QuizQuestion], path: Path) -> None:
    rows = []
    for i, q in enumerate(questions, 1):
        opts = "".join(
            f'<label class="opt"><input type="radio" name="q{i}" value="{j}">'
            f"{html.escape(o)}</label>"
            for j, o in enumerate(q.options)
        )
        rows.append(
            f"<div class='q' data-answer='{q.answer_index}'>"
            f"<p><b>{i}. {html.escape(q.question)}</b></p>{opts}"
            f"<p class='expl'>{html.escape(q.explanation)}</p></div>"
        )
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Practice Quiz</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#222}}
.q{{border-bottom:1px solid #ddd;padding:1rem 0}}
.opt{{display:block;margin:.3rem 0;padding:.4rem;border:1px solid #ddd;border-radius:6px;cursor:pointer}}
.opt:hover{{background:#f5f5f5}}
.expl{{display:none;color:#0a5}}
.correct{{background:#d4edda!important;border-color:#8fd19e}}
.wrong{{background:#f8d7da!important;border-color:#f1aeb5}}
button{{margin:1.5rem 0;padding:.7rem 1.4rem;font-size:1rem;border:none;border-radius:8px;background:#0a5;color:#fff;cursor:pointer}}
#score{{font-weight:bold;font-size:1.1rem}}
</style></head><body><h1>Practice Quiz</h1>
{''.join(rows)}
<button onclick="grade()">Grade my answers</button><div id="score"></div>
<script>
function grade(){{let score=0,total=0;document.querySelectorAll('.q').forEach(q=>{{
total++;const sel=q.querySelector('input:checked');
const expl=q.querySelector('.expl');
if(sel){{const ok=+sel.value===+q.dataset.answer;
score+=ok?1:0;sel.parentElement.classList.add(ok?'correct':'wrong');
if(!ok){{const r=q.querySelectorAll('input')[q.dataset.answer];r.parentElement.classList.add('correct');}}}}
expl.style.display='block';}});
document.getElementById('score').textContent=`You scored ${{score}} / ${{total}}`;}}
</script></body></html>"""
    path.write_text(page, encoding="utf-8")
    console.print(f"[green]Quiz -> {path}[/green]  (open in your browser)")


def write_summaries(summaries: list[Summary], path: Path) -> None:
    lines = [f"# Study Summaries ({len(summaries)} chunks)", ""]
    for s in summaries:
        lines += [f"## {s.title}", "", s.summary, "", "**Key points:**"]
        lines += [f"- {p}" for p in s.key_points]
        lines += ["", f"**Analogy:** {s.analogy}", "", "**Test yourself:**"]
        lines += [f"- {q}" for q in s.questions_to_test_yourself]
        lines += ["", "---", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]Summaries -> {path}[/green]")


def write_notebooklm_pack(summaries: list[Summary], path: Path) -> None:
    """One text file per chunk, plus a master prompt file. Drop these into NotebookLM."""
    pack = path / "notebooklm_sources"
    pack.mkdir(parents=True, exist_ok=True)
    master = []
    for s in summaries:
        fname = f"{path.name}_{summaries.index(s) + 1}.md".replace(" ", "_")
        (pack / fname).write_text(
            f"# {s.title}\n\n{s.summary}\n\n{s.notebooklm_prompt}\n", encoding="utf-8"
        )
        master.append(f"- {fname}: {s.summary}")
    (pack / "_master_prompt.md").write_text(
        "# Upload the files in this folder to NotebookLM as sources, then:\n"
        "1. Ask questions about the material.\n"
        "2. Generate an Audio Overview (it will sound like a podcast).\n"
        "3. Ask it to quiz you in a chat.\n\n" + "\n".join(master),
        encoding="utf-8",
    )
    console.print(f"[green]NotebookLM pack -> {pack}[/green]")


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\s-]", "", value.lower()).strip()
    return re.sub(r"\s+", "-", value)


def write_vault_bundle(summaries: list[Summary], concepts: list[Concept], root: Path) -> None:
    """Write a cleaned, vault-friendly bundle under a root folder.

    Structure:
      root/01_Active_Outputs/summary.md
      root/03_Concepts/concept.md
    """
    root.mkdir(parents=True, exist_ok=True)
    out_dir = root / "01_Active_Outputs"
    concept_dir = root / "03_Concepts"
    out_dir.mkdir(parents=True, exist_ok=True)
    concept_dir.mkdir(parents=True, exist_ok=True)

    for s in summaries:
        slug = _slugify(s.title) or "summary"
        summary_path = out_dir / f"{slug}.md"
        key_points = "\n".join(f"- {p}" for p in s.key_points)
        test_qs = "\n".join(f"- {q}" for q in s.questions_to_test_yourself)
        summary_path.write_text(
            "# " + s.title + "\n\n"
            + s.summary + "\n\n"
            + "## Key points\n" + key_points + "\n\n"
            + "## Analogy\n" + s.analogy + "\n\n"
            + "## Test yourself\n" + test_qs + "\n\n"
            + "## NotebookLM prompt\n" + s.notebooklm_prompt + "\n",
            encoding="utf-8",
        )

    for c in concepts:
        concept_path = concept_dir / f"{_slugify(c.name) or 'concept'}.md"
        related = "\n".join(f"- {term}" for term in c.related_terms)
        concept_body = (
            f"# {c.name}\n\n"
            f"**Definition:** {c.definition}\n\n"
            f"**Confidence:** {c.confidence:.2f}\n\n"
            f"**Related terms:**\n{related or '- none'}\n\n"
            f"**Source:** {c.source or 'unknown'}\n"
        )
        concept_path.write_text(concept_body, encoding="utf-8")

    console.print(f"[green]Vault bundle -> {root}[/green]")
