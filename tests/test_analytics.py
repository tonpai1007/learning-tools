"""Tests for the SQLite analytics module."""
from datetime import datetime, timedelta

import pytest

from lt.analytics import Analytics


@pytest.fixture
def analytics(tmp_path):
    db = tmp_path / "analytics.db"
    return Analytics(db_path=db)


def test_record_and_get_stats_empty(analytics):
    stats = analytics.get_stats()
    assert stats["total_reviews"] == 0
    assert stats["total_quizzes"] == 0
    assert stats["total_sessions"] == 0
    assert stats["avg_review_quality"] == 0
    assert stats["avg_quiz_score"] == 0


def test_record_review(analytics):
    analytics.record_review("card-1", quality=4, source="water_cycle.md")
    analytics.record_review("card-2", quality=5, source="water_cycle.md")

    stats = analytics.get_stats()
    assert stats["total_reviews"] == 2
    assert stats["reviews_this_week"] == 2
    assert round(stats["avg_review_quality"], 1) == 4.5


def test_record_quiz_attempt(analytics):
    analytics.record_quiz_attempt(10, 8, 120.0)
    analytics.record_quiz_attempt(5, 3, 60.0)

    stats = analytics.get_stats()
    assert stats["total_quizzes"] == 2
    assert round(stats["avg_quiz_score"], 1) == 70.0  # avg of 80% and 60%


def test_get_upcoming_reviews(analytics):
    now = datetime.now().isoformat()
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    two_days_ago = (datetime.now() - timedelta(days=2)).isoformat()

    # Card reviewed yesterday with quality 3 (1-day interval) — due now
    analytics.record_review("card-due", quality=3, source="s1", elapsed_days=1)
    # Card reviewed 2 days ago with quality 5 (7-day interval) — not due yet
    analytics.record_review("card-future", quality=5, source="s1", elapsed_days=2)

    upcoming = analytics.get_upcoming_reviews(limit=10)
    card_ids = {r["card_id"] for r in upcoming}
    assert "card-due" in card_ids
    assert "card-future" not in card_ids


def test_update_concept_strength(analytics):
    analytics.update_concept_strength("Photosynthesis", correct=True, source="biol.md")
    analytics.update_concept_strength("Photosynthesis", correct=False, source="biol.md")

    weak = analytics.get_weak_concepts(limit=10)
    concept = next(c for c in weak if c["concept"] == "Photosynthesis")
    assert concept["times_reviewed"] == 2
    assert concept["times_correct"] == 1
    assert concept["strength"] == 0.5


def test_get_strong_then_weak(analytics):
    analytics.update_concept_strength("Easy", correct=True)
    analytics.update_concept_strength("Hard", correct=False)
    analytics.update_concept_strength("OK", correct=True)

    weak = analytics.get_weak_concepts(limit=10)
    strong = analytics.get_strong_concepts(limit=10)

    assert weak[0]["concept"] == "Hard"
    assert strong[0]["concept"] == "Easy"


def test_get_daily_review_counts(analytics):
    analytics.record_review("c1", quality=5)
    analytics.record_review("c2", quality=4)

    daily = analytics.get_daily_review_counts(days=7)
    today = datetime.now().strftime("%Y-%m-%d")
    today_row = next(r for r in daily if r["day"] == today)
    assert today_row["count"] == 2


def test_get_quiz_history(analytics):
    analytics.record_quiz_attempt(10, 8, 100.0)
    analytics.record_quiz_attempt(5, 3, 50.0)

    history = analytics.get_quiz_history(limit=10)
    assert len(history) == 2
    assert history[0]["score_pct"] == 80.0
    assert history[1]["score_pct"] == 60.0


def test_get_source_stats(analytics):
    analytics.record_review("c1", quality=4, source="biology.md")
    analytics.record_review("c2", quality=5, source="biology.md")
    analytics.record_review("c3", quality=5, source="chemistry.md")

    stats = analytics.get_source_stats()
    bio = next(s for s in stats if s["source"] == "biology.md")
    assert bio["reviews"] == 2
    assert round(bio["avg_quality"], 1) == 4.5
