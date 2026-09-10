# Learning Tools

Learning Tools is a local AI study pipeline for turning notes, source material, and research into actionable learning outputs: flashcards, quizzes, summaries, tutor sessions, and structured knowledge exports.

It is designed to support a simple workflow:

1. Drop source material into `sources/`
2. Generate cards, summaries, and practice content
3. Keep only the useful outputs in your personal knowledge vault
4. Let AMADEUS and MySecondBrain consume the curated knowledge, not the noisy runtime folder

## What it produces

- Anki-friendly flashcards in TSV format
- Quiz pages in HTML format
- Summary notes with key ideas and self-tests
- NotebookLM-ready source packs
- A local, conversational tutor over your material
- Exam-focused study guides (concepts, formulas, worked examples, practice problems)
- SRS tracking for spaced repetition

## Setup

```powershell
cd learning-tools
pip install -r requirements.txt
Copy-Item .env.example .env
# edit .env: set OPENAI_API_KEY (leave empty for local Ollama)
# edit config.yaml: set ai.model to match your provider
```

Supported OpenAI-compatible providers:

| Provider | OPENAI_API_KEY | OPENAI_BASE_URL | ai.model |
| --- | --- | --- | --- |
| OpenAI | your key | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Ollama | empty | `http://localhost:11434/v1` | `llama3.2` |
| OpenRouter | your key | `https://openrouter.ai/api/v1` | any model |

## Typical usage

```powershell
python -m lt sample
python -m lt all
python -m lt quiz
python -m lt summarize
python -m lt study-guide
python -m lt tutor
python -m lt review
python -m lt stats
```

## Project layout

```text
learning-tools/
├─ config.yaml
├─ requirements.txt
├─ README.md
├─ .gitignore
├─ .env.example
├─ sources/                 # raw learning material
├─ output/                  # generated project exports
├─ data/                    # SRS state and local learning data
├─ lt/                      # core pipeline code
├─ tests/                   # validation tests
├─ sync_to_second_brain.py  # curated sync helper for MySecondBrain
└─ start.bat
```

## MySecondBrain sync model

The project should stay as the active working repository. For the vault, use a curated sync strategy instead of copying the whole project tree.

Recommended pattern:

- `output/` → curated summaries, quiz outputs, useful generated packs
- `sources/` → only selected source notes or useful reference material
- `notes` or reflection files → personal understanding and synthesis
- skip runtime noise, caches, logs, temp files, and generated local state

This project includes a simple helper script:

```powershell
python sync_to_second_brain.py --dry-run
python sync_to_second_brain.py
```

The script syncs only curated, useful outputs into the vault folder at:

`C:\Users\Tonpa\MySecondBrain\learning-tools`

## Vault layout

```text
MySecondBrain/
└─ learning-tools/
   ├─ 00_Source/
   ├─ 01_Active_Outputs/
   ├─ 02_Notes/
   ├─ 03_Concepts/
   └─ 04_Reference/
```

This gives a clean split:

- Learning Tools project = active working engine
- MySecondBrain = memory, synthesis, and long-term knowledge
- AMADEUS = orchestration and interpretation over the curated vault content

## Tuning ideas

- Raise `chunker.chunk_tokens` for more cohesive cards
- Increase card output with `--per-chunk`
- Use the tutor for weak topics and feed answers back into your learning loop

## Notes

- Costs scale with chunk count; use a lightweight model for regular study
- Anki import: File > Import > select `flashcards.tsv`
- Keep generated output clean and intentional so the vault remains useful rather than noisy
