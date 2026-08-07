import sys as _sys
from pathlib import Path as _Path
for _p in (_Path(__file__).resolve().parent, _Path(__file__).resolve().parent.parent):
    if str(_p) not in _sys.path:
        _sys.path.append(str(_p))
from config import PROJECT_ROOT
import os
import logging
import pickle
import numpy as np
import faiss
from pathlib import Path

logging.basicConfig(level=logging.INFO)

def build_faiss_index(embed_dir):
    embed_dir = Path(embed_dir)
    in_path = embed_dir / "embeddings.pkl"
    
    if not in_path.exists():
        logging.error("No embeddings found to index.")
        return
        
    with open(in_path, "rb") as f:
        data = pickle.load(f)
        
    embeddings = data["embeddings"]
    chunks = data["chunks"]
    
    if len(embeddings) == 0:
        logging.error("Empty embeddings array.")
        return
        
    dimension = embeddings.shape[1]
    
    # Using L2 distance FAISS index
    index = faiss.IndexFlatL2(dimension)
    
    # Normalize embeddings for cosine similarity (optional, but good for MiniLM)
    faiss.normalize_L2(embeddings)
    
    index.add(embeddings)
    
    # Save the index
    faiss_path = embed_dir / "faiss.index"
    faiss.write_index(index, str(faiss_path))
    
    logging.info(f"Built FAISS index with {index.ntotal} vectors of dimension {dimension}.")

if __name__ == "__main__":
    embed_dir = f"{PROJECT_ROOT}/data/tenants/tenant_1/embeddings"
    build_faiss_index(embed_dir)
