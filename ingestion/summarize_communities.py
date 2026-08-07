import sys as _sys
from pathlib import Path as _Path
for _p in (_Path(__file__).resolve().parent, _Path(__file__).resolve().parent.parent):
    if str(_p) not in _sys.path:
        _sys.path.append(str(_p))
from config import PROJECT_ROOT
import json
import logging
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:4b-instruct-2507-q4_K_M"

def summarize_community(nodes):
    prompt = f"""
You are an AI assistant analyzing a knowledge graph. Summarize the following cluster of related entities into a concise paragraph.
Entities: {', '.join(nodes)}
    """
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 2048}
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["response"].strip()
    except Exception as e:
        logging.error(f"Ollama summarization failed: {e}")
        return "Summary generation failed."

def process_community_summaries(graph_dir):
    graph_dir = Path(graph_dir)
    in_path = graph_dir / "communities.json"
    
    if not in_path.exists():
        logging.error("communities.json not found.")
        return
        
    with open(in_path, "r", encoding="utf-8") as f:
        communities = json.load(f)
        
    summaries = {}
    
    for c_id, nodes in communities.items():
        logging.info(f"Summarizing {c_id} ({len(nodes)} nodes)...")
        # In a real environment, we'd also pull the context chunks for these nodes
        summary = summarize_community(nodes)
        summaries[c_id] = summary
        
    out_path = graph_dir / "community_summaries.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)
        
    logging.info(f"Generated {len(summaries)} community summaries. Saved to {out_path}")

if __name__ == "__main__":
    graph_dir = f"{PROJECT_ROOT}/data/tenants/tenant_1/graph"
    process_community_summaries(graph_dir)
