import os
import sys
import faiss
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import tenant_dir
from utils.safe_store import load_chunks

# Load the SentenceTransformer once per process and share across tenants/instances
# (P4.14). Previously every VectorSearch() reloaded the model (~seconds each).
_MODEL_CACHE = {}


def _get_model(name: str = "all-MiniLM-L6-v2"):
    if name not in _MODEL_CACHE:
        _MODEL_CACHE[name] = SentenceTransformer(name)
    return _MODEL_CACHE[name]


class VectorSearch:
    def __init__(self, tenant_id="tenant_1"):
        self.embed_dir = tenant_dir(tenant_id) / "embeddings"
        self.faiss_path = self.embed_dir / "faiss.index"
        self.data_path = self.embed_dir / "embeddings.pkl"
        
        self.index = None
        self.chunks = None
        self.model = None
        
        self.load_index()

    def load_index(self):
        # chunks load from the safe .npy/.json format, falling back to legacy pickle
        if not self.faiss_path.exists():
            return
        self.chunks = load_chunks(self.embed_dir)
        if not self.chunks:
            return

        self.index = faiss.read_index(str(self.faiss_path))
        self.model = _get_model()
        self._query_cache = {}

    def search(self, query: str, top_k: int = 5):
        if not self.index:
            return []

        # Cache the query embedding so repeated identical queries skip encoding (P4.14)
        query_vec = self._query_cache.get(query)
        if query_vec is None:
            query_vec = self.model.encode([query])
            faiss.normalize_L2(query_vec)
            self._query_cache[query] = query_vec
        
        distances, indices = self.index.search(query_vec, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            chunk = self.chunks[idx]
            results.append({
                "content": chunk["page_content"],
                "metadata": chunk["metadata"],
                "score": float(distances[0][i])
            })
            
        return results

if __name__ == "__main__":
    # Test search
    vs = VectorSearch()
    res = vs.search("What is RAG-MicroSim?")
    for r in res:
        print(f"Score {r['score']}: {r['content'][:100]}...")
