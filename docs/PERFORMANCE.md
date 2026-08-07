# Performance Runbook

## In-process caches (implemented, measured)

| Optimization | Before | After | Notes |
|---|---|---|---|
| SentenceTransformer model load (`retrieval/vector_search.py::_get_model`) | ~6484 ms **per** `VectorSearch` instance | ~0.001 ms (shared) | Loaded once per process, shared across tenants. Multi-tenant routers no longer reload. |
| Query-embedding cache (`VectorSearch.search`) | re-encode every call | cached per query string | Repeated identical queries skip encoding. |
| SQL analytical templates (`retrieval/sql_templates.py::_rows`) | ~20 ms cold | ~0.15 ms warm (78–173×) | Bounded cache keyed by `analytics.duckdb` mtime → auto-invalidates on rebuild. `clear_sql_cache()` to force. |

Measured on this box, Ollama offline, tenant_1 data (369 students / 2952 subject rows).

## Ollama server flags (apply on the machine running `ollama serve`)

These are **server-side environment variables** — they cannot be set from app code
and were NOT measurable here because Ollama was not running. Set them before
starting the server:

```powershell
# Windows PowerShell
$env:OLLAMA_FLASH_ATTENTION = "1"     # Flash Attention: faster attention, less VRAM
$env:OLLAMA_KV_CACHE_TYPE   = "q8_0"  # quantize KV cache (q8_0) -> lower VRAM on the 4B model
$env:OLLAMA_KEEP_ALIVE      = "10m"   # keep model resident between requests
ollama serve
```

```bash
# Linux/macOS
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_KEEP_ALIVE=10m ollama serve
```

- `keep_alive: "10m"` is also sent per-request in the app payloads (router, answer,
  tabular, api warmup), so the model stays hot for 10 minutes after each call.
- **`num_ctx` is 2048 everywhere** (verified across all call sites) — do not raise it
  on the 4 GB-VRAM box; it directly drives KV-cache size.

## LLM-path latency (not measured — Ollama offline overnight)

The analytical SQL route (templates) is **LLM-free** and already fast (sub-ms warm).
LLM latency (router classify, text-to-SQL fallback, answer generation) should be
re-measured with the flags above once Ollama is running. The 3 canonical queries
in `tests/test_sql_route.py` run entirely without Ollama.
