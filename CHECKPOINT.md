# CHECKPOINT — Start up V2

Snapshot to resume work. Full timestamped trail: `OVERNIGHT_LOG.md`.

## State
- **Branch:** `overnight-hardening` (10 commits off `main` baseline). Not merged, not pushed, not deployed.
- **Tests:** 73 passed, 1 skipped, 0 failed (~7s). Hermetic, no live services required.
- **Ollama:** UP on :11434 (v0.19.0, model `qwen3:4b-instruct-2507-q4_K_M`). Left running.
- **PII:** untouched. `tabular.duckdb` + `embeddings.pkl` sha256 identical before/after. Retention rule honored.
- **Git:** repo init'd this session; `.gitignore` excludes venv + all PII/data (history is code-only).

## Commit trail (`git log main..overnight-hardening`)
```
ec6c5eb docs(perf): record live LLM-path latency (Ollama up)
87f43bd docs: overnight log morning summary
221d249 perf: cache model load, query embeddings, and SQL template results
19a2cb9 feat(router): deterministic aggregation route + parameterized SQL templates
ddc72e6 feat(sql): build consolidated exam_results analytics table (read-only from PII store)
4c1bd09 test: make suite real and hermetic (67 passed, 1 skipped, 0 failed)
4a7a5f9 security(upload): sanitize filename to basename + enforce MAX_FILE_SIZE
81cb294 security(deser): replace pickle.load on embeddings read path with .npy/.json
e6fb741 security(tenant): validate tenant_id on all path-building endpoints + traversal test
7e1bbdf refactor(paths): route all absolute path literals through config.PROJECT_ROOT
```

## Done
- **P1 security:** paths→`config.PROJECT_ROOT` (42 files); tenant_id validation on all path-building endpoints; `pickle.load`→safe `.npy/.json` (`utils/safe_store.py`), existing pkl migrated additively; upload filename sanitize + 413 size guard.
- **P2 tests:** real/hermetic; killed a collection hang + 2 import-time PII overwrites; rewrote fake/broken tests.
- **P3 SQL route:** `exam_results` in separate `analytics.duckdb` (built READ-ONLY from PII store); parameterized templates before LLM; guardrails (schema-in-prompt, read-only, LIMIT, timeout, allowlist, 1-shot self-correct) present.
- **P4 perf:** model load 6.5s→0 shared; SQL templates 78–173× warm; live LLM latency logged. `num_ctx`=2048 everywhere.

## THE TARGET QUERY — WORKING
"students who failed at least 4 subjects" → **10 students** (JAGTAP & SHELKE at 5; 8 more at 4). Deterministic, Ollama-free. "at least 2"→77. "failed most"→max 5. Fail def = grade in (FF,XX,AB). Ground-truthed vs DuckDB. Tests: `tests/test_sql_route.py` (6).

## Key files added
- `config.py` (extended: paths + validation + runtime knobs)
- `utils/safe_store.py` — safe embeddings I/O
- `ingestion/build_exam_results.py` — consolidated analytics table
- `retrieval/sql_templates.py` — parameterized analytical templates + matcher
- `tests/`: `test_tenant_isolation.py`, `test_upload_filename.py`, `test_safe_store.py`, `test_sql_route.py`, `conftest.py`
- `docs/PERFORMANCE.md`, `OVERNIGHT_LOG.md`

## PENDING — needs user decision (NOT auto-changed)
1. **`/review` + `/tenants` endpoints: no auth, iterate ALL tenants** (cross-tenant read). Whole API is currently unauthenticated. Decide: add auth vs scope per tenant.
2. **`exam_results.department` / `source_file` = NULL** — not derivable without fabricating; `semester` IS derived. Provide source rule to populate.
3. **Merge** `overnight-hardening` → `main` after review.
4. **Ollama server flags** (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`) — set before `ollama serve` for VRAM/throughput (see `docs/PERFORMANCE.md`). Current running server may lack them.

## Known, left as-is
- Manual diagnostic scripts in `tests/` (no assertions) — listed in `OVERNIGHT_LOG.md` P2 TODO.
- `benchmark_models_flushed.py` — pre-existing invalid `print(flush=True, ...)` (dead `_flushed` dup).
- Harmless `Event loop is closed` teardown noise from module-level httpx client on Windows.

## Resume commands
```bash
cd "R:/Startup research/Start up V2"
git log --oneline main..overnight-hardening        # review commits
./venv/Scripts/python.exe -m pytest tests/ -q -o addopts="" --continue-on-collection-errors
./venv/Scripts/python.exe ingestion/build_exam_results.py tenant_1   # rebuild analytics (read-only from PII)
```
