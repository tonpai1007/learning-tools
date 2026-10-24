"""Flask web interface for learning tools."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import json
from flask import Flask, jsonify, render_template, request, send_file

from .analytics import analytics
from .config import cfg
from .graph import build_code_graph

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"))


@app.template_filter("timestamp_to_date")
def timestamp_to_date(ts):
    """Convert a Unix timestamp to a human-readable date string."""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, TypeError):
        return str(ts)


@app.route("/")
def dashboard():
    stats = analytics.get_stats()
    upcoming = analytics.get_upcoming_reviews(limit=5)
    weak_concepts = analytics.get_weak_concepts(limit=5)
    daily = analytics.get_daily_review_counts(days=14)
    return render_template("dashboard.html", stats=stats, upcoming=upcoming,
                           weak_concepts=weak_concepts, daily=daily)


@app.route("/flashcards")
def flashcards_page():
    return render_template("flashcards.html")


@app.route("/flashcards/review")
def flashcards_review():
    """Get cards due for review."""
    cards = analytics.get_upcoming_reviews(limit=50)
    return jsonify(cards)


@app.route("/flashcards/review", methods=["POST"])
def flashcards_submit_review():
    """Submit a flashcard review."""
    data = request.json
    card_id = data.get("card_id", "")
    quality = int(data.get("quality", 3))
    source = data.get("source", "")
    analytics.record_review(card_id, quality, source)
    return jsonify({"status": "ok"})


@app.route("/quiz")
def quiz_page():
    return render_template("quiz.html")


@app.route("/quiz/submit", methods=["POST"])
def quiz_submit():
    """Submit a quiz attempt."""
    data = request.json
    total = data.get("total_questions", 0)
    correct = data.get("correct", 0)
    duration = data.get("duration_seconds", 0)
    analytics.record_quiz_attempt(total, correct, duration)
    return jsonify({"status": "ok"})


@app.route("/study-guide")
def study_guide_page():
    output_dir = cfg.output_dir
    guides = []
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.html")):
            guides.append({"name": f.stem.replace("_", " ").title(), "path": str(f)})
    return render_template("study_guide.html", guides=guides)


@app.route("/sources")
def sources_page():
    sources_dir = Path(__file__).resolve().parent.parent / "sources"
    sources = []
    if sources_dir.exists():
        for f in sorted(sources_dir.iterdir()):
            if f.is_file():
                sources.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                })
    return render_template("sources.html", sources=sources)


@app.route("/analytics")
def analytics_page():
    stats = analytics.get_stats()
    weak_concepts = analytics.get_weak_concepts(limit=20)
    strong_concepts = analytics.get_strong_concepts(limit=10)
    quiz_history = analytics.get_quiz_history(limit=20)
    source_stats = analytics.get_source_stats()
    daily = analytics.get_daily_review_counts(days=30)
    return render_template("analytics.html", stats=stats,
                           weak_concepts=weak_concepts, strong_concepts=strong_concepts,
                           quiz_history=quiz_history, source_stats=source_stats,
                           daily=daily)


@app.route("/api/stats")
def api_stats():
    return jsonify(analytics.get_stats())


@app.route("/api/weak-concepts")
def api_weak_concepts():
    limit = request.args.get("limit", 10, type=int)
    return jsonify(analytics.get_weak_concepts(limit=limit))


@app.route("/api/quiz-history")
def api_quiz_history():
    limit = request.args.get("limit", 20, type=int)
    return jsonify(analytics.get_quiz_history(limit=limit))


@app.route("/graph")
def graph_page():
    return render_template("graph.html")


@app.route("/api/graph")
def api_graph():
    data = build_code_graph()
    return jsonify(data)




# ---------------------------------------------------------
# MDIE Machine Design Engine & DOCX Integration APIs
# ---------------------------------------------------------

@app.route("/api/convert/docx", methods=["POST"])
def api_convert_docx():
    """
    Convert an HTML file or raw HTML payload into a Word .docx document.
    Payload (JSON):
      - html_path: str (path to HTML file on disk)
      - output_docx_path: str (optional output destination)
      - html: str (optional raw HTML content if not passing a file path)
      - enable_ai: bool (optional, run AI peer-review summary)
      - custom_ai_instructions: str (optional)
      - download: bool (if true, streams the file back as attachment)
    """
    try:
        from .docx_converter import HTMLToDocxConverter
        data = request.get_json(silent=True) or {}

        html_path_str = data.get("html_path")
        output_docx_path_str = data.get("output_docx_path")
        html_content = data.get("html")
        enable_ai = bool(data.get("enable_ai", False))
        custom_ai_instructions = data.get("custom_ai_instructions")
        download = bool(data.get("download", False) or request.args.get("download") in ("1", "true"))

        if html_content and not html_path_str:
            temp_dir = cfg.output_dir / "temp_html"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_html_path = temp_dir / f"convert_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            temp_html_path.write_text(html_content, encoding="utf-8")
            html_path_str = str(temp_html_path)
            if not output_docx_path_str:
                output_docx_path_str = str(temp_html_path.with_suffix(".docx"))

        if not html_path_str:
            return jsonify({"status": "error", "error": "Either 'html_path' or 'html' must be provided"}), 400

        result_path = HTMLToDocxConverter.convert(
            html_path=html_path_str,
            output_docx_path=output_docx_path_str,
            enable_ai=enable_ai,
            custom_ai_instructions=custom_ai_instructions
        )

        if download:
            return send_file(
                str(result_path),
                as_attachment=True,
                download_name=Path(result_path).name,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        return jsonify({
            "status": "ok",
            "docx_path": str(result_path),
            "filename": Path(result_path).name,
            "size_bytes": Path(result_path).stat().st_size
        })
    except Exception as e:
        logger.exception("DOCX conversion failed")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/mdie/status")
def api_mdie_status():
    """Check connectivity to MDIE computational design engine (port 8000)."""
    import urllib.request
    import urllib.error
    mdie_url = "http://127.0.0.1:8000"
    is_online = False
    details = {}
    try:
        req = urllib.request.Request(f"{mdie_url}/api/health", headers={"User-Agent": "LearningTools/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                is_online = True
                details = {"status_code": 200}
    except Exception as e:
        is_online = False
        details = {"error": str(e)}

    return jsonify({
        "status": "online" if is_online else "offline",
        "mdie_url": mdie_url,
        "engine": "Machine Design Intelligence Engine (MDIE)",
        "details": details
    })


@app.route("/api/mdie/ingest", methods=["POST"])
def api_mdie_ingest():
    """
    Ingest machine design engineering study materials (flashcards, quiz questions, formulas)
    exported from MDIE.
    """
    try:
        data = request.get_json(force=True)
        project_name = data.get("project", "machine_design")
        flashcards = data.get("flashcards", [])
        quiz_questions = data.get("quiz_questions", [])
        formulas = data.get("formulas", [])

        mdie_study_dir = cfg.output_dir / "mdie_study_packs"
        mdie_study_dir.mkdir(parents=True, exist_ok=True)
        pack_file = mdie_study_dir / f"{project_name}_study_pack.json"

        pack_data = {
            "project": project_name,
            "ingested_at": datetime.now().isoformat(),
            "flashcards": flashcards,
            "quiz_questions": quiz_questions,
            "formulas": formulas
        }
        pack_file.write_text(json.dumps(pack_data, indent=2), encoding="utf-8")

        if flashcards:
            from .generate import Flashcard
            from .export import write_anki
            cards = [
                Flashcard(
                    question=c.get("question", c.get("front", "")),
                    answer=c.get("answer", c.get("back", "")),
                    hint=c.get("hint", "")
                )
                for c in flashcards
            ]
            anki_file = mdie_study_dir / f"{project_name}_anki.tsv"
            write_anki(cards, anki_file)

        analytics.record_study_session(
            activity_type=f"mdie_study_pack_{project_name}",
            items_count=len(flashcards) + len(quiz_questions),
            duration_seconds=0
        )

        return jsonify({
            "status": "ok",
            "message": f"Successfully ingested study pack for '{project_name}'",
            "counts": {
                "flashcards": len(flashcards),
                "quiz_questions": len(quiz_questions),
                "formulas": len(formulas)
            },
            "saved_to": str(pack_file)
        })
    except Exception as e:
        logger.exception("MDIE ingest failed")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/mdie/study-packs")
def api_mdie_study_packs():
    """List all ingested MDIE machine design study packs."""
    mdie_study_dir = cfg.output_dir / "mdie_study_packs"
    packs = []
    if mdie_study_dir.exists():
        for f in mdie_study_dir.glob("*_study_pack.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                packs.append({
                    "project": data.get("project", f.stem),
                    "ingested_at": data.get("ingested_at"),
                    "flashcards_count": len(data.get("flashcards", [])),
                    "quiz_questions_count": len(data.get("quiz_questions", [])),
                    "formulas_count": len(data.get("formulas", [])),
                    "file_path": str(f)
                })
            except Exception:
                continue
    return jsonify(packs)




@app.route("/api/consolidate", methods=["POST"])
def api_consolidate():
    """
    Consolidate an engineering report or document into structured study materials:
    - Chunks document
    - Generates executive summaries and key learning points
    - Generates NotebookLM study pack
    - Optionally generates Word (.docx) document if HTML
    """
    try:
        from .ingest import Source
        from .chunker import chunk_sources
        from . import generate
        from . import export
        from .docx_converter import HTMLToDocxConverter

        data = request.get_json(silent=True) or {}
        report_path_str = data.get("report_path")
        if not report_path_str:
            return jsonify({"status": "error", "error": "'report_path' is required"}), 400

        report_path = Path(report_path_str)
        if not report_path.exists():
            return jsonify({"status": "error", "error": f"File not found: {report_path}"}), 404

        out_dir_str = data.get("output_dir")
        if out_dir_str:
            out_dir = Path(out_dir_str)
        else:
            out_dir = report_path.parent / "learning_materials"
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Ingest & Chunk
        source = Source(report_path)
        chunks = chunk_sources([source])

        generated_files = {}

        # 2. DOCX Conversion if HTML
        if data.get("convert_docx", True) and report_path.suffix.lower() in (".html", ".htm"):
            docx_path = out_dir / f"{report_path.stem}.docx"
            HTMLToDocxConverter.convert(
                html_path=report_path,
                output_docx_path=docx_path,
                enable_ai=bool(data.get("enable_ai", False))
            )
            generated_files["docx"] = str(docx_path)

        # 3. Summaries & NotebookLM Pack
        if data.get("generate_summaries", True) and chunks:
            summaries = generate.generate_summaries(chunks)
            sum_path = out_dir / f"{report_path.stem}_summaries.md"
            export.write_summaries(summaries, sum_path)
            generated_files["summaries"] = str(sum_path)

            if data.get("generate_notebooklm", True):
                export.write_notebooklm_pack(summaries, out_dir)
                generated_files["notebooklm_pack"] = str(out_dir / "notebooklm_pack")

        return jsonify({
            "status": "ok",
            "source": report_path.name,
            "chunks_count": len(chunks),
            "output_dir": str(out_dir),
            "generated_files": generated_files
        })
    except Exception as e:
        logger.exception("Consolidation failed")
        return jsonify({"status": "error", "error": str(e)}), 500


def run_web(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """Run the Flask web server."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_web(debug=True)