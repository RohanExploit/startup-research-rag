# Overnight autonomous run — 2026-08-19

Branch `phase-2-retrieval-upgrade`. Autonomous, pre-registered decision rules; user away.
Baseline = commit `5c996e2` (Phase 0). See `docs/PHASE_0_BASELINE.md`.

## Morning summary
_(written last)_

## Guardrails (checked after every change; fail → revert change, log, continue)
- TABULAR 21/22; `tabular.duckdb`/`analytics.duckdb` sha256 unchanged; egress OFF; suite ≥230p/1s.
- No commit on red. tenant_1 index backed up before any rebuild; PII guard (threshold=5) stays on.
- Product-decision ambiguity → SKIP + log. Nothing irreversible.
- Stop + report if: 2 phases fail gate / invariants break unrecoverably / Ollama dies.

## Pre-registered baselines (from 5c996e2, temp=0 deterministic)
- **stress** (n=120): FACT 33/66 (50%) end-to-end · route-class 44.4% · FACT-conditional 28/29 (96.6%) · GLOBAL 4/22 (18.2%) · LOCAL 10/20 (50%) · abstain 5/12 · overall 43.3%.
- **tenant_1** (n=46): FACT 4/11 (36.4%) · GLOBAL 3/7 · LOCAL 3/6 · TABULAR 21/22 · overall 67.4%.

---

## A.1 — Router TABULAR-miss → FACT fallback ✅ ACCEPTED (commit below)

**Change:** `config.TABULAR_FACT_FALLBACK` (default ON). In `retrieval/router.py`: when a
query is classified TABULAR but the tenant has no `tabular.duckdb` (document-only tenant),
skip the void tabular route and answer from the FACT vector path, reporting the route as
FACT so the answer is synthesised (not returned raw). A secondary empty/except guard covers
tenants that HAVE a db but a specific lookup yields nothing. FACT retrieval extracted to
`_fact_context()`.

**Two-step debug:** first cut (trigger on empty/exception) gave only +1 FACT — the DB-lookup
returns a non-empty graceful sentinel (`"No tabular/student data available…"`), not empty/raise,
so the guard missed. Fixed by a no-`tabular.duckdb` fast-path check at the branch top → catches
every no-db case regardless of how each lookup fails.

**Measured delta (stress n=120, egress-off, temp=0):**

| slice | before (5c996e2) | after A.1 | Δ |
|---|---|---|---|
| FACT (all) | 50.0% (33/66) | **93.9% (62/66)** | **+29 q** |
| &nbsp;FACT lexical | 52.6% | 94.7% | |
| &nbsp;FACT paraphrase | 48.9% | 93.6% | |
| GLOBAL | 18.2% (4/22) | 31.8% (7/22) | +3 |
| LOCAL | 50.0% | 60.0% | +2 |
| abstention | 41.7% (5/12) | 91.7% (11/12) | +6 |
| route-class | 44.4% | 75.0% | +30.6pp |
| overall | 43.3% | **76.7%** | +33.4pp |

**Regression gate — tenant_1 (has a real db, guard must not fire): IDENTICAL.**
FACT 4/11 · GLOBAL 3/7 · LOCAL 3/6 · TABULAR 21/22 · overall 67.4% — byte-for-byte the
Phase-0 baseline. Suite 230p/1s. duckdb checksums unchanged. ruff clean. New hermetic tests
`tests/test_router_tabular_fallback.py` (3).

**Caveat:** recovered questions convert at the FACT-conditional rate, and some tabular-shaped
FACT questions (e.g. "OBC tuition" → Rs 71,000) still miss on *retrieval* (wrong chunk pulled),
not routing — that residue is the ceiling A.2/embedder work would chase, not this lever.

## A.2 — ICETIS re-ingest + source-coverage assert
_in progress_
