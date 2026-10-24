"""Export flashcards to Anki TSV."""
import logging
from pathlib import Path
from ..generate import Flashcard

logger = logging.getLogger(__name__)


def write_anki(cards: list[Flashcard], path: Path) -> None:
    """Write flashcards as a TSV file for Anki import."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [card.to_anki() for card in cards]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"Wrote {len(cards)} flashcards to {path}")
