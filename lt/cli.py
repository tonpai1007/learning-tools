"""Learning Tools CLI.

  python -m lt ingest                  list/load sources
  python -m lt cards [--add]           generate Anki flashcards (+ add to spaced repetition)
  python -m lt quiz                    generate a practice quiz (HTML)
  python -m lt summarize               generate summaries + NotebookLM source pack
  python -m lt tutor                   interactive Socratic tutor over your sources
  python -m lt review                  spaced-repetition review session
  python -m lt stats                   show progress
  python -m lt all                     run the full pipeline
  python -m lt sample                  write a sample file into sources/
"""
import argparse
import sys
from pathlib import Path

from rich.console import Console

from . import ai, export, generate, ingest, srs
from .chunker import chunk_sources
from .config import cfg

console = Console()


def _load_sources(args):
    return ingest.ingest(args.paths if hasattr(args, "paths") else None)


def cmd_ingest(args):
    _load_sources(args)


def cmd_cards(args):
    sources = _load_sources(args)
    if not sources:
        return
    console.print("[cyan]Chunking...[/cyan]")
    chunks = chunk_sources(sources)
    console.print(f"[cyan]{len(chunks)} chunks -> generating flashcards...[/cyan]")
    cards = generate.generate_flashcards(chunks, per_chunk=args.per_chunk)
    if not cards:
        console.print("[red]No cards generated (check your API key / model).[/red]")
        return
    deck = cfg.output_dir / "flashcards.tsv"
    export.write_anki(cards, deck)
    generate.save_json(generate.to_dict_list(cards), cfg.output_dir / "flashcards.json")
    if args.add:
        n = srs.SRS().add_many(cards)
        console.print(f"[green]{n} new cards added to spaced repetition.[/green]")


def cmd_quiz(args):
    sources = _load_sources(args)
    if not sources:
        return
    chunks = chunk_sources(sources)
    console.print("[cyan]Generating quiz...[/cyan]")
    qs = generate.generate_quiz(chunks, num_questions=args.num)
    if qs:
        export.write_quiz(qs, cfg.output_dir / "quiz.html")
        generate.save_json(generate.to_dict_list(qs), cfg.output_dir / "quiz.json")


def cmd_summarize(args):
    sources = _load_sources(args)
    if not sources:
        return
    chunks = chunk_sources(sources)
    console.print("[cyan]Summarizing...[/cyan]")
    summaries = generate.generate_summaries(chunks)
    if not summaries:
        return
    export.write_summaries(summaries, cfg.output_dir / "summaries.md")
    export.write_notebooklm_pack(summaries, cfg.output_dir)


def cmd_tutor(args):
    sources = _load_sources(args)
    if not sources:
        return
    chunks = chunk_sources(sources)
    console.print(f"[cyan]{len(chunks)} chunks loaded into the tutor.[/cyan]")
    tutor.run_interactive(chunks, k=args.k)


def cmd_review(args):
    srs.SRS().review_session()


def cmd_stats(args):
    console.print(srs.SRS().stats())


def cmd_sample(args):
    target = cfg.sources_dir / "sample_notes.md"
    target.write_text(
        "# Sample: The Water Cycle\n\n"
        "The water cycle has four stages: evaporation, condensation, precipitation, and collection.\n"
        "Evaporation turns liquid water into vapor using solar energy. Condensation forms clouds.\n"
        "Precipitation returns water to Earth as rain or snow, and collection gathers it in oceans and rivers.\n"
        "Transpiration also releases water vapor from plants.\n",
        encoding="utf-8",
    )
    console.print(f"[green]Sample written to {target}[/green] Run: python -m lt all")


def cmd_all(args):
    args.per_chunk = getattr(args, "per_chunk", 6)
    args.add = getattr(args, "add", False)
    args.num = getattr(args, "num", cfg.ai().get("max_quiz_questions", 10))
    args.k = getattr(args, "k", cfg.tutor().get("k", 6))
    for cmd in (cmd_cards, cmd_quiz, cmd_summarize):
        try:
            print()
            cmd(args)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]step failed: {e}[/red]")


def build_parser():
    p = argparse.ArgumentParser(prog="lt", description="AI + NotebookLM learning toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("paths", nargs="*", help="optional extra files/dirs beyond sources/")

    sp = sub.add_parser("ingest", help="list and load sources"); add_common(sp)
    sp = sub.add_parser("cards", help="generate Anki flashcards"); add_common(sp)
    sp.add_argument("--per-chunk", type=int, default=6, help="cards per chunk")
    sp.add_argument("--add", action="store_true", help="also add to spaced repetition")
    sp = sub.add_parser("quiz", help="generate a quiz (HTML)"); add_common(sp)
    sp.add_argument("--num", type=int, default=cfg.ai().get("max_quiz_questions", 10))
    sp = sub.add_parser("summarize", help="summaries + NotebookLM pack"); add_common(sp)
    sp = sub.add_parser("tutor", help="interactive tutor"); add_common(sp)
    sp.add_argument("--k", type=int, default=cfg.tutor().get("k", 6))
    sub.add_parser("review", help="spaced-repetition review")
    sub.add_parser("stats", help="progress stats")
    sub.add_parser("sample", help="write a sample file into sources/")
    sp = sub.add_parser("all", help="run cards + quiz + summarize"); add_common(sp)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        {"ingest": cmd_ingest, "cards": cmd_cards, "quiz": cmd_quiz, "summarize": cmd_summarize,
         "tutor": cmd_tutor, "review": cmd_review, "stats": cmd_stats, "sample": cmd_sample,
         "all": cmd_all}[args.command](args)
    except KeyboardInterrupt:
        console.print("\n[yellow]stopped.[/yellow]")
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        if str(e).lower().find("api") != -1 or str(e).lower().find("auth") != -1:
            console.print("Check your .env: OPENAI_API_KEY and OPENAI_BASE_URL")
        sys.exit(1)


if __name__ == "__main__":
    main()
