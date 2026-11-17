"""learning-tools MCP server.

Exposes the learning-tools generators and thesis pipeline as MCP tools so any
MCP-capable agent (Amadeus, Kilo, Claude Desktop, OpenCode, ...) can call them.

Run:
    python -m lt.mcp_server            # stdio transport (default)
    python -m lt.mcp_server sse        # SSE transport

Client config example (Claude Desktop / OpenCode mcp servers):
    {
      "mcpServers": {
        "learning-tools": {
          "command": "python",
          "args": ["-m", "lt.mcp_server"],
          "cwd": "C:\\codework\\learning-tools"
        }
      }
    }
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "learning-tools",
    instructions=(
        "AI office file generation toolkit. Generates Markdown/DOCX documents "
        "and KMITL thesis-template Word files from Markdown manuscripts, and "
        "validates thesis DOCX files against the KMITL formatting guideline."
    ),
)


@mcp.tool()
def generate_thesis_docx(
    md_path: str,
    output_docx: str = "",
    title: str = "",
    author: str = "",
    year: str = "",
    degree: str = "",
    program: str = "",
    code: str = "",
) -> str:
    """Convert a Markdown thesis manuscript into a KMITL-template .docx file.

    The .md may include YAML front matter (title, author, student_id, year,
    degree, program, advisor, co_advisor, code, plan, abstract,
    acknowledgement). The listed arguments override front matter values.
    Returns the generated file path and a template-compliance summary.
    """
    from .converters.thesis_docx import convert_thesis_md
    from .thesis_lint import lint_thesis_docx

    overrides = {
        key: value
        for key, value in {
            "title": title, "author": author, "year": year,
            "degree": degree, "program": program, "code": code,
        }.items()
        if value
    }
    out = convert_thesis_md(
        md_path,
        output_docx=output_docx or None,
        meta_overrides=overrides,
    )
    report = lint_thesis_docx(out)
    return json.dumps(
        {"generated_path": str(out), "compliance": report["summary"]},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def lint_thesis_docx(docx_path: str) -> str:
    """Check a thesis .docx against the KMITL template formatting rules.

    Checks A4 paper, margins (1/1/1/1.5 inches), TH Sarabun New fonts,
    heading sizes, Roman/Arabic page numbering fields and chapter structure.
    Returns the full JSON report.
    """
    from .thesis_lint import lint_thesis_docx as _lint

    return json.dumps(_lint(docx_path), ensure_ascii=False, indent=2)


@mcp.tool()
def generate_md_document(content: str, output_path: str = "") -> str:
    """Generate a Markdown (.md) document from text/markdown content.

    If the content already starts with a '#' heading it is written as-is,
    otherwise the first line becomes the title. Returns the output path.
    """
    from .generators.md import generate_md

    out = generate_md(content, output_path or None)
    return str(out)


@mcp.tool()
def generate_docx_from_markdown(content: str, output_path: str = "") -> str:
    """Generate a plain styled Word .docx from markdown-style content.

    Supports # headings, **bold**, *italic*, bullets, numbered lists, tables
    and code blocks. For KMITL thesis formatting use generate_thesis_docx.
    Returns the output path.
    """
    from .generators.docx import docx_generator

    result = docx_generator(content, output_path=output_path or None)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def list_capabilities() -> str:
    """List available learning-tools capabilities, commands and tools."""
    from .converters import __all__ as converter_exports

    tools = {
        "generate_thesis_docx": "Markdown -> KMITL thesis-template .docx (+ compliance check)",
        "lint_thesis_docx": "Validate a thesis .docx against the KMITL template rules",
        "generate_md_document": "Text/markdown -> .md file",
        "generate_docx_from_markdown": "Markdown-style text -> plain styled .docx",
        "list_capabilities": "This listing",
    }
    return json.dumps(
        {
            "server": "learning-tools",
            "tools": tools,
            "converters": sorted(converter_exports),
            "notes": (
                "Thesis markdown contract: YAML front matter for metadata; "
                "'# Chapter' headings; pipe tables; ![caption](path) images; "
                "$$equation$$ blocks."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def main() -> None:
    import sys

    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run()  # stdio


if __name__ == "__main__":
    main()
