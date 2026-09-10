"""Sync curated learning exports into the MySecondBrain vault.

Uses config.yaml for paths and AMADEUS settings. Falls back to local copy
if AMADEUS is unavailable.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path

from lt.config import cfg

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent

ALLOWED_OUTPUT_FILES = {
    "summaries.md",
    "quiz.html",
    "flashcards.tsv",
    "_master_prompt.md",
}

ALLOWED_SOURCE_FILES = {
    "sample_notes.md",
    "notes.md",
    "study_notes.md",
    "reflections.md",
}

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    ".qodo",
    ".deepeval",
    "cache",
}


def build_destination_for(path: Path) -> Path:
    relative = path.relative_to(PROJECT_ROOT)
    vault_root = cfg.vault_root()
    if relative.parts[0] == "output":
        return vault_root / "01_Active_Outputs" / relative.name
    if relative.parts[0] == "sources":
        return vault_root / "00_Source" / relative.name
    if path.name in {"README.md", "config.yaml"}:
        return vault_root / "04_Reference" / path.name
    return vault_root / "02_Notes" / path.name


def is_ignored_dir(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def collect_candidate_files() -> list[Path]:
    candidates: list[Path] = []
    for root in (PROJECT_ROOT / "output", PROJECT_ROOT / "sources", PROJECT_ROOT):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if is_ignored_dir(path):
                continue
            rel = path.relative_to(PROJECT_ROOT)
            if len(rel.parts) > 1 and rel.parts[0] == "output" and path.name in ALLOWED_OUTPUT_FILES:
                candidates.append(path)
                continue
            if len(rel.parts) > 1 and rel.parts[0] == "sources" and path.name.lower() in {n.lower() for n in ALLOWED_SOURCE_FILES}:
                candidates.append(path)
                continue
            if path.name.lower() == "readme.md" and path.parent == PROJECT_ROOT:
                candidates.append(path)
                continue
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def sync_via_amadeus(dry_run: bool = False, force: bool = False) -> dict:
    """Delegate sync to AMADEUS via its REST API."""
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({"dry_run": dry_run, "force": force}).encode("utf-8")
        req = urllib.request.Request(
            cfg.amadeus_url(),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg.amadeus_api_key()}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "error": str(e), "fallback": True}


def sync_files_local(dry_run: bool = False) -> list[str]:
    synced: list[str] = []
    for src in collect_candidate_files():
        dst = build_destination_for(src)
        if dry_run:
            synced.append(f"{src} -> {dst}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        synced.append(f"{src} -> {dst}")
    return synced


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Sync curated learning exports into the MySecondBrain vault via AMADEUS."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be synced without copying them.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync even if conflicts are detected.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force local copy fallback instead of AMADEUS API.",
    )
    args = parser.parse_args()

    result = None
    if not args.local:
        result = sync_via_amadeus(dry_run=args.dry_run, force=args.force)

    if result and not result.get("fallback") and result.get("status") not in ("error",):
        print(json.dumps(result, indent=2))
        return

    if result and result.get("fallback"):
        print(f"AMADEUS unavailable ({result.get('error')}), falling back to local copy.")

    for entry in sync_files_local(dry_run=args.dry_run):
        print(entry)


if __name__ == "__main__":
    main()