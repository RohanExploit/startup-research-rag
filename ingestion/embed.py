import sys as _sys
from pathlib import Path as _Path
for _p in (_Path(__file__).resolve().parent, _Path(__file__).resolve().parent.parent):
    if str(_p) not in _sys.path:
        _sys.path.append(str(_p))
from config import PROJECT_ROOT
import os
import json
import logging
import pickle
from pathlib import Path
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)

def process_chunk_embeddings(chunked_dir, embed_dir):
    chunked_dir = Path(chunked_dir)
    embed_dir = Path(embed_dir)
    embed_dir.mkdir(parents=True, exist_ok=True)
    
    logging.info("Loading SentenceTransformer model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    chunk_files = list(chunked_dir.glob("*_chunks.json"))
    logging.info(f"Found {len(chunk_files)} chunk files to embed")
    
    all_chunks = []
    
    for cfile in chunk_files:
        with open(cfile, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            all_chunks.extend(chunks)
            
    if not all_chunks:
        logging.warning("No chunks found!")
        return
        
    logging.info(f"Generating embeddings for {len(all_chunks)} total chunks...")
    texts = [c["page_content"] for c in all_chunks]
    
    embeddings = model.encode(texts, show_progress_bar=True)
    
    # Save the embeddings alongside their metadata
    out_path = embed_dir / "embeddings.pkl"
    with open(out_path, "wb") as f:
        pickle.dump({
            "chunks": all_chunks,
            "embeddings": embeddings
        }, f)
        
    logging.info(f"Saved {len(embeddings)} embeddings to {out_path}")

if __name__ == "__main__":
    chunked_dir = f"{PROJECT_ROOT}/data/tenants/tenant_1/chunked"
    embed_dir = f"{PROJECT_ROOT}/data/tenants/tenant_1/embeddings"
    process_chunk_embeddings(chunked_dir, embed_dir)
