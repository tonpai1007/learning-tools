"""Progress tracker + SM-2 spaced repetition scheduler."""
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import cfg
from .generate import Concept, Flashcard

console = Console()

GRADES = {"1": ("again", 0), "2": ("hard", 1), "3": ("good", 2), "4": ("easy", 3)}


class SRS:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else cfg.data_dir / "cards.json"
        self.cards = self._load()

    def _load(self) -> list[dict]:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return []

    def save(self) -> None:
        self.path.write_text(json.dumps(self.cards, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, card: Flashcard) -> None:
        self.cards.append({
            "id": uuid.uuid4().hex[:8],
            "question": card.question,
            "answer": card.answer,
            "hint": card.hint,
            "ease": 2.5,
            "interval": 0,
            "due": datetime.now().isoformat(),
            "reps": 0,
            "lapses": 0,
        })

    def add_many(self, cards: list[Flashcard], reset: bool = False) -> int:
        if reset:
            self.cards = []
        existing = {c["question"] for c in self.cards}
        added = 0
        for c in cards:
            if c.question not in existing:
                self.add(c)
                existing.add(c.question)
                added += 1
        return added

    def due_cards(self) -> list[dict]:
        now = datetime.now()
        return sorted(
            [c for c in self.cards if datetime.fromisoformat(c["due"]) <= now],
            key=lambda c: c["due"],
        )

    def weak_topics(self, concepts: list[Concept]) -> list[dict]:
        if not concepts:
            return []

        results: list[dict] = []
        for concept in concepts:
            concept_text = concept.name.lower()
            related = {t.lower() for t in concept.related_terms}

            matches = [
                card for card in self.cards
                if concept_text in card["question"].lower()
                or any(term in card["question"].lower() for term in related)
            ]
            if not matches:
                matches = self.cards

            avg_ease = sum(float(card.get("ease", 2.5)) for card in matches) / max(1, len(matches))
            avg_lapses = sum(float(card.get("lapses", 0)) for card in matches) / max(1, len(matches))
            avg_reps = sum(float(card.get("reps", 0)) for card in matches) / max(1, len(matches))

            weak_score = (
                max(0.0, 1.0 - (concept.confidence or 0.0)) * 0.45
                + max(0.0, 1.0 - (avg_ease / 3.0)) * 0.30
                + min(1.0, avg_lapses / 2.0) * 0.15
                + max(0.0, 1.0 - (avg_reps / 5.0)) * 0.10
            )

            results.append({
                "name": concept.name,
                "source": concept.source,
                "confidence": float(concept.confidence or 0.0),
                "weak_score": round(min(1.0, weak_score), 3),
                "relevant_cards": len(matches),
                "avg_lapses": round(avg_lapses, 2),
                "avg_reps": round(avg_reps, 2),
            })

        return sorted(results, key=lambda item: item["weak_score"], reverse=True)

    def grade(self, card: dict, grade: int) -> None:
        s = cfg.spaced()
        card["reps"] += 1
        if grade == 0:  # again
            card["lapses"] += 1
            card["interval"] = int(s.get("learning_interval_min", 10))  # minutes
            card["ease"] = max(1.3, card["ease"] - 0.2)
            due = datetime.now() + timedelta(minutes=card["interval"])
        elif grade == 1:  # hard
            card["interval"] = max(1, int(card["interval"] * 1.2))
            card["ease"] = max(1.3, card["ease"] - 0.15)
            due = datetime.now() + timedelta(days=card["interval"])
        elif grade == 2:  # good
            if card["reps"] == 1:
                card["interval"] = int(s.get("grad_interval_h", 24)) / 24.0  # in days
            else:
                card["interval"] = max(1, int(card["interval"] * card["ease"]))
            due = datetime.now() + timedelta(days=card["interval"])
        else:  # easy
            card["ease"] += 0.15
            card["interval"] = max(2, int(card["interval"] * card["ease"] * 1.3))
            due = datetime.now() + timedelta(days=card["interval"])
        card["due"] = due.isoformat()

    def stats(self) -> Table:
        now = datetime.now()
        due = len(self.due_cards())
        t = Table(title=f"Progress ({len(self.cards)} cards)")
        t.add_column("Metric")
        t.add_column("Value")
        t.add_row("Due now", str(due))
        t.add_row("Total reviewed", str(sum(1 for c in self.cards if c["reps"] > 0)))
        t.add_row("Lapses (forgot)", str(sum(c["lapses"] for c in self.cards)))
        t.add_row("Avg ease", f'{sum(c["ease"] for c in self.cards) / max(1, len(self.cards)):.2f}')
        t.add_row("Next due", str((sorted(c["due"] for c in self.cards if datetime.fromisoformat(c["due"]) > now) or ["-"])[0][:16]))
        return t

    def review_session(self) -> None:
        due = self.due_cards()
        if not due:
            console.print("[green]Nothing due right now. Go learn something new![/green]")
            return
        console.print(f"[cyan]{len(due)} cards due.[/cyan] Grade: 1=again 2=hard 3=good 4=easy  (q=quit)\n")
        for card in due:
            console.print(f"[bold]{card['question']}[/bold]")
            if card["hint"]:
                console.print(f"[dim]hint: {card['hint']}[/dim]")
            try:
                input("Press Enter to reveal answer...")
            except (EOFError, KeyboardInterrupt):
                break
            console.print(f"Answer: {card['answer']}\n")
            while True:
                raw = input("Grade (1-4)? ").strip().lower()
                if raw in {"q", "quit", "exit"}:
                    self.save()
                    return
                if raw in GRADES:
                    self.grade(card, GRADES[raw][1])
                    break
                console.print("  enter 1, 2, 3, or 4")
        self.save()
        console.print("[green]Saved. Nice work![/green]")
