import logging
import sys
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from config import tenant_dir

from ingestion.parse import main as parse_main
from ingestion.chunk import process_markdown_files
from ingestion.embed import process_chunk_embeddings
from ingestion.vector_store import build_faiss_index
from ingestion.extract_entities import process_extractions
from ingestion.build_graph import build_graph
from ingestion.build_communities import detect_communities
from ingestion.summarize_communities import process_community_summaries
from utils.logging_config import setup_logging

setup_logging()

def get_file_hash(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def check_for_changes(raw_dir: str, tenant_id: str) -> bool:
    """Returns True if there are new or changed files based on manifest.db."""
    manifest_db = Path(raw_dir).parent / "manifest.db"
    conn = sqlite3.connect(manifest_db)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS manifest
                 (filepath TEXT PRIMARY KEY, hash TEXT, last_indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    raw_path = Path(raw_dir)
    if not raw_path.exists():
        logging.warning(f"Raw directory {raw_dir} does not exist.")
        return False

    has_changes = False
    current_files = list(raw_path.glob("**/*.*"))

    for f in current_files:
        if f.is_dir(): continue
        f_hash = get_file_hash(f)
        f_str = str(f)

        c.execute("SELECT hash FROM manifest WHERE filepath = ?", (f_str,))
        row = c.fetchone()

        if row is None or row[0] != f_hash:
            has_changes = True
            c.execute("REPLACE INTO manifest (filepath, hash, last_indexed_at) VALUES (?, ?, ?)",
                      (f_str, f_hash, datetime.now()))

    conn.commit()
    conn.close()
    return has_changes

def run_pipeline(tenant_id="tenant_1"):
    _td = tenant_dir(tenant_id)
    raw_dir = str(_td / "raw")
    parsed_dir = str(_td / "parsed")
    chunked_dir = str(_td / "chunked")
    embed_dir = str(_td / "embeddings")
    graph_dir = str(_td / "graph")

    if not check_for_changes(raw_dir, tenant_id):
        logging.info(f"No changes detected in {raw_dir}. Skipping ingestion pipeline for {tenant_id}.")
        return

    logging.info("=== 1. Parsing Documents (Docling) ===")
    import shutil
    import tempfile
    try:
        from utils.encryption import decrypt_file
        encryption_available = True
    except ImportError:
        encryption_available = False

    with tempfile.TemporaryDirectory() as temp_raw_dir:
        # Decrypt files to temp_raw_dir if encryption is available
        raw_path = Path(raw_dir)
        if raw_path.exists():
            for f in raw_path.iterdir():
                if f.is_file():
                    temp_f = Path(temp_raw_dir) / f.name
                    if encryption_available:
                        # Attempt to decrypt. If it fails, maybe it wasn't encrypted, so just copy it.
                        if not decrypt_file(f, temp_f):
                            shutil.copy2(f, temp_f)
                    else:
                        shutil.copy2(f, temp_f)

        parse_main(temp_raw_dir, parsed_dir)

    logging.info("=== 2. Semantic Chunking ===")
    process_markdown_files(parsed_dir, chunked_dir)

    logging.info("=== 3. Embedding Generation ===")
    process_chunk_embeddings(chunked_dir, embed_dir)

    logging.info("=== 4. FAISS Vector Store Indexing ===")
    build_faiss_index(embed_dir)

    logging.info("=== 5. Entity Extraction (Ollama) ===")
    process_extractions(chunked_dir, graph_dir)

    logging.info("=== 6. Graph Construction (NetworkX) ===")
    build_graph(graph_dir)

    logging.info("=== 7. Community Detection (Louvain) ===")
    detect_communities(graph_dir)

    logging.info("=== 8. Community Summarization ===")
    process_community_summaries(graph_dir)

    logging.info("Pipeline Complete!")

if __name__ == "__main__":
    run_pipeline()
