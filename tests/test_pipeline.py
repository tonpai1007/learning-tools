"""Pipeline smoke test with a mocked AI backend (no API key needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lt.ai as ai  # noqa: E402
from lt import export, generate  # noqa: E402
from lt.chunker import chunk_sources  # noqa: E402
from lt.config import cfg  # noqa: E402
from lt.generate import Concept, Summary  # noqa: E402
from lt.ingest import list_sources  # noqa: E402

FLASH = [{
    "question": "What are the 4 stages of the water cycle?",
    "answer": "Evaporation, condensation, precipitation, collection",
    "hint": "Think EC-PC",
}]
QUIZ = [{
    "question": "Which stage forms clouds?",
    "options": ["Condensation", "Evaporation", "Precipitation", "Collection"],
    "answer_index": 0,
    "explanation": "Condensation turns vapor into cloud droplets",
}]
SUMM = {
    "title": "Water Cycle",
    "summary": "Water moves through 4 stages.",
    "key_points": ["Evaporation uses solar energy"],
    "analogy": "A boiling kettle",
    "questions_to_test_yourself": ["What is transpiration?"],
    "notebooklm_prompt": "Explain the water cycle like a nature podcast.",
}
CONCEPTS = [{
    "name": "Condensation",
    "definition": "The process where water vapor cools and forms droplets.",
    "related_terms": ["clouds", "water cycle"],
    "confidence": 0.91,
}]


def fake_complete(prompt, system="", temperature=None):
    if "factual knowledge" in system:
        return str(FLASH).replace("'", '"')
    if "study summarizer" in system:
        return str(SUMM).replace("'", '"')
    if "extract core concepts" in system.lower():
        return str(CONCEPTS).replace("'", '"')
    return str(QUIZ).replace("'", '"')


def test_write_vault_bundle(tmp_path):
    summaries = [Summary(
        title="Water Cycle",
        summary="Water moves through repeated stages.",
        key_points=["Evaporation", "Condensation"],
        analogy="A loop",
        questions_to_test_yourself=["What drives evaporation?"],
        notebooklm_prompt="Explain the cycle.",
    )]
    concepts = [Concept(
        name="Condensation",
        definition="The process where vapor cools into droplets.",
        related_terms=["clouds", "water cycle"],
        confidence=0.91,
        source="sample_notes.md",
    )]

    export.write_vault_bundle(summaries, concepts, tmp_path / "vault")
    summary_file = tmp_path / "vault" / "01_Active_Outputs" / "water_cycle.md"
    concept_file = tmp_path / "vault" / "03_Concepts" / "condensation.md"
    assert summary_file.exists()
    assert concept_file.exists()
    assert "Condensation" in concept_file.read_text(encoding="utf-8")
    assert "Water Cycle" in summary_file.read_text(encoding="utf-8")


def main():
    ai.complete = fake_complete
    chunks = chunk_sources(list_sources())
    assert chunks, "no chunks"
    cards = generate.generate_flashcards(chunks, per_chunk=2, progress=False)
    assert cards, "no cards"
    export.write_anki(cards, cfg.output_dir / "flashcards.tsv")
    qs = generate.generate_quiz(chunks, num_questions=4, progress=False)
    assert qs, "no quiz"
    export.write_quiz(qs, cfg.output_dir / "quiz.html")
    sums = generate.generate_summaries(chunks, progress=False)
    assert sums, "no summaries"
    export.write_summaries(sums, cfg.output_dir / "summaries.md")
    export.write_notebooklm_pack(sums, cfg.output_dir)
    concepts = generate.extract_concepts(chunks, progress=False)
    assert concepts, "no concepts"
    assert concepts[0].name == "Condensation"
    export.write_vault_bundle(sums, concepts, cfg.output_dir / "vault_preview")
    print("PIPELINE OK:", len(cards), "cards,", len(qs), "quiz,", len(sums), "summaries,", len(concepts), "concepts")
    for f in ("flashcards.tsv", "quiz.html", "summaries.md", "notebooklm_sources/_master_prompt.md"):
        p = cfg.output_dir / f
        assert p.exists() and p.stat().st_size > 0, f
        print("  +", p)


if __name__ == "__main__":
    main()
