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
