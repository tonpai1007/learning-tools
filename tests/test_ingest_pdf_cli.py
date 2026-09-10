"""Integration tests for the ingest-pdf CLI command."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_ingest_pdf_cli_help():
    """Verify the ingest-pdf subcommand is registered."""
    result = subprocess.run(
        [sys.executable, "-m", "lt", "ingest-pdf", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0
    assert "ingest-pdf" in result.stdout.lower() or "path to pdf file" in result.stdout.lower()


def test_ingest_pdf_cli_missing_file():
    """Verify ingest-pdf handles missing file gracefully."""
    result = subprocess.run(
        [sys.executable, "-m", "lt", "ingest-pdf", "/nonexistent/file.pdf"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode != 0 or "not found" in (result.stdout + result.stderr).lower()


@pytest.mark.asyncio
async def test_ingest_pdf_command_with_mocked_api(tmp_path, monkeypatch, capsys):
    """Verify cmd_ingest_pdf calls the AMADEUS API and handles success."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    mock_response = type("MockResponse", (), {
        "read": lambda self: json.dumps({
            "status": "completed",
            "vault_path": "00_Source/documents/test.md",
            "chunks_indexed": 5,
        }).encode("utf-8"),
        "__enter__": lambda self: self,
        "__exit__": lambda self, *args: False,
    })()

    with patch("urllib.request.urlopen", return_value=mock_response):
        with patch.dict("os.environ", {"AMADEUS_BRAIN_API_KEY": "test_key"}):
            args = type("Args", (), {"path": str(pdf), "force": False})()
            # Import the function directly from the module
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "lt.cli",
                str(Path(__file__).resolve().parent.parent / "lt" / "cli.py")
            )
            cli_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli_module)
            cli_module.cmd_ingest_pdf(args)

    captured = capsys.readouterr()
    assert "PDF ingested" in captured.out or "completed" in captured.out
