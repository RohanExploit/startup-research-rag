# Company Brain — Multi-Tenant RAG for Academic & Institutional Data

> A privacy-first, offline-capable Retrieval-Augmented Generation (RAG) system that answers natural-language questions over student academic records, research documents, and institutional policy — with a deterministic query router that decides *how* to answer each question instead of throwing everything at an LLM.

<p>
<img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-blue">
<img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688">
<img alt="Next.js 16" src="https://img.shields.io/badge/dashboard-Next.js%2016-black">
<img alt="LLM: Ollama (local)" src="https://img.shields.io/badge/LLM-Ollama%20local-000">
<img alt="tests: 227 passing" src="https://img.shields.io/badge/tests-227%20passing-brightgreen">
<img alt="eval baseline 60.87%" src="https://img.shields.io/badge/eval%20baseline-60.87%25-yellow">
</p>

---

## Table of Contents

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
- **Reproducible evaluation** — a 46-question hand-verified golden set scored at `temperature=0`.
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
- **`LOCAL`** — deterministic entity linker maps question entities to graph nodes, fetches the k=2 neighborhood; falls back to vector search if no entity matches.
- **`GLOBAL`** — all Louvain community summaries fed to the LLM for a corpus-wide answer.

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
├─ tests/                # 42 modules, 227 passing; tests/eval/ golden set
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
| `ALLOW_EXTERNAL_LLM` | `1` | Set `0` to forbid **all** cloud LLM egress |
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
uv run pytest -q          # 227 passed, 1 skipped
uv run ruff check .
```

- **42 test modules / 171 test functions**, hermetic by default (monkeypatched router/generator via `tests/conftest.py`); live-service tests skip cleanly when Ollama/API are unavailable. The single skip is a manual PDF-parsing diagnostic.
- **Golden evaluation set** — `tests/eval/golden_set.json`, 46 hand-verified questions across the four routes (22 TABULAR, 11 FACT, 6 LOCAL, 7 GLOBAL), scored at `temperature=0` with `contains` / `contains_any` / `insufficient` matchers via `tests/eval/run_eval.py`.

Measured baseline (`tests/eval/baseline.json`):

| Route | Accuracy |
|-------|----------|
| **Overall** | **60.87%** (28/46) |
| Route classification | 84.78% |
| TABULAR | 95.5% (21/22) |
| GLOBAL | 42.9% (3/7) |
| FACT | 27.3% (3/11) |
| LOCAL | 16.7% (1/6) |

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

**Solid today:** the TABULAR route (95.5%), the full test gate (227 green), reproducible eval, tenant isolation, and the audit scorecard.

**Next levers** (from `PROJECT_STATE.md`):

1. Raise **FACT** to green — carry the k=10 + entity-link confidence gate to a measured win on the 11 FACT questions.
2. Grow **LOCAL** graph coverage from 1/6 toward 3/6 via merge-swap ingest.
3. Reduce **GLOBAL** churn — stop re-reading the graph per query; stabilize the 3/7 answers.

## License

No license file is currently included — this repository is **private / all rights reserved** pending a license decision. Do not redistribute without permission.

---

<sub>Built as a Phase-1 RAG research prototype. Model, eval numbers, and grade scale reflect the DBATU academic context the system was validated against.</sub>
