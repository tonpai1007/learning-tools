"""Analytics and statistics tracking for learning tools."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import cfg

logger = logging.getLogger(__name__)


class Analytics:
    """Track and report on study activity."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or cfg.data_dir / "analytics.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT NOT NULL,
                    source TEXT,
                    timestamp TEXT NOT NULL,
                    quality INTEGER NOT NULL,
                    elapsed_days REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_questions INTEGER NOT NULL,
                    correct INTEGER NOT NULL,
                    duration_seconds REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS study_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    items_count INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS concept_strength (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept TEXT UNIQUE NOT NULL,
                    source TEXT,
                    times_reviewed INTEGER DEFAULT 0,
                    times_correct INTEGER DEFAULT 0,
                    last_reviewed TEXT,
                    strength REAL DEFAULT 0.0
                );

                CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews(card_id);
                CREATE INDEX IF NOT EXISTS idx_reviews_timestamp ON reviews(timestamp);
                CREATE INDEX IF NOT EXISTS idx_concept_name ON concept_strength(concept);
            """)

    def record_review(self, card_id: str, quality: int, source: str = "", elapsed_days: float = 0) -> None:
        """Record a flashcard review. Quality: 0-5 (0=complete blackout, 5=perfect)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO reviews (card_id, source, timestamp, quality, elapsed_days) VALUES (?, ?, ?, ?, ?)",
                (card_id, source, datetime.now().isoformat(), quality, elapsed_days),
            )

    def record_quiz_attempt(self, total_questions: int, correct: int, duration_seconds: float = 0) -> None:
        """Record a quiz attempt."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO quiz_attempts (timestamp, total_questions, correct, duration_seconds) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), total_questions, correct, duration_seconds),
            )

    def record_study_session(self, activity_type: str, items_count: int = 0, duration_seconds: float = 0) -> None:
        """Record a study session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO study_sessions (timestamp, activity_type, items_count, duration_seconds) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), activity_type, items_count, duration_seconds),
            )

    def update_concept_strength(self, concept: str, correct: bool, source: str = "") -> None:
        """Update the strength estimate for a concept."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT times_reviewed, times_correct FROM concept_strength WHERE concept = ?",
                (concept,),
            ).fetchone()
            now = datetime.now().isoformat()
            if row:
                times_reviewed, times_correct = row
                times_reviewed += 1
                if correct:
                    times_correct += 1
                strength = times_correct / times_reviewed if times_reviewed > 0 else 0
                conn.execute(
                    """UPDATE concept_strength SET times_reviewed=?, times_correct=?,
                       last_reviewed=?, strength=? WHERE concept=?""",
                    (times_reviewed, times_correct, now, strength, concept),
                )
            else:
                conn.execute(
                    """INSERT INTO concept_strength (concept, source, times_reviewed, times_correct,
                       last_reviewed, strength) VALUES (?, ?, 1, ?, ?, ?)""",
                    (concept, source, 1 if correct else 0, now, 1.0 if correct else 0.0),
                )

    def get_stats(self) -> dict[str, Any]:
        """Get overall statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            total_reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            total_quizzes = conn.execute("SELECT COUNT(*) FROM quiz_attempts").fetchone()[0]
            total_sessions = conn.execute("SELECT COUNT(*) FROM study_sessions").fetchone()[0]

            avg_quality = conn.execute("SELECT AVG(quality) FROM reviews").fetchone()[0] or 0
            avg_quiz_score = conn.execute(
                "SELECT AVG(CAST(correct AS FLOAT) / total_questions * 100) FROM quiz_attempts"
            ).fetchone()[0] or 0

            # Reviews in last 7 days
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            reviews_this_week = conn.execute(
                "SELECT COUNT(*) FROM reviews WHERE timestamp > ?", (week_ago,)
            ).fetchone()[0]

            # Reviews in last 30 days
            month_ago = (datetime.now() - timedelta(days=30)).isoformat()
            reviews_this_month = conn.execute(
                "SELECT COUNT(*) FROM reviews WHERE timestamp > ?", (month_ago,)
            ).fetchone()[0]

            # Total study time
            total_study_time = conn.execute(
                "SELECT SUM(duration_seconds) FROM study_sessions"
            ).fetchone()[0] or 0

            # Total quiz time
            total_quiz_time = conn.execute(
                "SELECT SUM(duration_seconds) FROM quiz_attempts"
            ).fetchone()[0] or 0

            return {
                "total_reviews": total_reviews,
                "total_quizzes": total_quizzes,
                "total_sessions": total_sessions,
                "avg_review_quality": round(avg_quality, 2),
                "avg_quiz_score": round(avg_quiz_score, 1),
                "reviews_this_week": reviews_this_week,
                "reviews_this_month": reviews_this_month,
                "total_study_hours": round(total_study_time / 3600, 1),
                "total_quiz_minutes": round(total_quiz_time / 60, 1),
            }

    def get_weak_concepts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the weakest concepts (lowest strength, most reviewed)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT concept, source, times_reviewed, times_correct, strength, last_reviewed
                   FROM concept_strength ORDER BY strength ASC, times_reviewed DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_strong_concepts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the strongest concepts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT concept, source, times_reviewed, times_correct, strength, last_reviewed
                   FROM concept_strength ORDER BY strength DESC, times_reviewed DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_daily_review_counts(self, days: int = 30) -> list[dict[str, Any]]:
        """Get review counts per day for the last N days."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            start = (datetime.now() - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT DATE(timestamp) as day, COUNT(*) as count
                   FROM reviews WHERE timestamp > ?
                   GROUP BY DATE(timestamp) ORDER BY day""",
                (start,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_quiz_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent quiz attempts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT timestamp, total_questions, correct, duration_seconds,
                   ROUND(CAST(correct AS FLOAT) / total_questions * 100, 1) as score_pct
                   FROM quiz_attempts ORDER BY timestamp ASC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_source_stats(self) -> list[dict[str, Any]]:
        """Get review statistics grouped by source."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT source, COUNT(*) as reviews, AVG(quality) as avg_quality
                   FROM reviews WHERE source != '' GROUP BY source ORDER BY reviews DESC"""
            ).fetchall()
            return [dict(row) for row in rows]

    def get_upcoming_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get cards due for review based on SRS intervals."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Get the latest review for each card
            rows = conn.execute(
                """SELECT card_id, source, timestamp, quality, elapsed_days,
                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY timestamp DESC) as rn
                   FROM reviews"""
            ).fetchall()

            now = datetime.now()
            upcoming = []
            seen = set()
            for row in rows:
                if row["card_id"] in seen:
                    continue
                seen.add(row["card_id"])
                last_review = datetime.fromisoformat(row["timestamp"])
                # Adjust last_review by elapsed_days to get actual review time
                adjusted_review = last_review - timedelta(days=row["elapsed_days"])
                # Simple interval: quality 5 = 7 days, 4 = 3 days, 3 = 1 day, 2 = 0.5 day, 1/0 = 0.1 day
                intervals = {5: 7, 4: 3, 3: 1, 2: 0.5, 1: 0.1, 0: 0.1}
                interval_days = intervals.get(row["quality"], 0.1)
                due_date = adjusted_review + timedelta(days=interval_days)
                if due_date <= now:
                    upcoming.append({
                        "card_id": row["card_id"],
                        "source": row["source"],
                        "last_reviewed": row["timestamp"],
                        "quality": row["quality"],
                        "due_since_hours": round((now - due_date).total_seconds() / 3600, 1),
                    })
            upcoming.sort(key=lambda x: x["due_since_hours"], reverse=True)
            return upcoming[:limit]


analytics = Analytics()