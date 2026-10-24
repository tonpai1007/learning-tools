"""Tests for the Flask web dashboard routes."""
from pathlib import Path

import pytest

import lt.web as web_mod
from lt.analytics import Analytics


@pytest.fixture
def web_app(tmp_path, monkeypatch):
    test_analytics = Analytics(db_path=tmp_path / "analytics.db")
    monkeypatch.setattr(web_mod, "analytics", test_analytics)
    monkeypatch.setattr(
        web_mod,
        "build_code_graph",
        lambda root=None: {"nodes": [], "edges": [], "stats": {"total_nodes": 0}, "communities": {}},
    )
    return web_mod.app


def test_dashboard(web_app):
    with web_app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Learning" in resp.data or b"dashboard" in resp.data.lower() or b"Study" in resp.data


def test_flashcards_page(web_app):
    with web_app.test_client() as client:
        resp = client.get("/flashcards")
        assert resp.status_code == 200


def test_quiz_page(web_app):
    with web_app.test_client() as client:
        resp = client.get("/quiz")
        assert resp.status_code == 200


def test_study_guide_page(web_app):
    with web_app.test_client() as client:
        resp = client.get("/study-guide")
        assert resp.status_code == 200


def test_sources_page(web_app):
    with web_app.test_client() as client:
        resp = client.get("/sources")
        assert resp.status_code == 200


def test_analytics_page(web_app):
    with web_app.test_client() as client:
        resp = client.get("/analytics")
        assert resp.status_code == 200


def test_graph_page(web_app):
    with web_app.test_client() as client:
        resp = client.get("/graph")
        assert resp.status_code == 200


def test_api_stats(web_app):
    with web_app.test_client() as client:
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_reviews" in data
        assert "total_quizzes" in data


def test_api_weak_concepts(web_app):
    with web_app.test_client() as client:
        resp = client.get("/api/weak-concepts?limit=5")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


def test_api_quiz_history(web_app):
    with web_app.test_client() as client:
        resp = client.get("/api/quiz-history?limit=10")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


def test_api_graph(web_app):
    with web_app.test_client() as client:
        resp = client.get("/api/graph")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nodes" in data
        assert "edges" in data
        assert "stats" in data


def test_api_submit_review(web_app):
    with web_app.test_client() as client:
        resp = client.post("/flashcards/review", json={
            "card_id": "card-1",
            "quality": 4,
            "source": "notes.md",
        })
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


def test_api_submit_quiz(web_app):
    with web_app.test_client() as client:
        resp = client.post("/quiz/submit", json={
            "total_questions": 10,
            "correct": 7,
            "duration_seconds": 120,
        })
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

        # Verify the quiz attempt was recorded
        stats = client.get("/api/stats").get_json()
        assert stats["total_quizzes"] == 1
