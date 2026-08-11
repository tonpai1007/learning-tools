# Learning Tools

A dynamic AI + NotebookLM study pipeline. Drop any material (PDFs, notes, slides-as-text, `.docx`, web pages) into `sources/` and it generates:

- **Anki flashcards** (TSV, importable)
- **Practice quizzes** (interactive HTML)
- **Study summaries** with analogies and self-test questions
- **NotebookLM pack** — pre-digested sources + prompts for audio overviews
- **Interactive Socratic tutor** (RAG chat over your material)
- **Spaced repetition** review with progress tracking (SM-2)

It's subject-agnostic: it works on whatever you feed it.

## Setup

```powershell
cd learning-tools
pip install -r requirements.txt
Copy-Item .env.example .env
# edit .env: set OPENAI_API_KEY (leave empty for local Ollama)
# edit config.yaml: set ai.model to match your provider
```

Provider is any OpenAI-compatible API:

| Provider    | OPENAI_API_KEY         | OPENAI_BASE_URL              | ai.model        |
|-------------|------------------------|------------------------------|-----------------|
| OpenAI      | your key               | `https://api.openai.com/v1`  | `gpt-4o-mini`   |
| Ollama (local, free) | *(empty)*      | `http://localhost:11434/v1`  | `llama3.2`      |
| OpenRouter   | your key               | `https://openrouter.ai/api/v1` | any model    |

## Usage

```powershell
python -m lt sample                 # create a test file in sources/
python -m lt all                    # cards + quiz + summaries + NotebookLM pack
python -m lt cards --add            # flashcards + add to spaced repetition
python -m lt quiz                   # practice quiz (open output/quiz.html)
python -m lt summarize              # summaries + output/notebooklm_sources/
python -m lt tutor                  # chat with your material (Socratic tutor)
python -m lt review                 # spaced-repetition review session
python -m lt stats                  # progress table
python -m lt cards --add path\to\extra.pdf   # also ingest extra files
```

### NotebookLM workflow
1. Run `python -m lt summarize`.
2. Drag the files from `output/notebooklm_sources/` into NotebookLM as sources.
3. Ask it questions, generate an **Audio Overview** (podcast-style MP3), and use `_master_prompt.md` for guidance.

## Project layout

```
sources/     <- drop learning material here
output/      <- generated flashcards.tsv, quiz.html, summaries.md, notebooklm_sources/
data/        <- spaced-repetition state (cards.json)
lt/          <- the pipeline (ingest, chunk, ai, generate, export, tutor, srs, cli)
config.yaml  <- tune chunk sizes, card counts, tutor behavior
```

## Tuning ideas
- Bigger chunks → more cohesive cards but fewer of them: raise `chunker.chunk_tokens`.
- More cards per chunk: `python -m lt cards --per-chunk 10`.
- Weak on something? The tutor (`python -m lt tutor`) will quiz you on it — then feed your answers back as a source.

## Notes
- Costs scale with the number of chunks. Use `gpt-4o-mini` (or local Ollama) for daily use.
- Anki import: File > Import > select `flashcards.tsv`. Tags: `learnforge`.
