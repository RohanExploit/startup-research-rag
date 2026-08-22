# Company Brain — Multi-Tenant RAG for Academic & Institutional Data

> Answers natural-language questions over student records, research documents and
> institutional policy — **entirely on a 4 GB laptop GPU, with zero cloud calls** — using a
> router that decides *how* to answer each question instead of throwing everything at an LLM.

<p>
<img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-blue">
<img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688">
<img alt="Next.js 16" src="https://img.shields.io/badge/dashboard-Next.js%2016-black">
<img alt="LLM: Ollama local" src="https://img.shields.io/badge/LLM-Ollama%20local%204B-000">
<img alt="tests 280 passing" src="https://img.shields.io/badge/tests-280%20passing-brightgreen">
<img alt="bench 88.9%" src="https://img.shields.io/badge/bench-88.9%25%20(208q)-success">
<img alt="cloud egress: off" src="https://img.shields.io/badge/cloud%20egress-OFF%20by%20default-informational">
</p>

---

## The numbers

Same corpus, same 4B local model, same 4 GB GPU, same frozen scorer — 208 questions:

| Architecture | Overall | FACT (97) | GLOBAL (57) | LOCAL (54) |
|---|---|---|---|---|
| Naive RAG — top-3 chunks, no routing | 62.5% | 88 | 34 | **8** |
| GraphRAG-style — community summaries + graph edges | 69.7% | 94 | 20 | 31 |
| **This system** — routed, chunk fan-out + hybrid graph | **88.9%** | **95** | **46** | **44** |

**+26.4 points over naive RAG.** On multi-hop relational questions, **8/54 → 44/54 (5.5×)**.

| Also measured | |
|---|---|
| Abstains correctly on unanswerable questions | **20/20** — never invents an answer |
| Tabular accuracy on the real corpus | **21/22 (95.5%)** — SQL, exact figures |
| Median end-to-end latency | **1.85 s** on a 4 GB laptop GPU |
| Artifact floor (content-free answer) | 19.2% — our score is **4.6×** that |
| Automated tests | **280 passing**, 50 files |

Every figure is reproducible from this repo. Full methodology, the rejected experiments,
and an explicit list of what we have **not** measured: **[`docs/PITCH_METRICS.md`](docs/PITCH_METRICS.md)**.

## Why it wins where it wins

Three findings from our own measurement, each of which contradicted the obvious plan:

1. **Community summaries are worse than useless for corpus-wide questions.** The classic
   GraphRAG "global search" — summarise entity clusters, answer from summaries — scored
   **35.1%**. Serving the same questions from a broad chunk fan-out scored **82.5%**. Those
   summaries are generated from bare entity *names*, so they contain no figures, dates or
   sources; one literally reads *"The entity '62' appears to be a single numerical value
   without contextual information."*

2. **Graph and vector retrieval fail in disjoint places, so we use both.** Chunks beat
   graph edges 42/54 to 31/54 on relational questions, yet lost three questions
   *reproducibly* — all two-hop questions whose second hop sits in a document the question's
   own wording never retrieves. One answered with a confidently **wrong** department.
   The hybrid (edges + chunks) scores **44/54** and loses none of them.

3. **Fixing the router first would have made the product worse.** Route classification is
   54.3%, an obvious target — but with the routes as originally built, *correct* routing
   scored **66.8%** against 80.8% for the sloppy router, because misrouting was accidentally
   rescuing questions. Repair the destinations first, and the same work becomes a gain.

Anyone can report the number that flatters them. We publish the ones that didn't:
**two of four candidate improvements were rejected by our own pre-registered gates**, and
one was rejected after passing its first run and failing its replication.

---

## Table of Contents

- [The numbers](#the-numbers)
- [Why it wins where it wins](#why-it-wins-where-it-wins)
- [What it is](#what-it-is)
- [Key features](#key-features)
- [Architecture](#architecture)
- [The query router (the core idea)](#the-query-router-the-core-idea)
- [Tech stack](#tech-stack)
- [Project layout](#project-layout)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [The dashboard](#the-dashboard)
- [Ingestion pipeline](#ingestion-pipeline)
- [Testing & evaluation](#testing--evaluation)
- [Reproducing the benchmark](#reproducing-the-benchmark)
- [Enterprise audit suite](#enterprise-audit-suite)
- [Security & privacy posture](#security--privacy-posture)
- [Bots & scheduler](#bots--scheduler)
- [Deployment](#deployment)
- [Current state & roadmap](#current-state--roadmap)
- [License](#license)

---

## What it is

Company Brain ingests a tenant's documents (exam-result PDFs, conference brochures, fee sheets, research papers) and turns each corpus into **four coordinated stores**:

1. a **DuckDB** relational store of structured student records,
2. a **FAISS** vector index of document chunks,
3. a **NetworkX** knowledge graph of extracted entities and relations, and
4. **Louvain** community summaries over that graph.

At query time a **multi-layer router** classifies the question and dispatches it to exactly the right store — a SQL template for "how many students failed ≥4 subjects", a vector search for "who are the authors of the RAG-MicroSim paper", a graph walk for "which institutions co-organized ICETIS". The LLM (a local Ollama model) is used only where it adds value: entity extraction during ingestion, and answer synthesis for non-tabular routes.

Everything runs **locally by default** — a local Ollama model, on-disk stores, `127.0.0.1` binding — so student PII never has to leave the machine. Cloud LLM egress exists only as an opt-in fallback and can be forbidden entirely with a single env flag.

## Key features

- **Deterministic-first routing** — regex/keyword rules and parameterized SQL run *before* any LLM call, giving fast, reproducible, hallucination-resistant answers for the common query shapes.
- **Four retrieval routes** — `TABULAR` (SQL over DuckDB), `FACT` (vector search), `LOCAL` (graph neighborhood via entity linking), `GLOBAL` (community summaries).
- **Multi-tenant isolation** — every tenant is a sandboxed `data/tenants/<id>/` tree; tenant-id and filename validation block path traversal; API keys are scoped to a single tenant.
- **Order-independent fuzzy name lookup** — "rohan gaikwad result" and "result of rohan gaikwad" resolve to the same student via RapidFuzz matching.
- **Text-to-SQL guardrails** — table allowlist + auto-injected `LIMIT` on generated SQL.
- **PII controls** — optional roll-number redaction before any cloud egress; a hard `ALLOW_EXTERNAL_LLM=0` kill switch.
- **21-audit production gate** — integrity, hallucination, tenant isolation, prompt injection, RBAC and more, with a weighted scorecard and 5 deployment-blocking gates.
- **Reproducible evaluation** — a 208-question benchmark generated from a world model (so golds
  cannot disagree with the corpus), plus a 46-question hand-verified set on the real corpus, all
  scored at `temperature=0` with frozen answers so scoring is a free CPU replay.
- **Full-stack** — FastAPI backend + Next.js 16 operator dashboard (query console, health, documents, review queue, upload, live audit stream).
- **Green CI** — ruff + pytest (backend) and tsc + eslint (frontend) on every push.

## Architecture

```
                          ┌─────────────────────────────┐
                          │   Next.js 16 dashboard       │
                          │  query · health · documents  │
                          │  review · upload · audit      │
                          └──────────────┬──────────────┘
                                         │  HTTP (X-API-Key optional)
                                         ▼
┌───────────────────────────────────────────────────────────────────────┐
│                       FastAPI  (api/main.py :8000)                      │
│   auth gate · /query · /documents · /review · /upload · /audit/*        │
└───────────────────────────────┬───────────────────────────────────────┘
                                 ▼
              ┌──────────────────────────────────────┐
              │   QueryRouter  (retrieval/router.py)  │
              │  L1 deterministic rules               │
              │  L2 LLM classifier (fallback)         │
              │  L3 route → store                     │
              └───┬───────────┬───────────┬───────────┘
        TABULAR   │    FACT   │   LOCAL   │   GLOBAL
                  ▼           ▼           ▼           ▼
            DuckDB       FAISS index   NetworkX     Community
        tabular/analytics  (vectors)   graph        summaries
                  │           │           │           │
                  └───────────┴─────┬─────┴───────────┘
                                    ▼
                    generation/answer.py
              Ollama (local) ─► NVIDIA API (opt-in fallback)
```

Ingestion runs out-of-band and produces every store the router reads:

```
raw docs ─► parse (Docling) ─► chunk (LangChain) ─► embed (MiniLM)
   │                                                     │
   ├─► extract entities (Ollama) ─► build graph ─► Louvain communities ─► summarize (Ollama)
   └─► parse tabular ─► DuckDB (students, student_subjects, exam_results)
```

## The query router (the core idea)

`retrieval/router.py` decides each answer in three layers:

| Layer | Mechanism | Outcome |
|-------|-----------|---------|
| **L1 — deterministic** | Roll-number regex, student-record phrases, aggregate keywords, fact-attribute patterns | Direct `TABULAR` / `FACT` classification, no LLM |
| **L2 — LLM classifier** | Local Ollama model classifies into FACT/LOCAL/GLOBAL/TABULAR | Used only when L1 doesn't match |
| **L3 — retrieval** | Dispatch to the store for the chosen route | Context (or, for TABULAR, the final answer) |

Route behaviour:

- **`TABULAR`** — try a parameterized SQL template (`retrieval/sql_templates.py`); else an intent classifier (`retrieval/intent.py`) picks a deterministic handler (`name_search`, `average_sgpa`, `count_failures`, `below_sgpa`, `record_by_roll`); else LLM text-to-SQL with a table allowlist + row cap. Verified against DuckDB (369 students).
- **`FACT`** — vector search top-k=10, chunks packed into a ~5000-char context budget.
- **`GLOBAL`** — broad chunk fan-out (`GLOBAL_CHUNK_FANOUT=1`, default). Community summaries
  remain available behind the flag but measured **35.1% against 82.5%** for chunks: they are
  generated from bare entity *names*, so they carry no figures, dates or sources.
- **`LOCAL`** — **hybrid context** (`LOCAL_CONTEXT_MODE=hybrid`, default): graph edges *and*
  retrieved chunk text. Measured 31/54 for edges alone, 42/54 for chunks alone, **44/54 for
  both** — the two fail in disjoint places, so neither alone is sufficient.

Grade semantics follow the **DBATU** scale (`models/grades.py`): `AB` counts as **pass** (8.5), only an `FF`-dominated result is an academic fail — a correctness fix that also drives the dashboard's PASS/FAIL badge colours.

## Tech stack

| Layer | Choices |
|-------|---------|
| **API** | FastAPI 0.141, Uvicorn 0.52, Pydantic 2.13 |
| **LLM** | Ollama 0.6 (`qwen3:4b-instruct-2507-q4_K_M`, `num_ctx=2048`, `temp=0`); optional NVIDIA `meta/llama-3.1-70b-instruct` fallback |
| **Ingestion** | Docling 2.117 (parse), LangChain text-splitters 1.1 (chunk), sentence-transformers 5.6 / `all-MiniLM-L6-v2` (embed), FAISS-CPU 1.14 (index), NetworkX 3.4 (graph) |
| **Tabular / SQL** | DuckDB 1.5, pdfplumber 0.11, RapidFuzz 3.14 |
| **Scheduling / bots** | APScheduler 3.11, python-telegram-bot 22.8 |
| **Frontend** | Next.js 16, React 19, TypeScript 5 (strict), Tailwind CSS 4, shadcn |
| **Tooling** | Python 3.12, uv (lockfile), ruff 0.16, pytest 9.1 |

## Project layout

```
.
├─ start.py              # canonical entrypoint (uvicorn runner + dep preflight)
├─ config.py             # single source of truth: paths, validation, runtime knobs
├─ pipeline.py           # ingestion orchestrator
├─ api/
│  ├─ main.py            # FastAPI app, endpoints, auth gate
│  └─ audit_router.py    # /audit/* streaming router (admin-gated)
├─ retrieval/            # router, intent, vector_search, graph_traverse,
│                        #   entity_link, community_search, tabular_queries, sql_templates
├─ ingestion/            # parse, chunk, embed, vector_store, extract_entities,
│                        #   build_graph, build_communities, summarize_communities
├─ generation/answer.py  # Ollama + NVIDIA-fallback answer synthesis
├─ models/               # canonical.py (Pydantic records), grades.py (DBATU scale)
├─ adapters/             # result_pdf_adapter.py (DuckDB → StudentRecord)
├─ auth/                 # api_keys.py (scoped keys), allowlist.py (bot users)
├─ audit/                # 21 audit modules + weighted scorecard
├─ bots/                 # telegram_bot.py, whatsapp_bot.py
├─ scheduler/            # weekly_ingest.py (APScheduler cron)
├─ scripts/              # bootstrap, validation, benchmarking, diagnostics
├─ tests/                # 50 modules, 280 passing; tests/eval/ golden sets + bench
├─ dashboard/            # Next.js 16 operator UI
└─ data/tenants/<id>/    # raw · parsed · chunked · embeddings · graph · *.duckdb (gitignored)
```

## Quick start

### Prerequisites

- **Python 3.12** and [uv](https://github.com/astral-sh/uv)
- **[Ollama](https://ollama.com)** running locally with the model pulled:
  ```bash
  ollama pull qwen3:4b-instruct-2507-q4_K_M
  ```
- **Node 20+** (for the dashboard)

### Backend

```bash
# 1. install (from the lockfile)
uv sync --frozen --group dev

# 2. configure
cp .env.example .env        # edit as needed; defaults are localhost-safe

# 3. run  (binds 127.0.0.1:8000 by default)
uv run python start.py
#   --host / --port / --reload available; use --host 0.0.0.0 ONLY with REQUIRE_API_KEY=1
```

`start.py` runs a dependency preflight and fails fast with a clear message if `faiss`, `duckdb`, `fastapi`, or `uvicorn` are missing.

### Frontend

```bash
cd dashboard
npm ci
npm run dev                 # http://localhost:3000  → talks to the API on :8000
```

### Ingest a tenant's documents

Drop files into `data/tenants/<tenant_id>/raw/`, then either use the dashboard **Upload** page or run the pipeline directly. Ingestion is idempotent — a `manifest.db` tracks file hashes and skips unchanged files.

## Configuration

Everything is centralized in `config.py` and overridable via environment / `.env` (see `.env.example`). Highlights:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROJECT_ROOT` | auto-detect | Force the repo location |
| `DEFAULT_TENANT_ID` | `tenant_1` | Default tenant |
| `OLLAMA_MODEL` | `qwen3:4b-instruct-2507-q4_K_M` | Local model id |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `REQUIRE_API_KEY` | `0` (off) | Turn ON the `X-API-Key` gate — **required before binding 0.0.0.0** |
| `API_KEY` | — | Admin key value (constant-time compared) |
| `ALLOW_EXTERNAL_LLM` | `0` | Cloud LLM egress is **off by default**; set `1` to opt in |
| `LLM_PII_REDACTION` | `0` | Mask roll-number digit runs before egress |
| `SQL_ALLOWED_TABLES` | `students,student_subjects,needs_review` | Text-to-SQL table allowlist |
| `SQL_ROW_LIMIT` | `200` | Row cap injected when generated SQL has no `LIMIT` |
| `VALIDATE_TENANT_ID` / `VALIDATE_FILENAMES` / `VALIDATE_UPLOAD_ID` | `1` | Path-traversal guards |

## API reference

Base URL `http://127.0.0.1:8000`. All routes except `/health` pass through the auth gate (no-op when `REQUIRE_API_KEY=0`).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/query` | Route + answer a natural-language query for a tenant |
| `GET`  | `/health` | Liveness (unauthenticated) |
| `GET`  | `/admin/status` | Ollama status, tenant list, document totals |
| `GET`  | `/tenants` | Registered tenants + pipeline state |
| `GET`  | `/documents` | Document inventory + parse status |
| `GET`  | `/review` | Needs-review queue (extraction failures / flagged records) |
| `POST` | `/upload` | Stage a file for ingestion |
| `POST` | `/upload/{upload_id}/process` | Trigger the ingestion pipeline |
| `GET`  | `/upload/{upload_id}/status` | Poll ingestion status |
| `GET`  | `/audit/status` · `/scorecard` | Audit state + weighted scorecard (admin) |
| `POST` | `/audit/run` | Run the audit suite (admin) |
| `GET`  | `/audit/stream` | Server-sent events of live audit progress (admin) |

`POST /query` returns `{ query_type, answer, context_used, metadata }` where `query_type ∈ {FACT, LOCAL, GLOBAL, TABULAR}` and `metadata` may carry `fallback_reason` / `debug_sql`.

## The dashboard

A Next.js 16 (App Router) operator console — seven screens:

- **Query Console** (`/`) — ask questions, see the routed answer, student-record cards with a subjects/grade table, disambiguation picker, route legend, and fallback banners; query history sidebar.
- **Health** (`/health`) — LLM engine status, VRAM, tenant/document counts, pipeline-stage table; auto-refresh.
- **Tenants** (`/tenants`), **Documents** (`/documents`), **Review** (`/review`) — corpus and data-quality visibility.
- **Upload** (`/upload`) — staging → processing → success workflow with status polling.
- **Audit** (`/audit`) — 21-audit suite with a live SSE stream, per-category scores, and the production-gate scorecard.

Styling is Tailwind CSS 4 with a custom dark design-token system (IBM Plex Sans / JetBrains Mono, cobalt accent, semantic pass/fail/warn colours) and a hand-drawn 16-icon SVG set.

## Ingestion pipeline

| # | Stage | Module | LLM? |
|---|-------|--------|------|
| 1 | Parse (→ Markdown) | `ingestion/parse.py` (Docling) | — |
| 2 | Chunk (1000 chars / 200 overlap) | `ingestion/chunk.py` | — |
| 3 | Embed (`all-MiniLM-L6-v2`) | `ingestion/embed.py` | — |
| 4 | FAISS index (L2, normalized) | `ingestion/vector_store.py` | — |
| 5 | Extract entities & relations | `ingestion/extract_entities.py` | **Yes** |
| 6 | Build knowledge graph | `ingestion/build_graph.py` (NetworkX) | — |
| 7 | Louvain communities (`seed=42`) | `ingestion/build_communities.py` | — |
| 8 | Summarize communities | `ingestion/summarize_communities.py` | **Yes** |
| — | Tabular records → DuckDB | `ingestion/parse_tabular.py` | — |

Safety: FAISS **drift detection** refuses to serve if `index.ntotal ≠ len(chunks)`; DuckDB opens read-only and fails closed if a store is missing (no silent cross-tenant fallback).

## Testing & evaluation

```bash
uv run pytest -q          # 280 passed, 1 skipped
uv run ruff check .
```

- **50 test modules / 280 tests**, hermetic by default (monkeypatched router/generator via
  `tests/conftest.py`); live-service tests skip cleanly when Ollama/API are unavailable.
- **Three evaluation corpora**, never pooled:

| Set | n | Purpose |
|---|---|---|
| `golden_bench.json` | **208** | The instrument. Generated from a world model; GLOBAL 57 / LOCAL 54 / FACT 97 (incl. 20 unanswerable). |
| `golden_bench_sql.json` | 15 | TABULAR. 840 result rows, golds computed by SQL over the queried rows. |
| `golden_set.json` | 46 | The real corpus. Regression canary — small-n, so it gates nothing on its own. |

**Current results, 208-question benchmark, live routing:**

| Route | Accuracy |
|---|---|
| **Overall** | **88.9% (185/208)** |
| FACT | 97.9% (95/97) |
| GLOBAL | 80.7% (46/57) |
| LOCAL | 81.5% (44/54) |
| Unanswerable (abstention correct) | **100% (20/20)** |
| TABULAR *(real corpus, `golden_set.json`)* | **95.5% (21/22)** |

**Known weak spot, stated plainly:** cross-document arithmetic is **14/24**. A 4B model
quotes a table accurately and adds two of them together unreliably. Those questions are
scored as a separate sub-metric rather than mixed into the headline, so the number cannot
quietly flatter the retrieval work.

### How we keep the evaluation honest

| Guard | What it prevents |
|---|---|
| **Answers frozen before scoring** | A scorer written after seeing the numbers it judges |
| **Artifact floor** (score each answer against the *next* question's gold) | Gains bought by verbosity rather than comprehension — flat at 19.2% across every configuration |
| **Pre-registered accept/reject rules** | Deciding the threshold after seeing the result |
| **Confirmatory pairs** | Accepting a one-run fluke — this rejected a change that passed its first run |
| **`validate_bench.py`** | A benchmark that is wrong about its own corpus — it rejected 15 of our own questions |
| **`test_eval_no_egress.py`** | The evaluation silently calling a cloud model |

## Reproducing the benchmark

Every headline number can be regenerated from a clean checkout. Nothing is hand-recorded.

```bash
# 1. build the benchmark corpus + questions from the world model
python tests/eval/bench/render_corpus.py        # 30 documents
python tests/eval/bench/render_questions.py     # 208 questions
python tests/eval/derive_gold_v2.py     --kit "Dataset/bench_v1/golden" --corpus "Dataset/bench_v1/corpus"     --out tests/eval/golden_bench.json --tenant-id tenant_bench --version bench-1

# 2. prove the benchmark is sound BEFORE measuring anything with it
python tests/eval/bench/validate_bench.py
#   checks every anchor exists in its cited documents, every multi-hop question
#   spans documents, and no "unanswerable" question is accidentally answerable

# 3. ingest it as its own tenant (never touches production data)
python tests/eval/bench/ingest_bench.py all

# 4. run + score  (answers are frozen to JSONL; scoring is a free CPU replay)
python tests/eval/run_eval.py --golden tests/eval/golden_bench.json --answers run.jsonl
python tests/eval/score_answers.py --answers run.jsonl --golden tests/eval/golden_bench.json

# compare two configurations under the pre-registered statistical rule
python tests/eval/score_answers.py --answers before.jsonl --compare after.jsonl     --golden tests/eval/golden_bench.json
```

**`--force-route`** serves each question on the route its gold declares, holding routing
accuracy at 100%. Route *quality* and route *selection* are different failures with
different fixes, and no number that is the product of both can separate them.

**The TABULAR benchmark** is generated the same way — 840 result rows for 120 students,
with every gold computed by SQL over exactly the rows the system queries:

```bash
python tests/eval/bench/build_tabular.py
```

## Enterprise audit suite

`audit/` ships **21 audits** across integrity, security, retrieval, observability, performance, reliability, regression, and decision-intelligence, with a weighted scorecard (`audit/scorecard.py`). Five are **deployment-blocking gates**:

`document_integrity` · `hallucination` · `multi_tenant_isolation` · `prompt_injection` · `authorization`

Run and stream results from the dashboard **Audit** page or via `POST /audit/run` + `GET /audit/stream`.

## Security & privacy posture

This system handles student PII, so privacy is designed in, not bolted on:

- **Local-by-default** — Ollama model + on-disk stores; API binds `127.0.0.1`; CORS restricted to `localhost:3000`.
- **No PII in git** — `.gitignore` excludes `data/`, `Dataset/`, `Results Dataset/`, `graphify-out/`, all `*.xlsx` / `*.csv` / `*.duckdb`, `.env`, and `.encryption_key`. Raw student spreadsheets and eval result artifacts (which embed names) are never tracked. Only `.env.example` and `api_keys.example.json` templates are committed.
- **Cloud egress is opt-in** — the NVIDIA fallback only fires if the local model fails, can redact roll numbers first (`LLM_PII_REDACTION=1`), and can be disabled outright (`ALLOW_EXTERNAL_LLM=0`).
- **Tenant isolation** — per-tenant directory trees; `validate_tenant_id` / `safe_filename` / `validate_upload_id` block path traversal; tenant-scoped API keys.
- **Text-to-SQL is fenced** — table allowlist + injected row cap.
- **Fail-closed auth** — corrupt `api_keys.json` grants nothing; `REQUIRE_API_KEY=1` with no key configured returns 500 rather than opening up.

> **Before exposing beyond localhost:** set `REQUIRE_API_KEY=1`, configure `API_KEY`, and only then bind `--host 0.0.0.0`.

## Bots & scheduler

- **Telegram** (`bots/telegram_bot.py`) — allowlisted users, 5s/user rate limit, proxies to `/query`.
- **WhatsApp** (`bots/whatsapp_bot.py`) — ASGI webhook on `:8001`.
- **Scheduler** (`scheduler/weekly_ingest.py`) — APScheduler cron re-ingests all tenants weekly (Sun 02:00).

## Deployment

`docker-compose.yml` orchestrates four services:

| Service | Port | Role |
|---------|------|------|
| `api` | 8000 | FastAPI (mounts `./data`) |
| `telegram_bot` | — | Telegram interface |
| `whatsapp_bot` | 8001 | WhatsApp webhook |
| `scheduler` | — | Weekly ingest cron |

```bash
docker compose up --build
```

## Current state & roadmap

**Solid today:** 88.9% on a 208-question benchmark, TABULAR at 95.5% on the real corpus,
20/20 correct abstention, 280 green tests, provenance on every retrieval answer, tenant
isolation, and an evaluation harness whose guards have rejected our own work twice.

**Next levers, in evidence order:**

1. **Abstention when the answer is present.** Of 23 remaining failures, 18 are the system
   saying "I don't have enough information" — and in **13 of those the gold answer is
   sitting in the retrieved context**. That is a prompt/generation problem, not a retrieval
   one, and it is the largest single bucket left. Care is needed: abstention on genuinely
   unanswerable questions is currently perfect (20/20) and must not be traded away.
2. **Cross-document arithmetic** (14/24) — either a larger model or a compute step, rather
   than asking a 4B model to add figures it has correctly quoted.
3. **Router accuracy** is 54.3% — but now worth ~0 points. With both routes repaired,
   forced-correct routing and live routing both score 88.9%, so route *choice* has stopped
   mattering for accuracy. It still matters for latency and cost.
4. **External validity.** One synthetic corpus, one small model, single-sample runs. The
   next credible step is a second corpus with OCR noise and a confidence interval over
   repeated runs.

## License

No license file is currently included — this repository is **private / all rights reserved** pending a license decision. Do not redistribute without permission.

---

<sub>Built as a Phase-1 RAG research prototype. Model, eval numbers, and grade scale reflect the DBATU academic context the system was validated against.</sub>
