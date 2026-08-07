# Overnight Autonomous Work Log

Started: 2026-08-08 00:49:45 IST
Operator: Claude Opus 4.8 (autonomous overnight run)
Branch: overnight-hardening

## Ground rules honored
- ABSOLUTE HARD RULE: no delete/move/overwrite/truncate of any student-PII file or PII-derived output (chunks, embeddings, graph, DuckDB rows, raw docs). Skip + log any task requiring it.
- Do NOT modify community-detection or graph-extraction logic.
- Do NOT deploy or change model files.
- Local Ollama preferred; NVIDIA cloud fallback allowed.
- Commit each change separately on branch overnight-hardening.

## Decisions log
- **[2026-08-08 00:49:45 IST] P1.3 conflict resolved:** Instruction said rename `embeddings.pkl` -> `.pkl.bak`. HARD RULE forbids moving/renaming PII-derived outputs and explicitly overrides. Resolution: implement safe deserialization **additively** — new `.npy` writer + reader that prefers `.npy` and falls back to existing `.pkl`; generate a **sidecar** `.npy` next to the original without touching `embeddings.pkl`. Same safe-load outcome, zero PII file moved. Most reversible option.

## Timeline

### [2026-08-08 00:53:22] P1.1 — Path literals -> config.PROJECT_ROOT  ✅ COMMITTED
- Migrated 42 files: absolute path literals `R:/Startup research/Start up V2/...` rewritten to `f"{PROJECT_ROOT}/..."` with an idempotent config-import bootstrap.
- Core runtime (api/main, pipeline, retrieval/*, auth, encryption) already wired to config.py in prior session; this pass covered ingestion __main__ blocks, scripts/, tests/, benchmarks.
- Verify: compiled all non-venv .py; 18/18 core+ingestion modules import clean; PROJECT_ROOT auto-resolves to repo location.
- 1 remaining literal is inside a docstring in scripts/test_part_b.py (documentation only, not executable) — intentionally left.
- KNOWN PRE-EXISTING BREAK (not caused here, not fixed): benchmark_models_flushed.py has invalid `print(flush=True, "...")` lines (dead "_flushed" duplicate). Out of scope; logged.

### [2026-08-08 00:56:47] P1.2 — Strict tenant_id validation everywhere paths are built  ✅ COMMITTED
- config.validate_tenant_id already blocks traversal (pattern ^[A-Za-z0-9_-]{1,64}$, env-toggleable). Added _require_tenant() HTTP-400 helper in api/main.py.
- Wired validation into remaining client-facing endpoints: /documents, /upload/{id}/process, /upload/{id}/status (were building DATA_ROOT/tenant_id unvalidated). Retrieval classes + pipeline already go through tenant_dir().
- New test tests/test_tenant_isolation.py: 28 cases. Proves '../../other_tenant' (and 10 other payloads) raise ValueError at validate_tenant_id AND tenant_dir; proves valid ids accepted; proves the naive DATA_ROOT/bad WOULD escape but tenant_dir blocks it.
- Result: 28 passed in 0.10s. api.main imports clean.

### [2026-08-08 01:00:15] P1.3 — Safe deserialization (drop pickle.load on the read path)  ✅ COMMITTED
- New utils/safe_store.py: stores embeddings as embeddings.npy + embeddings_chunks.json (no code-exec on load). Readers prefer safe format, fall back to legacy pickle with a warning.
- Wired: retrieval/vector_search.py (load_chunks), ingestion/embed.py (writes safe format, keep_pickle=True for back-compat), ingestion/vector_store.py (load_embeddings).
- ADDITIVE migration of existing data (per HARD RULE — pkl never moved/deleted):
    - tenant_1/embeddings/embeddings.pkl sha256 BEFORE == AFTER (UNTOUCHED): 2ba734f1fa511ae5...40c5860
    - generated embeddings.npy (8.86 MB) + embeddings_chunks.json; shape (5769, 384), 5769 chunks — matches pickle.
- Data sidecars live under data/ (gitignored) — never committed.
- Tests: tests/test_safe_store.py — 5 passed (roundtrip, safe-preferred-over-pickle, pickle fallback, additive+nondestructive migration proven by byte-equality, no-pickle case).
