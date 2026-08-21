# Phase-B autonomous run — 2026-08-21

Branch `phase-2-retrieval-upgrade`, from `91967e5`. Owner away; pre-registered gates from
`docs/PHASE_B_COUNCIL_VERDICT.md`. Every number below came from the split harness
(`run_eval.py --answers` → `score_answers.py`), so every scoring claim can be replayed
from the frozen answer files without a GPU.

## Preflight

`.venv312` pinned (bare `python` is 3.10 and cannot even collect 11 of the test files).
233 passed / 1 skipped · ruff clean · `tabular.duckdb` `e9cdb8a4…54bde` ·
`analytics.duckdb` `230bb54e…e25be5` · 5.1 GB free RAM, no competing GPU job ·
Ollama up. Backups taken before anything ran:
`data/tenants/{tenant_1,tenant_stress}/{graph,embeddings}_bak_20260821T001029Z` and
`tenant_1/duckdb_bak_20260821T001029Z` — `data/` is entirely gitignored, so file copies
are the only rollback that exists.

## Baseline (P2) — the anchor every later number is measured against

| corpus | overall | FACT | GLOBAL | LOCAL | TABULAR | route-class | ans len (med) | latency med/max |
|---|---|---|---|---|---|---|---|---|
| tenant_stress (n=120) | 75.8% (91) | 73/78 | 6/22 | 12/20 | — | 77.5% | 88 ch | 1.8 s / 17.4 s |
| tenant_1 (n=46) | 71.7% (33) | 7/11 | 2/7 | 3/6 | **21/22** | 89.1% | 148 ch | 1.05 s / 17.2 s |

**Reproducibility finding, unprompted and important:** this differs from the overnight log
(stress 76.7% / GLOBAL 7; tenant_1 73.9% / GLOBAL 3) *with no code change between them*.
Re-running the identical binary moves GLOBAL by ±2 questions. **At temp=0 the GLOBAL slice
is not deterministic**, so on n=22 (and n=7) a ±2 swing is indistinguishable from any
intervention that isn't worth ≥5 questions. Every GLOBAL delta below is read against that.

## Accepted

### P1 — RUN/SCORE split (`124e4bc`)
Answers are frozen to JSONL as they are produced; scoring is a CPU replay. This is what
resolved the debate's central dispute — a scorer can no longer be authored after seeing
the numbers it judges, because the answers already exist on disk. Also: abort after 3
consecutive generation failures (a dead Ollama otherwise completes the eval at ~0% and a
gated harness "reverts" a good change), `--resume` for a killed run, and answer-length +
latency in every summary.

### P3 — provenance and honesty (`d3df465`, `7aab7fb`)
- Deleted the GLOBAL prompt's mandated `### 3. Citations / Sources` section. Its context
  is community summaries generated from bare entity *names*, which contain no source
  names — the instruction could only be satisfied by invention, so every passing GLOBAL
  answer was shipping a fabricated citation block.
- Real provenance: `metadata["sources"]` from the retrieval path; dashboard `SourcesPanel`;
  telegram admin-only. Labels never enter the context string — 15/120 stress and 16/46
  tenant_1 golds pass on source-label text *alone*, so labels in context would inflate
  every subsequent score.
- Student-identity role gate: mechanism only, `PII_ROLE_GATE=0`. `AllowlistManager.get_role()`
  finally reads the `roles` map that has sat unread in `allowlist.json`; both bots now send
  the sender id they previously discarded; roster templates render identity through
  `_student_label()`. Byte-equality with today's output asserted by test.
- Determinism debt: `LOUVAIN_SEED` wired (Louvain ran unseeded — 109 vs 110 communities on
  consecutive runs), ingestion LLM calls pinned to temperature 0 (were at Ollama's 0.8).

**Measured (stress, vs baseline):** FACT b=0/c=0, LOCAL b=0/c=0 — byte-identical.
GLOBAL b=2/c=0 → **INCONCLUSIVE, claimed as nothing** (needs 5). Answer length unmoved
(88 ch), artifact floor unmoved (12). tenant_1: TABULAR 21/22 held.
A correctness/honesty change that moved no metric it wasn't supposed to move.

## Rejected

### P4 — context capacity (ctx 4096 + budget 9000 + k=15) — **REJECTED, reverted**

| | overall | FACT | GLOBAL | LOCAL | latency med/max |
|---|---|---|---|---|---|
| P3 | 77.5% (93) | 73/78 | 8/22 | 12/20 | 1.89 s / 18.2 s |
| P4 | **75.0% (90)** | 73/78 | 5/22 | 12/20 | **4.28 s / 55.5 s** |

Failed its pre-registered latency gate (`max < 45 s`) at 55.5 s — half a second from
`API_TIMEOUT=60`, past which `generate_answer` returns an error string, not a slow answer.
Bought nothing on any slice. This is exactly the shape the systems bench predicted from
`/api/ps` residency: 2048 is the only fully-GPU-resident setting on a 4 GB card, and 4096
costs 46% of decode throughput. The knobs (`OLLAMA_NUM_CTX`, `CONTEXT_BUDGET_CHARS`,
`FACT_TOP_K`, `fe48a2c`) stay in the tree at today's values — the experiment is now an env
var rather than a diff — but the defaults do not move.

## Escalated to the owner (not decided unattended)

1. **Who may see student identities.** `PII_ROLE_GATE=1` is a one-line flip, but every
   non-admin role list in `auth/allowlist.json` is empty, so enabling it today would
   withhold names from everyone except the admin. Populate `registrar`/`faculty` first.
2. **`students_failed_at_least` has no `LIMIT`** — an unbounded roster dump. Capping it
   changes shipped answers.
3. **Source labels are raw filenames**, and one real tenant_1 document is named after a
   student (`Rutuja fees.md`). That is why bot citations are admin-only for now.
4. **tenant_1's corpus is ~90% synthetic filler** — 20 `HR_Policy_*`, 15 `Project_Proposal_*`,
   14 `funsd_train_*`, 10 `Financial_Report_*`, 5 UCI CSVs, against ~6 genuine institute
   documents. Its 7 GLOBAL golds ask *about the corpus* ("what conferences are mentioned"),
   not what a student or registrar would ask. No retrieval work fixes that.
5. **tenant_1's GLOBAL route serves a stale partition** — `communities.json` covers 667 of
   970 current graph nodes and 5 of its 69 summaries read `"Summary generation failed."`
   Refreshing it needs a Louvain re-run, which is PII-blocked: it would pull the
   `Darekar Rutuja Dnyaneshwar` fee-receipt node into a community, whose name would then be
   broadcast by `get_all_summaries()` on every GLOBAL query.
6. **Whether the graph layer belongs in the serving path at all** — and if it stays,
   whether to fund the repair: `build_graph.py:26` uses `nx.Graph()`, destroying
   `REPORTS_TO` direction at build time; the extraction prompt declares 6 relation types
   and produces 125; 58 edge endpoints are never declared as nodes, including a
   hallucinated `'Shri Nitin Kharcho'` beside the correct `'Shri Nitin Kharche'` from the
   same chunk.

## What the night established about the measuring instrument

- **GLOBAL cannot currently be improved measurably.** A zero-comprehension dump of every
  number in the corpus scores 7/22 — today's score. With the *whole corpus* in context and
  word-boundary matching, the ceiling is 9/22: 13 of 22 golds are unsatisfiable from corpus
  text (gold `CSE` vs corpus "Computer Science and Engineering"; gold `142000` vs corpus
  `1,42,000`; gold `DPDP` vs "Digital Personal Data Protection Act"). A live probe with
  perfect recall scored 1/7, failing G001 on the abbreviation while producing 94.1 / 92.4 /
  79.4 / 60.7 correctly.
- **Two golds pass on any English answer**: G003 and L010 expect `'AI'`, which matches the
  `ai` inside *chair*, *maintain*, *available*, *said*.
- **The word-boundary fix cannot simply be adopted**: it drops tenant_1 TABULAR from 21/22
  to 19/22, because gold `BC` stops matching "OBC" — 11 of the 22 TABULAR invariant golds
  have expect tokens of ≤3 characters. It ships as a *reported* scorer, never a gate.
- **Rotated-answer artifact floor on real answers: GLOBAL 0/22, LOCAL 0/20** (answers are
  short, median 88 chars). So today's scores are not length artifacts — but any change that
  lengthens answers has to be re-checked against its own rotated arm, which is now free.
