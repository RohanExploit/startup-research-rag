from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import contextlib
import logging
import httpx
import sqlite3
import subprocess
import os
from datetime import datetime

from retrieval.router import QueryRouter
from generation.answer import generate_answer
from api.audit_router import router as audit_router
from config import DATA_ROOT, validate_tenant_id, safe_filename

logging.basicConfig(level=logging.INFO)
OLLAMA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"

routers = {}

def get_router(tenant_id: str) -> QueryRouter:
    tenant_id = validate_tenant_id(tenant_id)
    if tenant_id not in routers:
        logging.info(f"Initializing router for {tenant_id}")
        routers[tenant_id] = QueryRouter(tenant_id)
    return routers[tenant_id]

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("FastAPI starting up: warming up models...")
    
    # 1. Eagerly load/warmup SentenceTransformer and index for default tenant
    try:
        default_router = get_router("tenant_1")
        if default_router.vs.model is None:
            logging.info("Loading SentenceTransformer model...")
            default_router.vs.load_index()
    except Exception as e:
        logging.error(f"Failed to eager load VectorSearch index: {e}")
        
    # 2. Warmup Ollama model to avoid first-query latency penalty
    logging.info("Sending warmup query to Ollama (qwen3:4b-instruct-2507-q4_K_M)...")
    payload = {
        "model": "qwen3:4b-instruct-2507-q4_K_M",
        "prompt": "Hello",
        "stream": False,
        "keep_alive": "10m",
        "options": {"num_predict": 2, "num_ctx": 2048}
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post("http://127.0.0.1:11434/api/generate", json=payload)
            logging.info("Ollama model warmed up successfully.")
    except Exception as e:
        logging.warning(f"Ollama warmup failed (is the server running?): {e}")
        
    yield

app = FastAPI(title="Company Brain API", lifespan=lifespan)
app.include_router(audit_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_ollama_status() -> dict:
    """Check if Ollama is reachable and return model + VRAM info."""
    try:
        import httpx as _httpx
        r = _httpx.get("http://127.0.0.1:11434/", timeout=2.0)
        ollama_ok = r.status_code < 400
    except Exception:
        ollama_ok = False

    vram_used, vram_total = None, None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) == 2:
                vram_used = round(int(parts[0]) / 1024, 1)   # GB
                vram_total = round(int(parts[1]) / 1024, 1)
    except Exception:
        pass

    return {
        "reachable": ollama_ok,
        "model": OLLAMA_MODEL,
        "vram_used_gb": vram_used,
        "vram_total_gb": vram_total,
    }


def _get_tenant_info() -> list:
    """Scan DATA_ROOT for tenants: doc count + last manifest ingestion."""
    from auth.allowlist import AllowlistManager
    mgr = AllowlistManager()
    allowlist = mgr.allowlist

    tenants = []
    if DATA_ROOT.exists():
        for tenant_dir in sorted(DATA_ROOT.iterdir()):
            if not tenant_dir.is_dir():
                continue
            tid = tenant_dir.name
            raw_dir = tenant_dir / "raw"
            doc_count = len(list(raw_dir.iterdir())) if raw_dir.exists() else 0

            last_indexed = None
            manifest_db = tenant_dir / "manifest.db"
            if manifest_db.exists():
                try:
                    conn = sqlite3.connect(manifest_db)
                    row = conn.execute(
                        "SELECT MAX(last_indexed_at) FROM manifest"
                    ).fetchone()
                    conn.close()
                    if row and row[0]:
                        last_indexed = row[0]
                except Exception:
                    pass

            tenants.append({
                "tenant_id": tid,
                "registered": tid in allowlist,
                "description": allowlist.get(tid, {}).get("description", ""),
                "doc_count": doc_count,
                "last_indexed_at": last_indexed,
                "has_pipeline_output": (tenant_dir / "embeddings").exists(),
            })
    return tenants


@app.get("/admin/status")
async def admin_status():
    """Live system status for the admin dashboard status strip."""
    ollama = _get_ollama_status()
    tenants = _get_tenant_info()
    registered = [t for t in tenants if t["registered"]]
    return {
        "ollama": ollama,
        "tenants": tenants,
        "registered_tenant_count": len(registered),
        "total_docs": sum(t["doc_count"] for t in registered),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

class QueryRequest(BaseModel):
    query: str
    tenant_id: str
    
class QueryResponse(BaseModel):
    query_type: str
    answer: str
    context_used: str
    debug_sql: str | None = None   # The exact SQL executed (for Text-to-SQL queries)
    metadata: dict = {}

@app.post("/query", response_model=QueryResponse)
async def query_documents(req: QueryRequest):
    # We remove the hardcoded tenant_1 rejection so we can serve any valid tenant
    try:
        tenant_router = get_router(req.tenant_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load tenant data: {e}")
        
    qtype, context, metadata = await tenant_router.route_query(req.query)
    context_text = str(context).strip()
    
    # Short-circuit formatting for disambiguation, error messages, and perfectly formatted student records
    if (context_text.startswith("Did you mean") or 
        context_text.startswith("Student matching") or 
        context_text.startswith("Could not extract") or
        context_text.startswith("🎓 **Student Record for")):
        return {
            "query_type": qtype,
            "answer": context_text,
            "context_used": context_text,
            "metadata": metadata
        }
        
    if not context_text:
        return {
            "query_type": qtype,
            "answer": "I don't have enough information to answer that.",
            "context_used": "",
            "metadata": metadata
        }
    
    answer = await generate_answer(req.query, context, qtype)
    
    return QueryResponse(
        query_type=qtype,
        answer=answer,
        context_used=context[:500] + "..." if len(context) > 500 else context,
        debug_sql=metadata.get("debug_sql"),
        metadata=metadata
    )

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tenants")
def tenants_overview():
    """Return all tenant directories with doc count, student count, manifest status."""
    result = []
    if DATA_ROOT.exists():
        for tenant_dir in sorted(DATA_ROOT.iterdir()):
            if not tenant_dir.is_dir() or tenant_dir.name.startswith("{"):
                continue
            raw_dir = tenant_dir / "raw"
            doc_count = len([f for f in raw_dir.iterdir() if f.is_file()]) if raw_dir.exists() else 0
            has_manifest = (tenant_dir / "manifest.db").exists()
            has_duckdb = (tenant_dir / "tabular.duckdb").exists()
            student_count = 0
            last_indexed = None
            if has_manifest:
                try:
                    conn = sqlite3.connect(tenant_dir / "manifest.db")
                    row = conn.execute("SELECT MAX(last_indexed_at) FROM manifest").fetchone()
                    conn.close()
                    last_indexed = row[0] if row else None
                except Exception:
                    pass
            if has_duckdb:
                try:
                    import duckdb
                    con = duckdb.connect(str(tenant_dir / "tabular.duckdb"), read_only=True)
                    student_count = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
                    con.close()
                except Exception:
                    pass
            result.append({
                "id": tenant_dir.name,
                "doc_count": doc_count,
                "student_count": student_count,
                "has_manifest": has_manifest,
                "has_duckdb": has_duckdb,
                "last_indexed": last_indexed,
            })
    return {"tenants": result}


@app.get("/review")
def review_queue():
    """Return all records in the needs_review table across tenants."""
    items = []
    if DATA_ROOT.exists():
        for tenant_dir in sorted(DATA_ROOT.iterdir()):
            if not tenant_dir.is_dir() or tenant_dir.name.startswith("{"):
                continue
            db_path = tenant_dir / "tabular.duckdb"
            if not db_path.exists():
                continue
            try:
                import duckdb
                con = duckdb.connect(str(db_path), read_only=True)
                rows = con.execute("SELECT * FROM needs_review LIMIT 200").fetchall()
                cols = [d[0] for d in con.description]
                con.close()
                for row in rows:
                    item = dict(zip(cols, row))
                    item["tenant_id"] = tenant_dir.name
                    items.append(item)
            except Exception:
                pass
    return {"items": items, "total": len(items)}


@app.get("/documents")
def documents_list(tenant_id: str = "tenant_1"):
    """Return manifest entries for a tenant — all documents with parse status."""
    tenant_dir = DATA_ROOT / tenant_id
    manifest_db = tenant_dir / "manifest.db"
    if not manifest_db.exists():
        return {"documents": [], "total": 0, "error": "manifest.db not found"}
    try:
        conn = sqlite3.connect(manifest_db)
        rows = conn.execute(
            "SELECT doc_id, file_hash, parse_status, last_indexed_at, "
            "error_message, page_count, file_size_bytes, flags "
            "FROM manifest ORDER BY last_indexed_at DESC"
        ).fetchall()
        conn.close()
        docs = []
        for r in rows:
            docs.append({
                "doc_id": r[0],
                "file_hash": r[1][:12] + "..." if r[1] else None,
                "parse_status": r[2],
                "last_indexed_at": r[3],
                "error_message": r[4],
                "page_count": r[5],
                "file_size_bytes": r[6],
                "flags": r[7],
            })
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        return {"documents": [], "total": 0, "error": str(e)}

import uuid
import shutil
from fastapi import UploadFile, File, Form, BackgroundTasks
from ingestion.parse import main as parse_main, _get_manifest_conn, _manifest_update

@app.post("/upload")
async def upload_file(tenant_id: str = Form(...), file: UploadFile = File(...)):
    try:
        tenant_id = validate_tenant_id(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = safe_filename(file.filename)
    upload_id = str(uuid.uuid4())
    staging_dir = DATA_ROOT.parent / "staging" / upload_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    file_path = staging_dir / filename
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Update live manifest to PENDING so frontend sees it immediately
    tenant_dir = DATA_ROOT / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    manifest_conn = _get_manifest_conn(tenant_dir)
    _manifest_update(manifest_conn, filename, "staging", "PENDING")
    manifest_conn.close()

    return {"upload_id": upload_id, "filename": filename, "tenant_id": tenant_id}


def _process_upload(upload_id: str, tenant_id: str, filename: str):
    staging_dir = DATA_ROOT.parent / "staging" / upload_id
    raw_dir = staging_dir / "raw"
    parsed_dir = staging_dir / "parsed"
    raw_dir.mkdir(exist_ok=True)
    parsed_dir.mkdir(exist_ok=True)
    
    file_path = staging_dir / filename
    raw_file_path = raw_dir / filename
    if file_path.exists():
        shutil.move(str(file_path), str(raw_file_path))
    
    tenant_dir = DATA_ROOT / tenant_id
    manifest_conn = _get_manifest_conn(tenant_dir)
    
    try:
        # Run parse.py main() which will process everything in raw_dir
        parse_main(input_dir=str(raw_dir), output_dir=str(parsed_dir))
        
        md_file = parsed_dir / f"{raw_file_path.stem}.md"
        if md_file.exists():
            # Get actual hash and size from the temporary manifest created by parse.py
            staging_conn = _get_manifest_conn(staging_dir)
            staging_row = staging_conn.execute(
                "SELECT file_hash, flags, file_size_bytes FROM manifest WHERE doc_id = ?", (filename,)
            ).fetchone()
            staging_conn.close()
            
            # Move to live tenant
            live_raw_dir = tenant_dir / "raw"
            live_parsed_dir = tenant_dir / "parsed"
            live_raw_dir.mkdir(exist_ok=True)
            live_parsed_dir.mkdir(exist_ok=True)
            
            shutil.copy2(str(raw_file_path), str(live_raw_dir / filename))
            shutil.copy2(str(md_file), str(live_parsed_dir / f"{raw_file_path.stem}.md"))
            
            if staging_row:
                import json
                flags = json.loads(staging_row[1]) if staging_row[1] else []
                _manifest_update(manifest_conn, filename, staging_row[0], "SUCCESS", 
                                 flags=flags, file_size_bytes=staging_row[2])
            else:
                _manifest_update(manifest_conn, filename, "unknown", "SUCCESS")
        else:
            _manifest_update(manifest_conn, filename, "staging", "FAILED", error_message="Parsing produced no output")
    except Exception as e:
        _manifest_update(manifest_conn, filename, "staging", "FAILED", error_message=str(e))
    finally:
        manifest_conn.close()


@app.post("/upload/{upload_id}/process")
def process_upload(upload_id: str, tenant_id: str, filename: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(_process_upload, upload_id, tenant_id, filename)
    return {"status": "processing_started"}


@app.get("/upload/{upload_id}/status")
def upload_status(upload_id: str, tenant_id: str, filename: str):
    tenant_dir = DATA_ROOT / tenant_id
    try:
        manifest_conn = _get_manifest_conn(tenant_dir)
        row = manifest_conn.execute(
            "SELECT parse_status, error_message FROM manifest WHERE doc_id = ?", (filename,)
        ).fetchone()
        manifest_conn.close()
        
        if row:
            return {"status": row[0], "error": row[1]}
        return {"status": "UNKNOWN", "error": "Not found in manifest"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


