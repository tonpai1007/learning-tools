"""Tests for the hybrid sync model: AMADEUS-first with local-copy fallback."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import sync_to_second_brain as sync
from lt.config import cfg


def _make_project(tmp_path: Path) -> Path:
    """Create a fake learning-tools project root with output + sources."""
    (tmp_path / "output").mkdir()
    (tmp_path / "sources").mkdir()
    (tmp_path / "output" / "summaries.md").write_text("summary here", encoding="utf-8")
    (tmp_path / "output" / "quiz.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "sources" / "sample_notes.md").write_text("# notes", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Learning Tools", encoding="utf-8")
    return tmp_path


def test_build_destination_for_output(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "PROJECT_ROOT", project)
    monkeypatch.setattr(cfg, "vault_root", lambda: vault)

    result = sync.build_destination_for(project / "output" / "summaries.md")
    assert result == vault / "01_Active_Outputs" / "summaries.md"

    result = sync.build_destination_for(project / "README.md")
    assert result == vault / "04_Reference" / "README.md"


def test_collect_candidate_files_respects_ignores(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    (project / "output" / "junk.log").write_text("noise", encoding="utf-8")
    (project / "__pycache__").mkdir()
    (project / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
    (project / ".git").mkdir()
    (project / ".git" / "config").write_text("cfg", encoding="utf-8")

    monkeypatch.setattr(sync, "PROJECT_ROOT", project)
    monkeypatch.setattr(cfg, "vault_root", lambda: tmp_path / "vault")

    candidates = sync.collect_candidate_files()
    names = {p.name for p in candidates}
    assert "summaries.md" in names
    assert "quiz.html" in names
    assert "sample_notes.md" in names
    assert "README.md" in names
    assert "junk.log" not in names
    assert "x.pyc" not in names
    assert "config" not in names


def test_local_sync_copies_to_vault(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "PROJECT_ROOT", project)
    monkeypatch.setattr(cfg, "vault_root", lambda: vault)

    synced = sync.sync_files_local()
    assert len(synced) > 0

    assert (vault / "01_Active_Outputs" / "summaries.md").read_text(encoding="utf-8") == "summary here"
    assert (vault / "01_Active_Outputs" / "quiz.html").read_text(encoding="utf-8") == "<html></html>"
    assert (vault / "00_Source" / "sample_notes.md").read_text(encoding="utf-8") == "# notes"
    assert (vault / "04_Reference" / "README.md").read_text(encoding="utf-8") == "# Learning Tools"


def test_local_sync_dry_run_no_copy(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "PROJECT_ROOT", project)
    monkeypatch.setattr(cfg, "vault_root", lambda: vault)

    synced = sync.sync_files_local(dry_run=True)
    assert len(synced) > 0
    assert not vault.exists()


def test_hybrid_falls_back_to_local_on_amadeus_error(tmp_path, monkeypatch, capsys):
    """When AMADEUS returns an error, sync must still copy files locally."""
    project = _make_project(tmp_path)
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "PROJECT_ROOT", project)
    monkeypatch.setattr(cfg, "vault_root", lambda: vault)

    error_result = {"status": "error", "error": "connection refused", "fallback": True}
    monkeypatch.setattr(sync, "sync_via_amadeus", lambda dry_run=False, force=False: error_result)

    monkeypatch.setattr("sys.argv", ["sync_to_second_brain.py"])
    sync.main()

    captured = capsys.readouterr()
    assert "falling back to local copy" in captured.out
    assert (vault / "01_Active_Outputs" / "summaries.md").read_text() == "summary here"


def test_hybrid_falls_back_on_connection_refused(tmp_path, monkeypatch, capsys):
    """A bare URLError from sync_via_amadeus (no 'fallback' key) should still fall back."""
    project = _make_project(tmp_path)
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "PROJECT_ROOT", project)
    monkeypatch.setattr(cfg, "vault_root", lambda: vault)

    monkeypatch.setattr(sync, "sync_via_amadeus", lambda dry_run=False, force=False: {
        "status": "error",
        "error": "URLError: <urlopen error [WinError 10061] No connection>",
        "fallback": True,
    })

    monkeypatch.setattr("sys.argv", ["sync_to_second_brain.py"])
    sync.main()

    captured = capsys.readouterr()
    assert "AMADEUS unavailable" in captured.out
    assert "falling back to local copy" in captured.out
    assert (vault / "01_Active_Outputs" / "summaries.md").read_text() == "summary here"


def test_local_flag_skips_amadeus(tmp_path, monkeypatch, capsys):
    """--local must never call the AMADEUS API."""
    project = _make_project(tmp_path)
    vault = tmp_path / "vault"
    monkeypatch.setattr(sync, "PROJECT_ROOT", project)
    monkeypatch.setattr(cfg, "vault_root", lambda: vault)

    calls = []
    monkeypatch.setattr(sync, "sync_via_amadeus", lambda **kw: calls.append(1) or {"status": "success"})

    monkeypatch.setattr("sys.argv", ["sync_to_second_brain.py", "--local"])
    sync.main()

    assert calls == []
    assert (vault / "01_Active_Outputs" / "summaries.md").read_text() == "summary here"