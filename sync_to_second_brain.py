from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VAULT_ROOT = Path(r"C:\Users\Tonpa\MySecondBrain\learning-tools")

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
}


def build_destination_for(path: Path) -> Path:
    relative = path.relative_to(PROJECT_ROOT)
    if relative.parts[0] == "output":
        return VAULT_ROOT / "01_Active_Outputs" / relative.name
    if relative.parts[0] == "sources":
        return VAULT_ROOT / "00_Source" / relative.name
    if relative.name in {"README.md", "config.yaml"}:
        return VAULT_ROOT / "04_Reference" / relative.name
    return VAULT_ROOT / "02_Notes" / relative.name


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
            name = path.name.lower()
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


def sync_files(dry_run: bool = False) -> list[str]:
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
    (VAULT_ROOT / "00_Source").mkdir(exist_ok=True)
    (VAULT_ROOT / "01_Active_Outputs").mkdir(exist_ok=True)
    (VAULT_ROOT / "02_Notes").mkdir(exist_ok=True)
    (VAULT_ROOT / "03_Concepts").mkdir(exist_ok=True)
    (VAULT_ROOT / "04_Reference").mkdir(exist_ok=True)

    synced: list[str] = []
    for src in collect_candidate_files():
        dst = build_destination_for(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dry_run:
            synced.append(f"{src} -> {dst}")
            continue
        shutil.copy2(src, dst)
        synced.append(f"{src} -> {dst}")
    return synced


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync curated learning exports into the MySecondBrain vault.")
    parser.add_argument("--dry-run", action="store_true", help="Show which files would be synced without copying them.")
    args = parser.parse_args()

    for entry in sync_files(dry_run=args.dry_run):
        print(entry)


if __name__ == "__main__":
    main()
