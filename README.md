# learning-tools
# learning-tools
`amadeus is the brain the mind the memory this is the hand the tools to make the files`

This metaphor frames the system's purpose:
- Amadeus = the AI intelligence, brain, mind, and memory
- learning-tools = the hands and tools that actually create the files

madeus is the brain the mind the memory this is the hand the tools to make the files

## Overview

learning-tools is an AI-powered office file generation system that transforms natural language prompts into professionally formatted Word documents, PDFs, markdown, and other text formats. The system is designed to be MCP and LLM-aware, capable of being wired to Amadeus or any AI agent system.

## Philosophy

madeus is the brain the mind the memory this is the hand the tools to make the files

This metaphor frames the system's purpose:
- **Amadeus** = the AI intelligence, brain, mind, and memory
- **learning-tools** = the hands and tools that actually create the files


## Features

### Document Generation

| Intent | Format | Markdown Support | MCP Sync |
|--------|--------|-----------------|----------|
| docx | Word .docx | **\u2713** headings, **bold**, *italic*, bullets, 1. lists | **\u2713** |
| pdf | PDF .pdf | Basic formatting | **\u2713** |
| markdown | .md text | **\u2713** full markdown | **\u2713** |
| 	xt | .txt plain | Basic | **\u2713** |
| quiz | HTML quiz | No | **\u2713** |
| summary | Text summary | No | **\u2713** |
| lashcards | Anki .apkg | No | **\u2713** |

### MCP & LLM Integration

- **FastAPI endpoint**: POST /generate/{intent} - All intents
- **Function calling schemas**: For OpenAI/Anthropic function calling
- **AMADEUS sync**: Posts generation results to AMADEUS MCP server
- **Direct imports**: rom lt.generators.docx import generate_docx
- **CLI commands**: python -m lt [command]


## Available Commands

\\ash
python -m lt ingest          list and load sources
python -m lt md              generate Markdown document
python -m lt pdf             generate PDF document
python -m lt docx            generate Word document
python -m lt quiz            generate practice quiz (HTML)
python -m lt summarize       generate summaries
python -m lt tutor           interactive Socratic tutor
python -m lt review          spaced-repetition review
python -m lt stats           show progress
python -m lt all             run the full pipeline
python -m lt sample          write a sample file
python -m lt export-plans    export Kilo plans to Obsidian via AMADEUS
python -m lt capabilities    list available system capabilities
\

## Architecture

### MCP Server (AI agent integration)

learning-tools ships a built-in MCP server exposing its generators to any MCP-capable agent:

```bash
python -m lt mcp-server        # or: start-mcp.bat / python -m lt.mcp_server
```

Client configuration (Claude Desktop, OpenCode, etc.):

```json
{
  "mcpServers": {
    "learning-tools": {
      "command": "python",
      "args": ["-m", "lt.mcp_server"],
      "cwd": "C:\\codework\\learning-tools"
    }
  }
}
```

Exposed tools:
- `generate_thesis_docx` — Markdown -> KMITL thesis-template .docx (runs the compliance linter automatically)
- `lint_thesis_docx` — validate a thesis .docx against the KMITL template rules
- `generate_md_document` — text/markdown -> .md file
- `generate_docx_from_markdown` — markdown-style text -> plain styled .docx
- `list_capabilities` — tool listing

### Thesis pipeline (KMITL template)

```bash
python -m lt thesis sources/thesis.md -o output/thesis.docx   # generate
python -m lt lint-thesis output/thesis.docx                   # validate
```

User LLM/AI Agent flows through the system:

Entry Layer: CLI (python -m lt), API (POST /generate/{intent}), Function calling (learning-tools/docx_generate)

Intent Detection: lt/intents.py detect_intent(prompt) returns {intent, confidence, details}

Office Controller: lt/controller.py process_input(prompt) runs full pipeline:
1. detect_intent
2. memory.update
3. generator.exec
4. sync_to_amadeus
5. return output

Generators: lt/generators/ - docx.py (markdown .docx), pdf.py (.pdf FPDF), md.py (.md), txt.py (.txt)

File Output: .docx, .pdf, .md, .txt

AMADEUS Sync: lt/controller.py sync_to_amadeus() posts to http://127.0.0.1:8000/api/v1/second-brain/sync/learning-tools
