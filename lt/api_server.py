"""FastAPI endpoint for learning-tools office generation.
Exposes the OfficeController as a REST API that LLMs/MCP can call.
"""

from fastapi import FastAPI

try:
    from .controller import get_controller
except ImportError:  # run as a script from the repo root
    from lt.controller import get_controller

app = FastAPI(
    title="learning-tools API",
    description="AI Office Assistant - Generate DOCX, PDF, TXT, Markdown files from natural language",
    version="0.1.0",
)


@app.post("/generate/{intent}")
async def generate(intent: str, prompt: str):
    """Generate office files from natural language prompts.

    Supported intents: docx, pdf, markdown, txt, excel, quiz, summary, flashcards

    Args:
        intent: The type of file to generate
        prompt: Natural language prompt describing what to generate

    Returns:
        Dictionary with generation results from OfficeController
    """
    controller_instance = controller.get_controller()
    result = controller_instance.process_input(prompt)
    return result


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "learning-tools-api"}


@app.post("/convert/thesis-md")
async def convert_thesis_md_api(payload: dict):
    """Convert a Markdown thesis manuscript into a KMITL-template DOCX.

    Body: {"md_path": "..."} or {"md_content": "...", "output_path": "..."},
    optional "meta": {"title": ..., "author": ..., "year": ...}
    """
    from .converters.thesis_docx import convert_thesis_md as _convert

    md_path = payload.get("md_path")
    md_content = payload.get("md_content")
    output_path = payload.get("output_path")
    meta = payload.get("meta") or {}

    try:
        if md_path:
            out = _convert(md_path, output_docx=output_path, meta_overrides=meta)
        elif md_content:
            from pathlib import Path
            import tempfile

            tmp = Path(tempfile.gettempdir()) / "lt_thesis_input.md"
            tmp.write_text(md_content, encoding="utf-8")
            out = _convert(tmp, output_docx=output_path, meta_overrides=meta)
        else:
            return {"error": "Provide either 'md_path' or 'md_content'"}
        return {"status": "ok", "generated_path": str(out)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/lint/thesis")
async def lint_thesis_api(payload: dict):
    """Check a thesis .docx against the KMITL template formatting rules.

    Body: {"docx_path": "..."}
    """
    from .thesis_lint import lint_thesis_docx

    docx_path = payload.get("docx_path")
    if not docx_path:
        return {"error": "Provide 'docx_path'"}
    try:
        return lint_thesis_docx(docx_path)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)