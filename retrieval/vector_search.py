import os
import sys
import pickle
import faiss
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import tenant_dir

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
        if not self.faiss_path.exists() or not self.data_path.exists():
            return
            
        self.index = faiss.read_index(str(self.faiss_path))
        with open(self.data_path, "rb") as f:
            data = pickle.load(f)
            self.chunks = data["chunks"]
            
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def search(self, query: str, top_k: int = 5):
        if not self.index:
            return []
            
        # Encode query
        query_vec = self.model.encode([query])
        faiss.normalize_L2(query_vec)
        
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
