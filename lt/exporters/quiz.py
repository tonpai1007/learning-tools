"""Export quiz questions to standalone HTML."""
import logging
from pathlib import Path
from ..generate import QuizQuestion

logger = logging.getLogger(__name__)


def write_quiz(questions: list[QuizQuestion], path: Path) -> None:
    """Write quiz questions as an HTML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>Quiz</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;max-width:800px;margin:40px auto;padding:0 20px}",
        ".q{background:#f8f9fa;border-radius:8px;padding:16px;margin:16px 0}",
        ".opt{margin:4px 0}",
        ".exp{display:none;background:#e8f5e9;padding:8px;border-radius:4px;margin-top:8px}",
        "button{background:#1976d2;color:#fff;border:0;padding:6px 12px;border-radius:4px;cursor:pointer}",
        "</style></head><body>",
        "<h1>Practice Quiz</h1>",
    ]
    for i, q in enumerate(questions, 1):
        html_parts.append(f"<div class='q'><p><strong>Q{i}. {q.question}</strong></p>")
        for j, opt in enumerate(q.options):
            html_parts.append(f"<div class='opt'>{chr(65+j)}. {opt}</div>")
        html_parts.append(
            f"<button onclick=\"this.nextElementSibling.style.display='block'\">Show Answer</button>"
        )
        html_parts.append(
            f"<div class='exp'><strong>Answer: {chr(65+q.answer_index)}</strong><br>{q.explanation}</div>"
        )
        html_parts.append("</div>")
    html_parts.append("</body></html>")
    path.write_text("\n".join(html_parts), encoding="utf-8")
    logger.info(f"Wrote {len(questions)} quiz questions to {path}")
