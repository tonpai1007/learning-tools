# Integrate AMADEUS, learning-tools, and MySecondBrain

## Current state

- **AMADEUS** (`C:\AMADEUS`) is a full-stack second-brain app with FastAPI backend, `brain/` cognition layer, MCP servers (including `obsidian_mcp.py`), Kilo config, graphify integration, and Docker support.
- **learning-tools** (`C:\Users\Tonpa\OneDrive\Documents\Default Project\learning-tools`) is a local project that generates study artifacts (`output/`, `sources/`) and currently syncs them to Obsidian via a one-way copy script (`sync_to_second_brain.py`).
- **MySecondBrain** (`C:\Users\Tonpa\MySecondBrain`) is an Obsidian vault with PARA-style folders, a `.amadeus/` state folder (sync state, knowledge graph, memory, metacognition), a `90-AMADEUS-Insights/` folder, and a `learning-tools/` subfolder.

Existing couplings:
- AMADEUS ↔ Obsidian via MCP server and `.amadeus/` vault folder
- learning-tools → Obsidian via one-way `shutil.copy2` sync
- AMADEUS and learning-tools both have Kilo `.kilo/` configs but no shared coordination

## Goal

Make AMADEUS the orchestrating second brain that owns the sync contract between learning-tools outputs and the Obsidian vault, while using Kilo as the planning layer for changes to any of the three.

## Proposed integration shape

1. **Replace the copy script with an AMADEUS-managed sync**
   - Move sync logic from `learning-tools/sync_to_second_brain.py` into AMADEUS (e.g. `brain/sync/obsidian_sync.py` or an AMADEUS automation job).
   - Keep the same folder mapping (outputs → `01_Active_Outputs`, sources → `00_Source`, etc.) but add:
     - Bidirectional awareness: read vault-side edits back into learning-tools metadata
     - Conflict detection: track `sync_state.json` hashes and surface conflicts instead of silently overwriting
     - Dry-run + audit log aligned with AMADEUS `.amadeus/audit_log.jsonl`

2. **Unify the `.amadeus/` state**
   - Currently there are two separate `.amadeus/` trees: one in the vault and one in `C:\AMADEUS`.
   - Decide on a single source of truth for `.amadeus/` state. Recommended: keep it in the vault (`C:\Users\Tonpa\MySecondBrain\.amadeus\`) because that is where human-readable notes and the knowledge graph already live, and have AMADEUS read/write there via the MCP server or direct file access.

3. **Add a Kilo → AMADEUS planning handoff**
   - Kilo plans for learning-tools or AMADEUS changes should land in a dedicated Obsidian folder (e.g. `01_Projects/learning-tools-plans/` or `90-AMADEUS-Insights/plans/`).
   - AMADEUS should be able to ingest those plans as structured tasks (extend `brain/planner/` or `brain/orchestration/`).

4. **Keep Obsidian as the user-facing source of truth**
   - All human review, annotations, and graph navigation stays in Obsidian.
   - AMADEUS acts as the automated layer: sync, summarization, knowledge graph maintenance, reminders, and tool orchestration.

## Tasks

1. Add an Obsidian sync module inside AMADEUS that reimplements `sync_to_second_brain.py` logic with conflict detection and audit logging.
2. Consolidate `.amadeus/` state into the vault and update `obsidian_mcp.py` / AMADEUS paths to use the vault copy as source of truth.
3. Create a Kilo plan export workflow that writes finalized plans into `MySecondBrain/90-AMADEUS-Insights/plans/` or `01_Projects/learning-tools-plans/`.
4. Wire AMADEUS task ingestion from those Obsidian plan folders so Kilo plans become executable AMADEUS tasks.
5. Update `learning-tools/sync_to_second_brain.py` to delegate to AMADEUS (HTTP call to the MCP server or a CLI wrapper) instead of copying files directly, so there is one sync owner.
6. Fix `VaultManager` default vault path: change fallback from `"C:/AMADEUS"` to `str(Path.home() / "MySecondBrain")` in `brain/memory/vault_manager.py`.
7. Run existing AMADEUS test suite and record pass/fail results.
8. Add missing test coverage for new integration surface:
   - `tests/test_second_brain_router.py`: test new `/sync/learning-tools`, `/sync/kilo-plan/*`, `/sync/vault-reverse` endpoints
   - `tests/test_obsidian_sync.py` in AMADEUS: unit tests for `ObsidianSync` with mocked vault/source dirs
   - `tests/test_scheduler.py`: add test that `sync_learning_tools_outputs` is registered and cooldown works
   - `tests/test_vault_manager_default_path.py`: verify default vault path resolves to `MySecondBrain` when env is unset
   - `tests/test_stale_amadeus_warning.py`: verify warning is logged when legacy `C:/AMADEUS/.amadeus` exists
9. **Fix GraphifyAdapter async mismatch**: `GraphifyAdapter.add_node` and `query_by_content` are `async def` but wrap purely sync `KnowledgeGraph` methods. Make both adapter methods sync, then remove `await` from all call sites (`second_brain_orchestrator.py`, `document_ingestion.py`).
10. **Add PDF deduplication**: In `document_ingestion.py`, check content hash before writing to vault to avoid duplicate notes from re-uploaded PDFs.
11. **Add scheduled document ingestion**: Register a periodic job in `brain/core/scheduler.py` to watch `00_Source/documents/` for new PDFs and auto-ingest them.
12. **Fix local-brain-search import**: Replace `sys.path.insert` hack in `document_ingestion.py` with a proper relative import or package registration.

## Implementation details for items 9-12

### Item 9: GraphifyAdapter sync fix
**Files to change:**
- `C:\AMADEUS\brain\memory\graphify_adapter.py`: Change `async def add_node` → `def add_node`, change `async def query_by_content` → `def query_by_content`
- `C:\AMADEUS\brain\orchestration\second_brain_orchestrator.py`: Remove `await` from `self.graphify.add_node(...)` and `await graphify.query_by_content(...)`
- `C:\AMADEUS\brain\sync\document_ingestion.py`: Remove `await` from `adapter.add_node(...)`
- `C:\AMADEUS\tests\test_document_ingestion.py`: Update any tests that mock async behavior

### Item 10: PDF deduplication
**Files to change:**
- `C:\AMADEUS\brain\sync\document_ingestion.py`: Add `_file_hash(path)` check in `ingest_pdf()`. If a vault note already exists with the same frontmatter hash, skip ingestion or update in place. Store hash in `.amadeus/pdf_ingest_state.json`.

### Item 11: Scheduled document ingestion
**Files to change:**
- `C:\AMADEUS\brain\scheduler\memory_jobs.py`: Add `async def ingest_new_documents()` that scans `00_Source/documents/` for new PDFs/markdown files and calls `DocumentIngestionPipeline`
- `C:\AMADEUS\brain\core\scheduler.py`: Register the new job with `add_job(ingest_new_documents, "interval", minutes=15, ...)`

### Item 12: Fix local-brain-search import
**Files to change:**
- `C:\AMADEUS\brain\sync\document_ingestion.py`: Replace `sys.path.insert(0, str(Path(r"C:/AMADEUS/brain/local-brain-search")))` with a proper import. Options: add `brain/local-brain-search` to `PYTHONPATH` in `.env`, or move the indexer into `brain/` package and use relative import.

## Validation
- Run `python -m pytest tests/test_document_ingestion.py tests/test_second_brain_router.py tests/test_scheduler.py -q`
- Verify no `RuntimeWarning: coroutine ... was never awaited` in test output
- Verify `GraphifyAdapter.add_node` and `query_by_content` are sync methods
- Verify scheduled jobs include `ingest_new_documents`

## Validation

- Run `python sync_to_second_brain.py --dry-run` and verify AMADEUS produces the same file mapping.
- Confirm `.amadeus/sync_state.json` in the vault is updated by AMADEUS after sync.
- Create a Kilo plan for a small learning-tools change, export it to Obsidian, and verify AMADEUS can read it back as a task.
- Check that Obsidian graph view reflects new notes without manual refresh.
- Run `python -m pytest tests/ -q` from `C:\AMADEUS` and confirm new tests pass alongside existing suite.
- Verify `OBSIDIAN_VAULT_PATH` is unset and `VaultManager().vault_path` resolves to `C:/Users/Tonpa/MySecondBrain`.

## Risks / open questions

- Obsidian Local REST API must be running for MCP writes. If it is not, AMADEUS needs a fallback (direct file write via Python).
- OneDrive sync latency may cause race conditions between AMADEUS writes and Obsidian indexing. Prefer atomic writes + small delay, or exclude `.amadeus/` from OneDrive if it causes conflicts.
- If you want true bidirectional note editing (vault → learning-tools), that requires a richer metadata model than current copy-based sync supports.
- The existing AMADEUS test suite may have failures unrelated to this integration; new tests should be isolated with mocks to avoid dependency on live Redis/Qdrant/Postgres.
- `VaultManager` default path fix may affect other components that relied on the `C:/AMADEUS` fallback; audit all `get_vault_manager()` call sites after changing the default.
