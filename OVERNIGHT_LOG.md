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
