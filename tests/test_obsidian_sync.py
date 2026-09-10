import json
import os
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, "C:/AMADEUS")

from brain.sync.obsidian_sync import ObsidianSync


@pytest.fixture()
def tmp_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".amadeus").mkdir()
    return vault


@pytest.fixture()
def tmp_source(tmp_path):
    src = tmp_path / "learning-tools"
    src.mkdir()
    (src / "output").mkdir()
    (src / "sources").mkdir()
    return src


def _make_sync(tmp_vault, tmp_source):
    sync = ObsidianSync.__new__(ObsidianSync)
    sync.vault = tmp_vault
    sync.vm = None
    sync.internal = tmp_vault / ".amadeus"
    sync.sync_state_path = tmp_vault / ".amadeus" / "sync_state.json"
    sync.audit_log_path = tmp_vault / ".amadeus" / "audit_log.jsonl"
    sync.sync_state = {"files": {}, "last_sync": None, "version": 1}
    sync.SOURCE_ROOT = tmp_source
    sync.ALLOWED_OUTPUT_FILES = {"summaries.md", "quiz.html", "flashcards.tsv", "_master_prompt.md"}
    sync.ALLOWED_SOURCE_FILES = {"sample_notes.md", "notes.md", "study_notes.md", "reflections.md"}
    sync.IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", ".qodo", ".deepeval"}
    return sync


def test_clean_sync_no_conflict(tmp_vault, tmp_source):
    src = tmp_source / "output" / "summaries.md"
    src.write_text("hello", encoding="utf-8")
    dst = tmp_vault / "01_Active_Outputs" / "summaries.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("hello", encoding="utf-8")

    sync = _make_sync(tmp_vault, tmp_source)
    conflict = sync._detect_conflict(src, dst)
    assert conflict is None


def test_both_changed_conflict(tmp_vault, tmp_source):
    src = tmp_source / "output" / "summaries.md"
    src.write_text("v1", encoding="utf-8")
    dst = tmp_vault / "01_Active_Outputs" / "summaries.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("v1", encoding="utf-8")

    sync = _make_sync(tmp_vault, tmp_source)
    sync.sync_state["files"][str(src)] = {"hash": sync._file_hash(src), "dst_hash": sync._file_hash(dst)}
    src.write_text("v2", encoding="utf-8")
    dst.write_text("v2-edit", encoding="utf-8")
    conflict = sync._detect_conflict(src, dst)
    assert conflict == "both_changed"


def test_vault_modified_conflict(tmp_vault, tmp_source):
    src = tmp_source / "output" / "summaries.md"
    src.write_text("v1", encoding="utf-8")
    dst = tmp_vault / "01_Active_Outputs" / "summaries.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("v1", encoding="utf-8")

    sync = _make_sync(tmp_vault, tmp_source)
    sync.sync_state["files"][str(src)] = {"hash": None, "dst_hash": sync._file_hash(dst)}
    dst.write_text("vault-edit", encoding="utf-8")
    conflict = sync._detect_conflict(src, dst)
    assert conflict == "vault_modified"


def test_force_skips_conflict(tmp_vault, tmp_source):
    src = tmp_source / "output" / "summaries.md"
    src.write_text("v1", encoding="utf-8")
    dst = tmp_vault / "01_Active_Outputs" / "summaries.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("v1", encoding="utf-8")

    sync = _make_sync(tmp_vault, tmp_source)
    sync.sync_state["files"][str(src)] = {"hash": sync._file_hash(src), "dst_hash": sync._file_hash(dst)}
    src.write_text("v2", encoding="utf-8")
    dst.write_text("v2-edit", encoding="utf-8")
    result = sync.sync(force=True)
    assert result["status"] == "completed"
    assert len(result["conflicts"]) == 0
