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
  python -m lt export-plans             export Kilo plans to Obsidian via AMADEUS
  python -m lt clean                   clear cache and temporary files
"""
import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console

from . import ai, export, generate, ingest, srs, studyguide

from .generators.md import generate_md, detect_intent

from .chunker import chunk_sources
from .config import cfg

console = Console()
logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging based on verbosity flags."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _estimate_api_calls(chunks, command: str) -> dict:
    """Estimate the number of API calls and tokens for a command."""
    n = len(chunks)
    estimates = {
        "chunks": n,
        "api_calls": 0,
        "estimated_tokens": 0,
    }

    if command == "cards":
        estimates["api_calls"] = n
        estimates["estimated_tokens"] = sum(len(c.text) // 4 for c in chunks) * 2
    elif command == "quiz":
        estimates["api_calls"] = n
        estimates["estimated_tokens"] = sum(len(c.text) // 4 for c in chunks) * 2
    elif command == "summarize":
        estimates["api_calls"] = n
        estimates["estimated_tokens"] = sum(len(c.text) // 4 for c in chunks) * 2
    elif command == "all":
        estimates["api_calls"] = n * 3  # cards + quiz + summarize
        estimates["estimated_tokens"] = sum(len(c.text) // 4 for c in chunks) * 6
    elif command == "study-guide":
        # concepts + formulas + worked example + practice + quick facts per source
        sources = len(set(c.source for c in chunks))
        estimates["api_calls"] = sources * 5
        estimates["estimated_tokens"] = sum(len(c.text) // 4 for c in chunks) * 3

    return estimates


def _load_sources(args):
    return ingest.ingest(args.paths if hasattr(args, "paths") else None)


def cmd_ingest(args):
    _load_sources(args)


def cmd_md(args):
    """Generate a Markdown document from text content.

    Args:
        args: Parsed CLI arguments with title, output, content, and dry_run
    """
    from .generators.md import generate_md

    # Handle dry-run mode
    if args.dry_run:
        console.print("[yellow]DRY RUN: Would generate Markdown document[/yellow]")
        console.print(f"  Title: {args.title}")
        console.print(f"  Output: {args.output}")
        if args.content:
            console.print(f"  Content preview: {args.content[:80]}{'...' if len(args.content) > 80 else ''}")
        return

    # Prepare content with title prepended (generate_md uses first line as title)
    content = args.content if args.content else ""
    if args.title and content:
        content = f"# {args.title}\n\n{content}"
    elif args.title and not content:
        content = f"# {args.title}\n\n"

    # Generate the Markdown document
    output_path = generate_md(content, args.output)
    console.print(f"[green]Generated:[/green] {output_path}")


def cmd_cards(args):
    sources = _load_sources(args)
    if not sources:
        return
    console.print("[cyan]Chunking...[/cyan]")
    chunks = chunk_sources(sources)

    if args.dry_run:
        est = _estimate_api_calls(chunks, "cards")
        console.print(f"[yellow]DRY RUN: Would generate flashcards from {est['chunks']} chunks[/yellow]")
        console.print(f"  Estimated API calls: {est['api_calls']}")
        console.print(f"  Estimated tokens: {est['estimated_tokens']:,}")
        return

    console.print(f"[cyan]{len(chunks)} chunks -> generating flashcards...[/cyan]")
    cards = generate.generate_flashcards(chunks, per_chunk=args.per_chunk, max_workers=args.workers)
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

    if args.dry_run:
        est = _estimate_api_calls(chunks, "quiz")
        console.print(f"[yellow]DRY RUN: Would generate quiz from {est['chunks']} chunks[/yellow]")
        console.print(f"  Estimated API calls: {est['api_calls']}")
        console.print(f"  Estimated tokens: {est['estimated_tokens']:,}")
        return

    console.print("[cyan]Generating quiz...[/cyan]")
    qs = generate.generate_quiz(chunks, num_questions=args.num, max_workers=args.workers)
    if qs:
        export.write_quiz(qs, cfg.output_dir / "quiz.html")
        generate.save_json(generate.to_dict_list(qs), cfg.output_dir / "quiz.json")


def cmd_summarize(args):
    sources = _load_sources(args)
    if not sources:
        return
    chunks = chunk_sources(sources)

    if args.dry_run:
        est = _estimate_api_calls(chunks, "summarize")
        console.print(f"[yellow]DRY RUN: Would generate summaries from {est['chunks']} chunks[/yellow]")
        console.print(f"  Estimated API calls: {est['api_calls']}")
        console.print(f"  Estimated tokens: {est['estimated_tokens']:,}")
        return

    console.print("[cyan]Summarizing...[/cyan]")
    summaries = generate.generate_summaries(chunks, max_workers=args.workers)
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
    from .tutor import run_interactive
    run_interactive(chunks, k=args.k)


def cmd_review(args):
    srs.SRS().review_session()


def cmd_stats(args):
    console.print(srs.SRS().stats())


def cmd_study_guide(args):
    """Generate a structured HTML study guide (concepts, formulas, worked examples, practice)."""
    sources = _load_sources(args)
    if not sources:
        return
    console.print("[cyan]Chunking...[/cyan]")
    chunks = chunk_sources(sources)
    if not chunks:
        console.print("[red]No chunks generated from sources.[/red]")
        return

    if args.dry_run:
        est = _estimate_api_calls(chunks, "study-guide")
        console.print(f"[yellow]DRY RUN: Would generate study guide from {est['chunks']} chunks[/yellow]")
        console.print(f"  Estimated API calls: {est['api_calls']}")
        console.print(f"  Estimated tokens: {est['estimated_tokens']:,}")
        return

    console.print(f"[cyan]{len(chunks)} chunks -> building study guide...[/cyan]")
    guides = studyguide.build_guides(chunks, num_practice=args.num_practice)
    if not guides:
        console.print("[red]No study guide generated (check your API key / model).[/red]")
        return
    out = studyguide.render_html(guides, title=args.title)
    generate.save_json(studyguide.to_dict_list(guides), cfg.output_dir / "study_guide.json")
    console.print(f"[green]Study guide saved: {out}[/green]")


def cmd_export_plans(args):
    """Export Kilo plans to Obsidian vault via AMADEUS."""
    from export_plans import export_all as export_kilo_plans
    result = export_kilo_plans(args.plans_dir)
    if result.get('status') == 'success':
        console.print(f"[green]Exported {result.get('count', 0)} plans to Obsidian vault.[/green]")
    else:
        console.print(f"[red]Export failed: {result.get('error', 'unknown')}[/red]")


def cmd_ingest_pdf(args):
    """Ingest a PDF into the Obsidian second brain via AMADEUS."""
    import urllib.request
    import urllib.error
    path = Path(args.path)
    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        return
    url = "http://127.0.0.1:8000/api/v1/document/ingest"
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {cfg.amadeus_api_key()}",
            },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = __import__('json').loads(resp.read().decode("utf-8"))
        if result.get("status") == "completed":
            console.print(f"[green]PDF ingested: {path.name} -> {result.get('vault_path')}[/green]")
            console.print(f"[green]Chunks indexed: {result.get('chunks_indexed', 0)}[/green]")
        else:
            console.print(f"[red]Ingestion failed: {result.get('error', 'unknown')}[/red]")
    except urllib.error.URLError as e:
        console.print(f"[red]AMADEUS unreachable: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


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


def cmd_clean(args):
    """Clear cache and temporary files."""
    import shutil
    count = ai.clear_cache()
    console.print(f"[green]Cleared {count} cached responses[/green]")
    if args.all:
        output_dir = cfg.output_dir
        if output_dir.exists():
            shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Cleared output directory[/green]")


def cmd_md(args):
    """Generate a Markdown document from text content."""
    from pathlib import Path
    from .generators.md import generate_md
    
    title = getattr(args, "title", "Document")
    output = getattr(args, "output", None)
    
    # Default content if none provided
    content = getattr(args, "content", None)
    if not content:
        content = f"# {title}\n\nGenerated markdown document."
    
    output_path = output or Path("output.md")
    result = generate_md(content, output_path)
    console.print(f"[green]Markdown generated: {result}[/green]")
    console.print(f"Title: {title}")


def cmd_all(args):
    args.per_chunk = getattr(args, "per_chunk", 6)
    args.add = getattr(args, "add", False)
    args.num = getattr(args, "num", cfg.ai().get("max_quiz_questions", 10))
    args.k = getattr(args, "k", cfg.tutor().get("k", 6))

    if args.dry_run:
        sources = _load_sources(args)
        if not sources:
            return
        chunks = chunk_sources(sources)
        est = _estimate_api_calls(chunks, "all")
        console.print(f"[yellow]DRY RUN: Would process {est['chunks']} chunks[/yellow]")
        console.print(f"  Estimated API calls: {est['api_calls']}")
        console.print(f"  Estimated tokens: {est['estimated_tokens']:,}")
        return

    for cmd in (cmd_cards, cmd_quiz, cmd_summarize):
        try:
            print()
            cmd(args)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]step failed: {e}[/red]")
            logger.exception(f"Step {cmd.__name__} failed")


def build_parser():
    p = argparse.ArgumentParser(prog="lt", description="AI + NotebookLM learning toolkit")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    p.add_argument("--quiet", "-q", action="store_true", help="Suppress non-error output")
    p.add_argument("--dry-run", action="store_true", help="Show what would be done without making API calls")
    p.add_argument("--workers", type=int, default=None, help="Number of parallel API workers")

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
    sp = sub.add_parser("study-guide", help="generate an HTML study guide (concepts, formulas, worked examples, practice)")
    sp.add_argument("--num-practice", type=int, default=cfg.study().get("num_practice_questions", 4))
    sp.add_argument("--title", default="Study Guide", help="title of the study guide HTML")
    sp = sub.add_parser("export-plans", help="export Kilo plans to Obsidian via AMADEUS")
    sp.add_argument("--plans-dir", help="path to .kilo/plans directory")
    sp = sub.add_parser("ingest-pdf", help="ingest a PDF into Obsidian second brain via AMADEUS")
    sp.add_argument("path", help="path to PDF file")
    sp.add_argument("--force", action="store_true", help="force re-ingest even if already indexed")
    sp = sub.add_parser("clean", help="clear cache and temporary files")
    sp.add_argument("--all", action="store_true", help="also clear output directory")
    sp = sub.add_parser("md", help="generate a Markdown document"); sp.add_argument("--title", default="Document", help="title of the markdown document"); sp.add_argument("--output", help="output file path"); sp.add_argument("--content", help="markdown content"); sp.add_argument("--dry_run", action="store_true", help="show what would be generated without writing")
    sp = sub.add_parser("all", help="run cards + quiz + summarize"); add_common(sp)
    return p


def main(argv=None):
    # Parse known args first for logging setup
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--verbose", "-v", action="store_true")
    pre_parser.add_argument("--quiet", "-q", action="store_true")
    pre_args, _ = pre_parser.parse_known_args(argv)
    _setup_logging(verbose=pre_args.verbose, quiet=pre_args.quiet)

    args = build_parser().parse_args(argv)
    try:
        {
            "ingest": cmd_ingest, "cards": cmd_cards, "quiz": cmd_quiz, "summarize": cmd_summarize,
            "tutor": cmd_tutor, "review": cmd_review, "stats": cmd_stats, "sample": cmd_sample,
            "md": cmd_md,
            "study-guide": cmd_study_guide, "all": cmd_all, "clean": cmd_clean,
            "export-plans": cmd_export_plans, "ingest-pdf": cmd_ingest_pdf,
        }[args.command](args)
    except KeyboardInterrupt:
        console.print("\n[yellow]stopped.[/yellow]")
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unhandled error")
        if str(e).lower().find("api") != -1 or str(e).lower().find("auth") != -1:
            console.print("Check your .env: OPENAI_API_KEY and OPENAI_BASE_URL")
        sys.exit(1)


if __name__ == "__main__":
    main()