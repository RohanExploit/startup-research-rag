import sys as _sys
from pathlib import Path as _Path
for _p in (_Path(__file__).resolve().parent, _Path(__file__).resolve().parent.parent):
    if str(_p) not in _sys.path:
        _sys.path.append(str(_p))
from config import PROJECT_ROOT
import json
import logging
from pathlib import Path
import networkx as nx
from networkx.algorithms.community import louvain_communities
from utils.logging_config import setup_logging

setup_logging()

def detect_communities(graph_dir):
    graph_dir = Path(graph_dir)
    in_path = graph_dir / "company_brain.graphml"
    
    if not in_path.exists():
        logging.error("GraphML file not found.")
        return
        
    G = nx.read_graphml(str(in_path))
    
    # Louvain works on undirected graphs
    G_undirected = G.to_undirected()
    
    communities = louvain_communities(G_undirected)
    
    community_data = {}
    for i, comm in enumerate(communities):
        community_data[f"community_{i}"] = list(comm)
        
    out_path = graph_dir / "communities.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(community_data, f, indent=2)
        
    logging.info(f"Detected {len(communities)} communities. Saved to {out_path}")

if __name__ == "__main__":
    graph_dir = f"{PROJECT_ROOT}/data/tenants/tenant_1/graph"
    detect_communities(graph_dir)
